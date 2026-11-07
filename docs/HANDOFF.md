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

### 2026-11-07: T13 voice in, Gladia live STT + intents (Devin)

- `voice/intents.py`: `parse_intent(text)` -> `VoiceIntent` by ordered EN/FR keyword rules
  (stop > no > fix > skip > explain > yes; "don't fix it" / "ne le corrige pas" is `no`), anything
  else with 2+ words is `steer`, lone noise is dropped. `button_intent()` is the dashboard fallback.
- `voice/listen.py`: `POST /v2/live` (solaria default, en+fr, code switching, partials) then the
  WebSocket; final transcripts -> intent; `--post URL` forwards to `/api/intent` (T14).
  `--wav` streams a file, `--mic [--ptt]` the microphone.
- Mic needs `pip install sounddevice` on the stage laptop; not added to `pyproject.toml` (shared
  file, and CI does not need it).
- Checked from the VM with the real Gladia API on synthesized WAVs (edge-tts): "Fix it.",
  "Stop.", "Corrige-le.", "Arrête.", a steer phrase and "Non, ne le corrige pas." all mapped right.
  **Live microphone on the stage laptop: not run yet (`needs:local`, commands in the PR).**

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
