# RESULTS: stage-laptop runs

Only facts from real runs on the stage laptop (H Agents API, US region). Raw run directories
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

## Not measured yet

- Devin fix + rebuild + replay-after-fix for a bug found by the H tester.
- Recall or false-positive rates over many runs (only the runs above exist).

The fix loop itself ran once end to end on a scripted KB1 finding (not from the H tester): Devin
fork PR merged into a `qa-run/` branch, rebuilt, replay log showed the fixed message
(docs/HANDOFF.md, T11).
