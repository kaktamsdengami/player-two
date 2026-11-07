# Issue drafts for kaktamsdengami/player-two

This uses the same format as accel_hack. Each block below becomes one GitHub issue with labels
`tier:*`, `area:*`, `status:*`, a milestone, and, where relevant, `needs:human`, `needs:local` or
`needs:team`. The creation script appends the common footer (Definition of done + agent prompt) to
every issue. **All code is written by Devin.** Claude orchestrates and runs the `needs:local` checks.

---

### T00 · Handoff kit: AGENTS.md, CLAUDE.md, HANDOFF.md, PLAN.md
tier: core · area: infra · milestone: M0 Set up · effort: ~0.5h · deps: none · resources: GitHub

**Objective.** Make the repo self-sufficient, so any agent (Devin, Claude) can continue without
chat history. It should cover:
- the rules, the live state and the plan;
- the repo layout and the game fork;
- the meaning of `needs:local` and `needs:team`;
- the rule that Devin writes the code while Claude orchestrates and checks locally.

**Owned files.** AGENTS.md, CLAUDE.md, docs/HANDOFF.md, docs/PLAN.md, .gitignore

**Acceptance checks.**
- [ ] These files are on main and describe the rules, the state and the plan.
- [ ] A fresh Devin session can start any `status:ready` issue from its prompt alone.

---

### T01 · Contracts and decisions
tier: core · area: infra · milestone: M0 Set up · effort: ~1h · deps: T00 · resources: none

**Objective.** Freeze the shared contracts, so Devin sessions can build in parallel:
- `GameEvent`, `AgentAction`, `Finding` (with `known_bug_ref`), `FixAttempt` (with
  `upstream_fix_ref`), `DebriefReport`, `PlacementSpot`, `ChildProfile`, `GameVerdict`, `Plan`;
- the SSE event types.

Record these decisions:
- the TTS provider (proposal: edge-tts, free);
- the product name;
- the voice intents: fix / skip / explain / stop / yes / no;
- the general shape of the event-log oracle, which T05 adapts to the chosen game.

**Owned files.** docs/CONTRACTS.md, app/contracts.py (Pydantic v2), docs/api-mock.json

**Acceptance checks.**
- [ ] The Pydantic models validate every sample payload in docs/api-mock.json.
- [ ] api-mock.json covers every dashboard view, so T15 can start on mock data.
- [ ] Each decision is recorded with a one-line reason.

---

### T02 · Accounts, keys and credits
tier: core · area: infra · milestone: M0 Set up · effort: ~0.5h (human) · deps: none · resources: all partners · **needs:human**

**Objective.** The human collects every key into a local `.env`. Keys never go into chat or Git.
- `HAI_API_KEY`. Also note the plan and token balance shown on platform.hcompany.ai.
- `DEVIN_API_KEY`. Also grant the Devin GitHub integration on the game fork once it exists.
- `GLADIA_API_KEY`.
- `LINKUP_API_KEY`.
- `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY`, in test mode.
- A Roblox account, for T19.

Also ask the organisers three things: the exact Gladia prize, the submission form fields, and
whether we can stay in the venue overnight.

**Owned files.** .env (git-ignored), .env.example, docs/HANDOFF.md (status only)

**Acceptance checks.**
- [ ] `python scripts/check_keys.py` (from T04) prints OK for every key without printing the key.
- [ ] The plan, the balances and the organisers' answers are recorded in docs/HANDOFF.md.

---

### T03 · Spike: can the H desktop agent play a real game? (gate)
tier: core · area: agents · milestone: M0 Set up · effort: ~1.5h · deps: T02 · resources: H Agents API · **needs:local**

**Objective.** Answer the riskiest question first. On the stage laptop (Windows 11), run H
desktop-environment sessions: first `h/holo-desktop`, then a custom agent. Use the **unmodified**
builds of the top two T05 candidates:
- Chocolate Doom with Freedoom or the shareware data;
- Shattered Pixel Dungeon, desktop JAR.

Task for the agent: "walk to the nearest wall, then into a corner, and describe what happens".
Measure:
- seconds per action;
- key and mouse accuracy;
- whether held keys work;
- whether the agent can tell game states apart.

Then estimate how much slow-mo or frame-step a real-time game needs. Write down, with numbers,
which candidate the agent can actually play. This feeds the team's T05 choice.

**Owned files.** spikes/t03/ (scripts, notes), docs/SPIKE_T03.md

