# HANDOFF: live state of the build

Update this file before you stop working. Put the newest entry on top. Keep it short and factual.

## Current state (2026-11-07 ~21:10 Paris, Devin)

- **Done (merged):** T01 contracts (#34), T04 skeleton + CI (#35), T15 dashboard on mock data (#37),
  T18 Stripe test-mode plans (#39), T10 Devin API client (#36), T05 game + QA build (#40),
  T06 launcher (#41). The KB1 fix PR from the T10 session
  (https://github.com/kaktamsdengami/chocolate-doom/pull/1) stays open: merge + replay are T11.
  **Stage bug = KB3 on E3M1** (red sky stays red while the world goes grey).
- **Not verified on Windows yet (T06):** gdigrab capture and Win32 foregrounding (commands in #41).
- **In progress (branches pushed, PRs next):** T07 tester (`t07-hostile-tester`; QA debug codes
  allowed, team decision in chat), T08 verifier (`t08-verifier-replay-steps`, 14 oracle tests on
  real logs), T12 narration on ElevenLabs (`t12-voice-out-narration`; replaces edge-tts from T01).
  The first real H tester run on the Devin VM got no screenshots (pyscreeze needs
  `XDG_SESSION_TYPE=x11`, fixed); rerun waits for a free H slot.
- **Open PRs:** T13 Gladia voice in (#38, needs:local): waits for the stage-laptop mic output
  (optional: buttons cover every intent).
- **Next:** T11 fix loop, T14 orchestrator, T09 skills.
- **Need from you:** the T13 mic check and the T06 Windows check on the stage laptop, when convenient.
- T18 note: `POST /api/billing/webhook` is a new endpoint; T14 must mount `app.routes_billing.router`
  and add it to CONTRACTS.md.

## Log

### 2026-11-07: T11 fix loop + upstream comparison (Devin)

- `agents/fix_loop.py`: `FixLoop.run(finding, attempt)`: follow the Devin session to `pr_open`,
  merge (only if `approve(attempt)`), pull + rebuild the base branch, replay, mark `fixed` /
  `not_fixed`; on `not_fixed` one `send_feedback` round, then stop with an honest status.
  `ScriptReplay` replays a known bug with its fork QA script (deterministic, no H) and records a clip.
- Fixes merge into a per-run fork branch `qa-run/<name>` (made from `player-two-qa`), so the QA
  branch keeps its known bugs for the next demo. `python -m agents.fix_loop FINDING.json --bug KB1
  --script qa/kb1_kb2_medikit.txt --map 1 1 --base qa-run/kb1-t11 [--attempt ATTEMPT.json]`.
- `insights/fix_compare.py`: Devin PR diff vs `KnownBug.upstream_fix_ref` commit (code files only,
  upstream limited to the files Devin touched), verdict same_approach / different_but_valid /
  incomplete (replay decides incomplete; an H Models call `holo4-27b` decides the rest, token
  overlap as fallback), `render_html` side-by-side page. KB3 has no upstream fix: no comparison.
- Real run: KB1 fork PR #1 merged into `qa-run/kb1-t11`, rebuilt, replay log shows
  "Never give up!", verdict different_but_valid. The finding was a scripted one, not from the H tester.

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
