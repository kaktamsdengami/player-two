import React from 'react'
import {
  AbsoluteFill, Audio, Freeze, Img, OffthreadVideo, Sequence, interpolate, spring,
  staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion'
import { loadFont as loadSans } from '@remotion/google-fonts/InstrumentSans'
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono'
import keys from './data/keys.json'
import vo1 from './data/vo_s1.json'
import vo2 from './data/vo_s2.json'
import vo3 from './data/vo_s3.json'
import vo4 from './data/vo_s4.json'
import vo5 from './data/vo_s5.json'
import vo6 from './data/vo_s6.json'
import vo7 from './data/vo_s7.json'
import vo8 from './data/vo_s8.json'

const { fontFamily: SANS } = loadSans('normal', { weights: ['500', '600'] })
const { fontFamily: MONO } = loadMono('normal', { weights: ['400', '500'] })

const C = {
  bg: '#0B0B0C', text: '#F5F5F7', sub: '#8E8E93', key: '#FFD84D', ok: '#30D158',
  line: '#2C2C2E', card: '#151517', red: '#FF453A',
}
const FPS = 30
const s = (sec: number) => Math.round(sec * FPS)

// ---------- scene plan (frames) ----------
const SC = {
  open: [0, s(11)], run: [s(11), s(40)], pickup: [s(40), s(60)], verify: [s(60), s(80)],
  devin: [s(80), s(110)], fixed: [s(110), s(125)], kid: [s(125), s(142)], end: [s(142), s(150)],
} as const
export const TOTAL = s(150)
const XF = 12 // crossfade frames between scenes

// ---------- helpers ----------
const ease = (f: number, fps: number, delay = 0) =>
  spring({ frame: f - delay, fps, config: { damping: 200 } })

const FadeIn: React.FC<{ delay?: number; children: React.ReactNode; style?: React.CSSProperties; rise?: number }> = ({ delay = 0, children, style, rise = 0 }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig()
  const p = ease(f, fps, delay)
  return (
    <div style={{ opacity: p, transform: `translateY(${(1 - p) * rise}px) scale(${0.95 + 0.05 * p})`, ...style }}>
      {children}
    </div>
  )
}

const Scene: React.FC<{ range: readonly [number, number]; children: React.ReactNode }> = ({ range, children }) => {
  const [a, b] = range
  const from = Math.max(0, a - XF)
  const dur = b - from + (b >= TOTAL ? 0 : XF)
  return (
    <Sequence from={from} durationInFrames={dur}>
      <SceneFade dur={dur} first={a === 0} last={b >= TOTAL}>{children}</SceneFade>
    </Sequence>
  )
}
const SceneFade: React.FC<{ dur: number; first: boolean; last: boolean; children: React.ReactNode }> = ({ dur, first, last, children }) => {
  const f = useCurrentFrame()
  const inO = first ? interpolate(f, [0, 20], [0, 1], { extrapolateRight: 'clamp' }) : interpolate(f, [0, XF * 2], [0, 1], { extrapolateRight: 'clamp' })
  const outO = last ? interpolate(f, [dur - 25, dur], [1, 0], { extrapolateLeft: 'clamp' }) : interpolate(f, [dur - XF * 2, dur], [1, 0], { extrapolateLeft: 'clamp' })
  return <AbsoluteFill style={{ opacity: Math.min(inO, outO) }}>{children}</AbsoluteFill>
}

const Frame: React.FC<{ w: number; h: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ w, h, children, style }) => (
  <div style={{ width: w, height: h, borderRadius: 16, overflow: 'hidden', border: `1.5px solid ${C.line}`, background: '#000', ...style }}>{children}</div>
)

const Pill: React.FC<{ children: React.ReactNode; color?: string; style?: React.CSSProperties }> = ({ children, color = C.sub, style }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, padding: '7px 16px', borderRadius: 999, border: `1.5px solid ${C.line}`, color, fontFamily: MONO, fontSize: 18, letterSpacing: 1, ...style }}>{children}</div>
)

