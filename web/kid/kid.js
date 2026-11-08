// Kid mode in the browser: Doom runs in this page (WebAssembly); every few seconds Pixel gets a
// small picture of the game canvas from the server (H Holo), says a line (ElevenLabs) and, while
// the child holds Talk, hears them (Gladia live).
'use strict'

const EVERY_MS = 3000
const MIN_GAP_MS = 12000 // between Pixel's own lines; an answer to the child does not wait
const SHOT_W = 480
const $ = (id) => document.getElementById(id)
const canvas = $('canvas')
const state = { recent: [], chat: [], speaking: false, busy: false, lastOwn: 0, audio: null, started: false }

// SDL draws with WebGL: keep the drawing buffer so the canvas can be read for Pixel's picture.
const getContext = HTMLCanvasElement.prototype.getContext
HTMLCanvasElement.prototype.getContext = function (type, attrs) {
  if (this === canvas && /webgl/.test(type)) attrs = Object.assign({}, attrs, { preserveDrawingBuffer: true })
  return getContext.call(this, type, attrs)
}

function status(text) { $('status').textContent = text }

function addChat(who, text) {
  const li = document.createElement('li')
  if (who === 'You') li.className = 'me'
  li.innerHTML = '<b></b><span></span>'
  li.querySelector('b').textContent = who
  li.querySelector('span').textContent = text.replace(/\s*\[[a-z ]+\]\s*/g, ' ').trim()
  $('chat').appendChild(li)
  li.scrollIntoView({ block: 'end' })
}

function stopVoice() {
  if (state.audio) { state.audio.pause(); state.audio.src = '' }
  state.audio = null
  state.speaking = false
  $('face').classList.remove('talking')
}

function say(text) {
  return new Promise((resolve) => {
    stopVoice()
    const a = new Audio('api/kid/say?text=' + encodeURIComponent(text))
    state.audio = a
    state.speaking = true
    $('face').classList.add('talking')
    const done = () => { if (state.audio === a) stopVoice(); resolve() }
    a.onended = done
    a.onerror = () => { status('voice unavailable'); done() }
    a.play().catch(done)
  })
}

function shot() {
  const c = document.createElement('canvas')
  c.width = SHOT_W
  c.height = Math.round((SHOT_W * canvas.height) / canvas.width) || 360
  c.getContext('2d').drawImage(canvas, 0, 0, c.width, c.height)
  return c.toDataURL('image/jpeg', 0.75)
}

async function turn(question = '') {
  if (state.busy) return
  state.busy = true
  try {
    status(question ? 'thinking about what you said…' : 'watching…')
    const r = await fetch('api/kid/line', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: shot(), recent: state.recent.slice(-8), chat: memory(), question, level: 'E1M1' }),
    })
    if (r.status === 429) { status((await r.json()).detail || 'resting'); return }
    if (!r.ok) { status('Pixel cannot see right now'); return }
    const { text } = await r.json()
    if (question) state.chat.push('Child: ' + question)
    if (!text) { status('watching…'); return }
    state.recent.push(text)
    state.chat.push('You: ' + text)
    if (!question) state.lastOwn = Date.now()
    addChat('Pixel', text)
    status('talking')
    await say(text)
    status('watching…')
  } catch (e) {
    status('connection problem')
  } finally {
    state.busy = false
  }
}

function memory() { // the start of the talk (names) plus the last 60 lines
  const c = state.chat
  return c.length <= 66 ? c : [...c.slice(0, 6), '...', ...c.slice(-60)]
}

function loop() {
  setInterval(() => {
    if (!state.started || state.speaking || state.busy || talking) return
    if (Date.now() - state.lastOwn < MIN_GAP_MS) return
    turn()
  }, EVERY_MS)
}

// ---------------------------------------------------------------- push to talk (Gladia live)

let talking = false
let mic = null
let ws = null
let setup = null // talkStart's pending setup: a quick release waits for it
let finals = []
let partial = ''

