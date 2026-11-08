import mock from '../../docs/api-mock.json'
import type { SseEvent, Snapshot, VoiceIntent } from './types'

/** Set VITE_API_BASE (e.g. http://localhost:8000) to switch from docs/api-mock.json to the live API;
 * `same-origin` when app.main serves the built dashboard itself (the public watch link). */
const RAW_BASE = import.meta.env.VITE_API_BASE ?? ''
export const API_BASE = RAW_BASE === 'same-origin' ? '' : RAW_BASE.replace(/\/$/, '')
export const USING_MOCK = RAW_BASE === ''
/** Opened from anywhere but the laptop itself (the tunnel link): watch only, no controls. */
export const VIEW_ONLY = !USING_MOCK && !['localhost', '127.0.0.1'].includes(window.location.hostname)

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

/** POST JSON; errors carry the API's `detail` (e.g. "no session") instead of a bare status code. */
async function post<T = unknown>(path: string, body?: unknown): Promise<T | null> {
  if (USING_MOCK) return null
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = (await r.json().catch(() => null)) as { detail?: unknown } | null
  if (!r.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : `HTTP ${r.status}`
    throw new Error(`${path.replace('/api/', '')}: ${detail}`)
  }
  return data as T
}

export const sendIntent = (intent: VoiceIntent) => post('/api/intent', intent)
export const stopSession = () => post('/api/stop')
export const getPtt = () => get<{ on: boolean }>('/api/ptt')
export const setPtt = (on: boolean) => post<{ on: boolean }>('/api/ptt', { on })
/** No `mode`: the server runs its configured mode (live on the stage laptop, recorded elsewhere). */
export const startSession = (plan: string, preset: string) =>
  post<{ started: boolean; live: boolean }>('/api/session/start', { plan: plan.trim() || null, preset })

export const checkout = async (plan: string): Promise<string | null> =>
  (await post<{ url: string }>('/api/billing/checkout', { plan }))?.url ?? null

/** Media URL, or null in mock mode (mock paths point to files that do not exist). */
export const media = (path?: string | null) =>
  !path || USING_MOCK ? null : `${API_BASE}/media/${path.replace(/^\//, '')}`
