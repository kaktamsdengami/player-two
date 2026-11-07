import type { AgentAction, AgentNote, DebriefReport, Finding, FixAttempt, Narration, PlacementSpot, Plan, SessionInfo, SseEvent, Snapshot, VoiceIntent } from './types'

export interface Voice {
  transcript: string
  final: boolean
  intent: VoiceIntent | null
  speaking: Narration | null
  at: number
}

export interface State {
  snap: Snapshot | null
  voice: Voice
  error: string | null
}

export const initialState: State = {
  snap: null,
  voice: { transcript: '', final: true, intent: null, speaking: null, at: 0 },
  error: null,
}

export type Action =
  | { type: 'loaded'; snap: Snapshot }
  | { type: 'event'; event: SseEvent }
  | { type: 'error'; message: string }
  | { type: 'intent'; intent: VoiceIntent }

function upsert<T>(list: T[], item: T, key: (t: T) => string): T[] {
  const k = key(item)
  const i = list.findIndex((x) => key(x) === k)
  if (i === -1) return [...list, item]
  const next = list.slice()
  next[i] = item
  return next
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'loaded':
      return { ...state, snap: normalize(action.snap), error: null }
    case 'error':
      return { ...state, error: action.message }
    case 'intent':
      return { ...state, voice: { ...state.voice, intent: action.intent, at: Date.now() } }
    case 'event':
      return applyEvent(state, action.event)
  }
}

// SSE payloads may omit fields that have defaults in app/contracts.py; fill them here.
const asFinding = (d: Record<string, unknown>): Finding => {
  const f = d as unknown as Finding
  const ev = (f.evidence ?? {}) as Partial<Finding['evidence']>
  return {
    ...f,
    steps: f.steps ?? [],
    evidence: { ...ev, screenshots: ev.screenshots ?? [], log_excerpt: ev.log_excerpt ?? [] },
  }
}
const asAction = (d: Record<string, unknown>): AgentAction => {
  const a = d as unknown as AgentAction
  return { ...a, keys: a.keys ?? [], description: a.description ?? '' }
}
const asNote = (d: Record<string, unknown>): AgentNote => {
  const n = d as unknown as AgentNote
  return { ...n, tags: n.tags ?? [] }
}

const asSpot = (d: Record<string, unknown>): PlacementSpot => {
  const p = d as unknown as PlacementSpot
  return { ...p, brand_candidates: p.brand_candidates ?? [] }
}
const asPlan = (d: Record<string, unknown>): Plan => {
  const p = d as unknown as Plan
  return { ...p, features: p.features ?? [] }
}
type Raw = Record<string, unknown>
export const normalize = (s: Snapshot): Snapshot => ({
  ...s,
  actions: s.actions.map((a) => asAction(a as unknown as Raw)),
  notes: s.notes.map((n) => asNote(n as unknown as Raw)),
  findings: s.findings.map((f) => asFinding(f as unknown as Raw)),
  placement: s.placement.map((p) => asSpot(p as unknown as Raw)),
  plans: s.plans.map((p) => asPlan(p as unknown as Raw)),
})

export function applyEvent(state: State, e: SseEvent): State {
  const snap = state.snap
  if (!snap) return state
  const d = e.data
  switch (e.type) {
    case 'session.state':
      return { ...state, snap: { ...snap, session: { ...snap.session, ...(d as Partial<SessionInfo>) } } }
    case 'agent.action':
      return {
        ...state,
        snap: { ...snap, actions: upsert(snap.actions, asAction(d), (a) => String(a.step)) },
      }
    case 'finding.new':
    case 'finding.updated':
      return { ...state, snap: { ...snap, findings: upsert(snap.findings, asFinding(d), (f) => f.id) } }
    case 'fix.updated':
      return { ...state, snap: { ...snap, fixes: upsert(snap.fixes, d as unknown as FixAttempt, (f) => f.id) } }
    case 'agent.note':
      return { ...state, snap: { ...snap, notes: upsert(snap.notes, asNote(d), (n) => n.ts) } }
    case 'debrief.ready':
      return { ...state, snap: { ...snap, debrief: { ...snap.debrief, ...(d as unknown as DebriefReport) } } }
    case 'placement.ready':
      return {
        ...state,
        snap: { ...snap, placement: upsert(snap.placement, asSpot(d), (p) => p.id) },
      }
    case 'plan.updated':
      return { ...state, snap: { ...snap, plans: upsert(snap.plans, asPlan(d), (p) => p.id) } }
    case 'voice.transcript':
      return {
        ...state,
        voice: { ...state.voice, transcript: String(d.text ?? ''), final: Boolean(d.final), at: Date.now() },
      }
    case 'voice.intent':
      return { ...state, voice: { ...state.voice, intent: d as unknown as VoiceIntent, at: Date.now() } }
    case 'voice.narration':
      return { ...state, voice: { ...state.voice, speaking: d as unknown as Narration, at: Date.now() } }
    case 'error':
      return { ...state, error: String(d.message ?? 'error') }
    default:
      return state
  }
}
