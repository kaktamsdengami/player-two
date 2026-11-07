# HANDOFF: live state of the build

Update this file before you stop working. Put the newest entry on top. Keep it short and factual.

## Current state (2026-11-07 ~22:00 Paris, Devin)

- **Done (merged):** T01 (#34), T04 (#35), T15 dashboard on mock data (#37), T18 Stripe (#39),
  T10 Devin client (#36), T05 game + QA build (#40), T06 launcher (#41).
  **Stage bug = KB3 on E3M1** (red sky stays red while the world goes grey).
- **Open PRs:** T07 tester (#42), T08 verifier (#43), T11 fix loop (#44, live KB1 loop proven with a
  scripted finding), T13 Gladia (#38, needs:local).
- **In progress:** T14 orchestrator (`t14-orchestrator-state-machine`): state machine, SSE bus,
  RECORDED replay, FastAPI app; unit tests pass. Waiting for a free US H slot for the live run
  (`python -m app.main --mode live --start`).
- **H notes:** EU desktop sessions stall at 0 steps (3 runs); use `HAI_REGIONS=https://agp.hcompany.ai`.
  The tester has no shell (`forbid_shell`): an earlier run read the QA log through
  `run_command_desktop`. Zombie sessions stay `running` after DELETE 204 and hold slots.
- **Not verified on Windows:** T06 gdigrab + foregrounding, T13 mic.
- **Judging:** round 1 is online (demo video + "how do I test your product live" link); stage only for
  the top 8. Frontend work is postponed by the team; backend first.

## Log

### 2026-11-07: T14 orchestrator (Devin)

- `app/orchestrator.py`: one thread runs explore → finding → verify → present (ElevenLabs voice +
  clip) → wait for `fix`/`skip` (button or voice intent) → Devin fix loop → re-verify → follow-up
  message to the same H session (no new session per finding). Every change is an `SseEvent`,
  persisted to `events.jsonl`; `Recorded` replays that file with `live=false`.
- `app/main.py`: REST snapshot + `/api/events` SSE + `/api/intent` + `/api/stop` (cancels H in < 5 s,
  never kills the process) + `/media/{path}` (runs dir and repo only) + T18 billing router.
  New endpoint: `POST /api/session/start {"mode": "live"|"recorded"}` (CONTRACTS.md note pending).
- Merge approval: the developer's `fix` intent is the human approval for the fix PR merge (into the
  per-run `qa-run/<session>` fork branch, never `player-two-qa`).

### 2026-11-07: T11 fix loop + upstream comparison (Devin)

- `agents/fix_loop.py`: `FixLoop.run(finding, attempt)`: follow the Devin session to `pr_open`,
  merge (only if `approve(attempt)`), pull + rebuild the base branch, replay, mark `fixed` /
  `not_fixed`; on `not_fixed` one `send_feedback` round, then stop with an honest status.
  `ScriptReplay` replays a known bug with its fork QA script (deterministic, no H) and records a clip.
- Fixes merge into a per-run fork branch `qa-run/<name>` (made from `player-two-qa`), so the QA
  branch keeps its known bugs for the next demo. `python -m agents.fix_loop FINDING.json --bug KB1
  --script qa/kb1_kb2_medikit.txt --map 1 1 --base qa-run/kb1-t11 --merge [--attempt ATTEMPT.json]`.
- `insights/fix_compare.py`: Devin PR diff vs `KnownBug.upstream_fix_ref` commit (code files only,
  upstream limited to the files Devin touched), verdict same_approach / different_but_valid /
  incomplete (replay decides incomplete; an H Models call `holo4-27b` decides the rest, token
  overlap as fallback), `render_html` side-by-side page. KB3 has no upstream fix: no comparison.
- Real run: KB1 fork PR #1 merged into `qa-run/kb1-t11`, rebuilt, replay log shows
  "Never give up!", verdict different_but_valid. The finding was a scripted one, not from the H tester.

||||||| merged common ancestors
### 2026-11-07: T07 hostile tester agent (Devin)

- `agents/tester.py`: one `h/holo-desktop`-style inline agent (`holo4-27b`, desktop env on
  `host: user_device`), quota check before start (needs 2 free slots), share link, event stream ->
  timestamped `AgentAction` log (`actions.jsonl`) for clip cuts, `send()` for follow-ups in the
  same session. `python -m agents.tester --map 3 1 --steps 40 --minutes 12` starts the game in
  frame-step mode, records the screen, runs the session, writes `tester_run.json`.
- `agents/tools.py`: `report_finding` / `note` / `ask_developer`, validated into `Finding` /
  `AgentNote`; bad calls return an error to the agent. The tester cannot set `known_bug_ref`.
- `agents/prompts/tester.md`: hostile QA persona, frame-step explained, keyboard only, never leave
  the window. Team decision (chat, 2026-11-07): Doom debug codes (`idbehold`, `iddqd`, `idkfa`) are
  allowed. No known-bug content (tested).
- Linux gotcha: pyscreeze needs `XDG_SESSION_TYPE=x11` on a bare X server (set by `Tester`).
- Open: a real H run that reports a known bug (stage laptop or Devin VM), see the PR.

### 2026-11-07: T06 launcher (Devin)

- `python -m launcher demo|build|fetch|query|clip`. `Game` starts the QA build with a fixed window
  (`launcher.cfg` via `-extraconfig`), map, speed (`Speed.parse("step:35" | "slow:4" | "normal")`),
  `-qa-log` in its run dir (`recordings/<ts>-<name>/`, git-ignored), finds and foregrounds the window
  (xdotool / Win32 ctypes). ffmpeg x11grab / gdigrab for screenshots, recording and clips
  (`clip_window(event.t, ...)`, optional "RECORDED · N× speed" label).
- `EventLog` tails the JSONL log; `happened(signature, since_t)` evaluates `LogSignature`
  (T08's `agents/oracles.py` can reuse `launcher.log.signature_hits`).
- Windows: no toolchain on the stage laptop; `python -m launcher fetch [--ref pull/N/head]` downloads
  the fork CI's `MSYS2 UCRT64` artifact (fork CI now also builds PRs against `player-two-qa`).

### 2026-11-07: T05 game fork + QA build (Devin)

- Fork `kaktamsdengami/chocolate-doom`, branch `player-two-qa` off `chocolate-doom-3.1.1`. QA flags:
  `-qa-tics N` (frame-step: frozen until a key press, then N tics), `-qa-slowmo K`, `-qa-log` (JSONL
  `GameEvent`), `-qa-trace`, `-qa-script` (timed QA actions), `-qa-wall-err/-qa-wall-len`.
- Freedoom 0.13.0 `freedoom1.wad` is downloaded, never committed. `eval/known_bugs.yaml` holds
  KB1–KB4 (hidden from the tester). Every signature matched its own scripted run; KB4 also matches on E3M1 (line 582, a real long wall).
- Decision: Freedoom renames strings via DEHACKED, so KB1 matches Freedoom's medikit text.

### 2026-11-07: T18 merged (#39) (Devin)

- #19 closed; no issue depends on T18. Review fixes: subscription id tracked so stale cancels or
  retried checkouts do not flip the plan; atomic plan-file writes; billing reads `.env`.

### 2026-11-07: T18 Stripe plans (Devin)

- `business/stripe_plans.py`: Pro €49 / Parent €9 / Kid €5 monthly prices in Stripe **test mode**,
  found by `lookup_key` `player_two_<plan>` (created once, reused after). Live keys are refused.
- `app/routes_billing.py` (`router`, mount it in T14): `GET /api/plans`, `POST /api/billing/checkout`
  -> `{url}`, `POST /api/billing/webhook` (new endpoint, not yet in CONTRACTS.md). The webhook checks
  `Stripe-Signature` (HMAC-SHA256, 5 min tolerance) and stores the active plan in
  `data/billing.json` (git-ignored). Checkout returns to `DASHBOARD_URL/?checkout=success#plans`.
- Env: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (from the Stripe dashboard or
  `stripe listen --print-secret`), `DASHBOARD_URL`.
- Checked end to end from the VM: test card 4242 on Stripe Checkout -> `stripe listen` forwarded
  `checkout.session.completed` -> 200 -> Plans page shows Parent as current plan. Screenshots in the PR.

### 2026-11-07: T15 merged (#37); T13 open (#38, needs:local) (Devin)

- T15 dashboard merged. `VITE_API_BASE` checked against a throwaway stand-in API (mock JSON +
  named SSE events): header shows LIVE and SSE notes arrive. The real T14 server is untested.
- T18 (#19) moved to ready (its only dependency was T15).
- T13 (#38): Gladia listener + EN/FR intents; real Gladia API checked from the VM with synthesized
  WAVs. **Needs from you:** run the mic commands in #38 on the stage laptop and paste the output.
- Still blocked: T05 needs `kaktamsdengami/chocolate-doom` (fork of chocolate-doom/chocolate-doom)
  with the Devin GitHub integration given access; T10 (#36) real-session check waits on that fork.

### 2026-11-07: T15 dashboard on mock data (Devin)
- `web/` React 18 + Vite 5 + TS. Tabs: Live, Bugs & fixes, Debrief, Plans, Parent. All views render
  from `docs/api-mock.json` (labelled MOCK DATA); `VITE_API_BASE=http://host:port` switches to the
  live REST + SSE API (T14). Buttons post `VoiceIntent` with `source: "button"` to `/api/intent`.
- SSE payloads may omit default fields; `web/src/state.ts` fills them (`normalize`).
- Not in CI yet (CI is a shared file): run `cd web && npm ci && npm run build && npm run lint`.

### 2026-11-07: T10 Devin API client (Devin)
- `devin/client.py` `DevinClient` (v3 sessions API): `create_fix_session(finding)` →
  `follow(attempt, on_update)` → `approve_merge` (merge via the same Devin session) or one
  `send_feedback` round. Prompt: `devin/prompts/fix_bug.md` (no known-bug ref, no upstream fix).
- Default `max_acu_limit=10` per fix session; repo `kaktamsdengami/chocolate-doom`, base `player-two-qa`.
- Open: the real-session check needs the game fork (T05) and Devin GitHub access to it.

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
