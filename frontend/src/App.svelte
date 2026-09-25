<script>
  const IDENTITY_LABELS = { apprentice: '学员', master: '师傅' }

  let username = 'processor'
  let password = 'herb123456'
  let token = localStorage.getItem('herb_token') || ''
  let role = localStorage.getItem('herb_role') || ''
  let identity = ''
  let rows = []
  let drafts = []
  let herb = '白芍'
  let tempC = 110
  let minutes = 10
  let error = ''

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '请求失败')
    return data
  }

  async function enter() {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    token = data.access_token
    role = data.role
    identity = data.identity || ''
    localStorage.setItem('herb_token', token)
    localStorage.setItem('herb_role', role)
    await load()
  }

  async function load() {
    const me = await api('/api/me')
    identity = me.identity || ''
    rows = await api('/api/batches')
    drafts = await api('/api/drafts')
  }

  async function setIdentity(next) {
    error = ''
    try {
      const data = await api('/api/identity', {
        method: 'PUT',
        body: JSON.stringify({ identity: next }),
      })
      identity = data.identity
      await load()
    } catch (err) {
      error = err.message
    }
  }

  async function save() {
    error = ''
    try {
      const body = JSON.stringify({
        herb,
        steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
      })
      if (identity === 'apprentice') {
        await api('/api/drafts', { method: 'POST', body })
      } else {
        await api('/api/batches', { method: 'POST', body })
      }
      await load()
    } catch (err) {
      error = err.message
    }
  }

  async function finalize(draft) {
    error = ''
    try {
      await api(`/api/drafts/${draft.id}/finalize`, { method: 'POST' })
      await load()
    } catch (err) {
      error = err.message
    }
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
    identity = ''
  }

  if (token) load()
</script>

<main>
  {#if !token}
    <h1>饮片炮制记录台</h1>
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。</p>
    <input bind:value={username} />
    <input type="password" bind:value={password} />
    <button on:click={enter}>登录</button>
    <p>processor / herb123456 可写；checker / check123456 只读</p>
  {:else}
    <header class="topbar">
      <strong>饮片炮制记录台</strong>
      <a href="#drafts">带教草稿</a>
      <button on:click={leave}>退出</button>
    </header>
    {#if error}<p class="error">{error}</p>{/if}

    <section>
      <h2>身份切换</h2>
      <p>
        可写账号分两种身份：<b>学员</b>只能建带教草稿（填饮片、温度、时长，不落正式行）；
        <b>师傅</b>打开草稿点定稿，定稿后才生成正式行并销掉草稿。质检员可看草稿列表，不能建草稿、不能定稿。
      </p>
      {#if role === 'writer'}
        <p>
          当前身份：{IDENTITY_LABELS[identity] || identity}
          <button on:click={() => setIdentity('apprentice')} disabled={identity === 'apprentice'}>标为学员</button>
          <button on:click={() => setIdentity('master')} disabled={identity === 'master'}>标为师傅</button>
        </p>
      {:else}
        <p>当前为质检员（只读），无需切换身份。</p>
      {/if}
    </section>

    {#if role === 'writer'}
      <section>
        <input bind:value={herb} placeholder="饮片" />
        <input type="number" bind:value={tempC} />
        <input type="number" bind:value={minutes} />
        {#if identity === 'apprentice'}
          <button on:click={save}>提交带教草稿</button>
        {:else}
          <button on:click={save}>写入清炒记录</button>
        {/if}
      </section>
    {/if}

    <section>
      <h2>炮制记录总表</h2>
      <ul>
        {#each rows as row}
          <li>{row.herb} · {row.verdict} · {row.reason} · 温度 {row.doc.steps[0].temp_c}</li>
        {/each}
      </ul>
    </section>

    <section id="drafts">
      <h2>带教草稿</h2>
      {#if drafts.length === 0}
        <p>暂无草稿。</p>
      {:else}
        <ul>
          {#each drafts as draft}
            <li>
              #{draft.id} {draft.herb} · 温度 {draft.doc.steps[0].temp_c} · 时长 {draft.doc.steps[0].minutes} 分钟 · 学员 {draft.created_by}
              {#if role === 'writer'}
                <button on:click={() => finalize(draft)}>定稿</button>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
      {#if role === 'writer' && identity !== 'master'}
        <p>定稿需师傅身份，学员点定稿会被拒绝。</p>
      {/if}
    </section>
  {/if}
</main>

<style>
  main { font-family: sans-serif; max-width: 720px; margin: 24px auto; color: #3f2f1f; }
  h1 { color: #7c2d12; }
  h2 { color: #7c2d12; font-size: 18px; }
  input { margin-right: 8px; padding: 6px; }
  .topbar { display: flex; gap: 16px; align-items: center; padding: 10px 0; border-bottom: 1px solid #d6c4b2; margin-bottom: 16px; }
  .topbar strong { color: #7c2d12; margin-right: auto; }
  .topbar a { color: #7c2d12; }
  .error { color: #b91c1c; }
  section { margin-bottom: 20px; }
</style>
