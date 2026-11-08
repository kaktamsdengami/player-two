// Pitch cut: the same real run as PlayerTwo (shortened, no kid mode), then the numbers, then the vision.
// The vision part is labelled VISION on screen: it is not a measured result.
import React from 'react'
import { AbsoluteFill, Sequence } from 'remotion'
import {
  C, SANS, MONO, s, FadeIn, Pill, Title, Sub, Mono, Stat, Voice, Scene, SceneOpen, SceneRun, ScenePickup,
  SceneVerify, SceneDevin, SceneFixed, DEVIN_VO, type VO,
} from './PlayerTwo'
import vo2 from './data/vo_s2.json'
import vo3 from './data/vo_s3.json'
import vo4 from './data/vo_s4.json'
import vo5 from './data/vo_s5.json'
import vo6 from './data/vo_s6.json'
import vo8 from './data/vo_s8.json'
import p1 from './data/vo_p1.json'
import p7 from './data/vo_p7.json'
import v1 from './data/vo_v1.json'
import v2 from './data/vo_v2.json'
import v3 from './data/vo_v3.json'
import v4 from './data/vo_v4.json'

const SC = {
  open: [0, s(14)], run: [s(14), s(43)], pickup: [s(43), s(63)], verify: [s(63), s(83)],
  devin: [s(83), s(113)], fixed: [s(113), s(128)], numbers: [s(128), s(141)], vision: [s(141), s(177)],
  end: [s(177), s(186)],
} as const
export const PITCH_TOTAL = s(186)

// start of each vision line, seconds into the vision scene
type VAt = { v1: number; v2: number; v3: number; v4: number; end: number }
const V_AT: VAt = { v1: 0.8, v2: 8.3, v3: 16, v4: 24.6, end: 36 }

export const SceneNumbers: React.FC = () => {
  const at = s(0.8)
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <FadeIn><Title size={56} style={{ textAlign: 'center' }}>One agent. One night.</Title></FadeIn>
      <div style={{ display: 'flex', gap: 90, marginTop: 56 }}>
        <Stat v="2 min 28 s" l="from start to the bug report" delay={at} />
        <Stat v="7 min 18 s" l="from “fix it” to FIXED" delay={at + s(1.9)} />
        <Stat v="33 years" l="the bug sat in Doom's code" delay={at + s(7.4)} />
      </div>
      <FadeIn delay={at + s(1)}><Mono size={16} style={{ marginTop: 40, textAlign: 'center' }}>times: stage run 00:37 UTC, chocolate-doom#4 · eval/runs/2026-11-08-stage-live-loop-fixed.json · bug: id Software's r_plane.c, 1993</Mono></FadeIn>
    </AbsoluteFill>
  )
}

const Step: React.FC<{ children: React.ReactNode; delay: number; color?: string }> = ({ children, delay, color = C.text }) => (
  <FadeIn delay={delay}>
    <div style={{ padding: '18px 30px', borderRadius: 16, border: `1.5px solid ${C.line}`, background: C.card, color, fontFamily: SANS, fontWeight: 600, fontSize: 34 }}>{children}</div>
  </FadeIn>
)
const Arrow: React.FC<{ delay: number }> = ({ delay }) => (
  <FadeIn delay={delay}><div style={{ fontFamily: MONO, fontSize: 34, color: C.sub }}>→</div></FadeIn>
)

export const SceneVision: React.FC<{ at?: VAt }> = ({ at = V_AT }) => {
  const a1 = s(at.v1), a2 = s(at.v2), a3 = s(at.v3), a4 = s(at.v4)
  const card = (from: number, to: number, children: React.ReactNode) => (
    <Sequence from={from} durationInFrames={to - from} layout="none">
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: '0 160px' }}>{children}</AbsoluteFill>
    </Sequence>
  )
  return (
    <AbsoluteFill>
      {card(0, a2 - s(0.6), <>
        <FadeIn delay={a1}><Title size={72} style={{ textAlign: 'center' }}>Now imagine real investment.</Title></FadeIn>
        <div style={{ display: 'flex', gap: 22, marginTop: 48 }}>
          {['more time', 'more compute', 'more tokens'].map((t, i) => (
            <FadeIn key={t} delay={a1 + s([3.0, 3.9, 4.8][i])}><Pill color={C.key} style={{ fontSize: 30, padding: '14px 30px' }}>{t}</Pill></FadeIn>
          ))}
        </div>
      </>)}
      {card(a2 - s(0.6), a3 - s(0.6), <>
        <FadeIn delay={s(0.6)}><Sub style={{ fontSize: 34, textAlign: 'center' }}>Point it at worlds the size of</Sub></FadeIn>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, marginTop: 26 }}>
          {[['GTA 6', 1.5], ['Spider-Man', 2.9], ['Wolverine', 3.8], ['the next James Bond', 4.7]].map(([t, d]) => (
            <FadeIn key={t} delay={s(0.6 + (d as number))} rise={10}><Title size={76} style={{ textAlign: 'center' }}>{t}</Title></FadeIn>
          ))}
        </div>
      </>)}
      {card(a3 - s(0.6), a4 - s(0.6), <>
        <FadeIn delay={s(0.6)}><Sub style={{ fontSize: 34, textAlign: 'center' }}>Testing AAA games today</Sub></FadeIn>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, marginTop: 30 }}>
          <FadeIn delay={s(0.6 + 1.9)}><Title size={64}>large QA teams</Title></FadeIn>
          <FadeIn delay={s(0.6 + 3.5)}><Title size={64}>months of manual testing</Title></FadeIn>
          <FadeIn delay={s(0.6 + 5.4)}><Title size={64} style={{ color: C.red }}>and bugs still ship</Title></FadeIn>
        </div>
      </>)}
      {card(a4 - s(0.6), s(at.end), <>
        <FadeIn delay={s(0.6)}><Title size={72} style={{ textAlign: 'center' }}>One program, plugged into your game and your code</Title></FadeIn>
        <div style={{ display: 'flex', alignItems: 'center', gap: 22, marginTop: 60 }}>
          <Step delay={s(0.6 + 4.5)}>plays</Step><Arrow delay={s(0.6 + 4.9)} />
          <Step delay={s(0.6 + 5.1)}>finds the bug</Step><Arrow delay={s(0.6 + 5.8)} />
          <Step delay={s(0.6 + 6.0)}>proves it</Step><Arrow delay={s(0.6 + 6.6)} />
          <Step delay={s(0.6 + 6.9)} color={C.ok}>gets the fix written</Step>
        </div>
        <FadeIn delay={s(0.6 + 8.5)}><Mono style={{ marginTop: 40, textAlign: 'center' }}>what you just saw on Doom, at the scale of a AAA studio</Mono></FadeIn>
      </>)}
      <div style={{ position: 'absolute', left: 32, top: 26 }}>
        <Pill color={C.key} style={{ fontSize: 16, padding: '5px 14px', background: 'rgba(11,11,12,0.7)' }}>VISION · not a measured result</Pill>
      </div>
    </AbsoluteFill>
  )
}

