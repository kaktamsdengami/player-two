# HANDOFF: live state of the build

Update this file before you stop working. Put the newest entry on top. Keep it short and factual.

## MORNING (T33 jury site, branch `t33-jury-site`, Devin, 2026-11-08 ~07:30 CET)

**What it is:** one link, zero clicks, and H Company's Holo (vision model, Models API) is visibly
playing Doom in the browser: it gets a 480x360 JPEG of the WebGL canvas about once a second,
answers strict JSON (`thought/keys/hold_ms/aim/status`), and the page presses real keys into the
Chocolate Doom WASM build (Freedoom E1M1). Then the juror takes over (tap or button) and gives it
back. Five looks, same engine.

**URLs** (run `scripts\jury_up.ps1` on the laptop; it prints them with the tunnel host):
`/` hub · `/arcade/` cabinet · `/live/` shared Twitch-style stream · `/lab/` X-ray (frame, JSON,
latency, pool) · `/story/` "The Bug Hunt" film · `/kid/` couch buddy · `/dashboard/` (the old `/`).
Devin's VM tunnel while its session is alive (will die): https://establishment-era-zen-guides.trycloudflare.com

**Recommended for the jury:** `/arcade/` (fastest "wow" + clearest takeover). Second: `/lab/`
(for the technical judges). `/live/` is the one to show on the big screen (one Holo loop,
N viewers).

**How it works:** `app/routes_holo.py` (`POST /api/holo/act`, `GET /api/holo/status`,
`POST /api/holo/say`), prompt `agents/prompts/holo_play.md`, engine `web/jury/shared/holo-doom.js`,
UI glue `web/jury/shared/jury.js`, shared stream `app/routes_live.py` + `scripts/live_broadcaster.py`
(headless Chromium plays, pushes steps to `/api/live/push`, viewers get them over `/api/live/ws`;
starts on the first viewer when `P2_LIVE_BROADCAST=1`, stops after 3 min without viewers).
Fallback `web/jury/recorded/run.json` + 111 JPEGs (a real Holo run, labelled RECORDED) plays when
there is no key, the model pool is exhausted (429/503) or the demo cap is hit, or after repeated
errors. Keys never reach the browser.

**Rate limit:** H Models API = 30 req/min per model. Pool `P2_HOLO_MODELS` (holo4-35b-a3b,
holo4-27b, holo3-1-35b-a3b) at `P2_HOLO_RPM=28` each ≈ 84 steps/min ≈ 4-5 simultaneous live
browsers; `P2_HOLO_RESERVE=12`/min is kept for localhost (the broadcaster). Beyond that visitors
get `busy` and switch to RECORDED silently, badge says so.

