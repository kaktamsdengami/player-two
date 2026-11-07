# Build plan: PLAYER TWO, the agent that plays your game (H Company × 42AI Computer Use Hackathon)

Working name: **PLAYER TWO** (confirm in T01). GitHub issues are the source of truth for task
status; this file holds the design, the decisions and the task map. Official submission deadline
(the only fixed date): Sunday 2026-11-08 14:00. Final pitches start at 15:45.

## 1. Product in one paragraph

A game developer points PLAYER TWO at a build of their game. A **computer-use agent plays it like
a hostile QA tester**. It walks into walls, spams inputs, pauses at the wrong moment and goes
through levels out of order, and it **decides by itself what to try**. When it breaks something,
it **tells the developer by voice while replaying the bug on screen**: "Look, if I do this, the
monster comes out through the wall. Fix it?". On a spoken "yes", the product **calls the Devin
API**. Devin opens a PR with the fix, the game is rebuilt, and the agent **replays the same steps
to prove the bug is gone**. After the session, a **debrief** lists game-design friction and
**product-placement spots** (for example, a wall clock is room for a watch brand), with brand
candidates found by Linkup.

Side features that others will not have:
- **publishing to Roblox** through Roblox Studio;
- a **parent mode**: the agent tries free games overnight against a child's profile;
- a **kid mode**: the agent comments like a friend on the couch.

Three Stripe plans: Pro (developer), Parent, Kid.

## 2. Judging criteria → evidence

| Criterion (weight) | What we show | Tasks |
|---|---|---|
| Use of Computer Use (25%) | Desktop, not web. A **real, well-known game**. The agent decides what to try, sees only pixels, and drives keyboard and mouse. Roblox Studio publish is a second desktop app | T03, T07, T09, T19 |
| Technical execution & reliability (25%) | Recall of **known historical bugs** over N runs, false positives, fix success through Devin, replay-verified fixes, and **Devin's fix compared with the real upstream fix** | T08, T11, T22, T23 |
| Usefulness & impact (20%) | QA playtesting is slow, manual and expensive. Developer debrief plus a monetisation angle (placement). Parent and kid modes widen the market | T16, T17, T20, T24 |
| Originality (15%) | Hostile-tester persona, voice + replay of the bug, self-fixing loop, rediscovering famous bugs, placement scouting, three audiences | T05, T12, T17, T20, T21 |
| UX & user control (10%) | Nothing changes without a spoken or clicked "yes" (fixes, merges, publish, ToS, purchases); live agent view; stop button | T13, T14, T15 |
| Demo & Q&A (5%) | One end-to-end journey, live, with a recorded backup, rehearsed | T25, T26 |

| Prize | How we compete | Tasks |
|---|---|---|
| **Best Use of Devin (€1k)** | **The Devin API is a runtime component.** The Devin team said on site that this is what they judge. Every confirmed bug becomes a Devin session; the product follows it, takes the PR, merges on approval and verifies the fix. Devin also writes all the product code from these issues | T10, T11 |
| Best Use of Gladia | Two-way voice: the developer steers the agent and approves fixes by voice in real time, in any language | T13 |
| LinkedIn / X posts (€500 + €500) | A clip of the agent breaking a famous game and the fix landing | T28 |

The **4-of-5 partner** rule: all five are covered. H runs the agent, Devin runs the fix loop,
Gladia handles voice in, Linkup provides design references and brands, Stripe handles the plans.

## 3. Real game, real bugs (no AI-generated demo game)

**Principle.** We test a **real, recognisable open-source game** at a **version where known bugs
still exist**. The game's own bug history gives us the ground truth: the bug list, the steps, and
the **upstream fix commit**. That makes three strong claims possible:
1. The agent **rediscovers known bugs blind**. It only sees pixels; the bug list is hidden from it.
2. Devin fixes them in the real codebase.
3. **Devin's fix vs the real developers' fix** is shown side by side.

Source code is required for the fix loop, so the target must be open source. We work in **a fork
under `kaktamsdengami`**, keep the original licence and credit the authors.

**Candidates (final choice in T05, together with the team):**

