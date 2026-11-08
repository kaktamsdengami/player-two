// Story cut (~2:20) for a jury that has never seen the project: the market, the problem, the idea, the live
// demo on a real game, the bug shown plainly, found -> proven -> fixed, kid mode (Pixel), then the potential
// (labelled VISION). Footage: public/v5 (scripts/cut_criteria.sh), v4/pr.png, sky_before/after.png,
// kid_cut.mp4 (kid_team_boost.mp4 from 15 s). Narration n1..n12 (scripts/tts.mjs, voice Brian).
import React from 'react'
import { AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from 'remotion'
import { C, SANS, MONO, s, Voice, FadeIn, KID_LINES, type VO } from './PlayerTwo'
import n1 from './data/vo_n1.json'
import n2 from './data/vo_n2.json'
import n3 from './data/vo_n3.json'
import n4 from './data/vo_n4.json'
import n5 from './data/vo_n5.json'
import n6 from './data/vo_n6.json'
import n7 from './data/vo_n7.json'
import n8 from './data/vo_n8.json'
import n9 from './data/vo_n9.json'
import n10 from './data/vo_n10.json'
import n11 from './data/vo_n11.json'
import n12 from './data/vo_n12.json'

// start time (s) of `word` in a voice line, so the on-screen text lands on the spoken word
const w = (vo: unknown, word: string): number => {
  const v = vo as VO
  const i = v.text.indexOf(word)
  if (i < 0) throw new Error(`"${word}" not in "${v.text}"`)
  return v.start[i]
}

const T = {
  market: 0, problem: 8.2, idea: 20, test: 29.4, fight: 41, open: 50.5, sky: 55.9, proven: 62.4,
  ask: 70.6, pr: 75.9, proof: 80.3, ba: 86, kid: 90.5, talk: 101.6, vision: 113.2, end: 134.4, total: 139.6,
}
const VO_LEAD = 0.3
export const STORY_TOTAL = s(T.total)

const At: React.FC<{ a: number; b: number; children: React.ReactNode }> = ({ a, b, children }) => (
  <Sequence from={s(a)} durationInFrames={s(b - a)}><AbsoluteFill style={{ background: C.bg }}>{children}</AbsoluteFill></Sequence>
)
const Tag: React.FC<{ children: React.ReactNode; color?: string }> = ({ children, color = C.sub }) => (
  <div style={{ position: 'absolute', left: 40, top: 28, fontFamily: MONO, fontSize: 20, letterSpacing: 1, color }}>{children}</div>
)
const Big: React.FC<{ children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties }> = ({ children, size = 64, color = C.text, style }) => (
  <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: size, color, letterSpacing: -1, lineHeight: 1.15, textAlign: 'center', ...style }}>{children}</div>
)
const Box: React.FC<{ top: number; left?: number; w: number; h: number; children: React.ReactNode; color?: string }> = ({ top, left, w: bw, h, children, color = C.line }) => (
  <div style={{ position: 'absolute', top, left: left ?? (1920 - bw) / 2, width: bw, height: h, overflow: 'hidden', border: `2px solid ${color}` }}>{children}</div>
)
const Vid: React.FC<{ f: string; w: number; h: number; from?: number }> = ({ f, w: vw, h, from = 0 }) => (
  <OffthreadVideo src={staticFile(f)} startFrom={s(from)} muted style={{ width: vw, height: h }} />
)
const Caption: React.FC<{ top: number; children: React.ReactNode; color?: string; size?: number; delay?: number }> = ({ top, children, color = C.text, size = 30, delay = 0 }) => (
  <FadeIn delay={s(delay)} style={{ position: 'absolute', top, left: 0, right: 0, textAlign: 'center', fontFamily: MONO, fontSize: size, color }}>{children}</FadeIn>
)
// delay inside a scene that starts at `scene`, for a word of the line that starts at scene + VO_LEAD
const d = (vo: unknown, word: string) => VO_LEAD + w(vo, word)

const STEPS: [string, string][] = [['plays', 'plays'], ['finds bugs', 'hunts'], ['proves them', 'proves'], ['gets them fixed', 'gets it']]

// kid mode: kid_cut.mp4 = kid_team_boost.mp4 from 15 s; the conversation in four pieces (kid_cut seconds)
const KID_OFF = 15
const KID_SEGS: [number, number][] = [[1.6, 3.1], [8.0, 11.9], [14.9, 17.1], [19.6, 23.3]]
const KID_LEN = KID_SEGS.reduce((n, [a, b]) => n + b - a, 0)
const kidAt = (t: number): number | null => {
  let at = 0
  for (const [a, b] of KID_SEGS) { if (t < at + b - a) return a + t - at; at += b - a }
  return null
}
const KID_H = 880, KID_W = Math.round(KID_H * 1316 / 1078)

