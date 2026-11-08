// PLAYER TWO jury site: the glue every front-end shares. Jury.boot() starts the HoloDoom engine
// with zero clicks, wires the step feed / status / buttons the page provides, and keeps the
// keyboard focused on the game while a human plays. Each page keeps its own HTML and look.
'use strict'

window.Jury = (() => {
  const $ = (sel, root = document) => (typeof sel === 'string' ? root.querySelector(sel) : sel)
  const KEY_LABEL = {
    up: '↑ forward', down: '↓ back', left: '← turn', right: '→ turn', strafe_left: '⇠ strafe', strafe_right: '⇢ strafe',
    run: '⇧ run', fire: 'CTRL fire', use: 'SPACE use', w1: '1 fist', w2: '2 pistol', w3: '3 shotgun', w4: '4 chaingun',
    w5: '5 rocket', w6: '6 plasma', w7: '7 BFG',
  }
  const HUMAN_KEYS = new Set(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'Control', 'Shift', 'Alt'])

  function median(a) { if (!a.length) return 0; const s = [...a].sort((x, y) => x - y); return s[s.length >> 1] }

  function boot(cfg) {
    const feed = $(cfg.feed), thought = $(cfg.thought), status = $(cfg.status), latency = $(cfg.latency)
    const over = $(cfg.over), back = $(cfg.back), tell = $(cfg.tell), send = $(cfg.send), sound = $(cfg.sound)
    const hd = HoloDoom.create(Object.assign({ container: $(cfg.container), speak: true }, cfg.engine || {}))
    const page = document.documentElement
    const lat = []
    let steps = 0

    const setStatus = (s) => {
      const m = s.mode
      page.dataset.mode = m
      if (status) {
        status.textContent = m === 'live' ? (s.thinking ? 'LIVE · Holo is looking at the screen…' : 'LIVE · Holo plays')
          : m === 'recorded' ? 'RECORDED · Holo run replay' + (s.why && s.why !== 'forced' ? ' (' + s.why + ')' : '')
            : m === 'human' ? 'YOU play · arrows move · Ctrl fires · Space opens' : 'loading Doom…'
      }
      if (over) over.hidden = m === 'human'
      if (back) back.hidden = m !== 'human'
      if (cfg.onState) cfg.onState(s)
    }
    hd.on('state', setStatus)
    hd.on('thinking', () => { page.classList.add('thinking'); if (status && hd.state().mode === 'live') status.textContent = 'LIVE · Holo is looking at the screen…' })
    hd.on('step', (s) => {
      page.classList.remove('thinking')
      steps++
      if (s.latency_ms) lat.push(s.latency_ms)
      if (latency) latency.textContent = lat.length ? median(lat.slice(-20)) + ' ms' : '—'
      if (thought) thought.textContent = (s.mode === 'live' && hd.state().instructionLeft > 0 ? '[you: ' + hd.state().instruction + '] ' : '') + (s.thought || (s.error ? 'Holo is busy, I keep moving: ' + s.error : '…'))
      if (feed) {
        const li = document.createElement('li')
        li.className = 'step ' + (s.mode || '') + (s.error ? ' err' : '')
        const keys = (s.keys || []).map((k) => `<b class="key k-${k}">${KEY_LABEL[k] || k}</b>`).join('')
        li.innerHTML = `<span class="n">#${s.step}</span><span class="keys">${keys}</span><span class="hold">${s.hold_ms} ms</span><span class="say">${esc(s.thought || s.error || '')}</span>${s.latency_ms ? `<span class="lat">${s.latency_ms} ms</span>` : ''}`
        feed.prepend(li)
        while (feed.children.length > (cfg.feedMax || 40)) feed.lastChild.remove()
      }
      if (cfg.onStep) cfg.onStep(s)
    })
    hd.on('busy', (b) => { if (status) status.textContent = `LIVE · H API free plan (30 req/min): too many jurors at once, Holo answers in ${b.retryAfter}s` })
    hd.on('error', (e) => { if (status && hd.state().mode === 'loading') status.textContent = e.message })

    if (over) over.onclick = () => hd.takeOver()
    if (back) back.onclick = () => hd.giveBack()
    if (tell) {
      const go = () => { if (tell.value.trim()) { hd.tell(tell.value.trim()); tell.value = ''; if (thought) thought.textContent = 'Holo heard you: ' + hd.state().instruction } }
      if (send) send.onclick = go
      tell.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); e.stopPropagation() })
    }
    if (sound) sound.onclick = async () => { await hd.unmute(); sound.classList.add('on'); sound.textContent = sound.dataset.on || 'sound on' }
    // while the human plays, keep the game keys from scrolling the page and the focus on the canvas
    window.addEventListener('keydown', (e) => { if (hd.state().mode === 'human' && HUMAN_KEYS.has(e.key) && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) e.preventDefault() })
    // any tap on the game while Holo plays = take over (the "INSERT COIN" moment)
    if (cfg.tapToPlay !== false) $(cfg.container).addEventListener('pointerdown', () => { if (hd.state().mode !== 'human') hd.takeOver() })
    hd.start().then(() => setStatus(hd.state()))
    return hd
  }

  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))

  // the credits line every page carries
  function credits(extra = '') {
    return `<a href="/">PLAYER TWO</a> · a 42AI × H Company hackathon build · vision by <a href="https://www.hcompany.ai" target="_blank" rel="noreferrer">H Company Holo</a> ·
      code by <a href="https://devin.ai" target="_blank" rel="noreferrer">Devin</a> · voice by ElevenLabs · ears by Gladia ·
      Doom: <a href="https://github.com/cloudflare/doom-wasm" target="_blank" rel="noreferrer">Chocolate Doom WebAssembly</a> (GPL) +
      <a href="https://freedoom.github.io" target="_blank" rel="noreferrer">Freedoom</a> (BSD) ${extra}`
  }
  for (const el of document.querySelectorAll('[data-credits]')) el.innerHTML = credits(el.dataset.credits)

  return { boot, credits, median }
})()
