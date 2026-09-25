import json
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from rules import judge

SECRET = os.environ.get("JWT_SECRET", "herb-process-dev-secret")
DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54393/herb")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
# 可写账号带身份字段：apprentice 学员（只能建草稿），master 师傅（可定稿、可直写正式行）
USERS = {
    "processor": {"role": "writer", "identity": "apprentice", "password_hash": pwd.hash("herb123456")},
    "checker": {"role": "reader", "password_hash": pwd.hash("check123456")},
}


def connect():
    return psycopg.connect(DSN, row_factory=dict_row)


class LoginIn(BaseModel):
    username: str
    password: str


class StepIn(BaseModel):
    name: str
    temp_c: float
    minutes: float


class BatchIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    steps: list[StepIn]


class IdentityIn(BaseModel):
    identity: Literal["apprentice", "master"]


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效令牌") from exc
    if payload.get("sub") not in USERS:
        raise HTTPException(status_code=401, detail="无效令牌")
    return {"username": payload["sub"], "role": payload.get("role")}


def require_writer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "writer":
        raise HTTPException(status_code=403, detail="仅炮制员可写入记录")
    return user


def identity_of(username: str) -> str | None:
    return USERS[username].get("identity")


def require_apprentice(user: dict = Depends(require_writer)) -> dict:
    if identity_of(user["username"]) != "apprentice":
        raise HTTPException(status_code=403, detail="仅学员身份可建草稿")
    return user


def require_master(user: dict = Depends(require_writer)) -> dict:
    if identity_of(user["username"]) != "master":
        raise HTTPException(status_code=403, detail="仅师傅身份可定稿")
    return user


app = FastAPI(title="饮片炮制记录台")


@app.on_event("startup")
def startup():
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS batches (
                id serial PRIMARY KEY,
                herb text NOT NULL,
                doc jsonb NOT NULL,
                verdict text NOT NULL,
                reason text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS drafts (
                id serial PRIMARY KEY,
                herb text NOT NULL,
                doc jsonb NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM batches").fetchone()["n"]
        if count == 0:
            now = datetime.now(timezone.utc)
            samples = [
                ("甘草", {"steps": [{"name": "清炒", "temp_c": 120, "minutes": 12}]}),
                ("黄芩", {"steps": [{"name": "清炒", "temp_c": 40, "minutes": 12}]}),
            ]
            for herb, doc in samples:
                verdict, reason = judge(doc)
                conn.execute(
                    """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
                       VALUES (%s, %s::jsonb, %s, %s, %s, %s)""",
                    (herb, json.dumps(doc, ensure_ascii=False), verdict, reason, "processor", now),
                )
        conn.commit()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "herb-process-record"}


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = USERS.get(body.username.strip())
    if not user or not pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": body.username.strip(), "role": user["role"], "exp": exp}, SECRET, algorithm="HS256")
    return {
        "access_token": token,
        "username": body.username.strip(),
        "role": user["role"],
        "identity": user.get("identity"),
    }


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return {"username": user["username"], "role": user["role"], "identity": identity_of(user["username"])}


@app.put("/api/identity")
def set_identity(body: IdentityIn, user: dict = Depends(require_writer)):
    USERS[user["username"]]["identity"] = body.identity
    return {"username": user["username"], "identity": body.identity}


@app.get("/api/batches")
def list_batches(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute("SELECT id, herb, doc, verdict, reason, created_by FROM batches ORDER BY id DESC").fetchall()
    return rows


@app.post("/api/batches", status_code=201)
def create_batch(body: BatchIn, user: dict = Depends(require_writer)):
    if identity_of(user["username"]) != "master":
        raise HTTPException(status_code=403, detail="学员只能提交带教草稿，待师傅定稿后落入正式记录")
    doc = {"steps": [s.model_dump() for s in body.steps]}
    verdict, reason = judge(doc)
    with connect() as conn:
        row = conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by""",
            (body.herb.strip(), json.dumps(doc, ensure_ascii=False), verdict, reason, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row


@app.get("/api/drafts")
def list_drafts(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute("SELECT id, herb, doc, created_by FROM drafts ORDER BY id DESC").fetchall()
    return rows


@app.post("/api/drafts", status_code=201)
def create_draft(body: BatchIn, user: dict = Depends(require_apprentice)):
    doc = {"steps": [s.model_dump() for s in body.steps]}
    with connect() as conn:
        row = conn.execute(
            """INSERT INTO drafts (herb, doc, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s)
               RETURNING id, herb, doc, created_by""",
            (body.herb.strip(), json.dumps(doc, ensure_ascii=False), user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row


@app.post("/api/drafts/{draft_id}/finalize", status_code=201)
def finalize_draft(draft_id: int, user: dict = Depends(require_master)):
    with connect() as conn:
        draft = conn.execute("SELECT id, herb, doc FROM drafts WHERE id = %s", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="草稿不存在或已定稿")
        verdict, reason = judge(draft["doc"])
        row = conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by""",
            (draft["herb"], json.dumps(draft["doc"], ensure_ascii=False), verdict, reason, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.execute("DELETE FROM drafts WHERE id = %s", (draft_id,))
        conn.commit()
    return row
