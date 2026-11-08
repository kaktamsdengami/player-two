# CONTRACTS: shared data and API contracts (frozen in T01, version 1.0)

The source of truth is `app/contracts.py` (Pydantic v2). This file explains it. **Changing a
contract** means: edit `app/contracts.py`, update this file and `docs/api-mock.json`, keep
`pytest tests/test_contracts.py` green, and note the change in `docs/HANDOFF.md` and the issue.

## Decisions (T01)

| Decision | Choice | Reason |
|---|---|---|
| Product name | **PLAYER TWO** | Short, says "an agent that plays with/against you", already used across the repo. |
| Game | Doom: Chocolate Doom (GPL-2.0) + Freedoom (BSD) data | Team decision in #6; T03 (#4) showed the H desktop agent can play it with a frame-step mode. |
| Stack | Python 3.12, FastAPI, Pydantic v2, pytest, ruff, GitHub Actions; React + Vite for `web/` | As proposed in AGENTS.md; nothing in T01–T03 argues against it. |
| TTS | **edge-tts** (Microsoft Edge neural voices) | Free, no key, natural voices in English and French; fallback is the OS voice (Windows SAPI) when offline. |
| Voice intents | `fix`, `skip`, `explain`, `stop`, `yes`, `no`, plus `steer` (free text sent to the running H session) | The six intents from the plan cover every approval gate; `steer` carries "try the door again". |
| Event-log oracle | QA build writes JSONL, one `GameEvent` per line; bugs are proven by a `LogSignature` | Deterministic, game-agnostic shape; T05 picks the Doom event types, T08 evaluates signatures. |
| Speed | QA frame-step mode, label demo video "RECORDED · N× speed" | T03: every key hold lasts one agent step (2–7 s). |
| Time base | `tic` (35 per second in Doom) inside the game log; `t_session_s` (seconds since the H session started) for agent actions, notes and clips | Clips are cut from the screen recording by session time; oracles reason in game tics. |

## Models

| Model | Purpose | Producer → consumer |
|---|---|---|
| `GameEvent` (+ `PlayerState`, `ActorRef`) | one line of the QA build's event log | game fork → launcher, oracles, debrief |
| `EventMatch`, `LogSignature` | deterministic proof of a bug in the log | `eval/known_bugs.yaml`, verifier → oracles |
| `KnownBug` | schema of each entry in `eval/known_bugs.yaml` (**hidden from the tester**) | T05 → T08, T22 |
| `AgentAction` | one agent step, timestamped for clip cuts | tester → orchestrator, dashboard timeline |
| `AgentNote` | `note(text)` tool: observations for debrief and placement | tester → T16, T17 |
| `Finding` (+ `Evidence`, `Clip`) | `report_finding()` payload; status `suspected → verified → presented → fixing → fixed / wontfix` | tester → verifier → orchestrator → dashboard |
| `FixAttempt` (+ `FixComparison`) | one Devin session for one finding; `round` 1 or 2 (single feedback round) | T10/T11 → dashboard |
| `DebriefReport` (+ `HeatCell`, `FindingSuggestion`, `Citation`) | post-session design debrief | T16 → dashboard |
| `PlacementSpot` (+ `BrandCandidate`) | placement suggestion with sourced brand candidates, never a claim of a deal | T17 → dashboard |
| `ChildProfile` | local-only child profile | parent mode (T20) |
| `GameVerdict` | one game checked for one child | T20 → parent report |
| `Plan` | Stripe plan (`pro`, `parent`, `kid`) | T18 → dashboard |
| `VoiceIntent` | intent from voice or a button (`source`) | T13 / dashboard → orchestrator |
| `Narration` (+ `NarrationCue`) | TTS audio + cues mapping audio time → clip time | T12 → dashboard |
| `SessionInfo` | session header; `live=false` for RECORDED or mock data | orchestrator → dashboard |
| `SseEvent` | SSE envelope `{id, type, ts, session_id, data}` | orchestrator → dashboard |

Rules baked into the models:
- `Finding.known_bug_ref` is set only by the verifier; the tester never sees the known-bug list.
- `Clip.speed` records the playback factor so the dashboard can label "RECORDED · N× speed".
- `SessionInfo.live` must be `false` for anything replayed or mocked.

