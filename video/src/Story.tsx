// Story cut (~1:45) for a jury that has never seen the project: the problem, the idea, the live demo
// on a real game, the bug shown plainly, found -> proven -> fixed, then the potential (labelled VISION).
// Footage: public/v5 (scripts/cut_criteria.sh), v4/pr.png, sky_before/after.png (same frame).
import React from 'react'
import { AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile } from 'remotion'
import { C, SANS, MONO, s, Voice, FadeIn, type VO } from './PlayerTwo'
import b1 from './data/vo_b1.json'
import b2 from './data/vo_b2.json'
import b3 from './data/vo_b3.json'
import b4 from './data/vo_b4.json'
import b5 from './data/vo_b5.json'
import b6 from './data/vo_b6.json'
import b7 from './data/vo_b7.json'
import b8 from './data/vo_b8.json'
import b9 from './data/vo_b9.json'
import b10 from './data/vo_b10.json'

export const STORY_TOTAL = s(105)

const At: React.FC<{ a: number; b: number; children: React.ReactNode }> = ({ a, b, children }) => (
  <Sequence from={s(a)} durationInFrames={s(b - a)}><AbsoluteFill style={{ background: C.bg }}>{children}</AbsoluteFill></Sequence>
)
const Tag: React.FC<{ children: React.ReactNode; color?: string }> = ({ children, color = C.sub }) => (
  <div style={{ position: 'absolute', left: 40, top: 28, fontFamily: MONO, fontSize: 20, letterSpacing: 1, color }}>{children}</div>
)
const Big: React.FC<{ children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties }> = ({ children, size = 64, color = C.text, style }) => (
  <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: size, color, letterSpacing: -1, lineHeight: 1.15, textAlign: 'center', ...style }}>{children}</div>
)
const Box: React.FC<{ top: number; left?: number; w: number; h: number; children: React.ReactNode; color?: string }> = ({ top, left, w, h, children, color = C.line }) => (
  <div style={{ position: 'absolute', top, left: left ?? (1920 - w) / 2, width: w, height: h, overflow: 'hidden', border: `2px solid ${color}` }}>{children}</div>
)
const Vid: React.FC<{ f: string; w: number; h: number; from?: number }> = ({ f, w, h, from = 0 }) => (
  <OffthreadVideo src={staticFile(f)} startFrom={s(from)} muted style={{ width: w, height: h }} />
)
const Caption: React.FC<{ top: number; children: React.ReactNode; color?: string; size?: number; delay?: number }> = ({ top, children, color = C.text, size = 30, delay = 0 }) => (
  <FadeIn delay={s(delay)} style={{ position: 'absolute', top, left: 0, right: 0, textAlign: 'center', fontFamily: MONO, fontSize: size, color }}>{children}</FadeIn>
)

const STEPS: [string, number][] = [['plays', 5.6], ['finds bugs', 6.3], ['proves them', 7.6], ['gets them fixed', 9.3]]
const VISION: [string, number][] = [
  ['a game as big as GTA 6', 5.3],
  ['hundreds of AI testers on every build, overnight', 7.4],
  ['every bug arrives with a video, a proof and a fix to review', 10.8],
]
// sky area of sky_before.png (800x600)
const SKY = { x: 140, y: 34, w: 492, h: 200 }