| Game | Why | Watch out |
|---|---|---|
| **Doom via Chocolate Doom** (GPL) + Freedoom (BSD) or the freely distributable shareware data | Iconic; the best wow on stage. The Doom Wiki keeps a documented list of **vanilla engine bugs** with explanations. Chocolate Doom reproduces them on purpose, and the source is small C that builds easily | Real-time: needs a QA patch with slow motion or a frame step. Some bugs depend on a specific map; choose bugs that are visible and reproducible |
| **Shattered Pixel Dungeon** (GPL, Java, desktop build via Gradle) | **Turn-based**, so agent latency does not matter. Very popular, pretty pixel art, public GitHub history of bugs and fixes | Bugs are often about items or logic, which is less visual than clipping; pick visual ones |
| **Battle for Wesnoth** (GPL) | Turn-based and beautiful, with a large public bug tracker | Heavy C++ build, especially on Windows |
| **Luanti / Minetest** (LGPL) | 3D voxel game with a big community and its own issue tracker | Real-time 3D: harder for the agent; bugs not yet checked |

Current recommendation: **Doom** for the wow (with a QA slow-motion patch) or **Shattered Pixel
Dungeon** for reliability. The team decides in T05 after a 15-minute look at both.

**QA build.** We add small QA-only patches to the fork, as studios do in internal test builds:
- **Slow motion / frame step** for real-time games. A computer-use agent needs seconds per action.
- **Event log (oracle):** player position, state, health, spawned actors, level events, as JSONL.
  The agent **never reads it while exploring**. It is used afterwards to **verify** a reported bug
  deterministically, which removes false positives.

These patches are tooling, not fixes, and they are kept separate from the bug-fix PRs.

## 4. How the agent finds and fixes bugs

1. **Explore (T07, T09).** An H desktop agent session with a **hostile QA tester** skill set: edges
   and corners, input spam and combos, pause abuse, back-tracking, menus during animations, "does
   this look interactive?". It keeps a coverage memory across runs. The custom tool
   `report_finding()` emits a structured `Finding` with: what, where, steps, expected vs actual,
   severity and screenshots.
2. **Verify and record (T08).** Reset the game, replay the steps and check the effect with the log
   oracle. Cut a clip. Only verified findings reach the developer; unverified ones are kept as
   "suspected". Verified findings are matched against the known-bug list for evaluation.
3. **Present (T12, T13).** Voice narration and the replay clip in sync. The developer answers by
   voice: fix, skip, explain or stop.
4. **Fix (T10, T11).** A Devin API session receives the bug report, the steps, a log excerpt and
   file hints, and opens a PR on the fork. After approval and merge, the game is rebuilt and
   relaunched, the agent replays the steps, and the result is fixed or not fixed. If not fixed,
   one feedback round goes back to the same Devin session. The final fix is compared with the
   upstream fix commit.

## 5. Architecture

```
 developer (voice / clicks)
   │  Gladia real-time STT ▲ TTS narration
   ▼                       │
 [Orchestrator / state machine]  explore → finding → verify → present → approve → fix → re-verify
   │        │                │                     │
   │        │                │                     └─► Devin API: session per bug → PR on the game fork
   │        │                └─► Linkup: design references, brand candidates for placement
   │        └─► Launcher (local): build/start/stop/reset the game, slow-mo, screenshots, clips, log oracle
   └─► H Agents API: desktop environment, tester skills, custom tools (report_finding,
       ask_developer), structured output; share link = live agent view
 FastAPI (SSE events) ─► Dashboard (live view, bug cards + clips, Devin status, debrief, plans)
 Stripe Checkout (test mode): Pro / Parent / Kid → webhook → plan flag
 Side: Roblox Studio publish (H desktop), parent overnight evaluation (H schedules), kid commentator
```

Repositories:
- `kaktamsdengami/player-two` holds the product (this plan).
- A **fork of the chosen game** under `kaktamsdengami`, with the QA patches. **Devin's runtime fix
  PRs land in the fork**, so product PRs and game fixes never mix.

## 6. Contracts (frozen in T01, in docs/CONTRACTS.md and app/contracts.py)