const Stamp: React.FC<{ label: string; delay: number }> = ({ label, delay }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig()
  const p = ease(f, fps, delay)
  return (
    <div style={{ opacity: p, transform: `scale(${1.06 - 0.06 * p})`, display: 'inline-flex', alignItems: 'center', gap: 14, padding: '14px 28px', borderRadius: 14, border: `2px solid ${C.ok}`, color: C.ok, fontFamily: SANS, fontWeight: 600, fontSize: 44, letterSpacing: 2, background: 'rgba(48,209,88,0.08)' }}>
      <span style={{ width: 16, height: 16, borderRadius: 8, background: C.ok, display: 'inline-block' }} />{label}
    </div>
  )
}

// ---------- captions from ElevenLabs alignment ----------
type VO = { text: string; chars: string[]; start: number[]; end: number[] }
type Phrase = { text: string; start: number; end: number }
const phrases = (vo: VO): Phrase[] => {
  const out: Phrase[] = []; let buf = ''; let st = -1
  vo.chars.forEach((ch, i) => {
    if (st < 0 && ch.trim()) st = vo.start[i]
    buf += ch
    const words = buf.trim().split(/\s+/).length
    const brk = /[.?!:]/.test(ch) || (ch === ',' && words >= 5) || (ch === ' ' && words >= 11)
    if (brk || i === vo.chars.length - 1) {
      if (buf.trim()) out.push({ text: buf.trim(), start: st, end: vo.end[i] })
      buf = ''; st = -1
    }
  })
  return out
}
const Voice: React.FC<{ file: string; vo: VO; at: number }> = ({ file, vo, at }) => {
  const ph = phrases(vo)
  const len = s(vo.end[vo.end.length - 1] + 0.6)
  return (
    <Sequence from={at} durationInFrames={len}>
      <Audio src={staticFile(`vo/${file}.mp3`)} />
      <Caption ph={ph} />
    </Sequence>
  )
}
const Caption: React.FC<{ ph: Phrase[] }> = ({ ph }) => {
  const f = useCurrentFrame(); const t = f / FPS
  const cur = ph.find((p, i) => t >= p.start - 0.05 && t < (ph[i + 1]?.start ?? p.end + 0.5))
  if (!cur) return null
  const o = interpolate(t, [cur.start - 0.05, cur.start + 0.15], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 34, pointerEvents: 'none' }}>
      <div style={{ opacity: o, maxWidth: 1400, textAlign: 'center', fontFamily: SANS, fontWeight: 500, fontSize: 34, color: C.text, background: 'rgba(11,11,12,0.82)', padding: '10px 22px', borderRadius: 12 }}>{cur.text}</div>
    </AbsoluteFill>
  )
}

// ---------- key badges from the real demo (agent.lmp) ----------
type Seg = { start: number; end: number; keys: string }
const SEGS = (keys as { segs: Seg[] }).segs
const KEYMAP: Record<string, string> = { UP: '↑', DOWN: '↓', LEFT: '←', RIGHT: '→', FIRE: 'FIRE', USE: 'USE', 'STRAFE': 'STRAFE' }
const keyAt = (srcSec: number): string[] => {
  const tic = Math.round((srcSec + 0.25) * 35)
  const seg = SEGS.find((g) => g.start <= tic && tic < g.end)
  if (!seg) return []
  const t = seg.keys.split(' ')
  const out: string[] = []
  for (let i = 0; i < t.length; i++) {
    if (t[i] === 'STRAFE') { out.push(`STRAFE ${t[i + 1] === 'L' ? '←' : '→'}`); i++ } else out.push(KEYMAP[t[i]] ?? t[i])
  }
  return out
}
const KeyBadges: React.FC<{ src: number }> = ({ src }) => {
  const k = keyAt(src)
  return (
    <div style={{ position: 'absolute', left: 24, bottom: 24, display: 'flex', gap: 12 }}>
      {k.map((x) => (
        <div key={x} style={{ minWidth: 64, height: 64, padding: '0 16px', borderRadius: 12, background: C.key, color: '#0B0B0C', fontFamily: MONO, fontWeight: 500, fontSize: x.length > 1 ? 24 : 34, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 0 #B89A2E' }}>{x}</div>
      ))}
    </div>
  )
}

// game video clip with live key badges (src seconds in agent_replay.mp4)
const RunClip: React.FC<{ from: number; to: number; w: number; h: number; badges?: boolean }> = ({ from, to, w, h, badges = true }) => {
  const f = useCurrentFrame()
  const src = from + f / FPS
  return (
    <div style={{ position: 'relative', width: w, height: h }}>
      <OffthreadVideo src={staticFile('agent_replay.mp4')} startFrom={s(from)} endAt={s(to)} muted style={{ width: w, height: h, objectFit: 'cover' }} />
      {badges && <KeyBadges src={src} />}
    </div>
  )
}

// ---------- scenes ----------
const Title: React.FC<{ children: React.ReactNode; size?: number; style?: React.CSSProperties }> = ({ children, size = 64, style }) => (
  <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: size, color: C.text, letterSpacing: -1.5, lineHeight: 1.08, ...style }}>{children}</div>
)
const Sub: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 26, color: C.sub, ...style }}>{children}</div>
)
const Mono: React.FC<{ children: React.ReactNode; color?: string; size?: number; style?: React.CSSProperties }> = ({ children, color = C.sub, size = 22, style }) => (
  <div style={{ fontFamily: MONO, fontSize: size, color, lineHeight: 1.5, ...style }}>{children}</div>
)