**Acceptance checks.**
- [ ] 5 runs per candidate are logged with seconds per action, success yes or no, and failure modes.
- [ ] A written recommendation backed by those numbers, recorded in HANDOFF.md.

---

### T04 · Repo skeleton and CI
tier: core · area: infra · milestone: M0 Set up · effort: ~1h · deps: T01 · resources: GitHub

**Objective.**
- Lay out the product repo: `app/ agents/ launcher/ voice/ devin/ insights/ business/ web/ eval/ scripts/`.
- Python 3.12, FastAPI, pytest, ruff, GitHub Actions.
- `scripts/check_keys.py`.

The game fork is created in T05, not here.

**Owned files.** pyproject.toml, .github/workflows/, scripts/check_keys.py, the skeleton directories

**Acceptance checks.**
- [ ] CI is green.
- [ ] `pytest` and `ruff check` pass locally.

---

### T05 · Choose the real game, fork it, QA build, known-bug list
tier: core · area: game · milestone: M1 Agent finds bugs · effort: ~3h · deps: T03, T04 · resources: GitHub, the game's upstream repo and bug history, Doom Wiki "Engine bug" page (if Doom) · **needs:team**

> **Consult the team first.** Before starting, and before each decision about the game (which
> game, which version, which bugs, the QA patches, how the agent plays), post a short proposal as
> a comment on this issue. Wait for the team's answer before you build. We want a **real,
> well-known game, not an AI-generated demo game**.

**Objective.**
1. **Choose**, together with the team, from the candidates in PLAN.md section 3 (Chocolate Doom,
   Shattered Pixel Dungeon, Wesnoth, Luanti), using the T03 numbers.
2. **Fork** the game under `kaktamsdengami`. Keep the licence and credit the authors. Use only
   freely distributable game data, for example Freedoom.
3. **Pick the version.** Choose a commit or release where **3–5 known, visual, reproducible bugs**
   still exist. Each bug must have a public source (an issue, a wiki page, a commit). Where
   possible, use bugs whose **upstream fix commit** exists, so it can be compared with Devin's fix
   later.
4. **QA build patches**, kept separate from any fix:
   - slow-mo or frame-step, if the game is real-time;
   - an event log (JSONL) with player position, state, health, spawned actors and level events;
   - a reset to a chosen save or map.
5. **Known-bug list** in `eval/known_bugs.yaml`: id, title, source link, steps, expected vs
   actual, the log signature that proves it, and the upstream fix ref. This list is **hidden from
   the tester agent**.

**Owned files.** the game fork (QA patches, build docs); eval/known_bugs.yaml; docs/GAME.md (choice, licence, build steps on Windows and Linux)

**Acceptance checks.**
- [ ] The team's approval of the choice is recorded in this issue.
- [ ] The QA build compiles on Linux (Devin) and on the stage laptop (Windows). Exact commands are in docs/GAME.md.
- [ ] Each known bug is reproduced by a scripted input or save, and the log shows its signature.

---

### T06 · Launcher: build/start/stop/reset, slow-mo, screenshots, clips, log tail
tier: core · area: infra · milestone: M1 Agent finds bugs · effort: ~1.5h · deps: T05 · resources: ffmpeg (gdigrab on Windows) · **needs:team**

> **Consult the team first** on anything that changes how the game looks or plays on stage:
> window size, speed, which map or save, and sound. Post a proposal on this issue and wait for an
> answer.

**Objective.** A local controller that the orchestrator and the agent tools call. It must:
- build the fork;
- launch the game at a fixed window position and size;
- reset to the chosen map or save;
- set the speed (slow-mo or frame step);
- take screenshots;
- record the game window and cut clips by timestamp;
- tail and query the event log;
- pull and rebuild after a fix.

**Owned files.** launcher/, tests/test_launcher.py

**Acceptance checks.**
- [ ] `python -m launcher demo` builds, starts the game, records 10 s, saves the clip, stops the game, and prints the paths.
- [ ] Log queries (for example "has signature X happened since t?") are unit-tested on recorded logs.

---

### T07 · Hostile-tester agent on H desktop + report_finding tool
tier: core · area: agents · milestone: M1 Agent finds bugs · effort: ~3h · deps: T03, T06 · resources: H Agents API · **needs:team**, **needs:local**

> **Consult the team first** on the tester persona, what counts as a bug in this game, and how
> aggressive the agent should be. Post the draft prompt on this issue before tuning it.

**Objective.** A custom H agent:
- desktop environment and the "hostile QA tester" instructions;
- custom tools `report_finding(Finding)`, `note(text)` (observations for the debrief and
  placement) and `ask_developer(question)`;