export const PlayerTwoStory: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg }}>
    {/* the problem */}
    <At a={0} b={9.6}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 34 }}>
        <FadeIn delay={s(0.4)}><Big size={84}>Every game ships with bugs.</Big></FadeIn>
        <FadeIn delay={s(2.6)}><Big size={44} color={C.sub}>Big teams of human testers. Months of replaying the same levels.</Big></FadeIn>
        <FadeIn delay={s(6.6)}><Big size={44} color={C.red}>And bugs still reach the players.</Big></FadeIn>
      </AbsoluteFill>
    </At>

    {/* the idea */}
    <At a={9.6} b={20.6}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <FadeIn delay={s(1.0)}><Big size={110} style={{ letterSpacing: -4 }}>PLAYER TWO</Big></FadeIn>
        <FadeIn delay={s(2.3)}><Big size={46} color={C.sub} style={{ marginTop: 10 }}>an AI that tests your game the way a player would</Big></FadeIn>
        <div style={{ display: 'flex', gap: 26, marginTop: 70, alignItems: 'center' }}>
          {STEPS.map(([t, d], i) => (
            <React.Fragment key={t}>
              {i > 0 && <FadeIn delay={s(0.3 + d)}><span style={{ fontFamily: MONO, fontSize: 40, color: C.sub }}>→</span></FadeIn>}
              <FadeIn delay={s(0.3 + d)}>
                <div style={{ padding: '18px 32px', border: `2px solid ${i === 3 ? C.ok : C.line}`, borderRadius: 16, fontFamily: SANS, fontWeight: 600, fontSize: 40, color: i === 3 ? C.ok : C.text }}>{t}</div>
              </FadeIn>
            </React.Fragment>
          ))}
        </div>
      </AbsoluteFill>
    </At>

    {/* the test: a real game, screen and keyboard only */}
    <At a={20.6} b={32}>
      <Box top={90} w={1920} h={740}><Vid f="v5/think.mp4" w={1920} h={740} /></Box>
      <Tag color={C.key}>LIVE TEST · recorded on our laptop, 8 Nov 2026</Tag>
      <Caption top={850} delay={2.8}>a real game: Doom (Freedoom, open source) · left: the game · right: our dashboard</Caption>
      <Caption top={900} delay={7.7} color={C.key}>the AI gets no code and no game data · only the screen and a keyboard</Caption>
    </At>

    {/* it plays */}
    <At a={32} b={42.2}>
      <Box top={90} w={1920} h={740}><Vid f="v5/fight.mp4" w={1920} h={740} from={4} /></Box>
      <Tag color={C.key}>LIVE TEST · 2× speed</Tag>
      <Caption top={850} delay={1.5}>the player is H, a computer-use agent · it attacks, takes hits, keeps testing</Caption>
    </At>

    {/* the bug, shown plainly */}
    <At a={42.2} b={47.6}>
      <Box top={90} w={1920} h={740}><Vid f="v5/open.mp4" w={1920} h={740} /></Box>
      <Tag color={C.key}>LIVE TEST · real time</Tag>
      <Caption top={850} delay={1.8}>H picks up invulnerability: the game must switch the whole view to grey</Caption>
    </At>
    <At a={47.6} b={55}>
      <div style={{ position: 'absolute', top: 70, left: 330, width: 1067, height: 800 }}>
        <Img src={staticFile('sky_before.png')} style={{ width: 1067, height: 800 }} />
        <FadeIn delay={s(0.2)} style={{ position: 'absolute', left: SKY.x * 1.333, top: SKY.y * 1.333, width: SKY.w * 1.333, height: SKY.h * 1.333, border: `5px solid ${C.key}`, borderRadius: 10 }}><span /></FadeIn>
      </div>
      <div style={{ position: 'absolute', top: 120, left: 1420, width: 440 }}>
        <FadeIn delay={s(0.3)}><Big size={54} color={C.key} style={{ textAlign: 'left' }}>The sky stays red.</Big></FadeIn>
        <FadeIn delay={s(1.4)}><Big size={34} color={C.sub} style={{ textAlign: 'left', marginTop: 24 }}>Everything else turned grey. The sky ignores the power-up.</Big></FadeIn>
        <FadeIn delay={s(3.4)}><Big size={34} color={C.text} style={{ textAlign: 'left', marginTop: 24 }}>In Doom's code since 1993. Still in the versions people play today.</Big></FadeIn>
      </div>
      <Tag color={C.key}>THE BUG · a frame of the same scene</Tag>
    </At>

    {/* proven */}
    <At a={55} b={63.4}>
      <Tag color={C.key}>FOUND → PROVEN</Tag>
      <div style={{ position: 'absolute', top: 110, left: 70, width: 820, background: C.card, border: `2px solid ${C.line}`, borderRadius: 16, padding: 30 }}>
        <div style={{ fontFamily: MONO, fontSize: 22, color: C.key }}>H's bug report, word for word</div>
        <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 36, color: C.text, margin: '14px 0 18px' }}>Sky not inverted during invulnerability power-up</div>
        {['Walked to the green invulnerability sphere in the canyon and picked it up',
          "Screen turned white/inverted and 'VANGUARD OF THE GODS!' message appeared",
          'Turned to look at the sky area - the sky remains RED while walls and floor are white/grey (inverted)'].map((t, i) => (
          <div key={i} style={{ fontFamily: SANS, fontSize: 25, color: C.text, lineHeight: 1.4, marginBottom: 8 }}>{i + 1}. {t}</div>
        ))}
      </div>
      <FadeIn delay={s(2.6)} style={{ position: 'absolute', top: 110, left: 940 }}>
        <div style={{ width: 920, height: 355, overflow: 'hidden', border: `2px solid ${C.line}` }}><Vid f="v5/verify.mp4" w={920} h={355} /></div>
        <div style={{ fontFamily: MONO, fontSize: 22, color: C.sub, marginTop: 12 }}>our verifier replays H's exact moves (6× speed)</div>
        <div style={{ fontFamily: MONO, fontSize: 24, color: C.text, marginTop: 30 }}>the engine's own log, never shown to H:</div>
        <div style={{ fontFamily: MONO, fontSize: 26, color: C.key, marginTop: 8 }}>render sky_ignores_colormap</div>
        <div style={{ fontFamily: MONO, fontSize: 30, color: C.ok, marginTop: 24 }}>verified</div>
      </FadeIn>
    </At>

    {/* fixed by Devin */}
    <At a={63.4} b={68.9}>
      <Box top={80} w={882} h={900}><Vid f="v5/ask.mp4" w={882} h={900} from={3.5} /></Box>
      <Tag color={C.key}>FIX · the dashboard reads the bug aloud, the developer answers by voice · real time</Tag>
    </At>
    <At a={68.9} b={74.2}>
      <Box top={80} w={1600} h={880}><Img src={staticFile('v4/pr.png')} style={{ width: 1600 }} /></Box>
      <Tag color={C.key}>FIX · Devin's pull request on GitHub (chocolate-doom#5), opened and merged by Devin</Tag>
    </At>

    {/* fixed, proven again */}
    <At a={74.2} b={80}>
      <Box top={80} w={1100} h={862}><Vid f="v5/proof.mp4" w={1100} h={862} from={0.6} /></Box>
      <Tag color={C.key}>PROOF · the rebuilt game, same scenario replayed · real time</Tag>
    </At>
    <At a={80} b={84}>
      <div style={{ position: 'absolute', top: 150, left: 120, display: 'flex', gap: 40 }}>
        {[['sky_before.png', 'BEFORE · sky red', C.red], ['sky_after.png', "AFTER DEVIN'S FIX · sky grey", C.ok]].map(([f, l, col]) => (
          <div key={f}>
            <div style={{ width: 820, height: 615, border: `3px solid ${col}` }}><Img src={staticFile(f)} style={{ width: 814, height: 609 }} /></div>
            <div style={{ fontFamily: MONO, fontSize: 30, color: col, marginTop: 16 }}>{l}</div>
          </div>
        ))}
      </div>
      <Tag color={C.ok}>FOUND · PROVEN · FIXED · 6 min 29 s after "fix it"</Tag>
    </At>

    {/* the potential */}
    <At a={84} b={100}>
      <Tag color={C.key}>VISION · not a measured result</Tag>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 30 }}>
        <FadeIn delay={s(0.3)}><Big size={44} color={C.sub}>Tonight: one bug, one classic game, one night.</Big></FadeIn>
        {VISION.map(([t, d], i) => (
          <FadeIn key={t} delay={s(0.3 + d)}><Big size={i === 0 ? 76 : 54} color={i === 2 ? C.ok : C.text}>{t}</Big></FadeIn>
        ))}
      </AbsoluteFill>
    </At>

    {/* end */}
    <At a={100} b={105}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <FadeIn delay={s(0.2)}><Big size={120} style={{ letterSpacing: -4 }}>PLAYER TWO</Big></FadeIn>
        <FadeIn delay={s(1.0)}><Big size={44} color={C.sub} style={{ marginTop: 8 }}>Your game's toughest tester.</Big></FadeIn>
        <FadeIn delay={s(1.8)}><div style={{ fontFamily: MONO, fontSize: 34, color: C.text, marginTop: 56 }}>player-two-doom.lovable.app</div></FadeIn>
        <FadeIn delay={s(2.2)}><div style={{ fontFamily: MONO, fontSize: 22, color: C.sub, marginTop: 16 }}>H · Devin · ElevenLabs · Gladia · Linkup · Stripe</div></FadeIn>
      </AbsoluteFill>
    </At>

    <Voice file="b1" vo={b1 as VO} at={s(0.5)} />
    <Voice file="b2" vo={b2 as VO} at={s(9.9)} />
    <Voice file="b3" vo={b3 as VO} at={s(20.9)} />
    <Voice file="b4" vo={b4 as VO} at={s(32.3)} />
    <Voice file="b5" vo={b5 as VO} at={s(42.5)} />
    <Voice file="b6" vo={b6 as VO} at={s(55.3)} />
    <Voice file="b7" vo={b7 as VO} at={s(63.7)} />
    <Voice file="b8" vo={b8 as VO} at={s(74.5)} />
    <Voice file="b9" vo={b9 as VO} at={s(84.3)} />
    <Voice file="b10" vo={b10 as VO} at={s(100.3)} />
  </AbsoluteFill>
)
