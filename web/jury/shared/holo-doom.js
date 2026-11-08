// PLAYER TWO · "Holo plays Doom in the browser": the shared engine behind /arcade/, /live/, /lab/
// and /story/. Doom (Chocolate Doom WebAssembly + Freedoom) runs in this page; every step the game
// is paused, the canvas is grabbed as a small JPEG and posted to /api/holo/act (H Company's Holo
// vision model); the answer {thought, keys, hold_ms, aim} is injected as real key events the SDL
// port receives, the game runs for hold_ms, repeat. When the server has no key or the demo cap is
// reached, the engine plays a RECORDED run (frames + moves) so nothing ever looks broken.
'use strict'

window.HoloDoom = (() => {
  const KID = '/kid/' // where the WASM build and the WAD are served
  const SHOT_W = 480
  const KEYS = {
    up: ['ArrowUp', 38], down: ['ArrowDown', 40], left: ['ArrowLeft', 37], right: ['ArrowRight', 39],
    fire: ['Control', 17, 'ControlLeft'], use: [' ', 32, 'Space'], run: ['Shift', 16, 'ShiftLeft'],
    strafe_left: ['ArrowLeft', 37, null, 'Alt'], strafe_right: ['ArrowRight', 39, null, 'Alt'],
    w1: ['1', 49, 'Digit1'], w2: ['2', 50, 'Digit2'], w3: ['3', 51, 'Digit3'], w4: ['4', 52, 'Digit4'],
    w5: ['5', 53, 'Digit5'], w6: ['6', 54, 'Digit6'], w7: ['7', 55, 'Digit7'],
    alt: ['Alt', 18, 'AltLeft'],
  }
  const LETTERS = (s) => [...s].map((ch) => [ch, ch.toUpperCase().charCodeAt(0), 'Key' + ch.toUpperCase()])
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const frames = (n = 1) => new Promise((r) => { const f = () => (--n <= 0 ? r() : requestAnimationFrame(f)); requestAnimationFrame(f) })
  const CID = Math.random().toString(36).slice(2, 10)
  const q = new URLSearchParams(location.search)

  // SDL draws with WebGL: keep the buffer so the canvas can be read back for Holo's picture.
  const getContext = HTMLCanvasElement.prototype.getContext
  HTMLCanvasElement.prototype.getContext = function (type, attrs) {
    if (this.dataset.holo === 'game' && /webgl/.test(type)) attrs = Object.assign({}, attrs, { preserveDrawingBuffer: true })
    return getContext.call(this, type, attrs)
  }
  // the browser mutes audio until a gesture; SDL2 keeps its context at Module.SDL2.audioContext,
  // one tap resumes it (wrapping window.AudioContext breaks the Asyncify build: do not).
  const contexts = { get list() { const c = window.Module && Module.SDL2 && Module.SDL2.audioContext; return c ? [c] : [] } }

  function keyEvent(type, def, mods = {}) {
    const [key, keyCode, code] = def
    return new KeyboardEvent(type, {
      key, keyCode, which: keyCode, code: code || key, bubbles: true, cancelable: true,
      altKey: !!mods.alt, ctrlKey: !!mods.ctrl, shiftKey: !!mods.shift,
    })
  }

  function create(opts) {
    const o = Object.assign({
      container: null, mode: q.get('mode') || 'auto', solo: q.has('solo'), pauseWhileThinking: false,
      warp: (q.get('warp') || '1 1').split(/[ ,]/), skill: q.get('skill') || '3', god: !q.has('nogod'),
      recordedUrl: '/jury/recorded/run.json', speak: false, pushUrl: null, onStep: () => {}, onState: () => {},
      onFrame: () => {}, record: q.has('record'), busyLimit: Number(q.get('busy')) || 40,
    }, opts)
    const el = o.container
    el.classList.add('holo-doom')
    if (!document.getElementById('holo-doom-base')) {
      const css = document.createElement('style'); css.id = 'holo-doom-base'
      css.textContent = '.holo-doom{position:relative;aspect-ratio:4/3;background:#000;overflow:hidden}.holo-doom canvas{position:absolute;inset:0;width:100%;height:100%;display:block;outline:none;image-rendering:pixelated}.holo-doom.live [data-holo=film],.holo-doom.human [data-holo=film]{display:none}.holo-doom.recorded [data-holo=game]{visibility:hidden}.holo-aim{position:absolute;pointer-events:none;transform:translate(-50%,-50%)}.holo-badge{position:absolute}'
      document.head.prepend(css)
    }
    el.innerHTML = '<canvas data-holo="game" tabindex="0" oncontextmenu="event.preventDefault()"></canvas><canvas data-holo="film"></canvas><div class="holo-aim"></div><div class="holo-badge"></div>'
    const game = el.querySelector('[data-holo=game]'), film = el.querySelector('[data-holo=film]')
    const aim = el.querySelector('.holo-aim'), badge = el.querySelector('.holo-badge')
    // SDL draws a 640x400 window; the build never sizes the canvas, so set the backing store here
    // (the default 300x150 shows only the bottom-left quarter).
    const cs = (q.get('cs') || o.canvasSize || '640x400').split('x').map(Number)
    if (!document.getElementById('canvas')) game.id = 'canvas' // SDL binds its keyboard listener to #canvas
    game.width = cs[0]; game.height = cs[1]
    film.width = 800; film.height = 600
    const st = {
      mode: 'loading', running: false, human: false, step: 0, recent: [], instruction: '', instructionLeft: 0,
      lastHash: null, same: 0, thinking: false, held: new Set(), latencies: [], started: 0, speaking: false,
      audio: false, recorded: null, recIndex: 0, booted: false, gameReady: false, errors: 0, keyUp: null, muted: false,
      tape: [], busyUntil: 0, busyCount: 0, loopRunning: false,
    }
    const listeners = {}
    const emit = (ev, data) => { (listeners[ev] || []).forEach((f) => f(data)); if (ev === 'step') o.onStep(data); if (ev === 'state') o.onState(data) }
    const on = (ev, f) => { (listeners[ev] = listeners[ev] || []).push(f); return api }
    const setMode = (m, why) => { st.mode = m; badge.textContent = m === 'live' ? 'LIVE · Holo' : m === 'recorded' ? 'RECORDED' : m === 'human' ? 'YOU' : m; badge.dataset.mode = m; emit('state', Object.assign({ why }, snapshot())) }
    const snapshot = () => ({ mode: st.mode, step: st.step, human: st.human, thinking: st.thinking, gameReady: st.gameReady, audio: st.audio, latencies: st.latencies.slice(-60), instruction: st.instruction })

    // ------------------------------------------------------------------ the game
    function target() { return window }
    function down(name, mods) { const d = KEYS[name]; if (!d || !st.loopRunning) return; target().dispatchEvent(keyEvent('keydown', d, mods)); st.held.add(name) }
    function up(name, mods) { const d = KEYS[name]; if (!d || !st.loopRunning) return; target().dispatchEvent(keyEvent('keyup', d, mods)); st.held.delete(name) }
    function releaseAll() { for (const k of [...st.held]) up(k); up('alt') }
    async function typeCheat(word) { for (const d of LETTERS(word)) { target().dispatchEvent(keyEvent('keydown', d)); await frames(2); target().dispatchEvent(keyEvent('keyup', d)); await frames(2) } }

    function boot() {
      if (st.booted) return
      st.booted = true
      window.Module = {
        noInitialRun: true,
        canvas: game,
        preRun: () => {
          Module.FS.createPreloadedFile('', 'doom1.wad', KID + 'doom1.wad', true, true)
          Module.FS.createPreloadedFile('', 'default.cfg', KID + 'default.cfg', true, true)
        },
        onRuntimeInitialized: async () => {
          callMain(['-iwad', 'doom1.wad', '-window', '-nogui', '-nomusic', '-config', 'default.cfg', '-skill', o.skill, '-warp', ...o.warp])
          // SDL resizes the canvas to its CSS size when video starts: that marks the main loop
          // running. Only then may key events reach the game (the build uses Asyncify: input
          // during start-up leaves every later frame dying with "memory access out of bounds").
          for (let i = 0; i < 100 && (game.width === cs[0] && game.height === cs[1]); i++) await sleep(100)
          await sleep(800)
          st.loopRunning = true
          if (o.god) await typeCheat('iddqd')
          st.gameReady = true
          emit('state', snapshot())
          emit('ready')
        },
        // A print callback that does anything (even a regex test or console.log on the text)
        // breaks this Asyncify build: every frame then throws "memory access out of bounds".
        // Keep it a no-op; printErr is safe.
        print: () => {},
        printErr: (t) => { if (q.has('debug')) console.warn(t) },
        setStatus: (t) => emit('status', t),
      }
      const s = document.createElement('script')
      s.src = KID + 'websockets-doom.js'
      document.body.appendChild(s)
    }

    // Module.pauseMainLoop/resumeMainLoop corrupt this Asyncify build (every later frame throws
    // "memory access out of bounds"), so the game is never frozen: while Holo thinks no key is
    // held and the marine simply stands still, like a human player reading the screen.
    function pause() {}
    function resume() {}

    const shotCanvas = document.createElement('canvas')
    function shot() {
      const src = st.mode === 'recorded' && !st.gameReady ? film : game
      shotCanvas.width = SHOT_W
      shotCanvas.height = Math.round((SHOT_W * src.height) / src.width) || 360
      const ctx = shotCanvas.getContext('2d')
      ctx.drawImage(src, 0, 0, shotCanvas.width, shotCanvas.height)
      // a coarse hash of the view (without the status bar) tells whether anything changed
      const d = ctx.getImageData(0, 0, shotCanvas.width, Math.round(shotCanvas.height * 0.8)).data
      let h = 0
      for (let i = 0; i < d.length; i += 97) h = (h * 31 + d[i]) >>> 0
      return { url: shotCanvas.toDataURL('image/jpeg', 0.7), hash: h, w: shotCanvas.width, h: shotCanvas.height }
    }

    // ------------------------------------------------------------------ Holo
    async function askHolo(frame, stalled) {
      const body = { image: frame.url, recent: st.recent.slice(-8), instruction: st.instructionLeft > 0 ? st.instruction : '', step: st.step, stalled }
      const r = await fetch('/api/holo/act?c=' + CID, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (r.status === 429 || r.status === 503) {
        const j = await r.json().catch(() => ({}))
        const d = j.detail || {}
        if (d.busy) throw Object.assign(new Error('Holo is busy'), { busy: true, retryAfter: Number(d.retry_after) || 10 })
        throw Object.assign(new Error(typeof d === 'string' ? d : 'capped'), { capped: true })
      }
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return r.json()
    }

    function localMove(stalled) { // Holo is unreachable for a moment: keep moving sensibly
      return stalled
        ? { thought: 'Nothing changed, I will turn around.', keys: ['left'], hold_ms: 900, aim: null, status: 'stuck', local: true }
        : { thought: 'Moving on while I think.', keys: ['up'], hold_ms: 500, aim: null, status: 'ok', local: true }
    }

    async function loadRecorded() {
      if (st.recorded) return st.recorded
      const r = await fetch(o.recordedUrl)
      if (!r.ok) throw new Error('no recorded run')
      st.recorded = await r.json()
      st.recorded.base = o.recordedUrl.replace(/[^/]*$/, '')
      return st.recorded
    }

    function drawFrame(src) {
      return new Promise((res) => {
        const img = new Image()
        img.onload = () => { film.width = img.naturalWidth; film.height = img.naturalHeight; film.getContext('2d').drawImage(img, 0, 0); res(img) }
        img.onerror = () => res(null)
        img.src = src
      })
    }

    function showAim(move, frame) {
      if (!move.aim || !frame) { aim.style.display = 'none'; return }
      aim.style.display = ''
      aim.style.left = (100 * move.aim.x / frame.w) + '%'
      aim.style.top = (100 * move.aim.y / frame.h) + '%'
    }

    async function speak(text) {
      if (!o.speak || !st.audio || st.speaking || st.muted || !text) return
      st.speaking = true
      try {
        const a = new Audio('/api/holo/say?c=' + CID + '&text=' + encodeURIComponent(text))
        await new Promise((res) => { a.onended = res; a.onerror = res; a.play().catch(res) })
      } finally { st.speaking = false }
    }

    async function perform(move) { // keys down -> game runs hold_ms -> keys up
      const mods = { alt: move.keys.some((k) => k.startsWith('strafe')), shift: move.keys.includes('run'), ctrl: move.keys.includes('fire') }
      resume()
      if (mods.alt) down('alt')
      for (const k of move.keys) down(k, mods)
      await sleep(move.hold_ms)
      for (const k of [...move.keys].reverse()) up(k, mods)
      if (mods.alt) up('alt')
      await frames(2) // SDL reads the key-up on the next loop turn
    }

    async function stepLive() {
      if (o.pauseWhileThinking) { pause(); await frames(1) }
      const frame = shot()
      const stalled = frame.hash === st.lastHash ? ++st.same >= 2 : (st.same = 0, false)
      st.lastHash = frame.hash
      st.thinking = true
      emit('thinking', { frame })
      const t0 = performance.now()
      let move
      try {
        if (st.busyUntil > Date.now()) throw Object.assign(new Error('Holo is busy'), { busy: true, retryAfter: 0 })
        move = await askHolo(frame, stalled)
        st.errors = 0
        st.busyCount = 0
      } catch (e) {
        if (e.capped) { setMode('recorded', e.message); st.thinking = false; return 'capped' }
        if (e.busy) { // the shared H budget is spent for this minute: everyone else gets a turn first
          if (e.retryAfter) { st.busyUntil = Date.now() + e.retryAfter * 1000; emit('busy', { retryAfter: e.retryAfter }) }
          if (++st.busyCount >= o.busyLimit) { setMode('recorded', 'Holo is busy: many people are playing'); st.thinking = false; return 'capped' }
          move = localMove(stalled); move.error = e.message; move.busy = true
          st.thinking = false
          st.step++
          const step = Object.assign({ step: st.step, frame, mode: 'live', t: Date.now() }, move)
          emit('step', step)
          await perform(move)
          return 'busy'
        }
        move = localMove(stalled)
        move.error = e.message
        if (++st.errors >= 6) { setMode('recorded', 'Holo unreachable: ' + e.message); st.thinking = false; return 'capped' }
      }
      move.latency_ms = move.latency_ms ?? Math.round(performance.now() - t0)
      move.client_ms = Math.round(performance.now() - t0)
      st.thinking = false
      if (st.same >= 5) { move.keys = ['left']; move.hold_ms = 900; move.thought = move.thought || 'Turning around.' } // local rescue
      if (move.status === 'dead' || move.status === 'menu') move.keys = ['use']
      st.step++
      st.latencies.push(move.latency_ms)
      st.recent.push({ keys: move.keys, hold_ms: move.hold_ms, thought: move.thought })
      if (st.instructionLeft > 0) st.instructionLeft--
      const step = Object.assign({ step: st.step, frame, mode: 'live', t: Date.now() }, move)
      showAim(move, frame)
      emit('step', step)
      if (o.record) st.tape.push({ step: st.step, thought: move.thought, keys: move.keys, hold_ms: move.hold_ms, aim: move.aim, status: move.status, latency_ms: move.latency_ms, image: frame.url })
      speak(move.thought)
      if (st.human) return
      await perform(move)
    }

    async function stepRecorded() {
      const rec = await loadRecorded()
      const steps = rec.steps || []
      if (!steps.length) { await sleep(1000); return }
      const s = steps[st.recIndex % steps.length]
      st.recIndex++
      st.thinking = true
      emit('thinking', {})
      const img = await drawFrame(rec.base + s.frame)
      const frame = img ? { w: img.naturalWidth, h: img.naturalHeight, url: img.src } : null
      await sleep(Math.min(s.latency_ms || 500, 900))
      st.thinking = false
      st.step++
      st.latencies.push(s.latency_ms || 0)
      const move = Object.assign({}, s, { aim: s.aim || null })
      const step = Object.assign({ step: st.step, frame, mode: 'recorded', t: Date.now() }, move)
      showAim(move, frame)
      emit('step', step)
      speak(s.thought)
      await sleep(s.hold_ms || 500)
    }

    async function loop() {
      st.started = Date.now()
      while (st.running) {
        try {
          if (st.human) { await sleep(250); continue }
          if (st.mode === 'live' && !st.gameReady) { await sleep(200); continue }
          if (st.mode === 'live') await stepLive()
          else if (st.mode === 'recorded') await stepRecorded()
          else await sleep(200)
        } catch (e) {
          emit('error', e)
          await sleep(800)
        }
      }
    }

    // ------------------------------------------------------------------ public API
    const api = {
      state: snapshot, on, canvas: game, film,
      async start() {
        if (st.running) return
        st.running = true
        let status = { live: false }
        try { status = await (await fetch('/api/holo/status')).json() } catch (e) { /* offline: recorded */ }
        const wantLive = o.mode === 'live' || (o.mode === 'auto' && status.live)
        if (wantLive) {
          setMode('live')
          el.classList.add('live')
          boot()
          await new Promise((res) => on('ready', res))
          emit('state', snapshot())
        } else {
          setMode('recorded', status.live ? 'forced' : 'Holo is resting (no key or demo cap): recorded run')
          el.classList.add('recorded')
          try { await loadRecorded() } catch (e) { emit('error', e) }
        }
        loop()
        return st.mode
      },
      stop() { st.running = false; releaseAll() },
      tell(text) { st.instruction = (text || '').slice(0, 240); st.instructionLeft = st.instruction ? 4 : 0; emit('state', snapshot()) },
      async takeOver() { // INSERT COIN: the human plays
        st.human = true
        releaseAll()
        if (!st.gameReady) { boot(); await new Promise((res) => on('ready', res)) }
        el.classList.add('human'); el.classList.remove('recorded')
        resume()
        game.focus()
        setMode('human')
      },
      giveBack() { // HOLO, YOUR TURN
        st.human = false
        el.classList.remove('human')
        const live = st.recorded && o.mode !== 'live' && !st.gameReady ? 'recorded' : 'live'
        setMode(live)
        if (live === 'live') el.classList.add('live')
      },
      async unmute() { // one tap: the browser lets audio play
        st.audio = true
        for (const c of contexts.list) { try { await c.resume() } catch (e) { /* ignore */ } }
        emit('state', snapshot())
      },
      mute(on) { st.muted = on },
      get tape() { return st.tape },
      cid: CID,
    }
    return api
  }

  return { create, KEYS }
})()
