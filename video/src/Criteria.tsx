// Criteria cut (~1:47): one chapter per judging criterion, all footage from the desktop screen
// recording of the 02:26 UTC live run (public/v5/*, cut by scripts/cut_criteria.sh), plain labels.
// Every number on screen comes from recordings/20261108-032604-session (events.jsonl, run/events.jsonl).
import React from 'react'
import { AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from 'remotion'
import { C, SANS, MONO, s, Voice, type VO } from './PlayerTwo'
import a0 from './data/vo_a0.json'
import a1 from './data/vo_a1.json'
import a2 from './data/vo_a2.json'
import a3 from './data/vo_a3.json'
import a4 from './data/vo_a4.json'
import a5 from './data/vo_a5.json'
import a6 from './data/vo_a6.json'

export const CRITERIA_TOTAL = s(107)

const Top: React.FC<{ chapter?: string; src: string }> = ({ chapter, src }) => (
  <div style={{ position: 'absolute', left: 40, right: 40, top: 26, display: 'flex', justifyContent: 'space-between', fontFamily: MONO, fontSize: 20, letterSpacing: 1 }}>
    <span style={{ color: C.key }}>{chapter ?? ''}</span><span style={{ color: C.sub }}>{src}</span>
  </div>
)
// one shot: [from, to) seconds on the timeline
const At: React.FC<{ a: number; b: number; children: React.ReactNode }> = ({ a, b, children }) => (
  <Sequence from={s(a)} durationInFrames={s(b - a)}><AbsoluteFill style={{ background: C.bg }}>{children}</AbsoluteFill></Sequence>
)
const Box: React.FC<{ top: number; w: number; h: number; children: React.ReactNode }> = ({ top, w, h, children }) => (
  <div style={{ position: 'absolute', top, left: (1920 - w) / 2, width: w, height: h, overflow: 'hidden', border: `1px solid ${C.line}` }}>{children}</div>
)
const Vid: React.FC<{ f: string; w: number; h: number; from?: number }> = ({ f, w, h, from = 0 }) => (
  <OffthreadVideo src={staticFile(`v5/${f}`)} startFrom={s(from)} muted style={{ width: w, height: h }} />
)
const Note: React.FC<{ top: number; children: React.ReactNode; color?: string; size?: number }> = ({ top, children, color = C.text, size = 26 }) => (
  <div style={{ position: 'absolute', top, left: 0, right: 0, textAlign: 'center', fontFamily: MONO, fontSize: size, color }}>{children}</div>
)
// shows children only between a and b seconds of the parent shot
const When: React.FC<{ a: number; b?: number; children: React.ReactNode }> = ({ a, b = 999, children }) => {
  const t = useCurrentFrame() / 30
  return t >= a && t < b ? <>{children}</> : null
}

// the real event times of the run (events.jsonl, UTC)
const EVENTS: [string, string][] = [
  ['02:26:04', 'run started'],
  ['02:34:15', 'H: report_finding (step 62)'],
  ['02:38:31', 'verifier: verified, known bug KB3'],
  ['02:38:45', 'developer, by voice: "Yes, fix it."'],
  ['02:40:38', 'Devin: pull request chocolate-doom#5'],
  ['02:41:10', 'merged, CI rebuild'],
  ['02:45:14', 'proof replay: FIXED'],
]
const CRISPY = [
  '	    // Sky is allways drawn full bright,',
  '	    //  i.e. colormaps[0] is used.',
  '	    // Because of this hack, sky is not affected',
  '	    //  by INVUL inverse mapping.',
  '	    // [crispy] no brightmaps for sky',
  '	    dc_colormap[0] = dc_colormap[1] = colormaps;',
]

export const PlayerTwoCriteria: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg }}>
    {/* 0 · what it is */}
    <At a={0} b={9}>
      <Box top={90} w={1920} h={740}><Vid f="open.mp4" w={1920} h={740} /></Box>
      <Top chapter="PLAYER TWO" src="screen recording · live run 8 Nov 2026, 02:26 UTC · real time" />
      <Note top={850} size={24} color={C.sub}>H just picked up invulnerability: the world turns white, the sky stays red</Note>
    </At>

    {/* 1 · use of computer use */}
    <At a={9} b={33.5}>
      <Box top={90} w={1920} h={740}><Vid f="fight.mp4" w={1920} h={740} /></Box>
      <Top chapter="1 · USE OF COMPUTER USE" src="screen recording · 2× speed" />
      <When a={9.5} b={15.5}><Note top={850} size={24}>H: “There's a large monster right in the center of the screen! … I should shoot it by holding Ctrl without moving.”</Note></When>
      <When a={16.5} b={22}><Note top={850} size={24}>H: “The monster is dead. Now I need to find the green sphere.”</Note></When>
      <When a={13.1}><Note top={900} size={26} color={C.key}>47 hits · 558 damage · health 999 → 441 · 3 kills · then the power-up</Note></When>
    </At>

    {/* 2 · technical execution and reliability */}
    <At a={33.5} b={37.5}>
      <Top chapter="2 · TECHNICAL EXECUTION AND RELIABILITY" src="events.jsonl of this run (UTC)" />
      <div style={{ position: 'absolute', top: 200, left: 460, fontFamily: MONO, fontSize: 34, lineHeight: 1.75 }}>
        {EVENTS.map(([t, l]) => <div key={t}><span style={{ color: C.sub }}>{t}</span>  <span style={{ color: C.text }}>{l}</span></div>)}
      </div>
    </At>
    <At a={37.5} b={41.8}>
      <Box top={90} w={1920} h={740}><Vid f="verify.mp4" w={1920} h={740} /></Box>
      <Top chapter="2 · TECHNICAL EXECUTION AND RELIABILITY" src="screen recording · the verifier replays H's inputs · 6× speed" />
    </At>
    <At a={41.8} b={46}>
      <Box top={80} w={882} h={900}><Vid f="ask.mp4" w={882} h={900} from={2.2} /></Box>
      <Top chapter="2 · TECHNICAL EXECUTION AND RELIABILITY" src="screen recording · the dashboard asks, the developer answers · real time" />
    </At>
    <At a={46} b={49.3}>
      <Box top={80} w={1600} h={880}><Img src={staticFile('v4/pr.png')} style={{ width: 1600 }} /></Box>
      <Top chapter="2 · TECHNICAL EXECUTION AND RELIABILITY" src="github.com/kaktamsdengami/chocolate-doom/pull/5 · opened and merged by Devin" />
    </At>
    <At a={49.3} b={54.3}>
      <Box top={80} w={1100} h={862}><Vid f="proof.mp4" w={1100} h={862} from={0.6} /></Box>
      <Top chapter="2 · TECHNICAL EXECUTION AND RELIABILITY" src="screen recording · proof replay on the rebuilt game · real time" />
    </At>
    <At a={54.3} b={58.6}>
      <Box top={90} w={1920} h={740}><Img src={staticFile('v5/focus.png')} style={{ width: 1920, height: 740 }} /></Box>
      <Top chapter="2 · TECHNICAL EXECUTION AND RELIABILITY" src="screen recording · 02:36:22 UTC" />
      <Note top={850} size={24} color={C.sub}>H clicked outside the game; the focus guard gave the keyboard back (4 times before FIXED)</Note>
    </At>

    {/* 3 · usefulness and impact */}
    <At a={58.6} b={71}>
      <Top chapter="3 · USEFULNESS AND IMPACT" src="github.com/fabiangreffrath/crispy-doom · src/doom/r_plane.c · master" />
      <div style={{ position: 'absolute', top: 150, left: 120, width: 1680 }}>
        <div style={{ fontFamily: MONO, fontSize: 24, color: C.sub, marginBottom: 14 }}>the 1993 line, still in Crispy Doom today (Chocolate Doom has the same code)</div>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, padding: '20px 28px' }}>
          {CRISPY.map((l, i) => <div key={i} style={{ fontFamily: MONO, fontSize: 28, whiteSpace: 'pre', color: i === 5 ? C.red : C.text, lineHeight: 1.5 }}>{l}</div>)}
        </div>
        <div style={{ fontFamily: MONO, fontSize: 24, color: C.sub, margin: '40px 0 14px' }}>what the developer got from PLAYER TWO, for this bug</div>
        <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 34, color: C.text, lineHeight: 1.5 }}>
          steps to reproduce · a 10 s clip · proof from the engine log · a pull request to review · a proof replay
        </div>
      </div>
    </At>

    {/* 4 · originality and innovation */}
    <At a={71} b={87}>
      <Box top={90} w={1920} h={740}><Vid f="think.mp4" w={1920} h={740} /></Box>
      <Top chapter="4 · ORIGINALITY AND INNOVATION" src="screen recording · real time: the game is paused while H thinks (frame-step)" />
      <When a={9.0}><Note top={850} size={24} color={C.sub}>hidden QA log, never shown to H:</Note>
        <Note top={890} size={26} color={C.key}>powerup power=0 · render sky_ignores_colormap fixedcolormap=32</Note></When>
    </At>

    {/* 5 · UX and user control */}
    <At a={87} b={91.1}>
      <Box top={80} w={882} h={900}><Img src={staticFile('v5/buttons.png')} style={{ width: 882, height: 900 }} /></Box>
      <Top chapter="5 · UX AND USER CONTROL" src="screen recording · push-to-talk, Fix · Skip · Explain · Yes · No · Stop" />
    </At>
    <At a={91.1} b={100.1}>
      <Box top={80} w={562} h={900}><Vid f="stop.mp4" w={562} h={900} /></Box>
      <Top chapter="5 · UX AND USER CONTROL" src="screen recording · Stop at 02:50:26, run stopped at 02:50:27 · real time" />
    </At>

    {/* end */}
    <At a={100.1} b={107}>
      <Box top={80} w={1200} h={750}><Img src={staticFile('v4/live.png')} style={{ width: 1200 }} /></Box>
      <Note top={870} size={52} color={C.text}>player-two-doom.lovable.app</Note>
      <Note top={945} size={22} color={C.sub}>H · Devin · ElevenLabs · Gladia · Linkup · Stripe</Note>
    </At>

    <Voice file="a0" vo={a0 as VO} at={s(0.5)} />
    <Voice file="a1" vo={a1 as VO} at={s(9.5)} />
    <Voice file="a2" vo={a2 as VO} at={s(34)} />
    <Voice file="a3" vo={a3 as VO} at={s(59)} />
    <Voice file="a4" vo={a4 as VO} at={s(71.5)} />
    <Voice file="a5" vo={a5 as VO} at={s(87.5)} />
    <Voice file="a6" vo={a6 as VO} at={s(100.6)} />
  </AbsoluteFill>
)
