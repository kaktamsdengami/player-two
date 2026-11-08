// Tight pitch cut: the pitch story plus "we stress-tested H", with no long silences
// (every scene is cut to its voice-over; extra lines fill the gaps).
import React from 'react'
import { AbsoluteFill, Sequence } from 'remotion'
import {
  C, s, Voice, Scene, SceneOpen, SceneRun, ScenePickup, SceneVerify, SceneDevin, SceneFixed, SceneKid, KID_LEN, type VO,
} from './PlayerTwo'
import k7 from './data/vo_k7.json'
import { Recorded, SceneEnd, SceneNumbers, SceneVision } from './Pitch'
import vo2 from './data/vo_s2.json'
import vo4 from './data/vo_s4.json'
import vo5 from './data/vo_s5.json'
import vo6 from './data/vo_s6.json'
import vo8 from './data/vo_s8.json'
import p1 from './data/vo_p1.json'
import st from './data/vo_st.json'
import p3 from './data/vo_p3.json'
import p5a from './data/vo_p5a.json'
import p6b from './data/vo_p6b.json'
import p7 from './data/vo_p7.json'
import v1 from './data/vo_v1.json'
import v2 from './data/vo_v2.json'
import v3 from './data/vo_v3.json'
import v4 from './data/vo_v4.json'

const at = (a: number, b: number) => [s(a), s(b)] as const
const K = 100.2 + KID_LEN
const SC = {
  open: at(0, 13.3), run: at(13.3, 43.3), pickup: at(43.3, 57.5), verify: at(57.5, 69),
  devin: at(69, 88.2), fixed: at(88.2, 100.2), kid: at(100.2, K), numbers: at(K, K + 10.3),
  vision: at(K + 10.3, K + 40.3), end: at(K + 40.3, K + 47.8),
}
export const TIGHT_TOTAL = SC.end[1]

const RUN_SEGS: [number, number][] = [[0, 6], [7, 14.5], [44, 53], [76, 83.5]] // 30 s of the run
const DEVIN_T = { A: 4.2, B: 8.2, Cc: 12.8, D: 16.2, end: 19.2 }
// s5 parts: [at (s into the scene), from, to (s in the mp3)]
const DEVIN_VO: [number, number, number | undefined][] = [[4.4, 0, 3.6], [8.4, 3.7, 7.1], [13.0, 7.1, 10.0], [16.4, 10.0, undefined]]
const V_AT = { v1: 0.6, v2: 6.8, v3: 13.3, v4: 20.8, end: 30 }

export const PlayerTwoTight: React.FC = () => {
  const T = TIGHT_TOTAL
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <Scene total={T} range={SC.open}><SceneOpen /></Scene>
      <Scene total={T} range={SC.run}><SceneRun segs={RUN_SEGS} /></Scene>
      <Scene total={T} range={SC.pickup}><ScenePickup /></Scene>
      <Scene total={T} range={SC.verify}><SceneVerify /></Scene>
      <Scene total={T} range={SC.devin}><SceneDevin t={DEVIN_T} /></Scene>
      <Scene total={T} range={SC.fixed}><SceneFixed /></Scene>
      <Scene total={T} range={SC.kid}><SceneKid /></Scene>
      <Scene total={T} range={SC.numbers}><SceneNumbers /></Scene>
      <Scene total={T} range={SC.vision}><SceneVision at={V_AT} /></Scene>
      <Scene total={T} range={SC.end}><SceneEnd /></Scene>

      <Voice file="p1" vo={p1 as VO} at={s(0.5)} />
      <Voice file="s2" vo={vo2 as VO} at={SC.run[0] + s(0.6)} />
      <Voice file="st" vo={st as VO} at={SC.run[0] + s(20.6)} />
      <Voice file="p3" vo={p3 as VO} at={SC.pickup[0] + s(1.0)} />
      <Voice file="s4" vo={vo4 as VO} at={SC.verify[0] + s(0.6)} />
      <Voice file="p5a" vo={p5a as VO} at={SC.devin[0] + s(0.5)} />
      {DEVIN_VO.map(([a, from, to]) => <Voice key={a} file="s5" vo={vo5 as VO} at={SC.devin[0] + s(a)} from={from} to={to} />)}
      <Voice file="s6" vo={vo6 as VO} at={SC.fixed[0] + s(1.0)} />
      <Voice file="p6b" vo={p6b as VO} at={SC.fixed[0] + s(8.7)} />
      <Voice file="k7" vo={k7 as VO} at={SC.kid[0] + s(0.4)} />
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
