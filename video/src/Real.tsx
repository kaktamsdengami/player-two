// Real-footage cut for the jury ("show the real product"): the desktop screen recording of the
// 02:26 UTC live run (player-two-live-0325.mkv, cut into public/v4/ by ffmpeg), the product's own
// narration audio, the live GitHub PR page, the kid-mode recording and the live site. Hard cuts,
// plain labels, no motion design. Clip prep: scripts/cut_real.sh.
import React from 'react'
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from 'remotion'
import {
  C, SANS, MONO, s, Voice, KID_INTRO, KID_SEGS, KID_LINES, kidSrc, type VO,
} from './PlayerTwo'
import r1 from './data/vo_r1.json'
import r2 from './data/vo_r2.json'
import r3 from './data/vo_r3.json'
import r4 from './data/vo_r4.json'
import r5 from './data/vo_r5.json'
import r6 from './data/vo_r6.json'
import r8 from './data/vo_r8.json'
import k7 from './data/vo_k7.json'

// [start, end] seconds of each shot
const SH = {
  run: [0, 23], pickup: [23, 38], verify: [38, 49.7], ask: [49.7, 70.7], pr: [70.7, 84], fixed: [84, 94.2],
  kid: [94.2, 115.6], end: [115.6, 128],
} as const
export const REAL_TOTAL = s(SH.end[1])

const Label: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ position: 'absolute', left: 40, top: 28, fontFamily: MONO, fontSize: 20, color: C.sub, letterSpacing: 1 }}>{children}</div>
)
const Shot: React.FC<{ at: readonly [number, number]; label: React.ReactNode; children: React.ReactNode }> = ({ at, label, children }) => (
  <Sequence from={s(at[0])} durationInFrames={s(at[1] - at[0])}>
    <AbsoluteFill style={{ background: C.bg }}>
      {children}
      <Label>{label}</Label>
    </AbsoluteFill>
  </Sequence>
)
const Clip: React.FC<{ file: string; w: number; h: number; top: number; freezeAfter?: number }> = ({ file, w, h, top, freezeAfter }) => {
  const v = <OffthreadVideo src={staticFile(`v4/${file}`)} muted style={{ width: w, height: h }} />
  return (
    <div style={{ position: 'absolute', top, left: (1920 - w) / 2, width: w, height: h, border: `1px solid ${C.line}` }}>
      {freezeAfter === undefined ? v : <>
        <Sequence durationInFrames={s(freezeAfter)} layout="none">{v}</Sequence>
        <Sequence from={s(freezeAfter)} layout="none"><Img src={staticFile(`v4/${file.replace('.mp4', '_end.png')}`)} style={{ width: w, height: h }} /></Sequence>
      </>}
    </div>
  )
}

// the product's own narration (voice/F1_narration.mp3), 02:38:32.66 UTC = 1.66 s into c4.mp4
const NARRATION: [number, number, string][] = [
  [0, 2.0, 'Look at this, in E3M1.'],
  [2.0, 5.6, 'Sky keeps its normal colours under invulnerability.'],
  [5.6, 11.6, 'It should be: the whole view, sky included, switches to the inverted grey invulnerability palette.'],
  [11.6, 13.6, 'Want me to fix it?'],
]
const Sub: React.FC<{ lines: [number, number, string][]; who?: string }> = ({ lines, who }) => {
  const t = useCurrentFrame() / 30
  const l = lines.find(([a, b]) => t >= a && t < b)
  if (!l) return null
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 34 }}>
      <div style={{ maxWidth: 1500, textAlign: 'center', fontFamily: SANS, fontWeight: 500, fontSize: 34, color: C.text, background: 'rgba(11,11,12,0.85)', padding: '10px 22px', borderRadius: 12 }}>
        {who && <span style={{ fontFamily: MONO, fontSize: 22, color: C.key, marginRight: 12 }}>{who}</span>}{l[2]}
      </div>
    </AbsoluteFill>
  )
}