- `GameEvent`: one log line.
- `AgentAction`.
- `Finding`: id, kind (bug, design or placement), title, location, steps[], expected, actual,
  severity, evidence (screenshots, clip), known_bug_ref, and status (suspected, verified,
  presented, fixing, fixed or wontfix).
- `FixAttempt`: devin_session_id, pr_url, round, result, upstream_fix_ref.
- `DebriefReport`.
- `PlacementSpot`.
- `ChildProfile`.
- `GameVerdict`.
- `Plan`.
- SSE event types.

## 7. Resources

### Product (runtime)

| Resource | Job | Tasks |
|---|---|---|
| H Agents API: desktop environment, skills, custom tools, structured output, share link, schedules, vaults | the tester, verifier replays, Roblox publish, parent overnight runs | T03, T07, T09, T19, T20 |
| H Models API (holo4-35b-a3b, the fast model) | kid-mode commentary, cheap screen checks | T21 |
| Devin API | runtime fix loop, one session per bug | T10, T11 |
| Gladia real-time STT | developer voice commands and replies | T13 |
| TTS (decided in T01) | agent narration | T12 |
| Linkup | design references, brand candidates with sources, game info for parent mode | T16, T17, T20 |
| Stripe (test mode) | three plans, Checkout, webhook | T18 |
| Roblox Studio + Roblox account | publish target | T19 |
| GitHub | issues, PRs, CI, the game fork | all |

### Development capacity

- **All code is written by Devin.** Each issue gets its own Devin session, and many sessions run in
  parallel.
- **Claude (desktop app) does not write product code.** It orchestrates: it keeps the plan and
  issues current, reviews PRs, and runs the `needs:local` checks on the stage laptop. It posts the
  exact output back into the issue or the Devin session, so Devin can fix what failed.
- Devin's machine is Linux and cannot reach our Windows desktop. Anything that needs the H desktop
  agent, Roblox Studio or the microphone is labelled `needs:local`.

## 8. Tasks

Labels:
- `needs:human`: a human action, such as accounts, keys, logins or a recording.
- `needs:local`: must run on the stage laptop.
- `needs:team`: talk to the team before building and before every decision about the game.

**V0 Setup (M0)**
- **T00** Handoff kit: AGENTS.md, CLAUDE.md, HANDOFF.md, PLAN.md · core · infra · deps: none
- **T01** Contracts and decisions · core · infra · deps: T00
- **T02** Accounts, keys and credits · core · infra · deps: none · needs:human
- **T03** Spike: can the H desktop agent play a real game? (gate) · core · agents · deps: T02 · needs:local
- **T04** Repo skeleton and CI · core · infra · deps: T01

**V1 The agent finds bugs (M1)**
- **T05** Choose the real game, fork it, build the QA version, build the known-bug list · core · game · deps: T03, T04 · needs:team
- **T06** Launcher: build/start/stop/reset, slow-mo, screenshots, clips, log tail · core · infra · deps: T05 · needs:team
- **T07** Hostile-tester agent on H desktop + report_finding tool · core · agents · deps: T03, T06 · needs:team, needs:local
- **T08** Verifier: replay steps, log oracle, clip per finding, match to known bugs · core · agents · deps: T06, T07 · needs:team
- **T09** Tester playbook skills + coverage memory · core · agents · deps: T07 · needs:team

**V2 Fix loop and voice (M2)**
- **T10** Devin API client: session from a Finding, follow it, PR, merge on approval · core · devin · deps: T01, T02
- **T11** Fix → rebuild → re-verify loop, compare with the upstream fix · core · devin · deps: T08, T10
- **T12** Voice out: narration synced with the clip · core · voice · deps: T08
- **T13** Voice in: Gladia real-time, with intents · core · voice · deps: T02 · needs:local
- **T14** Orchestrator state machine + SSE events · core · infra · deps: T08, T11, T12, T13
- **T15** Dashboard: live view, bug cards, Devin status, debrief, plans · core · ui · deps: T01 (mock), T14 (live)

