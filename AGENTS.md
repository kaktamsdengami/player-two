# AGENTS.md: rules for every coding agent (Devin, Claude, others)

You are joining a hackathon build (H Company × 42AI Computer Use Agents Hackathon, Paris).
**Devin writes all the code.** Claude orchestrates: it keeps the plan and the issues, reviews PRs,
and runs checks on the stage laptop. **Everything you need is in this repo. Do not rely on chat
history.**

## Read first, in this order

1. `docs/HANDOFF.md`: the live state (what is done, in progress, next, blocked).
2. `docs/PLAN.md`: product, architecture, resources, task map.
3. `docs/CONTRACTS.md` (after T01): data and API contracts. Do not change them without noting it
   in HANDOFF.md and the issue.
4. Your GitHub issue `[Txx]`: objective, dependencies, owned files, acceptance checks.

## Project in one line

PLAYER TWO: a computer-use agent (H Company Agents API, desktop environment) plays a **real
open-source game** like a hostile QA tester. It finds bugs from pixels, explains them by voice
while replaying them, and gets them fixed through the **Devin API**. Then it proves each fix by
replaying the bug, and writes a design and product-placement debrief.

## Repositories

- `kaktamsdengami/player-two`: the product (this repo).
- A fork of the chosen game under `kaktamsdengami`, created in T05. It holds the QA-build patches.
  Runtime fix PRs opened by the product's Devin sessions land there, never here.

## Labels that change how you work

- `needs:team`: **talk to the team before building.** Post your proposal as a comment on the
  issue. Cover the game choice, version, bugs, QA patches, tester persona and on-stage look. Wait
  for an answer from a team member before you implement.
- `needs:local`: the task must run on the stage laptop (Windows 11), which has the H desktop
  agent, Roblox Studio and the microphone. Devin's machine cannot reach it. Build and unit-test
  what you can, push it, and write in the PR the exact commands for the local check. Claude runs
  them and posts the output back to the issue.
- `needs:human`: a human action (accounts, keys, logins, recordings). Do not try to do it yourself.

## Stack (proposed; T01 ratifies)

- Python 3.12, FastAPI, Pydantic v2, pytest, ruff, GitHub Actions.
- H Agents API through the `hai-agents` SDK (`HAI_API_KEY`). Models API is OpenAI-compatible at
  `https://api.hcompany.ai/v1/`.
- Devin API (`DEVIN_API_KEY`), Gladia real-time STT, Linkup, Stripe (test mode).
- `web/`: React + Vite dashboard.
- ffmpeg for clips.

## Layout (target)

```
app/        FastAPI app, orchestrator, shared contracts (app/contracts.py)
agents/     tester, verifier, oracles, skills/, prompts/, fix loop, side modes
launcher/   build/start/stop/reset the game, speed control, screenshots, clips, log queries
devin/      Devin API client and prompt templates
voice/      TTS narration, Gladia listener, intents, kid commentator
insights/   debrief, placement scout, fix comparison, parent report
business/   Stripe plans
web/        dashboard
eval/       known_bugs.yaml, harness, runs/, RESULTS.md
scripts/    utilities (check_keys.py, ...)
docs/       PLAN, CONTRACTS, HANDOFF, GAME, pitch/
```

## Working rules

- One issue = one branch `txx-short-name` = one PR that links the issue. Do not close issues; the
  orchestrator closes them after checking.
- Touch only the files your issue owns. Shared files (`app/contracts.py`, CI, `AGENTS.md`,
  `docs/CONTRACTS.md`, `pyproject.toml`) need a note in the issue before editing.
- Commit small and push after every working step, including WIP. A session that gets cut off must
  lose minutes, not hours.
- Before you stop (done, blocked, or near a limit): update `docs/HANDOFF.md` and push.
- Secrets live in `.env` (git-ignored). Keep `.env.example` current. Never commit keys, game data
  that is not freely distributable, recordings with secrets, or personal data (child profiles stay
  local).
- **The tester agent must never see the known-bug list** (`eval/known_bugs.yaml`) or the event log
  while exploring. Skills hold general QA tactics only. Otherwise the rediscovery result means
  nothing.
- Every number in the README or pitch must come from a run record in `eval/runs/`. Mark demo
  content LIVE or RECORDED. Never invent results; a target is not a measurement.
- Respect the game's licence. Credit the authors. Ship only freely distributable data (e.g. Freedoom).
- Ask for human confirmation before irreversible or outward actions: merges, publishing, terms of
  service, purchases.

## Definition of done (every task)

The issue's acceptance checks pass, with the exact commands and their output in the PR (for
`needs:local`: the commands to run, then the orchestrator's output). HANDOFF.md is updated, the
branch is pushed, and the PR is open and linked.

## Handoff prompt (copy-paste for the next agent)

> Read AGENTS.md and docs/HANDOFF.md. Take issue Txx in kaktamsdengami/player-two, work on branch
> txx-<name>, implement only that issue, meet its acceptance checks, update docs/HANDOFF.md, push,
> and open a PR linked to the issue. Do not close the issue. If it is labelled needs:team, post
> your proposal as an issue comment and wait for the team's answer before building.
