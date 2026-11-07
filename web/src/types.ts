// Mirrors app/contracts.py (contracts v1.0). Only the fields the dashboard reads.
export type SessionState =
  | 'idle' | 'exploring' | 'verifying' | 'presenting' | 'awaiting_approval' | 'fixing'
  | 'reverifying' | 'debriefing' | 'stopped' | 'done' | 'error'

export interface SessionInfo {
  id: string; game: string; build: string; map?: string | null; state: SessionState
  started_at: string; h_session_id?: string | null; share_url?: string | null; speed: string
  live: boolean; steps: number; findings: number
}
export interface AgentAction {
  session_id: string; step: number; ts: string; t_session_s: number; kind: string; keys: string[]
  duration_ms?: number | null; description: string; screenshot?: string | null
}
export interface AgentNote {
  session_id: string; ts: string; t_session_s: number; text: string; tags: string[]
  location?: string | null; screenshot?: string | null
}
export interface Clip { path: string; start_s: number; end_s: number; speed: number }
export interface GameEvent { tic: number; map?: string; type: string; data?: Record<string, unknown> }
export interface Finding {
  id: string; session_id: string; kind: string; title: string; location: string; steps: string[]
  expected: string; actual: string; severity: string
  evidence: { screenshots: string[]; clip?: Clip | null; log_excerpt: GameEvent[]; share_url?: string | null }
  known_bug_ref?: string | null; status: string; reported_at: string; t_session_s?: number | null
  suggested_change?: string | null
}
export interface FixAttempt {
  id: string; finding_id: string; devin_session_id: string; devin_session_url?: string | null
  pr_url?: string | null; round: number; result: string; started_at: string; finished_at?: string | null
  acus?: number | null; upstream_fix_ref?: string | null
  comparison?: { upstream_fix_ref: string; upstream_diff: string; devin_diff: string; verdict: string; summary: string } | null
}
export interface NarrationCue { at_s: number; clip_s: number; text: string }
export interface Narration {
  finding_id?: string | null; text: string; language: string; audio_path: string
  duration_s?: number | null; cues: NarrationCue[]
}
export interface HeatCell { x: number; y: number; deaths: number; retries: number }
export interface Citation { title: string; url: string; snippet?: string | null }
export interface DebriefReport {
  session_id: string; game: string; maps: string[]; duration_s: number
  map_bounds?: [number, number, number, number] | null; heatmap: HeatCell[]; notes: AgentNote[]
  suggestions: { finding_id: string; suggestion: string }[]; references: Citation[]; generated_at: string
}
export interface PlacementSpot {
  id: string; name: string; surface: string; location: string; screen_time_s: number
  visibility: number; screenshot?: string | null; audience?: string | null
  brand_candidates: { name: string; rationale: string; source?: Citation | null }[]; disclaimer: string
}
export interface Plan {
  id: string; name: string; tagline: string; price_eur_month: number; features: string[]
  stripe_price_id?: string | null; active: boolean
}
export interface ChildProfile {
  id: string; nickname: string; age: number; language: string; interests: string[]; fears: string[]
  learning_goals: string[]
}
export interface GameVerdict {
  profile_id: string; game_title: string; game_url: string; scary: number; educational: number
  fit: number; reasons: string[]; purchase_required: boolean; played_s?: number | null
}
export type Intent = 'fix' | 'skip' | 'explain' | 'stop' | 'yes' | 'no' | 'steer'
export interface VoiceIntent {
  intent: Intent; text?: string; language?: string | null; source: 'voice' | 'button'
  confidence?: number | null; finding_id?: string | null
}
export interface SseEvent { id: number; type: string; ts: string; session_id?: string | null; data: Record<string, unknown> }

export interface Snapshot {
  session: SessionInfo; actions: AgentAction[]; notes: AgentNote[]; findings: Finding[]
  fixes: FixAttempt[]; narrations: Narration[]; debrief: DebriefReport; placement: PlacementSpot[]
  plans: Plan[]; profile: ChildProfile; report: GameVerdict[]
}