**V3 Insights and business (M3)**
- **T16** Design debrief: friction, difficulty, deaths heatmap · core · insights · deps: T07, T08
- **T17** Product-placement scout with Linkup brand candidates · core · insights · deps: T07
- **T18** Stripe: three plans, Checkout, webhook → plan flag · core · business · deps: T15
- **T19** Publish to Roblox via Roblox Studio · second-layer · agents · deps: T03 · needs:human, needs:local
- **T20** Parent mode: child profile → overnight evaluation → morning report · second-layer · agents · deps: T03, T17
- **T21** Kid mode: friend commentator · second-layer · voice · deps: T12

**V4 Evidence and pitch (M4)**
- **T22** Evaluation harness · core · eval · deps: T08, T11
- **T23** Final runs and frozen numbers · core · eval · deps: T22, T14 · needs:local
- **T24** Pitch deck, README, architecture figure, criterion → evidence · core · submission · deps: T23 (numbers); start early
- **T25** Backup demo video · core · submission · deps: T15, T23 · needs:human
- **T26** Final verification and rehearsal on the stage laptop · core · submission · deps: all core · needs:local
- **T27** Submission on the hack platform · core · submission · deps: T24, T25 · needs:human
- **T28** LinkedIn and X posts · core · submission · deps: T25 · needs:human

**Stretch**
- **T29** A second real game, to prove the agent is general
- **T30** Parallel testers (H subagents)
- **T31** Co-op player 2 for a slow or turn-based game
- **T32** itch.io publish

## 9. Order and parallel work

```
T00 ─► T01 ─► T04 ─┐
T02 (human) ─► T03 ┴─► T05 (team) ─► T06 ─► T07 ─► T08 ─┬─► T11 ─► T14 ─► T22 ─► T23 ─► T24 ─► T26 ─► T27
                                              T09 ◄──┘   │     ▲                    T25 ─┘  T28
                    T10 (after T01+T02) ─────────────────┘     │ T12, T13 in parallel
T15 from T01 on mock data → live after T14;  T16, T17 after T07;  T18 after T15
T19, T20 after T03 (side features);  T21 after T12
```

Parallel Devin sessions with no shared files:
- after T01: T04, T10, T15 (mock);
- after T08: T11, T12, T16, T17 together;
- T13 as soon as the Gladia key exists;
- T19 and T20 any time after T03.

Milestones:
- **M0** set up;
- **M1** the agent finds a verified known bug in the real game;
- **M2** voice + Devin fix verified end to end;
- **M3** debrief, placement, Stripe, side features;
- **M4** numbers frozen, pitch-ready, submitted.

## 10. Handoff between agents

- State lives in the repo: `AGENTS.md`, `docs/HANDOFF.md`, `docs/CONTRACTS.md`, and the issues.
  Each issue is self-contained and ends with a copy-paste prompt.
- Commit small and push after each working step. WIP branches are pushed too.
- Before stopping, the agent updates `HANDOFF.md`, pushes, and prints the next prompt.

## 11. Risks and fallbacks

| Risk | Fallback |
|---|---|
| The H desktop agent is too slow for a real-time game (T03) | QA slow-mo or frame-step patch; or switch to the turn-based candidate (Shattered Pixel Dungeon) |
| The chosen game's build is too heavy | The next candidate in the T05 table; the decision is recorded in HANDOFF.md |
| The known bugs are not visual enough | Pick bugs with a visible effect; the event-log oracle proves the rest |
| The agent reports false bugs | Only log-verified findings are presented; the rest are labelled "suspected" |
| The Devin fix takes long on stage | Start the fix live and show the session; a recorded fix of the same bug as backup, labelled RECORDED |
| Licence or assets of the game | Open-source engine + free data (e.g. Freedoom); licence and credits in the README; nothing proprietary is shipped |
| Gladia or the microphone fails in a noisy hall | Push-to-talk, plus a button for every voice intent |
| Roblox login, 2FA or ToS blocks the agent | The human logs in once; the agent stops before ToS and asks; otherwise show it recorded |
| Child-privacy questions about the kid and parent modes | Profiles stay local; nothing is published or bought without parental confirmation |
| Live demo fails on stage | Recorded backup video (T25) |
