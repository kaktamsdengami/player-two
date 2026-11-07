# HANDOFF: live state of the build

Update this file before you stop working. Put the newest entry on top. Keep it short and factual.

## Current state (2026-11-07 evening, written by the orchestrator)

- Phase: **planning done; nothing built yet.** T00 (handoff kit) is done on main.
- The plan is in docs/PLAN.md. All tasks are GitHub issues T00–T32. docs/ISSUES.md holds the
  source text the issues were created from.
- **Ready to start now:**
  - T01 Contracts and decisions;
  - T02 Accounts and keys (human).

  These become ready as soon as T01 lands: T04 Repo skeleton, T10 Devin API client, T15 Dashboard
  on mock data.
- **Gate:** T03, the spike on the stage laptop. It checks whether the H desktop agent can play
  Chocolate Doom and Shattered Pixel Dungeon. Its numbers feed the team's game choice in T05.
- **Waiting on the human:**
  - put the keys into `.env` (T02);
  - give Devin's GitHub integration access to this repo, and later to the game fork;
  - ask the organisers about the Gladia prize, the submission fields and staying overnight.
- Decided so far:
  - Devin writes all code.
  - The demo uses a **real open-source game at a version with known bugs**, not a generated game.
  - Tasks T05–T09 consult the team before every decision about the game.
  - The Devin API is a runtime component (this targets the Best Use of Devin prize).

## Log

### 2026-11-07: T15 dashboard on mock data (Devin)
- `web/` React 18 + Vite 5 + TS. Tabs: Live, Bugs & fixes, Debrief, Plans, Parent. All views render
  from `docs/api-mock.json` (labelled MOCK DATA); `VITE_API_BASE=http://host:port` switches to the
  live REST + SSE API (T14). Buttons post `VoiceIntent` with `source: "button"` to `/api/intent`.
- SSE payloads may omit default fields; `web/src/state.ts` fills them (`normalize`).
- Not in CI yet (CI is a shared file): run `cd web && npm ci && npm run build && npm run lint`.

### 2026-11-07: T04 repo skeleton and CI (Devin)
- `pyproject.toml` (Python 3.12, `pip install -e ".[dev]"`), CI in `.github/workflows/ci.yml`
  (ruff check, ruff format --check, pytest), package dirs, `scripts/check_keys.py`
  (`python -m scripts.check_keys` → one line per service, read-only, never prints keys).

### 2026-11-07: T01 contracts and decisions (Devin)
- `app/contracts.py` (Pydantic v2, contracts v1.0), `docs/CONTRACTS.md` (decisions + models + SSE +
  REST), `docs/api-mock.json` (MOCK data for every dashboard view), `tests/test_contracts.py`.
- Decisions: name PLAYER TWO; TTS edge-tts; intents fix/skip/explain/stop/yes/no + steer;
  JSONL `GameEvent` log + `LogSignature` oracle shape.

### 2026-11-07: repo created (Claude, orchestrator)
- Created the repo with PLAN, AGENTS, CLAUDE and HANDOFF; created the labels, milestones and issues.