**Known issues / deviations:**
- Fixed after Dmitry's phone test: voice was never on (`speak` defaulted to false; now the SOUND tap unlocks one <audio> element, iOS-friendly); Holo now keeps firing while it thinks after a shot, tries `use` before turning when blocked (doors look like walls), shorter walks, and the TELL instruction lasts 6 moves and is shown as `[you: ...]` in the thought line.
- Second phone round ("still walks into walls, shoots late"): the browser is now authoritative over the model's reflexes in `web/jury/shared/holo-doom.js`: stall = brightness-normalised grey-thumbnail difference < 3.5 after ONE unchanged move (dark rooms no longer hide a wall); when stalled, a plain `up` becomes `use+up`, then `left` 900 ms; consecutive turn-only moves keep one direction and the third becomes a step forward (the model used to swing left-right-left on the spot for a minute, calling itself `stuck` while the view moved); a thought that names an enemy adds `fire`, one that names a door adds `use`; fire holds are at least 600 ms. Pace is ~1 move/s (walk 500-900 ms + think ~600 ms); Dmitry said slower decisions are fine.
- Third phone round ("shoots a wall and calls it an enemy"): Holo now gets TWO images per request (previous view + current view, `prev_image` in `/api/holo/act`, same ~650 ms latency) and a QA-tester briefing on how a Doom level works (rooms/doors/lifts/keys/EXIT, what a monster looks like vs a wall, never `fire` without a live monster in the CURRENT view); after 3+ consecutive fire moves the prompt asks it to re-check for a live monster. The client no longer adds `fire` from the thought text (that was the wall-shooting amplifier); door words still add `use`.
- Fourth phone round ("shoots sideways at monsters"): Doom only hits what is straight ahead, so the prompt now says fire only when the monster stands above the gun (middle third) and turn towards it otherwise; the client enforces it with the model's own `aim`: `fire` with `aim.x` in the outer thirds becomes a 300 ms turn towards the target (fire follows on the next move once centred).
- Fifth phone round ("bumps into the first wall, does not shoot"): the symptom matched the local fallback move (`up` with an invented thought) that ran whenever the shared H budget or a 12 s timeout left a request unanswered. Now: no answer from Holo = stand still (or `use`/turn off a wall) with the honest thought `No answer from Holo (timeout | shared limit, retry in N s): ...`; pace is ~1 move per 2.5 s (`pace=1200` ms of plain play between moves, `?pace=` to tune) so one client uses ~25 req/min instead of ~55; screenshots are 640 px wide (was 480) for small distant monsters; server read timeout 9 s.
- Dashboard (/dashboard/): the `● Talk` mic button is gone; the voice panel has a text field instead (Enter → `POST /api/intent/text {text}`, parsed with `voice.intents.parse_intent`, echoed as a transcript, 422 for small talk). The intent buttons stay.
- Hub `/` now opens with TWO WAYS TO PLAY (Tester mode → /arcade/, Holo playing live; Kid mode → /kid/) above the five looks; the arcade, kid and dashboard headers carry `← home` and the link to the other mode, so a juror can go back and forth. Dmitry's call: the tester mode jurors see is the live Holo game, not the (mock-data) /dashboard/. /kid/ game is capped to the viewport height (no scrolling on a laptop).
- Mode switch is now a labelled bar on /arcade/ and /kid/ ("TESTER MODE: Holo plays, INSERT COIN takes over" / "KID MODE: you play, Pixel talks"). /arcade/ TELL button removed: the input alone, Enter sends (jury.js tolerates a missing `send`). Firing rule hardened: `fire` without an `aim` is dropped, off-centre aim turns instead, and fire is no longer held across the think gap (the target may have left the gun line: this was the "shoots sideways" report).
- /arcade/ has no TELL input any more (Dmitry: it did not work for him on the phone; the other looks keep theirs). Wall recovery: the second stuck move turns 1100 ms and resets the turn streak; the "turned enough, walking" shortcut needs >= 800 ms of accumulated turning and never fires while stalled (it used to walk straight back into the wall after two 400 ms turns).
- Stall detector compares only the top 52 % of the view (walls/ceiling): the bobbing gun while walking into a wall counted as motion, so Holo could push a wall for a minute saying "corridor continues". Second net: the same sentence + plain forward three times in a row = stuck. /arcade/ screen is capped to the viewport height (`.screen-wrap` width from 100vh) so INSERT COIN is above the fold on a laptop; on phones the marquee subtitle is hidden.
- /kid/ wears the arcade cabinet now (loads `/jury/arcade/arcade.css`, `kid.css` only adds Pixel: face, mic button, chat in the ticker column); kid.js untouched (same ids). Pixel never shows/speaks a line containing SKIP or "not sure what to say" (`MUTE` in commentator.py: the model put SKIP inside a sentence, the old check only looked at the start). `/api/kid/line` asks the Models API again after 2.5 s of silence (`STALL_S`) instead of waiting the full 6 s and saying nothing: measured healthy answers 0.3-0.9 s, with a 6 s ReadTimeout now and then, which was the "Pixel is slow" feel. TTS stays `eleven_v3` (first audio ~0.5 s; turbo/flash are 0.25 s but the team rejected their announcer tone).
- `Module.pauseMainLoop/resumeMainLoop` corrupts this Asyncify WASM build (every later frame throws
  "memory access out of bounds"), as does a non-empty `Module.print`. So the game is NOT paused
  while Holo thinks: no key is held, the marine stands still (~0.5-0.8 s). Documented in
  `holo-doom.js`; the T33 acceptance item "pause/resume verified" is therefore replaced by
  "keyboard injection + 35 s zero-error live run verified".
- `/live/` headless broadcaster needs Playwright Chromium on the server (`.venv/bin/playwright
  install chromium`); without it the page falls back to its own in-browser game after 8 s.
- `data/freedoom1.wad` is git-ignored: download Freedoom 0.13.0 into `data/` (jury_up.ps1 checks).
- `tests/test_taptest.py::test_zero_ms_tap_advances_the_game` fails on the base branch too
  (pre-existing, not T33).
- Holo on Freedoom tends to say "corridor clear, forward"; `skill` 3 (arcade default) brings imps
  sooner. The viewer instruction box ("go left", "shoot") is appended to the prompt.