const KidPlain: React.FC = () => {
  const t = useCurrentFrame() / 30
  const src = kidSrc(t)
  const line = src === null ? undefined : KID_LINES.find(([a, b]) => src >= a - 0.1 && src < b + 0.4)
  const H = 860, W = Math.round(H * 1316 / 1078)
  let at = s(KID_INTRO)
  return (
    <>
      <div style={{ position: 'absolute', top: 80, left: (1920 - W) / 2, width: W, height: H, border: `1px solid ${C.line}` }}>
        <Sequence durationInFrames={s(KID_INTRO)} layout="none">
          <OffthreadVideo src={staticFile('kid_team_boost.mp4')} startFrom={s(0.6)} endAt={s(0.6 + KID_INTRO)} muted style={{ width: W, height: H }} />
        </Sequence>
        {KID_SEGS.map(([a, b]) => { const from = at; at += s(b - a); return (
          <Sequence key={a} from={from} durationInFrames={s(b - a)} layout="none">
            <OffthreadVideo src={staticFile('kid_team_boost.mp4')} startFrom={s(a)} endAt={s(b)} style={{ width: W, height: H }} />
          </Sequence>
        ) })}
      </div>
      {line && (
        <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 34 }}>
          <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 34, color: C.text, background: 'rgba(11,11,12,0.85)', padding: '10px 22px', borderRadius: 12 }}>
            <span style={{ fontFamily: MONO, fontSize: 22, color: line[2] === 'Player' ? C.key : C.ok, marginRight: 12 }}>{line[2]}</span>{line[3]}
          </div>
        </AbsoluteFill>
      )}
    </>
  )
}

export const PlayerTwoReal: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg }}>
    <Shot at={SH.run} label="SCREEN RECORDING · live run, 8 Nov 2026, 02:26 UTC · 16× speed">
      <Clip file="c1.mp4" w={1920} h={740} top={90} />
    </Shot>
    <Shot at={SH.pickup} label="SCREEN RECORDING · the power-up · 2× speed">
      <Clip file="c2.mp4" w={1920} h={740} top={90} />
    </Shot>
    <Shot at={SH.verify} label="SCREEN RECORDING · verifier replays H's inputs · 10× speed">
      <Clip file="c3.mp4" w={1920} h={740} top={90} />
    </Shot>
    <Shot at={SH.ask} label="SCREEN RECORDING · the dashboard speaks the finding, the developer answers · real time">
      <Clip file="c4.mp4" w={882} h={900} top={80} />
      <Sequence from={s(1.66)} layout="none"><Audio src={staticFile('v4/narration.mp3')} /><Sub lines={NARRATION} who="PLAYER TWO" /></Sequence>
    </Shot>
    <Shot at={SH.pr} label="github.com/kaktamsdengami/chocolate-doom/pull/5 · opened and merged by Devin">
      <div style={{ position: 'absolute', top: 80, left: 160, width: 1600, height: 880, overflow: 'hidden', border: `1px solid ${C.line}` }}>
        <Img src={staticFile('v4/pr.png')} style={{ width: 1600 }} />
      </div>
    </Shot>
    <Shot at={SH.fixed} label="SCREEN RECORDING · proof replay on the rebuilt game · real time">
      <Clip file="c6.mp4" w={1100} h={862} top={80} freezeAfter={6.5} />
    </Shot>
    <Shot at={SH.kid} label="SCREEN RECORDING · Pixel, kid mode · H sees · Gladia hears · ElevenLabs speaks · pauses trimmed">
      <KidPlain />
    </Shot>
    <Shot at={SH.end} label="the live site">
      <div style={{ position: 'absolute', top: 80, left: 360, width: 1200, height: 750, overflow: 'hidden', border: `1px solid ${C.line}` }}>
        <Img src={staticFile('v4/live.png')} style={{ width: 1200 }} />
      </div>
      <div style={{ position: 'absolute', top: 870, width: 1920, textAlign: 'center', fontFamily: SANS, fontWeight: 600, fontSize: 52, color: C.text }}>player-two-doom.lovable.app</div>
      <div style={{ position: 'absolute', top: 945, width: 1920, textAlign: 'center', fontFamily: MONO, fontSize: 22, color: C.sub }}>PLAYER TWO · H · Devin · ElevenLabs · Gladia · Linkup · Stripe</div>
    </Shot>

    <Voice file="r1" vo={r1 as VO} at={s(SH.run[0] + 0.5)} />
    <Voice file="r2" vo={r2 as VO} at={s(SH.pickup[0] + 0.5)} />
    <Voice file="r3" vo={r3 as VO} at={s(SH.verify[0] + 0.5)} />
    <Voice file="r4" vo={r4 as VO} at={s(SH.ask[0] + 15.5)} />
    <Voice file="r5" vo={r5 as VO} at={s(SH.pr[0] + 0.5)} />
    <Voice file="r6" vo={r6 as VO} at={s(SH.fixed[0] + 0.5)} />
    <Voice file="k7" vo={k7 as VO} at={s(SH.kid[0] + 0.4)} />
    <Voice file="r8" vo={r8 as VO} at={s(SH.end[0] + 0.5)} />
  </AbsoluteFill>
)
