# PLAYER TWO

**An H desktop agent plays real Doom from pixels like a hostile QA tester, finds a visual bug,
proves it, explains it by voice, and gets it fixed by the Devin API.**

Built at the H Company × 42AI Computer Use Agents Hackathon (Paris, November 2026) with the
H Agents API, Devin, Gladia, Linkup and Stripe.

## The loop

1. **Play.** An H Agents API desktop agent (model `holo4-35b-a3b`) plays real
   **Chocolate Doom + Freedoom** on a real Windows desktop. It sees only screenshots and presses
   keys. A QA frame-step mode lets the game wait for each agent action.
2. **Find.** When something looks wrong, the agent calls its custom tool `report_finding` (what,
   where, steps, expected vs actual). It never sees the known-bug list or the game's event log.
3. **Verify.** The verifier replays the **agent's own demo** (`agent.lmp`, vanilla Doom demo
   recorded during play) and checks a **hidden QA event log** written by our fork against log
   signatures. Only a verified finding reaches the developer, with a clip of the replay.
4. **Explain.** Voice narration over the clip; the developer answers by voice (Gladia real-time
   STT) or button: fix, skip, explain, stop.
5. **Fix.** On "fix", the product opens a **Devin API session** with the finding, steps and a log
   excerpt. Devin opens a PR on the game fork; the developer's approval merges it.
6. **Prove.** The game is rebuilt and the same steps are replayed: fixed or not fixed.
7. **Debrief.** Deaths heatmap, design notes with Linkup references, and product-placement spots
   with brand candidates. Dashboard shows the whole run live.

## Architecture

```mermaid
flowchart LR
  Dev([Developer<br/>voice + clicks]) -- Gladia STT --> Orch
  Orch -- TTS narration + clip --> Dev
  subgraph Laptop[Stage laptop, Windows]
    Game[Chocolate Doom QA build<br/>+ Freedoom]
    Log[(hidden QA event log<br/>+ agent.lmp demo)]
    Game --> Log
  end
  H[H Agents API<br/>desktop agent] -- keys --> Game
  Game -- pixels --> H
  H -- report_finding --> Orch[Orchestrator<br/>state machine]
  Orch --> Ver[Verifier<br/>demo replay + log oracle]
  Ver --> Log
  Orch -- fix session --> Devin[Devin API]
  Devin -- PR --> Fork[(game fork<br/>kaktamsdengami/chocolate-doom)]
  Fork -- rebuild + replay --> Ver
  Orch --> Ins[Debrief + placement<br/>H vision, Linkup]
  Orch -- REST + SSE --> UI[Dashboard<br/>React + Vite]
  UI --> Stripe[Stripe test-mode plans]
```

Code: `agents/` (tester, verifier, fix loop), `launcher/` (game, frame-step, replay, clips),
`devin/` (API client), `voice/`, `insights/`, `app/` (FastAPI + orchestrator), `web/`
(dashboard). Details: [docs/PLAN.md](docs/PLAN.md), [docs/GAME.md](docs/GAME.md),
[docs/CONTRACTS.md](docs/CONTRACTS.md).

## Results (honest)

All from stage-laptop runs; run records in [eval/runs/](eval/runs/), details in
[eval/RESULTS.md](eval/RESULTS.md).

| Run | Mode | Result |
|---|---|---|
| Stage run 2 | **Blind** (no test plan) | First blind rediscovery: 4 findings, verifier **verified KB4** (long-wall wobble) from the QA log; the other 3 stayed suspected. |
| Stage run 4, preset `stage-play` | **Spec-based** (visible developer test plan) | 37 actions, 1107 game tics; picked up a shotgun, the invulnerability sphere and bullets; `report_finding` "Sky not inverted during invulnerability power-up". Demo replay 31/31 player samples identical. Verifier: **verified, KB3**, replay `demo`, 10 s clip. |

- **Blind vs spec-based.** Stage presets (`stage-play`, `stage-kb3`) give the agent a visible
  developer test plan that states the expected behaviour under invulnerability. Those runs are
  spec-based testing, not blind rediscovery. Only the KB4 run was blind.
- **Real bugs.** KB1–KB4 are documented vanilla Doom defects that Chocolate Doom keeps on purpose
  (sources in `eval/known_bugs.yaml`, hidden from the tester). KB3 is id Software's original
  "sky not affected by invulnerability" behaviour in `r_plane.c`; there is no upstream fix to copy.
- **Not measured yet:** a Devin fix + replay-after-fix for an H-found bug. The fix loop was run
  end to end once on a scripted KB1 finding (not from the H tester).
- Demo content is marked **LIVE** (a real run happening now) or **RECORDED** (a saved run replayed
  from its `events.jsonl`) in the dashboard.

## How to run

**Mock mode (any machine, no keys):**

```bash
uv sync --extra dev && .venv/bin/pytest -q      # Python 3.12
cd web && npm ci && npm run dev                 # dashboard on mock data, labelled MOCK DATA
```

RECORDED mode replays a saved run: `python -m app.main --mode recorded --recording <events.jsonl>`
and `VITE_API_BASE=http://localhost:8000 npm run dev`.

**Live mode (stage laptop only):** needs the Windows laptop with the H desktop agent, the
microphone, the fork's QA build (`python -m launcher fetch`) and Freedoom, plus the keys in
[.env.example](.env.example) (`HAI_API_KEY`, `DEVIN_API_KEY`, `DEVIN_ORG_ID`, `GLADIA_API_KEY`,
`LINKUP_API_KEY`, Stripe test keys).

```bash
python -m agents.tester --preset stage-play     # one tester run -> recordings/<run>/
python -m agents.verifier recordings/<run>      # demo replay + log oracle
python -m app.main --mode live --start          # full loop, with the dashboard
```

## Credits and licences

- [Chocolate Doom](https://github.com/chocolate-doom/chocolate-doom) 3.1.1, GPL-2.0, by Simon
  Howard and contributors, based on the id Software source release. Our QA fork:
  [kaktamsdengami/chocolate-doom](https://github.com/kaktamsdengami/chocolate-doom), branch
  `player-two-qa`, licence unchanged.
- [Freedoom](https://freedoom.github.io/) 0.13.0, BSD-3-Clause, by the Freedoom project.
  Downloaded at build time, never committed.
- Bug write-ups: [Doom Wiki](https://doomwiki.org/). Reference fixes:
  [Crispy Doom](https://github.com/fabiangreffrath/crispy-doom) (GPL-2.0).
- All product code was written by Devin sessions; rules for coding agents in [AGENTS.md](AGENTS.md),
  live build state in [docs/HANDOFF.md](docs/HANDOFF.md).
