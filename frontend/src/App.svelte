<script>
  let username = 'processor'
  let password = 'herb123456'
  let token = localStorage.getItem('herb_token') || ''
  let role = localStorage.getItem('herb_role') || ''
  // 炮制员（可写账号）的带教身份：apprentice 学员 / master 师傅，登录默认学员
  let identity = localStorage.getItem('herb_identity') || 'apprentice'
  let page = 'home'
  let rows = []
  let drafts = []
  let herb = '白芍'
  let tempC = 110
  let minutes = 10
  let error = ''
  let notice = ''

  const isWriter = () => role === 'writer'

  async function api(path, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.withIdentity ? { 'X-Identity': identity } : {}),
    }
    const res = await fetch(path, { ...options, headers })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '请求失败')
    return data
  }

  async function enter() {
    error = ''
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      token = data.access_token
      role = data.role
      identity = 'apprentice'
      localStorage.setItem('herb_token', token)
      localStorage.setItem('herb_role', role)
      localStorage.setItem('herb_identity', identity)
      await loadBatches()
    } catch (err) {
      error = err.message
    }
  }

  async function loadBatches() {
    rows = await api('/api/batches')
  }

  async function loadDrafts() {
    drafts = await api('/api/drafts')
  }

  async function goto(target) {
    page = target
    error = ''
    notice = ''
    if (target === 'home') await loadBatches()
    if (target === 'drafts') await loadDrafts()
  }

  async function switchIdentity(next) {
    identity = next
    localStorage.setItem('herb_identity', identity)
    error = ''
    notice = ''
  }

  // 学员建草稿：只填饮片温度时长，不落正式行
  async function saveDraft() {
    error = ''
    notice = ''
    try {
      await api('/api/drafts', {
        method: 'POST',
        withIdentity: true,
        body: JSON.stringify({
          herb,
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
        }),
      })
      notice = '草稿已保存，师傅定稿前不会进入总表。'
      await loadDrafts()
    } catch (err) {
      error = err.message
    }
  }

  // 师傅定稿：生成正式行并销草稿；学员点定稿应由后端拒绝
  async function finalizeDraft(draft) {
    error = ''
    notice = ''
    try {
      await api(`/api/drafts/${draft.id}/finalize`, { method: 'POST', withIdentity: true })
      notice = `「${draft.herb}」已定稿，正式行已生成。`
      await loadDrafts()
    } catch (err) {
      error = err.message
    }
  }

  // 师傅在总表直接写正式记录
  async function saveBatch() {
    error = ''
    notice = ''
    try {
      await api('/api/batches', {
        method: 'POST',
        withIdentity: true,
        body: JSON.stringify({
          herb,
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
        }),
      })
      await loadBatches()
    } catch (err) {
      error = err.message
    }
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
    identity = 'apprentice'
    page = 'home'
  }

  if (token) loadBatches()
</script>