const BeforeAfter: React.FC<{ w: number; delay?: number }> = ({ w, delay = 0 }) => {
  const h = Math.round(w * 0.75)
  return (
    <div style={{ display: 'flex', gap: 28 }}>
      {[['sky_before.png', 'BEFORE · the sky stays red', C.red], ['sky_after.png', "AFTER DEVIN'S FIX · the sky inverts too", C.ok]].map(([f, l, col], i) => (
        <FadeIn key={f} delay={delay + i * 8}>
          <Frame w={w} h={h}><Img src={staticFile(f)} style={{ width: w, height: h }} /></Frame>
          <Mono color={col} size={20} style={{ marginTop: 14 }}>{l}</Mono>
        </FadeIn>
      ))}
    </div>
  )
}

const SceneOpen: React.FC = () => (
  <AbsoluteFill style={{ padding: '96px 120px', alignItems: 'center' }}>
    <FadeIn delay={4}><Title size={58} style={{ textAlign: 'center', marginBottom: 12 }}>An AI found a 1993 Doom bug. Devin fixed it. A replay proved it.</Title></FadeIn>
    <FadeIn delay={14}><Sub style={{ textAlign: 'center', marginBottom: 36 }}>Same frame, same power-up: Freedoom E3M1 in Chocolate Doom</Sub></FadeIn>
    <BeforeAfter w={700} delay={20} />
  </AbsoluteFill>
)

const H_LINES_RUN = [
  ['02:26:32', 'I can see the Doom game with the green invulnerability sphere visible ahead in the canyon. Let me walk toward it.'],
  ['02:30:41', "There's a large monster right in the center of the screen! According to the instructions, I should shoot it by holding Ctrl without moving."],
  ['02:30:55', 'The monster is dead. Now I need to find the green sphere.'],
  ['02:33:16', 'I can see the green sphere right in front of me! Let me walk straight to it to pick it up.'],
]
const HLines: React.FC<{ lines: string[][]; every: number; first?: number }> = ({ lines, every, first = 20 }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
    {lines.map(([t, l], i) => (
      <FadeIn key={t} delay={first + i * every} rise={12}>
        <Mono size={17} color={C.sub}>H · {t} UTC</Mono>
        <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 25, color: C.text, lineHeight: 1.35 }}>“{l}”</div>
      </FadeIn>
    ))}
  </div>
)

const RUN_SEGS: [number, number][] = [[0, 6], [7, 14], [44, 53], [76, 83]]
const SceneRun: React.FC = () => {
  const W = 1170, H = Math.round(W * 800 / 1066)
  let at = 0
  return (
    <AbsoluteFill style={{ padding: '70px 64px', flexDirection: 'row', gap: 44 }}>
      <div>
        <FadeIn><Frame w={W} h={H}>
          {RUN_SEGS.map(([a, b]) => { const from = at; at += s(b - a); return (
            <Sequence key={a} from={from} durationInFrames={s(b - a)} layout="none"><RunClip from={a} to={b} w={W} h={H} /></Sequence>
          ) })}
        </Frame></FadeIn>
        <div style={{ display: 'flex', gap: 14, marginTop: 16 }}>
          <Pill>game time, agent thinking cut</Pill><Pill color={C.key}>keys from the run's own demo file</Pill>
        </div>
      </div>
      <div style={{ width: 560, paddingTop: 8 }}>
        <FadeIn><Title size={40}>H plays from pixels only</Title></FadeIn>
        <FadeIn delay={8}><Mono style={{ margin: '10px 0 30px' }}>desktop agent · holo4-35b-a3b<br />keyboard only · no game state · no logs</Mono></FadeIn>
        <HLines lines={H_LINES_RUN} every={s(6)} first={s(2)} />
      </div>
    </AbsoluteFill>
  )
}

