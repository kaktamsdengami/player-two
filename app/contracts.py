"""Shared data contracts for PLAYER TWO (frozen in T01, see docs/CONTRACTS.md).

Changing a model here is a contract change: note it in docs/HANDOFF.md and in the issue.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACTS_VERSION = "1.0"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


# ---------------------------------------------------------------- game log (oracle)


class PlayerState(Model):
    x: float
    y: float
    z: float = 0.0
    angle: float = 0.0
    health: int | None = None
    armor: int | None = None
    sector: int | None = None


class ActorRef(Model):
    id: int
    type: str
    x: float | None = None
    y: float | None = None
    z: float | None = None
    health: int | None = None


class GameEvent(Model):
    """One JSONL line written by the QA build's event log."""

    tic: int = Field(ge=0, description="game tic (Doom: 35 per game second)")
    t: float | None = Field(None, description="wall-clock seconds since the game started")
    map: str | None = None
    type: str = Field(description="e.g. player, damage, death, spawn, pickup, use, special, level")
    player: PlayerState | None = None
    actor: ActorRef | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class EventMatch(Model):
    """Matches one GameEvent. `where` maps dotted paths to a value or {op: value}.

    ops: eq, ne, gt, ge, lt, le, in, exists. Example: {"player.health": {"gt": 100}}.
    """

    type: str
    where: dict[str, Any] = Field(default_factory=dict)


class LogSignature(Model):
    """Deterministic proof of a bug in the event log; evaluated by agents/oracles.py."""

    description: str
    all_of: list[EventMatch] = Field(min_length=1)
    none_of: list[EventMatch] = Field(default_factory=list)
    within_tics: int | None = Field(None, ge=1, description="all matches inside this window")


class KnownBug(Model):
    """One entry of eval/known_bugs.yaml. Never shown to the tester agent."""

    id: str
    title: str
    source_url: str
    map: str | None = None
    steps: list[str]
    expected: str
    actual: str
    log_signature: LogSignature
    upstream_fix_ref: str | None = None
    visual: bool = True


# ---------------------------------------------------------------- agent


class ActionKind(StrEnum):
    key_press = "key_press"
    key_hold = "key_hold"
    click = "click"
    type_text = "type_text"
    wait = "wait"
    screenshot = "screenshot"
    tool_call = "tool_call"
    message = "message"
    other = "other"


class AgentAction(Model):
    session_id: str
    step: int = Field(ge=0)
    ts: datetime
    t_session_s: float = Field(ge=0, description="seconds since session start, for clip cuts")
    kind: ActionKind
    keys: list[str] = Field(default_factory=list)
    duration_ms: int | None = Field(None, ge=0)
    description: str = ""
    screenshot: str | None = None


class AgentNote(Model):
    """`note(text)` tool: observations for the debrief and placement scout."""

    session_id: str
    ts: datetime
    t_session_s: float = Field(ge=0)
    text: str
    tags: list[str] = Field(default_factory=list, description="e.g. confusing, too_hard, placement")
    location: str | None = None
    screenshot: str | None = None


# ---------------------------------------------------------------- findings and fixes


class FindingKind(StrEnum):
    bug = "bug"
    design = "design"
    placement = "placement"


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingStatus(StrEnum):
    suspected = "suspected"
    verified = "verified"
    presented = "presented"
    fixing = "fixing"
    fixed = "fixed"
    wontfix = "wontfix"


class Clip(Model):
    path: str
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    speed: float = Field(1.0, gt=0, description="playback speed vs recording (RECORDED · N×)")


class Evidence(Model):
    screenshots: list[str] = Field(default_factory=list)
    clip: Clip | None = None
    log_excerpt: list[GameEvent] = Field(default_factory=list)
    share_url: str | None = None


class Finding(Model):
    id: str
    session_id: str
    kind: FindingKind = FindingKind.bug
    title: str
    location: str
    steps: list[str] = Field(min_length=1)
    expected: str
    actual: str
    severity: Severity = Severity.medium
    evidence: Evidence = Field(default_factory=Evidence)
    known_bug_ref: str | None = Field(None, description="set by the verifier, never by the tester")
    status: FindingStatus = FindingStatus.suspected
    reported_at: datetime
    t_session_s: float | None = Field(None, ge=0)
    suggested_change: str | None = None