const KidTalk: React.FC = () => {
  const t = useCurrentFrame() / 30
  const k = kidAt(t)
  const src = k === null ? null : k + KID_OFF
  const line = src === null ? undefined : KID_LINES.find(([a, b]) => src >= a - 0.1 && src < b + 0.4)
  let at = 0
  return (
    <>
      <div style={{ position: 'absolute', top: 76, left: (1920 - KID_W) / 2, width: KID_W, height: KID_H, border: `2px solid ${C.line}` }}>
        {KID_SEGS.map(([a, b]) => { const from = at; at += s(b - a); return (
          <Sequence key={a} from={from} durationInFrames={s(b - a)} layout="none">
            <OffthreadVideo src={staticFile('kid_cut.mp4')} startFrom={s(a)} endAt={s(b)} volume={1.35} style={{ width: KID_W, height: KID_H }} />
          </Sequence>
        ) })}
      </div>
      {line && (
        <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 150 }}>
          <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 44, color: C.text, background: 'rgba(11,11,12,0.88)', padding: '12px 28px', borderRadius: 14 }}>
            <span style={{ fontFamily: MONO, fontSize: 28, color: line[2] === 'Player' ? C.key : C.ok, marginRight: 16 }}>{line[2] === 'Player' ? 'YOU' : 'PIXEL'}</span>{line[3]}
          </div>
        </AbsoluteFill>
      )}
    </>
  )
}

// sky area of sky_before.png (800x600)
const SKY = { x: 140, y: 34, w: 492, h: 200 }

const Num: React.FC<{ n: string; l: string; delay: number; color?: string }> = ({ n, l, delay, color = C.text }) => (
  <FadeIn delay={s(delay)}>
    <div style={{ textAlign: 'center', width: 640 }}>
      <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: 150, color, letterSpacing: -5, lineHeight: 1 }}>{n}</div>
      <div style={{ fontFamily: MONO, fontSize: 30, color: C.sub, marginTop: 18 }}>{l}</div>
    </div>
  </FadeIn>
)