export const SceneEnd: React.FC = () => (
  <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
    <FadeIn delay={4}><Mono color={C.text} size={22} style={{ textAlign: 'center' }}>19 / 19 pull requests in kaktamsdengami/player-two written by Devin</Mono></FadeIn>
    <FadeIn delay={s(2.6)}><Title size={110} style={{ letterSpacing: -4, marginTop: 30 }}>PLAYER TWO</Title></FadeIn>
    <FadeIn delay={s(3.5)}><Sub style={{ textAlign: 'center', marginTop: 6 }}>Your game's toughest tester.</Sub></FadeIn>
    <FadeIn delay={s(4.5)}><Mono style={{ marginTop: 46, textAlign: 'center' }}>H · Devin · ElevenLabs · Gladia · Linkup · Stripe</Mono></FadeIn>
    <FadeIn delay={s(5)}><Mono color={C.text} style={{ marginTop: 10 }}>player-two-doom.lovable.app</Mono></FadeIn>
  </AbsoluteFill>
)

export const Recorded: React.FC = () => (
  <div style={{ position: 'absolute', left: 32, top: 26 }}>
    <Pill color={C.text} style={{ fontSize: 16, padding: '5px 14px', background: 'rgba(11,11,12,0.7)' }}>
      <span style={{ width: 8, height: 8, borderRadius: 4, background: C.red, display: 'inline-block' }} />RECORDED
    </Pill>
  </div>
)

export const PlayerTwoPitch: React.FC = () => {
  const T = PITCH_TOTAL
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <Scene total={T} range={SC.open}><SceneOpen /></Scene>
      <Scene total={T} range={SC.run}><SceneRun /></Scene>
      <Scene total={T} range={SC.pickup}><ScenePickup /></Scene>
      <Scene total={T} range={SC.verify}><SceneVerify /></Scene>
      <Scene total={T} range={SC.devin}><SceneDevin /></Scene>
      <Scene total={T} range={SC.fixed}><SceneFixed /></Scene>
      <Scene total={T} range={SC.numbers}><SceneNumbers /></Scene>
      <Scene total={T} range={SC.vision}><SceneVision /></Scene>
      <Scene total={T} range={SC.end}><SceneEnd /></Scene>

      <Voice file="p1" vo={p1 as VO} at={s(0.6)} />
      <Voice file="s2" vo={vo2 as VO} at={SC.run[0] + s(0.8)} />
      <Voice file="s3" vo={vo3 as VO} at={SC.pickup[0] + s(1.5)} />
      <Voice file="s4" vo={vo4 as VO} at={SC.verify[0] + s(0.8)} />
      {DEVIN_VO.map(([at, from, to]) => <Voice key={at} file="s5" vo={vo5 as VO} at={SC.devin[0] + s(at)} from={from} to={to} />)}
      <Voice file="s6" vo={vo6 as VO} at={SC.fixed[0] + s(1.5)} />
      <Voice file="p7" vo={p7 as VO} at={SC.numbers[0] + s(0.8)} />
      <Voice file="v1" vo={v1 as VO} at={SC.vision[0] + s(V_AT.v1)} />
      <Voice file="v2" vo={v2 as VO} at={SC.vision[0] + s(V_AT.v2)} />
      <Voice file="v3" vo={v3 as VO} at={SC.vision[0] + s(V_AT.v3)} />
      <Voice file="v4" vo={v4 as VO} at={SC.vision[0] + s(V_AT.v4)} />
      <Voice file="s8" vo={vo8 as VO} at={SC.end[0] + s(0.6)} />

      <Sequence durationInFrames={SC.numbers[1]} layout="none"><Recorded /></Sequence>
    </AbsoluteFill>
  )
}