async function micStream(rate) {
  if (!mic) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    const ctx = new AudioContext({ sampleRate: rate })
    const src = ctx.createMediaStreamSource(stream)
    const proc = ctx.createScriptProcessor(2048, 1, 1)
    proc.onaudioprocess = (e) => {
      if (!talking || !ws || ws.readyState !== 1) return
      const f = e.inputBuffer.getChannelData(0)
      const pcm = new Int16Array(f.length)
      for (let i = 0; i < f.length; i++) pcm[i] = Math.max(-1, Math.min(1, f[i])) * 0x7fff
      ws.send(pcm.buffer)
    }
    src.connect(proc)
    proc.connect(ctx.destination)
    mic = { ctx }
  }
  if (mic.ctx.state === 'suspended') await mic.ctx.resume()
}

function talkStart() {
  if (talking || !state.started) return
  talking = true
  setup = openEars()
}

async function openEars() {
  stopVoice()
  finals = []
  partial = ''
  $('talk').classList.add('on')
  $('heard').textContent = 'listening…'
  try {
    const r = await fetch('api/kid/listen', { method: 'POST' })
    if (!r.ok) throw new Error((await r.json()).detail || 'no ears')
    const { url, sample_rate } = await r.json()
    await micStream(sample_rate)
    ws = new WebSocket(url)
    ws.onmessage = (m) => {
      let msg
      try { msg = JSON.parse(m.data) } catch { return }
      if (msg.type !== 'transcript') return
      const text = ((msg.data || {}).utterance || {}).text || ''
      if (!text.trim()) return
      if (msg.data.is_final) { finals.push(text.trim()); partial = '' } else partial = text.trim()
      $('heard').textContent = [...finals, partial].join(' ')
    }
  } catch (e) {
    $('heard').textContent = 'mic unavailable: ' + e.message
    talking = false
    $('talk').classList.remove('on')
  }
}

async function talkEnd() {
  if (!talking) return
  talking = false
  $('talk').classList.remove('on')
  await setup
  const sock = ws
  ws = null
  if (sock) {
    if (sock.readyState === 0) await new Promise((res) => { sock.onopen = res; setTimeout(res, 2000) })
    const closed = new Promise((res) => { sock.onclose = res; setTimeout(res, 2500) })
    if (sock.readyState === 1) sock.send(JSON.stringify({ type: 'stop_recording' }))
    await closed
    try { sock.close() } catch { /* already closed */ }
  }
  const q = [...finals, partial].join(' ').trim()
  $('heard').textContent = q ? '“' + q + '”' : 'did not catch that'
  if (q) { addChat('You', q); await waitIdle(); turn(q) }
}

function waitIdle() {
  return new Promise((res) => { const t = setInterval(() => { if (!state.busy) { clearInterval(t); res() } }, 100) })
}

const talkBtn = $('talk')
talkBtn.addEventListener('pointerdown', (e) => { e.preventDefault(); talkStart() })
window.addEventListener('pointerup', () => { talkEnd(); canvas.focus() })
window.addEventListener('keydown', (e) => { if (e.key === 't' && !e.repeat) talkStart() }, true)
window.addEventListener('keyup', (e) => { if (e.key === 't') talkEnd() }, true)

// ---------------------------------------------------------------- start

$('go').addEventListener('click', async () => {
  $('start').style.display = 'none'
  talkBtn.disabled = false
  canvas.focus()
  window.Module = {
    noInitialRun: true,
    canvas,
    preRun: () => {
      Module.FS.createPreloadedFile('', 'doom1.wad', 'doom1.wad', true, true)
      Module.FS.createPreloadedFile('', 'default.cfg', 'default.cfg', true, true)
    },
    onRuntimeInitialized: () => {
      callMain(['-iwad', 'doom1.wad', '-window', '-nogui', '-nomusic', '-config', 'default.cfg', '-skill', '2', '-warp', '1', '1'])
      state.started = true
      canvas.focus()
      fetch('api/kid/hello').then((r) => r.json()).then(({ hello }) => {
        addChat('Pixel', hello)
        state.recent.push(hello)
        state.chat.push('You: ' + hello)
        state.lastOwn = Date.now()
        say(hello)
      }).catch(() => status('Pixel is offline: you can still play'))
      loop()
    },
    print: (t) => console.log(t),
    printErr: (t) => console.warn(t),
    setStatus: (t) => t && status(t),
  }
  status('loading Doom…')
  const s = document.createElement('script')
  s.src = 'websockets-doom.js'
  document.body.appendChild(s)
})
canvas.addEventListener('click', () => canvas.focus())
