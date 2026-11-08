# HANDOFF: live state of the build

Update this file before you stop working. Put the newest entry on top. Keep it short and factual.


- Kid mode (T21, branch `t21-kid-mode-friend`): start the game fullscreen (`-fullscreen`), then `python -m voice.commentator --window "Chocolate Doom" --minutes 2 --age 8`. Each turn: a 320 px JPEG of the window (Pillow, ~0.05 s; ffmpeg took ~3 s) -> `holo4-35b-a3b` with thinking off (`chat_template_kwargs.enable_thinking=false`, ~0.3 s; with thinking 7 s or empty at small max_tokens) -> ElevenLabs via ffplay. Never talks over itself (`MIN_GAP_S`), drops a line whose frame is older than `MAX_AGE_S`; `grab_s`/`vision_s`/`tts_s`/`latency_s` per line in `<out>/comments.jsonl` + `summary.json`. Laptop: 30 s run, 3/3 lines spoken and on-screen (before the speed fix).
- Push-to-talk is on the dashboard: the voice panel's **Talk** button sets `POST /api/ptt`; `voice.listen --mic --post` follows it (Enter in that terminal still works). Start the listener once, then the stage team only uses the browser.
- Stage presets have `goal="powerup"`: if H finishes a round with no `powerup` event in the QA log, the orchestrator sends it back to the sphere (`GOAL_NUDGE`, up to 3 times) instead of accepting the answer.
- Stage rerun 01:15 UTC: the H create call timed out after the server had started the session, which then drove the desktop with no game. `Tester` now uses a 120 s client timeout, cancels its own live sessions (`list_sessions` by agent, created since start) when create fails or `stop()` runs without a handle, and reconnects the event stream after a read timeout. Prompts: if a monster is in the centre, fire in that step without moving.
- Stage rerun 01:06 UTC: H took the zombies' red damage flash for the power-up and reported before the sphere; the verifier rejected it. `stage-play` now has no zombies at the start, the plan describes the green sphere and the "Vanguard of the gods!" pickup message, and the focus guard stops once the session is stopped.
## Current state (2026-11-08, Devin)

