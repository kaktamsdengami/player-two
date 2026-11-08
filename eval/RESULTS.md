# RESULTS: stage-laptop runs

Only facts from real runs on the stage laptop (H Agents API, US region). Run records:
[`eval/runs/`](runs/) (one JSON summary per run). Raw run directories
(`tester_run.json`, `verdicts.json`, `agent.lmp`, clips) stay on the stage laptop under
`recordings/`; the outputs were posted on
[PR #42](https://github.com/kaktamsdengami/player-two/pull/42) and logged in
[docs/HANDOFF.md](../docs/HANDOFF.md). Nothing here is a target or an estimate.

## Stage run 2: blind rediscovery (RECORDED)

- Mode: **blind**. Free play on E3M1, no developer test plan.
- H session `c960e650…`: 39 actions, max game tic 595, 4 findings.
- Verifier: F3 **verified = KB4** (long-wall wobble), proven by the hidden QA log, clip cut.
  F1, F2, F4 stayed suspected (normal Doom behaviour: screen border, close-range explosions,
  death view).

## Stage run 4: preset `stage-play` (RECORDED)

- Mode: **spec-based**. The preset gives the agent a visible developer test plan that states the
  expected behaviour under invulnerability. This is not a blind rediscovery.
- H session `0d17032d-5bb1-4dc3-8832-d9565409af77`: 37 actions, 1107 game tics.
- Pickups: shotgun, invulnerability sphere, bullets.
- Agent's `report_finding`: "Sky not inverted during invulnerability power-up".
- Demo replay (`agent.lmp`): 31/31 player samples identical.
- Verifier: status **verified**, `known_bug_ref` **KB3**, replay `demo`, 10 s clip.

## KB3 Devin fix for the stage run 4 finding (RECORDED)

Record: [`runs/2026-11-08-kb3-devin-fix.json`](runs/2026-11-08-kb3-devin-fix.json).

- Input: the KB3 finding the H tester reported in stage run 4 ("Sky not inverted during
  invulnerability power-up"), sent with the product's prompt template `devin/prompts/fix_bug.md`
  to a [Devin session](https://app.devin.ai/sessions/0153bbeefe6d4dbfa2c118e8ce2254d2).
  That session was started from the orchestrator's Devin session on the Devin VM (no
  `DEVIN_API_KEY` there), **not** by `app.main` on the stage laptop. The finding JSON was rebuilt
  from the run's finding text + fixture log lines.
- Output: fork [PR #2](https://github.com/kaktamsdengami/chocolate-doom/pull/2) (base
  `qa-run/kb3-fix-demo`, CI green, **not merged**): `src/doom/r_plane.c` +15/-5, the sky uses
  `fixedcolormap` when set.
- Check (Devin VM, scripted QA replay `qa/kb3_sky_invul_e3m1.txt` on E3M1): before, 1
  `sky_ignores_colormap` event and a red sky; after, 0 events and a grey sky like the rest of
  the scene.

## Not measured yet

- The same loop end to end via `app.main` live on the stage laptop, with merge + rebuild.
- Recall or false-positive rates over many runs (only the runs above exist).

The fix loop itself ran once end to end on a scripted KB1 finding (not from the H tester): Devin
fork PR merged into a `qa-run/` branch, rebuilt, replay log showed the fixed message
(docs/HANDOFF.md, T11).