- budgets `max_steps` and `max_time_s`;
- structured output with the list of findings.

The agent sees **pixels only**. It never reads the event log or the known-bug list. Keep the share
link (the live agent view) for the dashboard. Log every action with a timestamp, so clips can be
cut.

**Owned files.** agents/tester.py, agents/prompts/tester.md, agents/tools.py, tests/test_tools.py

**Acceptance checks.**
- [ ] In one session, the agent reports at least 1 known bug with usable steps. The run log and share link are in the PR.
- [ ] Every tool call arrives as a valid `Finding` or note, as defined in the contracts.

---

### T08 · Verifier: replay steps, log oracle, clip, match to known bugs
tier: core · area: agents · milestone: M1 Agent finds bugs · effort: ~2h · deps: T06, T07 · resources: H Agents API (replay), launcher · **needs:team**

> **Consult the team first** on how a match to a known bug is decided, and on what to do with
> new bugs that are not on the list. Post the rules on this issue.

**Objective.** For each `Finding`:
1. Reset the game.
2. Replay the steps. Use a deterministic input sequence where possible, otherwise a short H
   session told to "do exactly these steps".
3. Check the effect with the log oracle.
4. Cut the clip.
5. Set the status to verified or suspected.
6. Match it to `eval/known_bugs.yaml`. New verified bugs stay as new; they are a bonus.

**Owned files.** agents/verifier.py, agents/oracles.py, tests/test_oracles.py

**Acceptance checks.**
- [ ] Oracles are unit-tested on recorded logs, with one positive and one negative case per known bug.
- [ ] One real T07 finding ends up verified and matched, with a clip (path in the PR).

---

### T09 · Tester playbook skills + coverage memory
tier: core · area: agents · milestone: M1 Agent finds bugs · effort: ~1.5h · deps: T07 · resources: H skills · **needs:team**

> **Consult the team first.** Share the list of tactics on this issue before writing them as
> skills. The skills must stay **general QA tactics**, never hints about the known bugs. Otherwise
> the rediscovery claim is worthless.

**Objective.**
- Turn QA heuristics into H skills (markdown): edges and corners, input spam and combos, pause
  abuse, back-tracking and re-entry, menus during animations, "does this look interactive?",
  and genre-specific tactics (e.g. monster behaviour around walls and doors for a shooter).
- Coverage memory: pass the areas and tactics already tried into the next session.

