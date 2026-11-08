// Kid mode in the browser: Doom runs in this page (WebAssembly); every few seconds Pixel gets a
// small picture of the game canvas from the server (H Holo), says a line (ElevenLabs) and hears
// the child through an open mic (Gladia live).
'use strict'

const EVERY_MS = 1000
const MIN_GAP_MS = 10000 // between Pixel's own lines; an answer to the child does not wait
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

let blobOnly = false // after one refused stream, fetch every line whole: one synthesis per line

function say(text, t = {}) {
  return new Promise((resolve) => {
    stopVoice()
    const url = 'api/kid/say?text=' + encodeURIComponent(text)
    const t0 = performance.now()
    const a = new Audio()
    state.audio = a
    state.speaking = true
    $('face').classList.add('talking')
    const done = () => { if (state.audio === a) stopVoice(); resolve() }
    const fail = () => { status('voice unavailable'); done() }
    a.onplaying = () => { t.voice_ms = Math.round(performance.now() - t0); timing(t) }
    a.onended = done
    const asBlob = async () => { // some browsers refuse a chunked mp3 stream
      try {
        const r = await fetch(url)
        if (!r.ok) throw new Error('HTTP ' + r.status)
        const blob = await r.blob()
        if (state.audio !== a) return done()
        a.onerror = fail
        a.src = URL.createObjectURL(blob)
        await a.play()
      } catch (e) { fail() }
    }
    if (blobOnly) return asBlob()
    a.onerror = () => { if (state.audio !== a) return done(); blobOnly = true; asBlob() }
    a.src = url
    a.play().catch((e) => { if (e.name === 'NotAllowedError') fail() }) // a media error goes to onerror
  })
}

const DEBUG = new URLSearchParams(location.search).has('debug')
function timing(t) {
  console.log('pixel timing', JSON.stringify(t))
  if (DEBUG) $('timing').textContent = Object.entries(t).map(([k, v]) => k + ' ' + v).join(' · ')
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
    const t0 = performance.now()
    const image = shot()
    const t = { grab_ms: Math.round(performance.now() - t0) }
    const r = await fetch('api/kid/line', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image, recent: state.recent.slice(-8), chat: memory(), question, level: 'E1M1' }),
    })
    t.line_ms = Math.round(performance.now() - t0)
    if (r.status === 429) { status((await r.json()).detail || 'resting'); return }
    if (!r.ok) { status('Pixel cannot see right now'); return }
    const { text, vision_s, server_s, skipped } = await r.json()
    Object.assign(t, { vision_s, server_s }, skipped ? { skipped } : {})
    timing(t)
    if (question) state.chat.push('Child: ' + question)
    if (!text) { status('watching…'); return }
    state.recent.push(text)
    state.chat.push('You: ' + text)
    if (!question) state.lastOwn = Date.now()
    addChat('Pixel', text)
    status('talking')
    await say(text, t)
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
    if (!state.started || state.speaking || state.busy || childSpeaking()) return
    if (Date.now() - state.lastOwn < MIN_GAP_MS) return
    turn()
  }, EVERY_MS)
}

// ---------------------------------------------------------------- open mic (Gladia live)
// Like the laptop buddy: the mic is always on; the child talking cuts Pixel off (barge-in); what
// the mic hears of Pixel's own last lines through the speakers is ignored.

let muted = false
let mic = null
let ws = null
let voiceAt = 0 // last time the child was heard: Pixel does not start a line of its own then
const pending = []
const NEW = new Set(['left', 'right', 'ahead', 'behind', 'back', 'up', 'down', 'red', 'blue', 'yellow'])

function words(t) { return new Set(t.toLowerCase().match(/[a-z0-9']+/g) || []) }
function similar(a, b) { // share of the shorter line's words found in the other (commentator.similar)
  const wa = words(a), wb = words(b)
  if (!wa.size || !wb.size) return 0
  for (const w of [...wa, ...wb]) if (wa.has(w) !== wb.has(w) && (NEW.has(w) || /^\d+$/.test(w))) return 0
  let n = 0
  for (const w of wa) if (wb.has(w)) n++
  return n / Math.min(wa.size, wb.size)
}
function childSpeaking() { return Date.now() - voiceAt < 2000 }

function heard(text, final) {
  text = text.trim()
  const short = text.split(/\s+/).length < 2 && !(final && text.length > 2)
  if (short || state.recent.slice(-2).some((r) => similar(text, r) >= 0.6)) return // noise or echo
  voiceAt = Date.now()
  if (state.speaking) stopVoice()
  $('heard').textContent = final ? '“' + text + '”' : text + '…'
  if (!final) return
  addChat('You', text)
  pending.push(text)
  answer()
}

async function answer() {
  await waitIdle()
  if (!pending.length) return
  const q = pending.splice(0).join(' ')
  turn(q)
}

async function micStream(rate) {
  if (!mic) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
    const ctx = new AudioContext({ sampleRate: rate })
    const src = ctx.createMediaStreamSource(stream)
    const proc = ctx.createScriptProcessor(2048, 1, 1)
    proc.onaudioprocess = (e) => {
      if (muted || !ws || ws.readyState !== 1) return
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

async function openEars(tries = 0) {
  try {
    const r = await fetch('api/kid/listen', { method: 'POST' })
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'no ears')
    const { url, sample_rate } = await r.json()
    await micStream(sample_rate)
    const sock = new WebSocket(url)
    ws = sock
    sock.onopen = () => { tries = 0; micLabel() }
    sock.onmessage = (m) => {
      let msg
      try { msg = JSON.parse(m.data) } catch { return }
      if (msg.type !== 'transcript') return
      const text = ((msg.data || {}).utterance || {}).text || ''
      if (text.trim()) heard(text, !!msg.data.is_final)
    }
    sock.onclose = () => { if (ws === sock) { ws = null; setTimeout(() => openEars(tries + 1), 2500) } }
  } catch (e) {
    $('heard').textContent = 'mic unavailable: ' + e.message
    if (tries < 3 && !/denied|Permission|NotAllowed/i.test(e.message)) setTimeout(() => openEars(tries + 1), 3000)
  }
}

function micLabel() {
  const b = $('talk')
  b.textContent = muted ? 'Mic off: click to talk to Pixel' : 'Mic on: just talk to Pixel (click to mute)'
  b.classList.toggle('on', !muted)
}

function waitIdle() {
  return new Promise((res) => { const t = setInterval(() => { if (!state.busy) { clearInterval(t); res() } }, 100) })
}

const talkBtn = $('talk')
talkBtn.addEventListener('click', () => { muted = !muted; micLabel(); canvas.focus() })

// ---------------------------------------------------------------- start

$('go').addEventListener('click', async () => {
  $('start').style.display = 'none'
  talkBtn.disabled = false
  micLabel()
  openEars()
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