class FixResult(StrEnum):
    queued = "queued"
    working = "working"
    pr_open = "pr_open"
    merged = "merged"
    fixed = "fixed"
    not_fixed = "not_fixed"
    failed = "failed"


class FixVerdict(StrEnum):
    same_approach = "same_approach"
    different_but_valid = "different_but_valid"
    incomplete = "incomplete"


class FixComparison(Model):
    upstream_fix_ref: str
    upstream_diff: str
    devin_diff: str
    verdict: FixVerdict
    summary: str


class FixAttempt(Model):
    id: str
    finding_id: str
    devin_session_id: str
    devin_session_url: str | None = None
    pr_url: str | None = None
    round: int = Field(1, ge=1, le=2, description="1 = first try, 2 = the single feedback round")
    result: FixResult = FixResult.queued
    started_at: datetime
    finished_at: datetime | None = None
    acus: float | None = Field(None, ge=0, description="cost if the Devin API exposes it")
    devin_says: str | None = Field(None, description="Devin's latest message, for the dashboard")
    upstream_fix_ref: str | None = None
    comparison: FixComparison | None = None


# ---------------------------------------------------------------- insights


class Citation(Model):
    title: str
    url: str
    snippet: str | None = None


class HeatCell(Model):
    x: float
    y: float
    deaths: int = Field(0, ge=0)
    retries: int = Field(0, ge=0)


class FindingSuggestion(Model):
    finding_id: str
    suggestion: str


class DebriefReport(Model):
    session_id: str
    game: str
    maps: list[str]
    duration_s: float = Field(ge=0)
    map_bounds: tuple[float, float, float, float] | None = Field(
        None, description="min_x, min_y, max_x, max_y in map units for the heatmap"
    )
    heatmap: list[HeatCell] = Field(default_factory=list)
    notes: list[AgentNote] = Field(default_factory=list)
    suggestions: list[FindingSuggestion] = Field(default_factory=list)
    references: list[Citation] = Field(default_factory=list)
    generated_at: datetime


class BrandCandidate(Model):
    name: str
    rationale: str
    sources: list[Citation] = Field(min_length=1)


class PlacementSpot(Model):
    id: str
    session_id: str
    name: str
    surface: Literal["screen", "poster", "wall", "item", "other"]
    location: str
    screen_time_s: float = Field(ge=0)
    visibility: float = Field(ge=0, le=1)
    screenshot: str | None = None
    audience: str | None = None
    brand_candidates: list[BrandCandidate] = Field(default_factory=list)
    disclaimer: str = "Suggestions only. No brand deal exists or is implied."


# ---------------------------------------------------------------- parent / kid modes


class ChildProfile(Model):
    """Stored locally only; never published or sent to the repo."""

    id: str
    nickname: str
    age: int = Field(ge=2, le=17)
    language: str = "en"
    interests: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    learning_goals: list[str] = Field(default_factory=list)


class GameVerdict(Model):
    profile_id: str
    game_title: str
    game_url: str
    scary: int = Field(ge=0, le=5)
    educational: int = Field(ge=0, le=5)
    fit: int = Field(ge=0, le=5)
    reasons: list[str] = Field(min_length=1)
    screenshots: list[str] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)
    purchase_required: bool = False
    played_s: float | None = Field(None, ge=0)


# ---------------------------------------------------------------- business


class PlanId(StrEnum):
    pro = "pro"
    parent = "parent"
    kid = "kid"


class Plan(Model):
    id: PlanId
    name: str
    tagline: str
    price_eur_month: float = Field(ge=0)
    features: list[str]
    stripe_price_id: str | None = None
    active: bool = False


# ---------------------------------------------------------------- voice


class Intent(StrEnum):
    fix = "fix"
    skip = "skip"
    explain = "explain"
    stop = "stop"
    yes = "yes"
    no = "no"
    steer = "steer"