const FINDING = {
  title: 'Sky not inverted during invulnerability power-up',
  steps: [
    'Walked to the green invulnerability sphere in the canyon and picked it up',
    "Screen turned white/inverted and 'VANGUARD OF THE GODS!' message appeared",
    'Turned to look at the sky area - the sky remains RED while walls and floor are white/grey (inverted)',
  ],
  actual: 'The sky remains its normal red color while the walls and floor are correctly inverted to white/grey.',
}
const Typed: React.FC<{ text: string; start: number; cps?: number; style?: React.CSSProperties }> = ({ text, start, cps = 55, style }) => {
  const f = useCurrentFrame()
  const n = Math.max(0, Math.floor(((f - start) / FPS) * cps))
  return <span style={style}>{text.slice(0, n)}</span>
}
const ScenePickup: React.FC = () => {
  const W = 1110, H = Math.round(W * 800 / 1066)
  const play = s(90.4 - 83.5)
  return (
    <AbsoluteFill style={{ padding: '70px 64px', flexDirection: 'row', gap: 44 }}>
      <div>
        <Frame w={W} h={H}>
          <Sequence durationInFrames={play} layout="none"><RunClip from={83.5} to={90.4} w={W} h={H} /></Sequence>
          <Sequence from={play} layout="none"><Freeze frame={play - 1}><RunClip from={83.5} to={90.4} w={W} h={H} badges={false} /></Freeze></Sequence>
        </Frame>
        <FadeIn delay={play}><Mono color={C.text} size={22} style={{ marginTop: 16 }}>“Vanguard of the gods!” · the world inverts · the sky stays red</Mono></FadeIn>
      </div>
      <div style={{ width: 620, paddingTop: 6 }}>
        <FadeIn delay={s(2.5)}><HLines lines={[["02:34:14", 'I can clearly see the bug! The sky is still RED while the walls and floor are white/grey (inverted).']]} every={1} first={0} /></FadeIn>
        <FadeIn delay={s(5)} style={{ marginTop: 30 }}>
          <div style={{ background: C.card, border: `1.5px solid ${C.line}`, borderRadius: 16, padding: 26 }}>
            <Mono color={C.key} size={19}>H called report_finding(…)</Mono>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 28, color: C.text, margin: '10px 0 14px' }}><Typed text={FINDING.title} start={s(5.5)} /></div>
            <Mono size={17} color={C.sub}>steps</Mono>
            {FINDING.steps.map((t, i) => (
              <div key={i} style={{ fontFamily: SANS, fontSize: 19, color: C.text, lineHeight: 1.35, marginBottom: 6 }}>{i + 1}. <Typed text={t} start={s(6.6 + i * 1.7)} cps={75} /></div>
            ))}
            <Mono size={17} color={C.sub} style={{ marginTop: 8 }}>actual</Mono>
            <div style={{ fontFamily: SANS, fontSize: 19, color: C.text, lineHeight: 1.35 }}><Typed text={FINDING.actual} start={s(12)} cps={75} /></div>
          </div>
        </FadeIn>
      </div>
    </AbsoluteFill>
  )
}