## Event-log oracle shape

The QA build writes `GameEvent` JSONL. Required keys: `tic`, `type`. Optional: `t`, `map`,
`player`, `actor`, `data`. T05 fixes the Doom event types (proposal: `level`, `player`,
`damage`, `death`, `spawn`, `pickup`, `use`, `special`, `face`) and documents them in docs/GAME.md.

A `LogSignature` proves a bug:

```yaml
log_signature:
  description: medikit picked up below 25 health shows the normal message
  all_of:
    - type: pickup
      where: {data.item: medikit, data.health_before: {lt: 25}, data.message: {ne: "Picked up a medikit that you REALLY need!"}}
  within_tics: 35
```

`where` maps dotted paths to a literal (equality) or `{op: value}` with `op` in
`eq, ne, gt, ge, lt, le, in, exists`. `all_of` must all match (inside `within_tics` if set);
`none_of` must not match in that window.

## SSE event types

| `type` | `data` model |
|---|---|
| `session.state` | `SessionInfo` |
| `agent.action` | `AgentAction` |
| `agent.note` | `AgentNote` |
| `finding.new`, `finding.updated` | `Finding` |
| `fix.updated` | `FixAttempt` |
| `voice.narration` | `Narration` |
| `voice.transcript` | `{text, final, language}` |
| `voice.intent` | `VoiceIntent` |
| `debrief.ready` | `DebriefReport` |
| `placement.ready` | `PlacementSpot` |
| `plan.updated` | `Plan` |
| `error` | `{message, where}` |

Stream: `GET /api/events` (`text/event-stream`, `event:` = type, `data:` = the envelope JSON,
`id:` = envelope id). The mock file holds the same envelopes as a JSON list.

## REST API (served by T14, mocked in docs/api-mock.json)

`docs/api-mock.json` is keyed by `"METHOD /path"`; each value validates against
`API_RESPONSES` in `app/contracts.py`.

| Endpoint | Response |
|---|---|
| `GET /api/session` | `SessionInfo` |
| `GET /api/actions` | `AgentAction[]` |
| `GET /api/notes` | `AgentNote[]` |
| `GET /api/findings` | `Finding[]` |
| `GET /api/fixes` | `FixAttempt[]` |
| `GET /api/narrations` | `Narration[]` |
| `GET /api/debrief` | `DebriefReport` |
| `GET /api/placement` | `PlacementSpot[]` |
| `GET /api/plans` | `Plan[]` |
| `GET /api/parent/profile` | `ChildProfile` |
| `GET /api/parent/report` | `GameVerdict[]` |
| `GET /api/events` | SSE stream of `SseEvent` |
| `POST /api/session/start` | body `{mode: "live" \| "recorded"}` → `SessionInfo` (T14) |
| `POST /api/intent` | body `VoiceIntent` (buttons use `source: "button"`) |
| `POST /api/transcript` | body `TranscriptPayload`; republished as `voice.transcript` (the voice listener) |
| `GET/POST /api/ptt` | body `{"on": bool}`; push-to-talk state set by the dashboard's Talk button (or Enter in the listener), followed by `voice.listen --mic --post`; echoed as `voice.transcript` |
| `POST /api/stop` | stops the session (H session cancelled within 5 s) |
| `POST /api/billing/checkout` | body `{plan: PlanId}` → `{url}` (T18) |
| `POST /api/billing/webhook` | Stripe signed webhook → active plan (T18) |
| `GET /media/{path}` | clips, screenshots, audio |

Control endpoints (`session/start`, `intent`, `stop`) take JSON only (`Content-Type:
application/json`, else 415). When `P2_CONTROL_TOKEN` is set they also need the header
`X-P2-Token` (else 401). CORS origins come from `P2_CORS_ORIGINS` (default: localhost Vite).
`GET /api/session` returns an idle `SessionInfo` (`id: "idle"`, `live: false`) before a run.

Dashboard views → mock keys: live view (`session`, `actions`, `events`), bug cards (`findings`,
`narrations`), Devin panel (`fixes`), voice indicator (`events` of type `voice.*`), Debrief tab
(`debrief`, `placement`), Plans page (`plans`), parent report (`parent/profile`, `parent/report`).
