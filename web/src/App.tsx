import { useEffect, useReducer, useState } from 'react'
import { USING_MOCK, checkout, loadSnapshot, media, sendIntent, stopSession, subscribe } from './api'
import { initialState, reducer, type Voice } from './state'
import type { Finding, FixAttempt, Intent, Narration, Snapshot } from './types'

type Tab = 'live' | 'bugs' | 'debrief' | 'plans' | 'parent'
const TABS: [Tab, string][] = [
  ['live', 'Live'],
  ['bugs', 'Bugs & fixes'],
  ['debrief', 'Debrief'],
  ['plans', 'Plans'],
  ['parent', 'Parent'],
]

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [tab, setTab] = useState<Tab>(() => (location.hash.slice(1) as Tab) || 'live')

  useEffect(() => {
    loadSnapshot()
      .then((snap) => dispatch({ type: 'loaded', snap }))
      .catch((e: Error) => dispatch({ type: 'error', message: e.message }))
    return subscribe((event) => dispatch({ type: 'event', event }))
  }, [])

  useEffect(() => {
    location.hash = tab
  }, [tab])

  const intent = (i: Intent, finding_id?: string, text = '') => {
    const body = { intent: i, source: 'button' as const, finding_id: finding_id ?? null, text }
    dispatch({ type: 'intent', intent: body })
    sendIntent(body).catch((e: Error) => dispatch({ type: 'error', message: e.message }))
    if (i === 'stop') stopSession().catch(() => undefined)
  }

  const snap = state.snap
  return (
    <div className="app">
      <header>
        <div className="brand">
          PLAYER <span>TWO</span>
        </div>
        {snap && <SessionBar snap={snap} />}
        <nav>
          {TABS.map(([id, label]) => (
            <button key={id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
      </header>
      {state.error && <div className="error">{state.error}</div>}
      {!snap ? (
        <main className="loading">Loading…</main>
      ) : (
        <main>
          {tab === 'live' && <LiveView snap={snap} voice={state.voice} onIntent={intent} />}
          {tab === 'bugs' && <BugsView snap={snap} onIntent={intent} />}
          {tab === 'debrief' && <DebriefView snap={snap} />}
          {tab === 'plans' && <PlansView snap={snap} />}
          {tab === 'parent' && <ParentView snap={snap} />}
        </main>
      )}
    </div>
  )
}

function SessionBar({ snap }: { snap: Snapshot }) {
  const s = snap.session
  const mode = USING_MOCK ? 'MOCK DATA' : s.live ? 'LIVE' : 'RECORDED'
  return (
    <div className="session">
      <span className={`badge ${mode === 'LIVE' ? 'live' : 'rec'}`}>{mode}</span>
      <span>{s.game}</span>
      <span className="dim">{s.map}</span>
      <span className={`state st-${s.state}`}>{s.state.replace('_', ' ')}</span>
      <span className="dim">
        {s.speed} · step {Math.max(s.steps, snap.actions.at(-1)?.step ?? 0)} ·{' '}
        {Math.max(s.findings, snap.findings.length)} findings
      </span>
    </div>
  )
}

// ---------------------------------------------------------------- live

function LiveView({ snap, voice, onIntent }: { snap: Snapshot; voice: Voice; onIntent: (i: Intent) => void }) {
  const s = snap.session
  const last = snap.actions[snap.actions.length - 1]
  const shot = media(last?.screenshot)
  return (
    <div className="live-grid">
      <section className="panel agent">
        <h2>Agent view</h2>
        {s.share_url && !USING_MOCK ? (
          <iframe title="H live view" src={s.share_url} />
        ) : shot ? (
          <img src={shot} alt="latest agent screenshot" />
        ) : (
          <div className="placeholder">
            <div>H desktop live view</div>
            <div className="dim">{USING_MOCK ? 'mock mode: no stream' : 'waiting for the first frame'}</div>
          </div>
        )}
        {last && (
          <div className="caption">
            step {last.step} · {last.kind} {last.keys.join('+')} — {last.description}
          </div>
        )}
      </section>
      <section className="panel side">
        <VoicePanel voice={voice} onIntent={onIntent} />
        <h2>Action timeline</h2>
        <ol className="timeline">
          {[...snap.actions].reverse().map((a) => (
            <li key={a.step}>
              <span className="t">{fmtS(a.t_session_s)}</span>
              <span className="k">{a.keys.join('+') || a.kind}</span>
              <span>{a.description}</span>
            </li>
          ))}
        </ol>
        <h2>Tester notes</h2>
        <ul className="notes">
          {snap.notes.map((n) => (
            <li key={n.ts}>
              <span className="t">{fmtS(n.t_session_s)}</span> {n.text}
              {n.tags.map((t) => (
                <span key={t} className="tag">
                  {t}
                </span>
              ))}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

const INTENTS: Intent[] = ['fix', 'skip', 'explain', 'yes', 'no', 'stop']

function VoicePanel({ voice, onIntent }: { voice: Voice; onIntent: (i: Intent) => void }) {
  const fresh = Date.now() - voice.at < 4000
  return (
    <div className="voice">
      <div className={`mic ${fresh ? 'hot' : ''}`} aria-label="voice activity" />
      <div className="voice-text">
        {voice.speaking && <div className="speaking">{voice.speaking.text}</div>}
        <div className={voice.final ? '' : 'dim'}>{voice.transcript ? `“${voice.transcript}”` : 'Say “fix it”, “skip”, “stop”…'}</div>
        {voice.intent && (
          <div className="intent">
            intent: <b>{voice.intent.intent}</b> ({voice.intent.source})
          </div>
        )}
      </div>
      <div className="intent-buttons">
        {INTENTS.map((i) => (
          <button key={i} className={i === 'stop' ? 'danger' : ''} onClick={() => onIntent(i)}>
            {i}
          </button>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- bugs

function BugsView({ snap, onIntent }: { snap: Snapshot; onIntent: (i: Intent, f?: string) => void }) {
  if (!snap.findings.length) return <div className="empty">No findings yet.</div>
  return (
    <div className="cards">
      {snap.findings.map((f) => (
        <BugCard
          key={f.id}
          f={f}
          fix={snap.fixes.filter((x) => x.finding_id === f.id).at(-1)}
          narration={snap.narrations.find((n) => n.finding_id === f.id)}
          onIntent={onIntent}
        />
      ))}
    </div>
  )
}

function BugCard({
  f,
  fix,
  narration,
  onIntent,
}: {
  f: Finding
  fix?: FixAttempt
  narration?: Narration
  onIntent: (i: Intent, f?: string) => void
}) {
  const clip = f.evidence.clip
  const src = media(clip?.path)
  return (
    <article className={`card sev-${f.severity}`}>
      <div className="card-head">
        <span className={`status s-${f.status}`}>{f.status}</span>
        <span className="sev">{f.severity}</span>
        <h3>{f.title}</h3>
        <div className="dim">{f.location}</div>
      </div>
      <div className="card-body">
        <div className="clip">
          {src ? (
            <video
              src={`${src}#t=${clip!.start_s},${clip!.end_s}`}
              controls
              muted
              onLoadedMetadata={(e) => (e.currentTarget.playbackRate = clip!.speed)}
            />
          ) : (
            <div className="placeholder small">clip {clip ? `${fmtS(clip.start_s)}–${fmtS(clip.end_s)}` : 'pending'}</div>
          )}
          {clip && <span className="speed">RECORDED · {clip.speed}× speed</span>}
        </div>
        <div className="repro">
          <ol>
            {f.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <div>
            <b>Expected:</b> {f.expected}
          </div>
          <div>
            <b>Actual:</b> {f.actual}
          </div>
          {narration && <div className="narration">{narration.text}</div>}
          {f.evidence.log_excerpt.length > 0 && (
            <details>
              <summary>event log ({f.evidence.log_excerpt.length})</summary>
              <pre>{f.evidence.log_excerpt.map((e) => JSON.stringify(e)).join('\n')}</pre>
            </details>
          )}
        </div>
      </div>
      <div className="card-actions">
        {!fix && (
          <>
            <button className="primary" onClick={() => onIntent('fix', f.id)}>
              Fix?
            </button>
            <button onClick={() => onIntent('explain', f.id)}>Explain</button>
            <button onClick={() => onIntent('skip', f.id)}>Skip</button>
          </>
        )}
        {fix?.result === 'pr_open' && (
          <>
            <button className="primary" onClick={() => onIntent('yes', f.id)}>
              Merge
            </button>
            <button onClick={() => onIntent('no', f.id)}>Not yet</button>
          </>
        )}
      </div>
      {fix && <DevinPanel fix={fix} />}
    </article>
  )
}

function DevinPanel({ fix }: { fix: FixAttempt }) {
  const c = fix.comparison
  return (
    <div className="devin">
      <div className="devin-head">
        <b>Devin</b>
        <span className={`fix r-${fix.result}`}>{fix.result.replace('_', ' ')}</span>
        <span className="dim">round {fix.round}</span>
        {fix.devin_session_url && (
          <a href={fix.devin_session_url} target="_blank" rel="noreferrer">
            session
          </a>
        )}
        {fix.pr_url && (
          <a href={fix.pr_url} target="_blank" rel="noreferrer">
            pull request
          </a>
        )}
        {fix.acus != null && <span className="dim">{fix.acus} ACU</span>}
      </div>
      {c && (
        <div className="compare">
          <div>
            <div className="dim">Devin</div>
            <pre>{c.devin_diff}</pre>
          </div>
          <div>
            <div className="dim">Upstream ({c.upstream_fix_ref})</div>
            <pre>{c.upstream_diff}</pre>
          </div>
          <div className="verdict">
            <b>{c.verdict.replaceAll('_', ' ')}</b> — {c.summary}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- debrief

function DebriefView({ snap }: { snap: Snapshot }) {
  const d = snap.debrief
  return (
    <div className="debrief-grid">
      <section className="panel">
        <h2>Deaths & retries heatmap</h2>
        <Heatmap cells={d.heatmap} bounds={d.map_bounds} />
        <div className="dim">
          {d.maps.join(', ')} · {fmtS(d.duration_s)} played
        </div>
      </section>
      <section className="panel">
        <h2>Design notes</h2>
        <ul className="notes">
          {d.notes.map((n) => (
            <li key={n.ts}>
              {n.text}
              {n.tags.map((t) => (
                <span key={t} className="tag">
                  {t}
                </span>
              ))}
            </li>
          ))}
        </ul>
        <h2>Suggestions</h2>
        <ul>
          {d.suggestions.map((s) => (
            <li key={s.finding_id + s.suggestion}>{s.suggestion}</li>
          ))}
        </ul>
        <h2>References</h2>
        <ul>
          {d.references.map((r) => (
            <li key={r.url}>
              <a href={r.url} target="_blank" rel="noreferrer">
                {r.title}
              </a>
            </li>
          ))}
        </ul>
      </section>
      <section className="panel wide">
        <h2>Product placement</h2>
        <div className="cards">
          {snap.placement.map((p) => (
            <div key={p.id} className="card">
              <h3>{p.name}</h3>
              <div className="dim">
                {p.surface} · {p.location} · {fmtS(p.screen_time_s)} on screen · visibility{' '}
                {Math.round(p.visibility * 100)}%
              </div>
              <ul>
                {p.brand_candidates.map((b) => (
                  <li key={b.name}>
                    <b>{b.name}</b> — {b.rationale}
                  </li>
                ))}
              </ul>
              <div className="disclaimer">{p.disclaimer}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function Heatmap({ cells, bounds }: { cells: { x: number; y: number; deaths: number; retries: number }[]; bounds?: [number, number, number, number] | null }) {
  if (!cells.length) return <div className="placeholder small">no data</div>
  const [x0, y0, x1, y1] = bounds ?? [
    Math.min(...cells.map((c) => c.x)) - 64,
    Math.min(...cells.map((c) => c.y)) - 64,
    Math.max(...cells.map((c) => c.x)) + 64,
    Math.max(...cells.map((c) => c.y)) + 64,
  ]
  const max = Math.max(1, ...cells.map((c) => c.deaths * 3 + c.retries))
  return (
    <svg className="heatmap" viewBox={`${x0} ${-y1} ${x1 - x0} ${y1 - y0}`} preserveAspectRatio="xMidYMid meet">
      <rect x={x0} y={-y1} width={x1 - x0} height={y1 - y0} className="hm-bg" />
      {cells.map((c) => {
        const w = (c.deaths * 3 + c.retries) / max
        return <circle key={`${c.x},${c.y}`} cx={c.x} cy={-c.y} r={(x1 - x0) / 25 + w * ((x1 - x0) / 12)} fill={`rgba(255,${Math.round(180 - 150 * w)},40,${0.35 + 0.5 * w})`} />
      })}
    </svg>
  )
}

// ---------------------------------------------------------------- plans & parent

function PlansView({ snap }: { snap: Snapshot }) {
  const [msg, setMsg] = useState('')
  const buy = (id: string) =>
    checkout(id)
      .then((url) => (url ? (location.href = url) : setMsg('Mock mode: Stripe Checkout opens here in live mode.')))
      .catch((e: Error) => setMsg(e.message))
  return (
    <div>
      <div className="plans">
        {snap.plans.map((p) => (
          <div key={p.id} className={`plan ${p.active ? 'active' : ''}`}>
            <h3>{p.name}</h3>
            <div className="price">
              €{p.price_eur_month}
              <span>/month</span>
            </div>
            <div className="dim">{p.tagline}</div>
            <ul>
              {p.features.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
            <button className="primary" disabled={p.active} onClick={() => buy(p.id)}>
              {p.active ? 'Current plan' : 'Choose'}
            </button>
          </div>
        ))}
      </div>
      {msg && <div className="dim center">{msg}</div>}
      <div className="dim center">Stripe test mode. No real payment.</div>
    </div>
  )
}

function ParentView({ snap }: { snap: Snapshot }) {
  const p = snap.profile
  return (
    <div className="debrief-grid">
      <section className="panel">
        <h2>Child profile</h2>
        <div className="profile">
          <div className="big">
            {p.nickname}, {p.age}
          </div>
          <div>Likes: {p.interests.join(', ')}</div>
          <div>Avoid: {p.fears.join(', ')}</div>
          <div>Learning: {p.learning_goals.join(', ')}</div>
        </div>
      </section>
      <section className="panel wide">
        <h2>Morning report</h2>
        <table className="report">
          <thead>
            <tr>
              <th>Game</th>
              <th>Scary</th>
              <th>Educational</th>
              <th>Fit</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {snap.report.map((g) => (
              <tr key={g.game_url}>
                <td>
                  <a href={g.game_url} target="_blank" rel="noreferrer">
                    {g.game_title}
                  </a>
                  {g.purchase_required && <span className="tag">paid</span>}
                </td>
                <td>{dots(g.scary)}</td>
                <td>{dots(g.educational)}</td>
                <td>{dots(g.fit)}</td>
                <td>{g.reasons.join(' · ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

const dots = (n: number) => '●'.repeat(n) + '○'.repeat(5 - n)
const fmtS = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