const SceneVerify: React.FC = () => {
  const W = 1110, H = Math.round(W * 800 / 1066)
  const clip = s(10)
  return (
    <AbsoluteFill style={{ padding: '70px 64px', flexDirection: 'row', gap: 44 }}>
      <div style={{ position: 'relative' }}>
        <Frame w={W} h={H}>
          <Sequence durationInFrames={clip} layout="none"><OffthreadVideo src={staticFile('bug_clip.mp4')} muted style={{ width: W, height: H }} /></Sequence>
          <Sequence from={clip} layout="none"><Freeze frame={clip - 1}><OffthreadVideo src={staticFile('bug_clip.mp4')} muted style={{ width: W, height: H }} /></Freeze></Sequence>
        </Frame>
        <div style={{ position: 'absolute', right: 26, top: 26 }}><Stamp label="VERIFIED" delay={s(7.8)} /></div>
        <Pill style={{ marginTop: 16 }}>verifier replay of H's own inputs · clip cut by the product</Pill>
      </div>
      <div style={{ width: 620, paddingTop: 6, display: 'flex', flexDirection: 'column', gap: 26 }}>
        <FadeIn><Title size={40}>We don't take its word for it</Title></FadeIn>
        <FadeIn delay={s(1.2)}><Mono color={C.text}>replayed H's exact inputs<br />tic for tic (agent.lmp)</Mono></FadeIn>
        <FadeIn delay={s(2.6)}><Mono color={C.text}>replay sync: 31 / 31 player<br />positions identical</Mono></FadeIn>
        <FadeIn delay={s(4)}><Mono color={C.text}>hidden engine log, never shown to H:<br /><span style={{ color: C.key }}>powerup power=0</span><br /><span style={{ color: C.key }}>render sky_ignores_colormap fixedcolormap=32</span></Mono></FadeIn>
        <FadeIn delay={s(7.8)}><Mono color={C.ok}>verdict: verified · known bug KB3</Mono></FadeIn>
      </div>
    </AbsoluteFill>
  )
}