- **Done (merged):** T01 (#34), T04 (#35), T15 (#37), T18 (#39), T10 (#36), T05 (#40), T06 (#41).
  **Stage bug = KB3 on E3M1** (sky keeps normal colours under invulnerability).
- **Integration branch = `t14-orchestrator-state-machine` (#46).** It now contains every open
  feature branch: T07 tester (#42), T08 verifier (#43), T11 fix loop (#44), T12 narration (#45),
  T13 Gladia voice-in (#38), T16 debrief (#47), T17 placement (#48). The stage laptop runs only
  this branch. `uv sync --extra dev`: ruff clean, 240 passed; `web` build + lint clean.
- **Stage presets** (open run settings, recorded in `tester_run.json`): `stage-kb3` (sphere near the
  start) and `stage-play` (shotgun, armour, stimpack, zombie, imps, then the sphere at the end of
  the first canyon). Fork player-two-qa 5ad5e7f6 (`spawn` QA command).
- **Live loop status:** stage-play run 4 verified KB3. The first full live loop (#42 comment
  6714953320) went H -> verified KB3 -> narration -> Devin fork PR chocolate-doom#3, then stopped:
  the fix step needed a local `cd-fork` and `make`. Since t14 @137a7e8:
  - the fix step needs no clone: it creates `qa-run/<session>` with `gh api`, downloads the QA
    script from GitHub, and unpacks the fork CI's Windows build of the PR head (`pull/N/head`) to
    `<run>/fix/build`, so the buggy build stays for the next demo;
  - the fork CI (player-two-qa @9c8ddd0c) builds `qa-run/**` branches;
  - a voice "fix it" counts only after the narration;
  - `voice.listen --mic` is push-to-talk by default;
  - the narration says the played map and the verified bug's title.

  **Done on stage (#42 comment 6715339509, t14 @f6432de):** dashboard click -> H -> verified KB3
  -> narration -> Fix button -> Devin fork PR chocolate-doom#4 -> merged -> CI build -> replay 0
  signature events, grey sky -> FIXED in 7 min 18 s (`eval/runs/2026-11-08-stage-live-loop-fixed.json`).
  Fixes after it: the next round plays the fixed build and is told to re-test the fixed bug in
  the agent's own words; `foreground()` uses the same AttachThreadInput path as the focus guard
  (clips showed other windows over the game); push-to-talk ON/OFF shows in the dashboard voice
  panel. **Not yet seen on stage:** voice "fix it" inside a loop, and the agent re-testing the sky.
- **H notes:** real H runs only on the stage laptop (US region, `HAI_REGIONS=https://agp.hcompany.ai`).
  The team cancelled the "H showcase" list (#42): no new features, main loop first.
- **Judging:** round 1 is online (demo video + a live link the jury clicks); stage only for the top 8.

## Log

- 2026-11-08 (Devin): README.md rewritten as the submission page (pitch, loop, Mermaid
  architecture, honest results, how to run, credits). `eval/RESULTS.md` lists the stage runs 2
  (blind, KB4) and 4 (`stage-play`, spec-based, KB3), the KB3 Devin fix (fork PR #2, not merged;
  started from the VM, not `app.main`) and what is not measured yet.

- 2026-11-08 (Devin): stage run 4 (`stage-play`, session `0d17032d…`): the agent called
  `report_finding` on the sky (KB3), replay 31/31 in sync, but the verifier replayed key presses
  cut at `t_session_s` (wall clock, mostly H thinking) and stopped at tic 140, before the power-up
  at tic 409. Fix: when the run has `agent.lmp` the verifier plays the tester's demo
  (`replay: "demo"`) and judges events up to the report tic + the largest `within_tics`
  (`tester_run.json` now stores `game_started_at`; older runs judge the whole demo).
  `stage-play` adds two zombies right ahead of the start (holding Ctrl killed both in 5 s on the
  VM; prompt now says hold Ctrl ~1 s). KB3 fix demo: fork branch `qa-run/kb3-fix-demo` (base for
  the fix PR, keeps `player-two-qa` buggy for demos).

- 2026-11-08 (Devin): stage run 3 (`stage-play`, session `69026364…`): the preset reached KB3 on
  screen (sky red while the world is inverted) but the agent judged it correct: 0 findings. Team
  request on #42: the stage presets' plan now states the developer's expected behaviour under
  invulnerability (spec-based test plan, visible in the dashboard and `tester_run.json`; runs with
  it are not "blind" rediscoveries). taptest sends a warm-up tap (cold Windows start lost the first).

- 2026-11-08 (Devin): T12, T13, T16, T17 merged into t14 (T12's branch drops the verifier files; t14
  keeps them). Contract addition: `POST /api/transcript` (`TranscriptPayload` -> `voice.transcript`),
  posted by `voice.listen --post` with `X-P2-Token` when `P2_CONTROL_TOKEN` is set. Debrief counts
  retries per game launch (rounds relaunch the game) and sums launch durations.

- 2026-11-08 ~00:30 (Devin): team decision on #42 (stage demo). `agents.tester --plan "<text>"`
  appends "The developer asks you to focus on: ..."; `--preset stage-kb3` (launcher `PRESETS`,
  `P2_PRESET`) starts E3M1 with an invulnerability sphere spawned ~200 units ahead under the red
  sky (fork QA script `spawn <doomednum> <x> <y>`, player-two-qa 5ad5e7f6; E3M1 has no sphere of
  its own and its only door is the exit). Preset lines go into `qa_start.txt`, so `launcher replay`
  and the verifier start the same way. Dashboard Live tab: "New run" (test plan + preset).
  Tester prompt: door/switch/lift/item rules; default 120 steps / 20 min.

### 2026-11-08 ~02:00: team decision on #42: faster model, 8-tic steps, demo replay (Devin)

- Tester model `holo4-35b-a3b` by default; `P2_TESTER_MODEL=holo4-27b` to compare.
- `DEFAULT_STEP = 8` (~0.23 s per tap); holding a key still runs the game. Run records save the
  explicit speed (`Speed.spec()`, e.g. `step:8`), so replays survive default changes.
- Every tester run records `<run_dir>/agent.lmp` (`-record`, vanilla demo). Fork bcbadb21: the
  demo is written every 7 tics (the game is closed, not quit), typed letters are logged as `key`
  events, and QA scripts have a `key <code>` command.
- `python -m launcher replay <run_dir>`: `-playdemo` at game speed with a QA script built from
  `qa_start.txt` + `key` events (cheat codes are not in demos), records ffmpeg, labels
  "Agent session · replayed at game speed" -> `agent_replay.mp4` + `replay.json`
  (`game_started_at`, `rec_started_at`; `replay/events.jsonl` + `capture.clip_window` cut clips).
  Sync check on Linux: 8-tic taps, a hold, `idkfa`, weapon switch, fire: 17/17 player samples
  identical at the same tics, replay quits at the demo end (`show_endoom 0` in extraconfig).
- Orchestrator: round 1 is recorded to `game/agent.lmp`; its log is kept as
  `game/agent_events.jsonl` when later rounds restart the game.

### 2026-11-08 ~01:00: team decision on #42: play well, think like a tester (Devin)

- Tester prompt rewritten: progress through the level like a competent player (doors, switches,
  shooting, pickups) and try what could break on the way; controls (Ctrl fire, 1-7 weapons,
  Space use, `-`/`=` screen size); tap vs hold; frozen between presses is normal. No routes to
  known bugs.
- Default frame-step 12 tics (`DEFAULT_STEP`); fork 516905e6: a key held past its step keeps the
  game running (tap = 12 tics, 2 s hold = 70 tics, measured with `-qa-trace 1`).
- `P2_GOD=god|tough|off` (default tough since ~02:30, Dmitry delegated the choice; was god): QA start script for free play only
  (replay scripts set their own). Note: vanilla god mode blocks all damage (no pain face, no
  damage events), so damage bugs such as KB2 cannot trigger; `tough` = 999 health. Asked the team.
- The verifier replays at the speed saved in `tester_run.json`; the orchestrator uses 12 tics.

### 2026-11-07 ~00:30: stage run 2: first blind rediscovery (Devin)

- Stage laptop, t14 @ d086321, fork 38f5c344, US: session `c960e650…`, 39 actions, max tic 595.
  4 findings; the verifier VERIFIED F3 = **KB4** (proven by the QA log, clip cut). F1/F2/F4 stayed
  suspected (vanilla screen border, close-range explosions, death view). T07/T08 acceptance met.
- Fixes after the run: taptest waits for the first frame and refocuses (first tap was lost once
  on first launch); tester prompt lists normal Doom behaviour that is not a bug. `iddqd` works in
  frame-step on the fork (xdotool type, delay 0 and 80 ms: "God mode on." at tic 10 / 21).

### 2026-11-07 ~23:30: stage run 1 diagnosis + frame-step latch (Devin)

- Stage-laptop tester run (US, session `1f447785…`, 37 actions, slots freed): the game advanced one
  step (tic 0 -> 35) and then froze. H's key taps are near-instant, and the frame-step clock polled
  `SDL_GetKeyboardState`, so it missed them. F1-F3 were artefacts of the freeze, not game bugs.
- Fork fix `38f5c344` (player-two-qa): an SDL event watch counts every key-down as one step, and
  `G_Responder` keeps the key held for the whole step even if key-up arrives first. Checked on the
  Devin VM with 0 ms xdotool taps on E3M1: 4 taps -> tics 35/70/105/140, player moves and turns.
  The Windows artifact for `38f5c344` is the newest one, so `python -m launcher fetch` picks it.
- Windows fixes: the tester loads `.env` before reading `HAI_API_KEY`; dependency is
  `hai-agents[desktop]`; `player_two.egg-info/` is untracked and ignored. On Windows, if `uv sync`
  hits MAX_PATH, set `UV_PROJECT_ENVIRONMENT` to a short path (e.g. `C:\p2venv`).
- `python -m launcher.taptest` (+ `tests/test_taptest.py`): starts the QA build in frame-step
  mode, sends 0 ms taps (xdotool `--delay 0` / Win32 `keybd_event`), checks one step per tap.
  Devin VM: old build `1233d939` -> `[1, 1, 1, 1, 35] FAIL`; `38f5c344` -> `[1, 35, 70, 105, 140] PASS`.
  Run it on the stage laptop before each H session.
- Next: rerun step 1 on the stage laptop; verifier only on a genuine finding.

### 2026-11-07: T14 orchestrator (Devin)

- End of run (`debriefing`): the orchestrator writes `tester_run.json` (findings with their final
  status, notes, recording) into the game run dir, then runs `Deps.debrief` (T16
  `insights.debrief.build`) and `Deps.placement` (T17 `insights.placement.scout`) → `debrief.ready`
  / `placement.ready` events. Both are optional imports until #47/#48 merge, and best effort.
  Live mode records the game window into `<run>/run/recording.mp4` for the placement scout, and
  appends each round's QA log to `<run>/run/events.jsonl` (Game.start wipes it).
- Shared-file note: `docs/CONTRACTS.md` now lists `POST /api/session/start`, the T18
  `POST /api/billing/webhook`, and the control guard (JSON only, optional `X-P2-Token` when
  `P2_CONTROL_TOKEN` is set, `P2_CORS_ORIGINS`). Both env vars are in `.env.example`.
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

||||||| b9fe6d8
||||||| cf48dac
### 2026-11-07: T17 product-placement scout (Devin)

- `python -m insights.placement <run_dir> [--every 5] [--spots 5] [--no-linkup]` →
  `<run_dir>/placement.json` (list of `PlacementSpot`). Frames every 5 s from the run's recording
  (ffmpeg) → H Models API vision (`holo4-27b`, `HAI_API_KEY`, override `P2_VISION_MODEL`) lists
  surfaces per frame → same surface merged across frames → score = screen time × mean visibility.
  The tester's `note(tags=["placement"])` calls become spots too.
- Brands: `insights.linkup.structured` (Linkup `outputType=structured`, `includeSources`), 3
  candidates per spot; a candidate without an http(s) source link is dropped. Every spot keeps the
  "Suggestions only. No brand deal exists or is implied." disclaimer.
- Real APIs on the Devin VM (keys bound from org secrets), on the recording of an earlier VM tester
  run on E3M1 (exploratory, not the acceptance run): 4 spots (left/right rock wall 45 s, path 35 s,
  red rock wall 5 s), each with 3 brands and a source link. Linkup structured calls sometimes return
  a 400 that succeeds when repeated, and a vision call can time out: both are retried now.
- Acceptance (≥3 spots on the real tester run) still runs on the stage laptop after the tester run.

### 2026-11-07: T16 design debrief (Devin)

- `python -m insights.debrief <run_dir> [--no-linkup]` → `<run_dir>/debrief.json` (`DebriefReport`).
  Heatmap: `death` events and level restarts (every `level` event after the first per map) in
  128-unit cells over the bounds of all player positions. Notes come from `tester_run.json`.
  Suggestions: one per finding (`suggested_change`, or built from actual → expected); verified
  findings from `verdicts.json` replace the tester's. References: one Linkup search (`POST
  /v1/search`, `searchResults`), 2 citations from different sites. The topic follows the notes'
  tags (`too_hard`, `confusing`) and the deaths.
- Shared `insights/linkup.py` (new file, also used by T17).
- Checked on the Devin VM: Linkup search works with the real key. Ran it on a real but short H
  run (E3M1, 13 actions, no deaths, no notes). The acceptance run with real evidence goes on the
  stage laptop, after the tester run.

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