class VoiceIntent(Model):
    intent: Intent
    text: str = ""
    language: str | None = None
    source: Literal["voice", "button"] = "voice"
    confidence: float | None = Field(None, ge=0, le=1)
    finding_id: str | None = None


class NarrationCue(Model):
    at_s: float = Field(ge=0, description="offset in the audio")
    clip_s: float = Field(ge=0, description="offset in the clip to show at that moment")
    text: str


class Narration(Model):
    finding_id: str | None = None
    text: str
    language: str = "en"
    audio_path: str
    duration_s: float | None = Field(None, ge=0)
    cues: list[NarrationCue] = Field(default_factory=list)


# ---------------------------------------------------------------- session + SSE


class SessionState(StrEnum):
    idle = "idle"
    exploring = "exploring"
    verifying = "verifying"
    presenting = "presenting"
    awaiting_approval = "awaiting_approval"
    fixing = "fixing"
    reverifying = "reverifying"
    debriefing = "debriefing"
    stopped = "stopped"
    done = "done"
    error = "error"


class SessionInfo(Model):
    id: str
    game: str
    build: str
    map: str | None = None
    state: SessionState = SessionState.idle
    started_at: datetime
    h_session_id: str | None = None
    share_url: str | None = None
    speed: str = Field("frame-step", description="QA speed mode, e.g. frame-step or 0.25x")
    live: bool = Field(description="True for a live run, False for a RECORDED replay or mock")
    steps: int = Field(0, ge=0)
    findings: int = Field(0, ge=0)


class SseType(StrEnum):
    session_state = "session.state"
    agent_action = "agent.action"
    agent_note = "agent.note"
    finding_new = "finding.new"
    finding_updated = "finding.updated"
    fix_updated = "fix.updated"
    narration = "voice.narration"
    transcript = "voice.transcript"
    intent = "voice.intent"
    debrief_ready = "debrief.ready"
    placement_ready = "placement.ready"
    plan_updated = "plan.updated"
    error = "error"


SSE_PAYLOAD: dict[str, type[BaseModel]] = {}


class SseEvent(Model):
    """Envelope for every server-sent event. `data` validates against SSE_PAYLOAD[type]."""

    id: int = Field(ge=0)
    type: SseType
    ts: datetime
    session_id: str | None = None
    data: dict[str, Any]

    def payload(self) -> BaseModel | None:
        model = SSE_PAYLOAD.get(self.type)
        return model.model_validate(self.data) if model else None


class ErrorPayload(Model):
    message: str
    where: str | None = None


class TranscriptPayload(Model):
    text: str
    final: bool
    language: str | None = None


SSE_PAYLOAD.update(
    {
        SseType.session_state: SessionInfo,
        SseType.agent_action: AgentAction,
        SseType.agent_note: AgentNote,
        SseType.finding_new: Finding,
        SseType.finding_updated: Finding,
        SseType.fix_updated: FixAttempt,
        SseType.narration: Narration,
        SseType.transcript: TranscriptPayload,
        SseType.intent: VoiceIntent,
        SseType.debrief_ready: DebriefReport,
        SseType.placement_ready: PlacementSpot,
        SseType.plan_updated: Plan,
        SseType.error: ErrorPayload,
    }
)


# ---------------------------------------------------------------- REST API (see docs/CONTRACTS.md)

API_RESPONSES: dict[str, Any] = {
    "GET /api/session": SessionInfo,
    "GET /api/actions": list[AgentAction],
    "GET /api/notes": list[AgentNote],
    "GET /api/findings": list[Finding],
    "GET /api/fixes": list[FixAttempt],
    "GET /api/narrations": list[Narration],
    "GET /api/debrief": DebriefReport,
    "GET /api/placement": list[PlacementSpot],
    "GET /api/plans": list[Plan],
    "GET /api/parent/profile": ChildProfile,
    "GET /api/parent/report": list[GameVerdict],
    "GET /api/events": list[SseEvent],
}