**Laptop checklist (5 min):** `git checkout t33-jury-site` → `uv sync --extra dev` →
`.venv\Scripts\playwright install chromium` → `.env` has `HAI_API_KEY` (+ `ELEVENLABS_API_KEY`
for narration) → `data\freedoom1.wad` present → `powershell -File scripts\jury_up.ps1` → open
the printed `/arcade/` on the phone and the laptop → see LIVE badge within ~5 s → tap, play, hand
back. Checks on the VM: `pytest` 306 passed (+1 pre-existing fail), ruff clean, `web` build+lint
clean, 10 concurrent clients served wasm+wad+status in 0.75 s, tunnel served `/` in 0.5 s.


- **Game screen for viewers**: `GET /api/screen` returns a JPEG of the Doom window (one ffmpeg grab a second at most, shared by every viewer; 404 when no game runs). The Live tab shows it above H's live view iframe, so the jury sees Doom even if H's `share_url` asks for a login. VM: unit test + build only; the gdigrab grab on the laptop is not yet checked.
- **One public link for the jury, many viewers at once** (t14 now includes `t28-kid-web`): `app.main` serves the dashboard at `/` (view-only behind the tunnel) and kid mode at `/kid/`, so one server on 8000 and one `cloudflared tunnel --url http://127.0.0.1:8000` cover both; `scripts/kid_web.ps1` (8010) is no longer needed on stage. Each kid tab sends a random `c=` id so jurors on one venue IP get their own per-client gaps; total caps raised to 4000 lines / 2000 voice / 600 listens (`P2_KID_MAX_*`). Kid Doom runs in each juror's browser, not on the laptop, so it does not steal focus from H's game; only Holo vision, ElevenLabs and Gladia calls hit the laptop. VM check: `/` and `/kid/` load from one server, Doom runs at `/kid/`; live keys not tested on the VM.
- **Kid mode in the browser** (branch `t28-kid-web`, for the jury to play themselves): `uv run uvicorn voice.kid_web:app --host 127.0.0.1 --port 8010`, then `cloudflared tunnel --url http://127.0.0.1:8010` for a public link (`scripts/kid_web.ps1` does both). Doom runs in the page (Chocolate Doom WebAssembly from cloudflare/doom-wasm, built with emsdk 3.1.61, see `web/kid/README.md`; WAD = `data/freedoom1.wad` or `P2_KID_WAD`). Every second (10 s between Pixel's own lines) the page sends a 480 px JPEG of the canvas to `POST /api/kid/line` (same `commentator.comment()` + kid prompt, repeats and bot phrases dropped), plays `GET /api/kid/say` (ElevenLabs Chris/v3 streamed through the server), and an open mic streams 16 kHz PCM to a Gladia live socket (`POST /api/kid/listen`, reopened when Gladia ends it): the child talking cuts Pixel off, Pixel's own echo is ignored (same rules as `commentator.ears`), a small button mutes. `?debug` shows per-turn timings (grab, line, vision, server, first voice); `/api/kid/say` sends `X-First-Audio-Ms`. On Windows use 127.0.0.1, not localhost (IPv6 first: ~2 s per request). Keys stay on the server; per-client gaps and total caps (`P2_KID_MAX_LINES`/`SAYS`/`LISTENS`). VM check: Doom plays and the canvas is readable in Chrome; Pixel's vision, voice and ears not yet verified with real keys.

- **Jury mode, nothing to click.** `P2_AUTO_FIX=1`: after the narration a verified bug goes straight to Devin (`Orchestrator(auto_fix=True)`, no `awaiting_approval`; Skip still cancels). `P2_CACHED_FIX_BUG/EXE/PR[/DEVIN]`: for that bug the run skips the new Devin session and replays the bug at once on the build from an earlier Devin fix (e.g. KB3 from chocolate-doom#5). The replay is live; the dashboard Devin card says the fix is cached from that PR.
- **Public watch link for the jury (view only).** Build the dashboard once for same-origin: `cd web; $env:VITE_API_BASE='same-origin'; npm run build` (PowerShell). `app.main` then serves `web/dist` at `/` next to the API, so `cloudflared tunnel --url http://127.0.0.1:8000` gives one https link to the running dashboard (live H view, findings, Devin card). Anything that arrives through Cloudflare (`Cf-Connecting-Ip` header) gets 403 on every control endpoint (`control()`), and the page hides New run, voice and Fix/Merge buttons when it is not opened from localhost (`VIEW_ONLY`). The team keeps the usual Vite dashboard on the laptop for control. The H live view iframe is H's `share_url`: check in a private window that it opens without an H login.
- **Devin is visible on the dashboard.** A strip under the header says what Devin does at runtime (every verified bug -> Devin API session -> fix PR to the game -> H replays it) and that Devin built the product (numbers from `gh pr list`, constant `DEVIN_BUILD` in `web/src/App.tsx`). While a fix runs, the Live view shows a Devin card: steps (session, PR, merged/rebuilt, replay), elapsed time, session/PR links and Devin's latest message. Contracts: `FixAttempt.devin_says` (optional, Devin's last message; `DevinClient.from_env` reads `/messages` on every refresh).
- **Live loop @3bfc1d1 (stage, 02:26-02:50 UTC): FIXED end to end by voice** (#42 comment 6716381625): H found KB3 at step 62, verified, "Yes, fix it." -> `fix` (voice), Devin fork PR kaktamsdengami/chocolate-doom#5 in 2 min, merged, rebuilt, re-verified **fixed** 6.5 min after "fix it". Round 2 failed: H wandered in the canyon and imps wore 999 health down to a death. Now `stage-play` always starts in god mode (`Preset.start`), and after a restart the round message says where the sphere is (`Preset.again`). "Thank you"-style small talk is no longer a `steer` intent (`_SMALL_TALK`).
- Kid mode (T21, branch `t21-kid-mode-friend`): start the game fullscreen without music (`-fullscreen -nomusic`, team pick: with music the open mic hears the kids badly; sound effects stay), then `python -m voice.commentator --window "Chocolate Doom" --minutes 2 --age 8 [--map E1M1]`. Each turn: a 480 px JPEG of the window (Pillow, ~0.05 s; ffmpeg took ~3 s) -> `holo4-35b-a3b` with thinking off (`chat_template_kwargs.enable_thinking=false`, ~0.3 s) and a Doom primer in `agents/prompts/kid.md` (keys, doors+Space, key cards, HUD order) -> ElevenLabs **streaming** TTS piped into ffplay (`StreamVoice`; `P2_KID_STREAM=0` = old whole-mp3 path). Never talks over itself (`MIN_GAP_S`), drops a line whose frame is older than `MAX_AGE_S` before TTS; `grab_s`/`vision_s`/`tts_s`/`latency_s` per line in `<out>/comments.jsonl` + `summary.json`. The streaming endpoint is not yet verified with a real key (no ELEVENLABS secret on the VM). `--talk`: the child talks to the buddy (open mic -> Gladia). The child's first words cut the buddy off (barge-in, `ears()`); transcripts matching its own last lines (echo) are ignored; a phrase skips `MIN_GAP_S` (12 s between its own lines) and is answered with a fresh frame (`"heard"` in the row). A line too close to a recent one (`similar() >= SAME`) is not spoken (`"repeat"`). Laptop @26499ff: 21 lines spoken, 9 questions answered, latency median 1.09 s. Persona "Pixel" (`agents/prompts/kid.md`): a friend with feelings, remembers the start of the talk + the last 60 lines (`memory()`, `CHAT`), talks like a calm real person (hesitations, no hype); bot phrases in its own lines are never spoken (`BOT`), says hello/goodbye (`greet()`), answers trimmed to whole sentences (`trim()`); voice set by `P2_KID_VOICE` (`VOICE_SETTINGS`, stability 0.5, style 0). The team found the voice ad-like ("terrible", Matilda on flash). Now: ElevenLabs only (no OpenAI key), default Chris on `eleven_v3` (the team's pick by ear @2a237ce: first audio 0.47 s, laptop run latency median 1.48 s, max 2.91 s) (`P2_KID_TTS_MODEL`; `flash` read like an announcer), no "!" in TTS text and "..." pauses (`spoken()`); `eleven_v3` also performs [laughs]/[sighs] tags (prompt `{tags}`, stripped for other models). `python -m voice.commentator --try-voices` plays one casual line in 11 voice/model pairs (`CANDIDATES`) with time to first audio, so the team picks by ear. A Models call that stalls past `VISION_TIMEOUT_S`=6 s is skipped (a question is asked again) instead of waiting 30 s. The Gladia listener reconnects when its session ends (laptop: it went deaf after ~5-7 min). Last team session @ce95d25 (#51 comment 6716558071): 25 lines spoken, 1 skipped, vision median 0.41 s, latency median 1.08 s, max 1.59 s, no errors. Model `holo4-27b` (VM: ~0.3 s warm, better answers than `holo4-35b-a3b`; `P2_KID_MODEL` overrides). The window is checked every loop turn (`closed()`): on Windows the run ends ~2 s after the game closes (`GONE_S`), then says goodbye (`{"greeting": ...}` in the output).
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