<main>
  {#if !token}
    <h1>饮片炮制记录台</h1>
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。</p>
    <input bind:value={username} />
    <input type="password" bind:value={password} />
    <button on:click={enter}>登录</button>
    {#if error}<p class="error">{error}</p>{/if}
    <p>processor / herb123456 为炮制员（可在带教草稿页切换学员/师傅身份）；checker / check123456 为质检员，只读</p>
  {:else}
    <header class="topbar">
      <h1>饮片炮制记录台</h1>
      <nav>
        <a href="javascript:void(0)" class:active={page === 'home'} on:click={() => goto('home')}>总表</a>
        <a href="javascript:void(0)" class:active={page === 'drafts'} on:click={() => goto('drafts')}>带教草稿</a>
      </nav>
      <div class="who">
        {#if isWriter()}
          <span class="badge">当前身份：{identity === 'master' ? '师傅' : '学员'}</span>
        {:else}
          <span class="badge">质检员（只读）</span>
        {/if}
        <button on:click={leave}>退出</button>
      </div>
    </header>

    {#if page === 'home'}
      <section>
        <h2>炮制记录总表</h2>
        <p class="muted">共 {rows.length} 行（草稿不计入总表）。</p>
        {#if isWriter()}
          {#if identity === 'master'}
            <div class="form">
              <input bind:value={herb} placeholder="饮片" />
              <input type="number" bind:value={tempC} />
              <input type="number" bind:value={minutes} />
              <button on:click={saveBatch}>师傅写入清炒记录</button>
            </div>
          {:else}
            <p class="muted">当前为学员身份，只能在
              <a href="javascript:void(0)" on:click={() => goto('drafts')}>带教草稿</a>
              页建草稿，不能直接写正式行。</p>
          {/if}
        {/if}
        {#if error}<p class="error">{error}</p>{/if}
        <ul>
          {#each rows as row}
            <li>{row.herb} · {row.verdict} · {row.reason} · 温度 {row.doc.steps[0].temp_c} · 时长 {row.doc.steps[0].minutes} 分钟 · {row.created_by}</li>
          {/each}
        </ul>
      </section>
    {:else}
      <section>
        <h2>带教草稿</h2>

        <div class="panel">
          <h3>身份切换说明</h3>
          <ul class="rules">
            <li><strong>学员</strong>：只能建草稿，填写饮片、清炒温度与时长；草稿不落正式行、不进总表，也不能定稿。</li>
            <li><strong>师傅</strong>：可打开学员草稿点「定稿」；定稿后才生成正式行并判定放行，同时销毁草稿。师傅也可在总表直接写正式记录。</li>
            <li><strong>质检员</strong>：可查看草稿列表，不能建草稿、不能定稿。</li>
          </ul>
          {#if isWriter()}
            <div class="switch">
              <span>切换当前炮制员身份：</span>
              <button class:active={identity !== 'master'} on:click={() => switchIdentity('apprentice')}>学员</button>
              <button class:active={identity === 'master'} on:click={() => switchIdentity('master')}>师傅</button>
            </div>
          {:else}
            <p class="muted">质检员账号无学员/师傅身份，以下草稿仅供查看。</p>
          {/if}
        </div>

        {#if isWriter() && identity !== 'master'}
          <div class="panel">
            <h3>学员建草稿</h3>
            <div class="form">
              <input bind:value={herb} placeholder="饮片" />
              <input type="number" bind:value={tempC} placeholder="温度℃" />
              <input type="number" bind:value={minutes} placeholder="时长分钟" />
              <button on:click={saveDraft}>保存草稿（不落正式行）</button>
            </div>
          </div>
        {/if}

        <div class="panel">
          <h3>草稿列表 / 定稿区</h3>
          {#if notice}<p class="notice">{notice}</p>{/if}
          {#if error}<p class="error">{error}</p>{/if}
          {#if drafts.length === 0}
            <p class="muted">暂无草稿。</p>
          {:else}
            <table>
              <thead>
                <tr><th>饮片</th><th>温度℃</th><th>时长(分)</th><th>建稿人</th><th>操作</th></tr>
              </thead>
              <tbody>
                {#each drafts as draft}
                  <tr>
                    <td>{draft.herb}</td>
                    <td>{draft.doc.steps[0].temp_c}</td>
                    <td>{draft.doc.steps[0].minutes}</td>
                    <td>{draft.created_by}</td>
                    <td>
                      {#if isWriter()}
                        <button on:click={() => finalizeDraft(draft)}>定稿</button>
                      {:else}
                        <span class="muted">仅查看</span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
            {#if isWriter() && identity !== 'master'}
              <p class="muted">当前为学员身份，点「定稿」会被拒绝；请切换师傅身份后定稿。</p>
            {/if}
          {/if}
        </div>
      </section>
    {/if}
    {/if}
  </main>

<style>
  main { font-family: sans-serif; max-width: 820px; margin: 24px auto; color: #3f2f1f; }
  h1 { color: #7c2d12; margin: 0; font-size: 22px; }
  h2 { color: #7c2d12; }
  .topbar { display: flex; align-items: center; gap: 20px; border-bottom: 2px solid #e7d9c8; padding-bottom: 10px; margin-bottom: 16px; }
  .topbar nav { display: flex; gap: 14px; flex: 1; }
  .topbar nav a { text-decoration: none; color: #8a5a33; font-weight: bold; }
  .topbar nav a.active { color: #7c2d12; border-bottom: 2px solid #7c2d12; }
  .who { display: flex; align-items: center; gap: 10px; }
  .badge { background: #f3e7d8; border-radius: 10px; padding: 3px 10px; font-size: 13px; }
  .panel { background: #fbf6ef; border: 1px solid #e7d9c8; border-radius: 8px; padding: 12px 16px; margin: 14px 0; }
  .rules li { margin: 4px 0; }
  .switch { margin-top: 10px; }
  .form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  input { padding: 6px; width: 110px; }
  .form input:first-child { width: 140px; }
  button { padding: 6px 12px; cursor: pointer; }
  button.active { background: #7c2d12; color: #fff; border-color: #7c2d12; }
  table { border-collapse: collapse; width: 100%; margin-top: 8px; }
  th, td { border: 1px solid #e7d9c8; padding: 6px 10px; text-align: left; }
  .error { color: #b91c1c; }
  .notice { color: #166534; }
  .muted { color: #8a7a68; }
</style>
