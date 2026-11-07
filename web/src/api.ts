import mock from '../../docs/api-mock.json'
import type { SseEvent, Snapshot, VoiceIntent } from './types'

/** Set VITE_API_BASE (e.g. http://localhost:8000) to switch from docs/api-mock.json to the live API. */
export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')
export const USING_MOCK = API_BASE === ''

const MOCK = mock as unknown as Record<string, unknown>

async function get<T>(path: string): Promise<T> {
  if (USING_MOCK) return structuredClone(MOCK[`GET ${path}`]) as T
  const r = await fetch(`${API_BASE}${path}`)
  if (!r.ok) throw new Error(`GET ${path}: HTTP ${r.status}`)
  return (await r.json()) as T
}

export async function loadSnapshot(): Promise<Snapshot> {
  const [session, actions, notes, findings, fixes, narrations, debrief, placement, plans, profile, report] =
    await Promise.all([
      get<Snapshot['session']>('/api/session'),
      get<Snapshot['actions']>('/api/actions'),
      get<Snapshot['notes']>('/api/notes'),
      get<Snapshot['findings']>('/api/findings'),
      get<Snapshot['fixes']>('/api/fixes'),
      get<Snapshot['narrations']>('/api/narrations'),
      get<Snapshot['debrief']>('/api/debrief'),
      get<Snapshot['placement']>('/api/placement'),
      get<Snapshot['plans']>('/api/plans'),
      get<Snapshot['profile']>('/api/parent/profile'),
      get<Snapshot['report']>('/api/parent/report'),
    ])
  return { session, actions, notes, findings, fixes, narrations, debrief, placement, plans, profile, report }
}

/** Live: SSE from /api/events. Mock: replays the mock events in a loop so the UI moves. */
const SSE_TYPES = [
  'session.state', 'agent.action', 'agent.note', 'finding.new', 'finding.updated', 'fix.updated',
  'voice.narration', 'voice.transcript', 'voice.intent', 'debrief.ready', 'placement.ready',
  'plan.updated', 'error',
]

export function subscribe(onEvent: (e: SseEvent) => void): () => void {
  if (!USING_MOCK) {
    const es = new EventSource(`${API_BASE}/api/events`)
    // the stream names each event (`event: <type>`), so onmessage alone would never fire
    // the native connection `error` event shares the name of our `error` type but has no data
    const handle = (m: Event) => {
      const data = (m as MessageEvent).data
      if (typeof data === 'string' && data) onEvent(JSON.parse(data) as SseEvent)
    }
    es.onmessage = handle
    for (const t of SSE_TYPES) es.addEventListener(t, handle)
    return () => es.close()
  }
  // the mock 'error' event would pin the error banner on every view; skip it in the replay
  const events = (MOCK['GET /api/events'] as SseEvent[]).filter((e) => e.type !== 'error')
  let i = 0
  const timer = setInterval(() => {
    onEvent(structuredClone(events[i % events.length]))
    i += 1
  }, 1500)
  return () => clearInterval(timer)
}

async function post(path: string, body?: unknown): Promise<void> {
  if (USING_MOCK) return
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`POST ${path}: HTTP ${r.status}`)
}

export const sendIntent = (intent: VoiceIntent) => post('/api/intent', intent)
export const stopSession = () => post('/api/stop')

export async function checkout(plan: string): Promise<string | null> {
  if (USING_MOCK) return null
  const r = await fetch(`${API_BASE}/api/billing/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan }),
  })
  if (!r.ok) throw new Error(`checkout: HTTP ${r.status}`)
  return ((await r.json()) as { url: string }).url
}

/** Media URL, or null in mock mode (mock paths point to files that do not exist). */
export const media = (path?: string | null) =>
  !path || USING_MOCK ? null : `${API_BASE}/media/${path.replace(/^\//, '')}`