**Owned files.** agents/skills/*.md, agents/coverage.py

**Acceptance checks.**
- [ ] Known-bug recall over 3 runs is higher with the skills than without. The numbers come from the T22 harness, or from a manual table if T22 is not ready yet.
- [ ] A team member reviews the skills and confirms that no skill leaks a known bug.

---

### T10 · Devin API client: session from a Finding, follow it, PR, merge on approval
tier: core · area: devin · milestone: M2 Fix loop and voice · effort: ~2h · deps: T01, T02 · resources: Devin API

**Objective.** Create one Devin session per verified bug on the game fork. The prompt template
contains:
- the title, the repro steps, expected vs actual;
- the log excerpt and file hints;
- the instruction "fix in source, add a regression test if the codebase allows it, open a PR".

Then:
- follow the session status and extract the PR URL;
- post status to SSE;
- merge on the human's approval (from T13 or T15);
- send feedback to the same session on "not fixed";
- log the cost per session if the API exposes it.

**Owned files.** devin/client.py, devin/prompts/fix_bug.md, tests/test_devin_client.py (mocked HTTP)

**Acceptance checks.**
- [ ] One real session for a known bug opens a PR on the fork. The link is in the PR.
- [ ] Mocked tests cover create, follow, PR extraction and the feedback round.

---

### T11 · Fix → rebuild → re-verify loop, compare with the upstream fix
tier: core · area: devin · milestone: M2 Fix loop and voice · effort: ~1.5h · deps: T08, T10

**Objective.** After the merge:
1. Pull, rebuild and relaunch through the launcher.
2. Replay the finding with the verifier and mark it fixed or not fixed.
3. If not fixed, send at most 1 feedback round to Devin, then stop with an honest status.
4. Produce a **side-by-side diff of Devin's fix and the upstream fix commit**, plus a one-line
   assessment: same approach / different but valid / incomplete.

**Owned files.** agents/fix_loop.py, insights/fix_compare.py, tests/test_fix_loop.py

**Acceptance checks.**
- [ ] End to end on one known bug: found, verified, Devin PR, merged, and the replay shows the fix (log and clip in the PR).
- [ ] The comparison with upstream is rendered for that bug.

---

### T12 · Voice out: narration synced with the clip
tier: core · area: voice · milestone: M2 Fix loop and voice · effort: ~1.5h · deps: T08 · resources: TTS per T01

**Objective.** Turn a verified `Finding` into a short spoken explanation in the developer's
language, for example "Look: if I stand here, the monster comes out through the wall. Want me to
fix it?". Add timing cues, so the clip plays the matching moment while the voice speaks. Add short
voice lines for status changes (Devin working, fixed).

**Owned files.** voice/narrate.py, voice/tts.py, tests/test_narrate.py

**Acceptance checks.**
- [ ] For a verified finding, an audio file and a cue list are produced, and dashboard playback is in sync (screen recording in the PR).

---

### T13 · Voice in: Gladia real-time with intents
tier: core · area: voice · milestone: M2 Fix loop and voice · effort: ~2h · deps: T02 · resources: Gladia real-time STT · **needs:local**

**Objective.**
- Stream the microphone to Gladia real-time.
- Intents: fix / skip / explain / stop / yes / no.
- Free-form steering text is forwarded to the running H session as a message, for example "try
  the door again".
- Any language.
- Push-to-talk and buttons as a fallback for a noisy hall.

**Owned files.** voice/listen.py, voice/intents.py, tests/test_intents.py

**Acceptance checks.**
- [ ] Spoken "fix it" and "stop" are recognised in English and French (transcripts in the PR).
- [ ] Every intent also works with a button.

---

### T14 · Orchestrator state machine + SSE events
tier: core · area: infra · milestone: M2 Fix loop and voice · effort: ~2h · deps: T08, T11, T12, T13

**Objective.** One process runs a whole session: explore → finding → verify → present (voice +
clip) → wait for approval → fix → re-verify → next. It can be stopped at any point. FastAPI
publishes every state change as SSE events (per T01) and serves clips and screenshots.

**Owned files.** app/main.py, app/orchestrator.py, tests/test_orchestrator.py

**Acceptance checks.**
- [ ] A full session on the real game runs from one command, and the SSE stream shows every state.
- [ ] Stop halts the H session within 5 s.

---

### T15 · Dashboard: live view, bug cards, Devin status, debrief, plans
tier: core · area: ui · milestone: M2 Fix loop and voice · effort: ~2.5h · deps: T01 (mock), T14 (live)

**Objective.** A web dashboard (React/Vite) that looks great on a projector. It shows:
- the live agent view (the H share link or the screen);
- an action timeline;
- bug cards with the clip, a "Fix?" button and the status;
- a Devin panel with the PR link and the comparison with upstream;
- a voice indicator;
- a Debrief tab;
- a Plans page (T18).

It starts on api-mock.json and switches to live data with an environment variable.

**Owned files.** web/

**Acceptance checks.**
- [ ] Every view renders on mock data; screenshots in the PR.
- [ ] `VITE_API_BASE` switches it to the live API.

---

### T16 · Design debrief: friction, difficulty, deaths heatmap
tier: core · area: insights · milestone: M3 Insights and business · effort: ~1.5h · deps: T07, T08 · resources: Linkup

**Objective.** After a session:
- deaths and retries per area, from the log, drawn as a heatmap over the map;
- the agent's own notes ("confusing", "too hard");
- each finding with a suggested change;
- one or two design references from Linkup, with citations.

**Owned files.** insights/debrief.py, tests/test_debrief.py

**Acceptance checks.**
- [ ] The debrief JSON validates against `DebriefReport` and contains evidence from the real run.

---

### T17 · Product-placement scout with Linkup brand candidates
tier: core · area: insights · milestone: M3 Insights and business · effort: ~1.5h · deps: T07 · resources: Linkup

**Objective.**
- From the agent's notes and screenshots, find in-game objects or surfaces that suit native
  placement (screens, posters, walls, items).
- Score each by screen time and visibility, using the log and the agent's path.
- Ask Linkup for brand candidates per spot and audience, with sources.
- Present them as suggestions, never as claims of brand deals.

**Owned files.** insights/placement.py, tests/test_placement.py

**Acceptance checks.**
- [ ] At least 3 spots are found in the real run, each with 2–3 brand candidates and source links.

---

### T18 · Stripe: three plans, Checkout, webhook → plan flag
tier: core · area: business · milestone: M3 Insights and business · effort: ~1h · deps: T15 · resources: Stripe test mode

**Objective.**
- Three products with prices in test mode: Pro (developer), Parent, Kid.
- Checkout opens from the Plans page.
- The webhook sets the active plan, which unlocks the matching mode in the dashboard.

**Owned files.** business/stripe_plans.py, app/routes_billing.py, tests/test_billing.py

**Acceptance checks.**
- [ ] A checkout with a test card switches the plan in the UI (screenshots in the PR).
- [ ] The webhook signature is verified.

---

### T19 · Publish to Roblox via Roblox Studio
tier: second-layer · area: agents · milestone: M3 Insights and business · effort: ~2h · deps: T03 · resources: Roblox Studio, Roblox account, H desktop · **needs:human**, **needs:local**

**Objective.** The H desktop agent opens a prepared Roblox place in Studio and publishes it. It
fills in the name, the description (generated from the debrief), the genre and the age guidance.
- The **human logs in once**. The agent never types passwords.
- Before any terms or agreement screen, the agent stops and asks for confirmation through
  `ask_developer`.

**Owned files.** agents/publish_roblox.py, agents/prompts/publish_roblox.md, docs/ROBLOX.md

**Acceptance checks.**
- [ ] One publish is completed, and the human confirmation step is visible in the run log. The link to the published place is in the PR.

---

### T20 · Parent mode: child profile → overnight evaluation → morning report
tier: second-layer · area: agents · milestone: M3 Insights and business · effort: ~2.5h · deps: T03, T17 · resources: H schedules, Linkup

**Objective.**
- The parent describes the child: age, interests, fears, learning goals. This becomes a
  `ChildProfile`, stored locally only.
- An H schedule runs sessions overnight. Each tries a game from a shortlist of free games
  (Roblox experiences or free demos). Linkup builds the shortlist, with ratings and sources.
- Each session plays a few minutes and returns a `GameVerdict`: scary, educational, fit, reasons,
  screenshots.
- A morning report ranks the games.
- Any purchase is only prepared and waits for the parent's explicit confirmation.

**Owned files.** agents/parent_mode.py, agents/prompts/parent.md, insights/parent_report.py

**Acceptance checks.**
- [ ] A report for one profile covering at least 3 games, each verdict with screenshots and reasons.
- [ ] The confirmation gate appears before any purchase step.

---

### T21 · Kid mode: friend commentator
tier: second-layer · area: voice · milestone: M3 Insights and business · effort: ~1.5h · deps: T12 · resources: H Models API (holo4-35b-a3b), TTS

**Objective.** While a kid plays:
1. Take a screenshot every ~3 s.
2. A fast Holo model writes a short, friendly, age-appropriate comment or suggestion.
3. TTS speaks it.

A rate limit keeps it from talking over the game. Real-time co-op control of player 2 is out of
scope because of agent latency (that is stretch T31); we say this honestly on stage.

**Owned files.** voice/commentator.py, agents/prompts/kid.md

**Acceptance checks.**
- [ ] 2 minutes of play produce comments that match the screen (recording in the PR), with the latency per comment reported.

---

### T22 · Evaluation harness
tier: core · area: eval · milestone: M4 Pitch-ready · effort: ~2h · deps: T08, T11

**Objective.** Run N tester sessions on the QA build at the known-bug version. Record:
- recall of `eval/known_bugs.yaml`;
- false positives (verified vs suspected);
- new bugs found;
- time to the first verified bug;
- actions per bug;
- H tokens and cost;
- Devin fix success and time;
- similarity of each fix to the upstream fix.

Write one record per run in eval/runs/.

**Owned files.** eval/harness.py, eval/runs/, tests/test_harness.py

**Acceptance checks.**
- [ ] `python -m eval.harness --runs 3` writes run records and a summary table.

---

### T23 · Final runs and frozen numbers
tier: core · area: eval · milestone: M4 Pitch-ready · effort: ~1.5h (mostly waiting) · deps: T22, T14 · **needs:local**

**Objective.** Run as many full runs as time allows on the stage laptop, aiming for 10. Freeze the
numbers in eval/RESULTS.md. Every number in the pitch comes from that file.

**Owned files.** eval/RESULTS.md

**Acceptance checks.**
- [ ] Every number in RESULTS.md links to its run records. No target is presented as a measurement.

---

### T24 · Pitch deck, README, architecture figure, criterion → evidence
tier: core · area: submission · milestone: M4 Pitch-ready · effort: ~1.5h · deps: T23 (numbers); start early

**Objective.**
- A short deck: the problem (playtesting is manual and slow), the live demo on a famous game, how
  it works, the numbers, Devin vs upstream fixes, three audiences and plans, why now.
- A demo script with LIVE / RECORDED labels.
- A README with run steps.
- An architecture figure.
- A criterion → evidence table.
- A Q&A sheet covering: latency and slow-mo, why the bug list is hidden from the agent, privacy for
  kids, why not the engine's copilot, what Devin does, game licences.

**Owned files.** README.md, docs/pitch/, docs/architecture.png

**Acceptance checks.**
- [ ] Every claim is backed by RESULTS.md or a source.
- [ ] The demo script fits the pitch time, and it was timed.

---

### T25 · Backup demo video
tier: core · area: submission · milestone: M4 Pitch-ready · effort: ~1.5h · deps: T15, T23 · **needs:human**

**Objective.** A 2–3 minute recording of the best full run: the agent breaks the famous game,
explains the bug by voice, Devin fixes it, the replay proves the fix, then the comparison with
upstream, the debrief and the placement. Captions are burned in, and the video is labelled
RECORDED. It is also used for the social posts.

**Owned files.** video/ (script.md, render notes); large media git-ignored

**Acceptance checks.**
- [ ] The MP4 plays offline on the stage laptop, with no secrets visible.

---

### T26 · Final verification and rehearsal on the stage laptop
tier: core · area: submission · milestone: M4 Pitch-ready · effort: ~1h · deps: all core · **needs:local**

**Objective.**
- A clean-boot checklist: keys, mic, window positions, game reset, network fallback (a phone
  hotspot), the backup video ready.
- 2 timed rehearsals of the pitch and demo.
- Q&A practice with the T24 sheet.

**Owned files.** docs/STAGE_CHECKLIST.md

**Acceptance checks.**
- [ ] 2 rehearsals are done within the time limit, and the checklist is ticked.

---

### T27 · Submission on the hack platform, all fields
tier: core · area: submission · milestone: M4 Pitch-ready · effort: ~0.5h · deps: T24, T25 · **needs:human**

**Objective.** Fill in every field on builderbase before the official deadline. Make the repos
public if required, after checking that no secrets are in the history.

**Owned files.** docs/SUBMISSION.md (a copy of what was submitted)

**Acceptance checks.**
- [ ] The submission is confirmed, and the confirmation is recorded in HANDOFF.md.

---

### T28 · LinkedIn and X posts
tier: core · area: submission · milestone: M4 Pitch-ready · effort: ~0.5h · deps: T25 · **needs:human**

**Objective.** One post each on LinkedIn and X, with a 20–30 s clip, tagging H Company, 42AI,
Gladia, Cognition/Devin, Linkup and Stripe. An agent drafts the texts; the human publishes them.

**Owned files.** docs/pitch/posts.md

**Acceptance checks.**
- [ ] Both posts are live, and their links are recorded in HANDOFF.md.

---

### Stretch
- **T29** A second real game: run the tester on the other T05 candidate to prove the agent is general.
- **T30** Parallel testers: H subagents explore several maps or builds at once and merge their findings.
- **T31** Co-op player 2 for a slow or turn-based game.
- **T32** Publish to itch.io.

---

## Common footer (added to every issue)

## Definition of done
Acceptance checks pass, with the exact commands and their output in the PR. docs/HANDOFF.md is updated, the branch is pushed, and the PR is open and linked. Never invent results. Context: docs/PLAN.md.

## Prompt for any agent
> Read AGENTS.md and docs/HANDOFF.md in kaktamsdengami/player-two. Take issue Txx (#N), work on branch txx-short-name, implement only this issue, meet its acceptance checks, update docs/HANDOFF.md, push, and open a PR linked to the issue. Do not close the issue. If the issue is labelled needs:team, post your proposal as an issue comment and wait for the team's answer before building.

## Labels and milestones to create
- Tier: `tier:core`, `tier:second-layer`, `tier:stretch`
- Area: `area:infra`, `area:game`, `area:agents`, `area:devin`, `area:voice`, `area:ui`, `area:insights`, `area:business`, `area:eval`, `area:submission`
- Status: `status:ready`, `status:blocked`, `status:in-progress`, `status:review`
- Needs: `needs:human`, `needs:local`, `needs:team`
- Milestones (no dates): M0 Set up · M1 Agent finds bugs · M2 Fix loop and voice · M3 Insights and business · M4 Pitch-ready