const DIFF: [string, string][] = [
  [' ', '    // Sky is allways drawn full bright,'],
  ['-', '    //  i.e. colormaps[0] is used.'],
  ['-', '    // Because of this hack, sky is not affected'],
  ['-', '    //  by INVUL inverse mapping.'],
  ['-', '    dc_colormap = colormaps;'],
  ['+', '    //  i.e. colormaps[0] is used, unless a fixed'],
  ['+', '    //  colormap (INVUL inverse mapping) is active.'],
  ['+', '    if (fixedcolormap)'],
  ['+', '        dc_colormap = fixedcolormap;'],
  ['+', '    else'],
  ['+', '    {'],
  ['+', '        dc_colormap = colormaps;'],
  ['+', '        QA_SkyDrawn(viewplayer->fixedcolormap);'],
  ['+', '    }'],
]
const SceneDevin: React.FC = () => {
  const f = useCurrentFrame()
  const A = s(6), B = s(14), Cc = s(20), D = s(28.5)
  const zoom = interpolate(f, [Cc, D], [1, 1.05], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <AbsoluteFill style={{ padding: '80px 120px', alignItems: 'center', justifyContent: 'center' }}>
      <Sequence durationInFrames={A + XF} layout="none">
        <SubFade dur={A + XF}>
          <Title size={40} style={{ marginBottom: 18 }}>The developer answers by voice</Title>
          <Frame w={1176} h={483} style={{ background: C.card }}><Img src={staticFile('dash_voice.png')} style={{ width: 1176, height: 483 }} /></Frame>
          <Mono style={{ marginTop: 14 }}>our dashboard · ElevenLabs speaks the finding · Gladia hears “fix it” → intent: fix (voice)</Mono>
        </SubFade>
      </Sequence>
      <Sequence from={A} durationInFrames={B - A + XF} layout="none">
        <SubFade dur={B - A + XF}>
          <Mono color={C.key} size={22}>POST /v3/organizations/…/sessions · Devin API</Mono>
          <div style={{ marginTop: 18, width: 1180, background: C.card, border: `1.5px solid ${C.line}`, borderRadius: 18, padding: 40 }}>
            <Mono size={20}>Devin session · created by our backend · origin: api</Mono>
            <Title size={44} style={{ margin: '12px 0 22px' }}>PLAYER TWO fix: Sky not inverted during invulnerability power-up</Title>
            <Mono color={C.text} size={22}>category: bug_fixing · tags: player-two, finding:F1</Mono>
            <Mono color={C.ok} size={22} style={{ marginTop: 10 }}>pull request: kaktamsdengami/chocolate-doom#5 · merged</Mono>
            <Mono size={20} style={{ marginTop: 10 }}>app.devin.ai/sessions/e8c90a86df22497b8585fd3e541d1435</Mono>
          </div>
        </SubFade>
      </Sequence>
      <Sequence from={B} durationInFrames={Cc - B + XF} layout="none">
        <SubFade dur={Cc - B + XF}>
          <Frame w={960} h={798} style={{ background: '#fff' }}><Img src={staticFile('pr_header.jpg')} style={{ width: 960, height: 798 }} /></Frame>
          <Mono style={{ marginTop: 14 }}>github.com/kaktamsdengami/chocolate-doom/pull/5 · opened and merged by devin-ai-integration</Mono>
        </SubFade>
      </Sequence>
      <Sequence from={Cc} durationInFrames={D - Cc + XF} layout="none">
        <SubFade dur={D - Cc + XF}>
          <div style={{ transform: `scale(${zoom})` }}>
            <Mono color={C.text} size={24} style={{ marginBottom: 14 }}>src/doom/r_plane.c · R_DrawPlanes() · <span style={{ color: C.ok }}>+9</span> <span style={{ color: C.red }}>−5</span></Mono>
            <div style={{ width: 1180, background: C.card, border: `1.5px solid ${C.line}`, borderRadius: 16, padding: '22px 0' }}>
              {DIFF.map(([k, l], i) => (
                <div key={i} style={{ fontFamily: MONO, fontSize: 25, whiteSpace: 'pre', padding: '2px 28px', color: k === '+' ? C.ok : k === '-' ? C.red : C.sub, background: k === '+' ? 'rgba(48,209,88,0.08)' : k === '-' ? 'rgba(255,69,58,0.08)' : 'transparent' }}>{k} {l}</div>
              ))}
            </div>
            <Mono style={{ marginTop: 14 }}>the 1993 comment says it: “Because of this hack, sky is not affected by INVUL inverse mapping.”</Mono>
          </div>
        </SubFade>
      </Sequence>
      <Sequence from={D} layout="none">
        <SubFade dur={s(30) - D}>
          <div style={{ display: 'flex', gap: 22 }}><Pill color={C.ok} style={{ fontSize: 30, padding: '14px 30px' }}>merged</Pill><Pill color={C.text} style={{ fontSize: 30, padding: '14px 30px' }}>rebuilding · CI Windows build</Pill></div>
        </SubFade>
      </Sequence>
    </AbsoluteFill>
  )
}
const SubFade: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig()
  const p = ease(f, fps)
  const out = interpolate(f, [dur - XF, dur], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: Math.min(p, out), transform: `scale(${0.96 + 0.04 * p})` }}>{children}</AbsoluteFill>
}

const SceneFixed: React.FC = () => {
  const W = 1180, H = Math.round(W * 800 / 1066)
  const clip = s(7.76)
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <Sequence durationInFrames={clip + s(1.5)} layout="none">
        <SubFade dur={clip + s(1.5)}>
          <div style={{ position: 'relative' }}>
            <Frame w={W} h={H}>
              <Sequence durationInFrames={clip} layout="none"><OffthreadVideo src={staticFile('after_fix.mp4')} muted style={{ width: W, height: H }} /></Sequence>
              <Sequence from={clip} layout="none"><Freeze frame={clip - 1}><OffthreadVideo src={staticFile('after_fix.mp4')} muted style={{ width: W, height: H }} /></Freeze></Sequence>
            </Frame>
            <div style={{ position: 'absolute', right: 26, top: 26 }}><Stamp label="FIXED" delay={s(3)} /></div>
          </div>
          <Mono style={{ marginTop: 16 }}>proof replay on the rebuilt game · same power-up · 0 sky_ignores_colormap events</Mono>
        </SubFade>
      </Sequence>
      <Sequence from={clip + s(1.5)} layout="none">
        <SubFade dur={s(15) - clip - s(1.5)}><BeforeAfter w={760} /></SubFade>
      </Sequence>
    </AbsoluteFill>
  )
}