export const PlayerTwoStory: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg }}>
    {/* the market */}
    <At a={T.market} b={T.problem}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 70 }}>
        <FadeIn delay={s(d(n1, 'biggest'))}><Big size={60}>The biggest entertainment business on Earth.</Big></FadeIn>
        <div style={{ display: 'flex', gap: 80 }}>
          <Num n="$200B" l="spent on games every year" delay={d(n1, 'two hundred')} color={C.ok} />
          <Num n="3.5B" l="players worldwide" delay={d(n1, 'Three')} color={C.key} />
        </div>
      </AbsoluteFill>
      <Caption top={1010} size={20} color={C.sub} delay={1.5}>source: Newzoo global games market estimates (rounded)</Caption>
    </At>

    {/* the problem */}
    <At a={T.problem} b={T.idea}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 40 }}>
        <FadeIn delay={s(d(n2, 'every'))}><Big size={88}>Every game ships with bugs.</Big></FadeIn>
        <FadeIn delay={s(d(n2, 'Studios'))}><Big size={44} color={C.sub}>Testing eats a big part of every budget.</Big></FadeIn>
        <FadeIn delay={s(d(n2, 'rooms'))}><Big size={44} color={C.sub}>Rooms of people. Months of replaying the same levels.</Big></FadeIn>
        <FadeIn delay={s(d(n2, 'And bugs'))}><Big size={52} color={C.red}>And bugs still reach the players.</Big></FadeIn>
      </AbsoluteFill>
    </At>

    {/* the idea */}
    <At a={T.idea} b={T.test}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <FadeIn delay={s(d(n3, 'PLAYER'))}><Big size={120} style={{ letterSpacing: -4 }}>PLAYER TWO</Big></FadeIn>
        <FadeIn delay={s(d(n3, 'an AI'))}><Big size={46} color={C.sub} style={{ marginTop: 10 }}>an AI that tests your game the way a player would</Big></FadeIn>
        <div style={{ display: 'flex', gap: 26, marginTop: 70, alignItems: 'center' }}>
          {STEPS.map(([t, word], i) => (
            <React.Fragment key={t}>
              {i > 0 && <FadeIn delay={s(d(n3, word))}><span style={{ fontFamily: MONO, fontSize: 40, color: C.sub }}>→</span></FadeIn>}
              <FadeIn delay={s(d(n3, word))}>
                <div style={{ padding: '18px 32px', border: `2px solid ${i === 3 ? C.ok : C.line}`, borderRadius: 16, fontFamily: SANS, fontWeight: 600, fontSize: 40, color: i === 3 ? C.ok : C.text }}>{t}</div>
              </FadeIn>
            </React.Fragment>
          ))}
        </div>
      </AbsoluteFill>
    </At>

    {/* the test: a real game, screen and keyboard only */}
    <At a={T.test} b={T.fight}>
      <Box top={90} w={1920} h={740}><Vid f="v5/think.mp4" w={1920} h={740} /></Box>
      <Tag color={C.key}>LIVE TEST · recorded on our laptop, 8 Nov 2026</Tag>
      <Caption top={850} delay={d(n4, 'Doom')}>a real game: Doom (Freedoom, open source) · left: the game · right: our dashboard</Caption>
      <Caption top={900} delay={d(n4, 'The AI')} color={C.key}>the AI gets no code and no game data · only the screen and a keyboard</Caption>
    </At>

    {/* it plays */}
    <At a={T.fight} b={T.open}>
      <Box top={90} w={1920} h={740}><Vid f="v5/fight.mp4" w={1920} h={740} from={4} /></Box>
      <Tag color={C.key}>LIVE TEST · 2× speed</Tag>
      <Caption top={850} delay={d(n5, 'The player')}>the player is H, a computer-use agent · it attacks, takes hits, keeps testing</Caption>
    </At>

    {/* the bug, shown plainly */}
    <At a={T.open} b={T.sky}>
      <Box top={90} w={1920} h={740}><Vid f="v5/open.mp4" w={1920} h={740} /></Box>
      <Tag color={C.key}>LIVE TEST · real time</Tag>
      <Caption top={850} delay={d(n6, 'Invulnerability')}>H picks up invulnerability: the game must switch the whole view to grey</Caption>
    </At>
    <At a={T.sky} b={T.proven}>
      <div style={{ position: 'absolute', top: 70, left: 330, width: 1067, height: 800 }}>
        <Img src={staticFile('sky_before.png')} style={{ width: 1067, height: 800 }} />
        <FadeIn delay={s(0.2)} style={{ position: 'absolute', left: SKY.x * 1.333, top: SKY.y * 1.333, width: SKY.w * 1.333, height: SKY.h * 1.333, border: `5px solid ${C.key}`, borderRadius: 10 }}><span /></FadeIn>
      </div>
      <div style={{ position: 'absolute', top: 120, left: 1420, width: 440 }}>
        <FadeIn delay={s(0.3)}><Big size={54} color={C.key} style={{ textAlign: 'left' }}>The sky stays red.</Big></FadeIn>
        <FadeIn delay={s(1.4)}><Big size={34} color={C.sub} style={{ textAlign: 'left', marginTop: 24 }}>Everything else turned grey. The sky ignores the power-up.</Big></FadeIn>
        <FadeIn delay={s(3.0)}><Big size={34} color={C.text} style={{ textAlign: 'left', marginTop: 24 }}>In Doom's code since 1993. Still in the versions people play today.</Big></FadeIn>
      </div>
      <Tag color={C.key}>THE BUG · a frame of the same scene</Tag>
    </At>

    {/* proven */}
    <At a={T.proven} b={T.ask}>
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
      <FadeIn delay={s(d(n7, 'Then'))} style={{ position: 'absolute', top: 110, left: 940 }}>
        <div style={{ width: 920, height: 355, overflow: 'hidden', border: `2px solid ${C.line}` }}><Vid f="v5/verify.mp4" w={920} h={355} /></div>
        <div style={{ fontFamily: MONO, fontSize: 22, color: C.sub, marginTop: 12 }}>our verifier replays H's exact moves (6× speed)</div>
        <div style={{ fontFamily: MONO, fontSize: 24, color: C.text, marginTop: 30 }}>the engine's own log, never shown to H:</div>
        <div style={{ fontFamily: MONO, fontSize: 26, color: C.key, marginTop: 8 }}>render sky_ignores_colormap</div>
        <div style={{ fontFamily: MONO, fontSize: 30, color: C.ok, marginTop: 24 }}>verified</div>
      </FadeIn>
    </At>

    {/* fixed by Devin */}
    <At a={T.ask} b={T.pr}>
      <Box top={80} w={882} h={900}><Vid f="v5/ask.mp4" w={882} h={900} from={3.5} /></Box>
      <Tag color={C.key}>FIX · the dashboard reads the bug aloud, the developer answers by voice · real time</Tag>
    </At>
    <At a={T.pr} b={T.proof}>
      <Box top={80} w={1600} h={880}><Img src={staticFile('v4/pr.png')} style={{ width: 1600 }} /></Box>
      <Tag color={C.key}>FIX · Devin's pull request on GitHub (chocolate-doom#5), opened and merged by Devin</Tag>
    </At>

    {/* fixed, proven again */}
    <At a={T.proof} b={T.ba}>
      <Box top={80} w={1100} h={862}><Vid f="v5/proof.mp4" w={1100} h={862} from={0.6} /></Box>
      <Tag color={C.key}>PROOF · the rebuilt game, same scenario replayed · real time</Tag>
    </At>
    <At a={T.ba} b={T.kid}>
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

    {/* kid mode */}
    <At a={T.kid} b={T.talk}>
      <Tag color={C.key}>KID MODE</Tag>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <FadeIn delay={s(d(n10, 'In kid'))}><Big size={44} color={C.sub}>kid mode</Big></FadeIn>
        <FadeIn delay={s(d(n10, 'Pixel'))}><Big size={130} color={C.ok} style={{ letterSpacing: -4, marginTop: 6 }}>Pixel</Big></FadeIn>
        <FadeIn delay={s(d(n10, 'a game buddy'))}><Big size={48} style={{ marginTop: 6 }}>a game buddy for children</Big></FadeIn>
        <div style={{ display: 'flex', gap: 28, marginTop: 70 }}>
          {([['H', 'sees the screen', 'sees'], ['Gladia', 'hears your voice', 'hears'], ['ElevenLabs', 'is the voice that answers', 'answers']] as const).map(([who, what, word]) => (
            <FadeIn key={who} delay={s(d(n10, word))}>
              <div style={{ padding: '18px 30px', border: `2px solid ${C.line}`, borderRadius: 16, textAlign: 'center' }}>
                <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 38, color: C.text }}>{who}</div>
                <div style={{ fontFamily: MONO, fontSize: 24, color: C.sub, marginTop: 6 }}>{what}</div>
              </div>
            </FadeIn>
          ))}
        </div>
      </AbsoluteFill>
    </At>
    <At a={T.talk} b={T.vision}>
      <KidTalk />
      <Tag color={C.key}>KID MODE · recorded on our laptop · a team member talks to Pixel, real voices, real time</Tag>
    </At>

    {/* the potential */}
    <At a={T.vision} b={T.end}>
      <Tag color={C.key}>VISION · not a measured result</Tag>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 34 }}>
        <FadeIn delay={s(d(n11, 'That'))}><Big size={42} color={C.sub}>Tonight: one bug, one laptop, one night.</Big></FadeIn>
        <FadeIn delay={s(d(n11, 'Now point'))}><Big size={96} color={C.ok} style={{ letterSpacing: -3 }}>a $200B industry</Big></FadeIn>
        <FadeIn delay={s(d(n11, 'Hundreds'))}><Big size={52}>hundreds of AI testers on every build of a game as big as GTA 6</Big></FadeIn>
        <FadeIn delay={s(d(n11, 'Every bug'))}><Big size={52}>every bug: a video, a proof and a fix to review</Big></FadeIn>
        <FadeIn delay={s(d(n11, 'And for'))}><Big size={52} color={C.key}>and for every player, a buddy inside the game</Big></FadeIn>
      </AbsoluteFill>
    </At>

    {/* end */}
    <At a={T.end} b={T.total}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <FadeIn delay={s(0.2)}><Big size={140} style={{ letterSpacing: -5 }}>PLAYER TWO</Big></FadeIn>
        <FadeIn delay={s(d(n12, 'Your'))}><Big size={46} color={C.sub} style={{ marginTop: 8 }}>Your game's toughest tester.</Big></FadeIn>
        <FadeIn delay={s(d(n12, 'and its'))}><Big size={46} color={C.ok} style={{ marginTop: 4 }}>And its best friend.</Big></FadeIn>
        <FadeIn delay={s(2.4)}><div style={{ fontFamily: MONO, fontSize: 24, color: C.sub, marginTop: 60 }}>built with Devin · powered by H · Gladia · ElevenLabs · Linkup · Stripe</div></FadeIn>
      </AbsoluteFill>
    </At>

    <Voice file="n1" vo={n1 as VO} at={s(T.market + VO_LEAD)} />
    <Voice file="n2" vo={n2 as VO} at={s(T.problem + VO_LEAD)} />
    <Voice file="n3" vo={n3 as VO} at={s(T.idea + VO_LEAD)} />
    <Voice file="n4" vo={n4 as VO} at={s(T.test + VO_LEAD)} />
    <Voice file="n5" vo={n5 as VO} at={s(T.fight + VO_LEAD)} />
    <Voice file="n6" vo={n6 as VO} at={s(T.open + VO_LEAD)} />
    <Voice file="n7" vo={n7 as VO} at={s(T.proven + VO_LEAD)} />
    <Voice file="n8" vo={n8 as VO} at={s(T.ask + VO_LEAD)} />
    <Voice file="n9" vo={n9 as VO} at={s(T.proof + VO_LEAD)} />
    <Voice file="n10" vo={n10 as VO} at={s(T.kid + VO_LEAD)} />
    <Voice file="n11" vo={n11 as VO} at={s(T.vision + VO_LEAD)} />
    <Voice file="n12" vo={n12 as VO} at={s(T.end + VO_LEAD)} />
  </AbsoluteFill>
)
export { KID_LEN }