const KID_W = 1080, KID_H = Math.round(1080 * 1078 / 1316)
const SceneKid: React.FC = () => (
  <AbsoluteFill style={{ padding: '60px 64px', flexDirection: 'row', gap: 44, alignItems: 'flex-start' }}>
    <FadeIn>
      <Frame w={KID_W} h={KID_H}>
        <OffthreadVideo src={staticFile('kid_team.mp4')} startFrom={s(20)} endAt={s(37.5)}
          volume={(f) => interpolate(f, [s(7.8), s(8.6)], [0.18, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })}
          style={{ width: KID_W, height: KID_H }} />
      </Frame>
      <Pill style={{ marginTop: 14 }}>recorded on our laptop · a person playing and talking to Pixel</Pill>
    </FadeIn>
    <div style={{ width: 640 }}>
      <FadeIn delay={8}><Title size={48}>Pixel</Title></FadeIn>
      <FadeIn delay={16}><Sub style={{ marginTop: 8 }}>a game buddy that watches the screen with H's eyes and talks back</Sub></FadeIn>
      <FadeIn delay={30}><Mono style={{ marginTop: 26 }}>Doom in the browser<br />H vision · ElevenLabs voice · Gladia ears</Mono></FadeIn>
    </div>
  </AbsoluteFill>
)

const Stat: React.FC<{ v: string; l: string; delay: number }> = ({ v, l, delay }) => (
  <FadeIn delay={delay}>
    <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 56, color: C.text, letterSpacing: -1.5 }}>{v}</div>
    <Mono size={19}>{l}</Mono>
  </FadeIn>
)
const SceneEnd: React.FC = () => (
  <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
    <FadeIn><Title size={110} style={{ letterSpacing: -4 }}>PLAYER TWO</Title></FadeIn>
    <FadeIn delay={6}><Sub style={{ textAlign: 'center', marginTop: 6 }}>Your game's toughest tester.</Sub></FadeIn>
    <div style={{ display: 'flex', gap: 80, marginTop: 52 }}>
      <Stat v="2 min 28 s" l="from start to the bug report" delay={14} />
      <Stat v="7 min 18 s" l="from “fix” to the proof replay" delay={20} />
      <Stat v="19 / 19" l="pull requests written by Devin" delay={26} />
    </div>
    <FadeIn delay={34}><Mono style={{ marginTop: 46, textAlign: 'center' }}>H · Devin · ElevenLabs · Gladia · Linkup · Stripe</Mono></FadeIn>
    <FadeIn delay={40}><Mono color={C.text} style={{ marginTop: 10 }}>player-two-doom.lovable.app</Mono></FadeIn>
  </AbsoluteFill>
)

export const PlayerTwo: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg }}>
    <Scene range={SC.open}><SceneOpen /></Scene>
    <Scene range={SC.run}><SceneRun /></Scene>
    <Scene range={SC.pickup}><ScenePickup /></Scene>
    <Scene range={SC.verify}><SceneVerify /></Scene>
    <Scene range={SC.devin}><SceneDevin /></Scene>
    <Scene range={SC.fixed}><SceneFixed /></Scene>
    <Scene range={SC.kid}><SceneKid /></Scene>
    <Scene range={SC.end}><SceneEnd /></Scene>

    <Voice file="s1" vo={vo1 as VO} at={s(0.5)} />
    <Voice file="s2" vo={vo2 as VO} at={SC.run[0] + s(0.8)} />
    <Voice file="s3" vo={vo3 as VO} at={SC.pickup[0] + s(1.5)} />
    <Voice file="s4" vo={vo4 as VO} at={SC.verify[0] + s(0.8)} />
    <Voice file="s5" vo={vo5 as VO} at={SC.devin[0] + s(0.8)} />
    <Voice file="s6" vo={vo6 as VO} at={SC.fixed[0] + s(1.5)} />
    <Voice file="s7" vo={vo7 as VO} at={SC.kid[0] + s(0.8)} />
    <Voice file="s8" vo={vo8 as VO} at={SC.end[0] + s(0.6)} />

    <div style={{ position: 'absolute', left: 32, top: 26 }}>
      <Pill color={C.text} style={{ fontSize: 16, padding: '5px 14px', background: 'rgba(11,11,12,0.7)' }}>
        <span style={{ width: 8, height: 8, borderRadius: 4, background: C.red, display: 'inline-block' }} />RECORDED
      </Pill>
    </div>
  </AbsoluteFill>
)
