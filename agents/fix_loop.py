"""T11: Devin fix -> merge -> rebuild -> replay -> fixed / not fixed (1 feedback round) -> compare.

The QA branch keeps its known bugs for the next demo: fixes merge into a per-run branch
(`qa-run/...`, created from `player-two-qa`), and the replay rebuilds that branch.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from agents.oracles import proven
from app.contracts import Clip, Finding, FixAttempt, FixResult, KnownBug
from devin.client import DevinClient
from insights.fix_compare import compare, pr_diff, upstream_diff
from launcher import capture
from launcher.build import pull_and_rebuild
from launcher.config import LauncherConfig, Speed
from launcher.game import Game

Update = Callable[[FixAttempt], None]


@dataclass
class Replay:
    """Outcome of one replay on a rebuilt game."""

    still_there: bool
    note: str
    clip: Path | None = None
    duration_s: float = 0.0


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ScriptReplay:
    """Replay a known bug with its QA script (`qa/*.txt` in the fork); deterministic, no H."""

    game: Game
    bug: KnownBug
    script: Path
    episode: int
    map_: int
    timeout_s: float = 60.0
    record: bool = True

    def __call__(self, finding: Finding, tag: str) -> Replay:
        out = self.game.run_dir / tag
        out.mkdir(parents=True, exist_ok=True)
        win = self.game.start(self.episode, self.map_, Speed.parse("normal"), self.script)
        if win is None:
            raise RuntimeError("game window did not appear for the replay")
        path = out / f"{finding.id}_{tag}.mp4"
        rec = capture.record(win, path, self.game.cfg.fps) if self.record else None
        t0 = time.monotonic()
        try:
            end = time.monotonic() + self.timeout_s
            while self.game.running and time.monotonic() < end:
                time.sleep(0.2)
        finally:
            clip = rec.stop() if rec else None
            self.game.stop()
        events = self.game.log.since()
        hits = proven(events, [self.bug])
        if hits:
            note = f"{self.bug.id} signature still in the QA log: {hits[0].first.model_dump_json()}"
        else:
            note = f"{self.bug.id} signature absent from {len(events)} QA log events"
        return Replay(bool(hits), note, clip, time.monotonic() - t0)


@dataclass
class FixLoop:
    devin: DevinClient
    replay: Callable[[Finding, str], Replay]
    rebuild: Callable[[str], Path]
    approve: Callable[[FixAttempt], bool] = lambda a: True
    on_update: Update | None = None
    poll_s: float = 15
    timeout_s: float = 3600
    log: list[str] = field(default_factory=list)

    def _emit(self, a: FixAttempt, msg: str | None = None) -> FixAttempt:
        if msg:
            self.log.append(f"{_now():%H:%M:%S} {msg}")
        if self.on_update:
            self.on_update(a)
        return a

    def _follow(self, a: FixAttempt, until: set[FixResult]) -> FixAttempt:
        return self.devin.follow(
            a, self.on_update, until=frozenset(until), poll_s=self.poll_s, timeout_s=self.timeout_s
        )

    def run(
        self, finding: Finding, attempt: FixAttempt | None = None
    ) -> tuple[FixAttempt, Replay | None]:
        """Drive one finding to fixed / not_fixed / failed, with at most one feedback round."""
        a = attempt or self.devin.create_fix_session(finding)
        self._emit(a, f"Devin session {a.devin_session_url or a.devin_session_id}")
        replay = None
        while True:
            a = self._follow(a, {FixResult.pr_open, FixResult.merged, FixResult.failed})
            if a.result == FixResult.failed:
                return self._emit(a, "Devin session failed"), replay
            if a.result == FixResult.pr_open:
                self._emit(a, f"PR open {a.pr_url}")
                if not self.approve(a):
                    return self._emit(a, "merge not approved: stopping with the PR open"), replay
                self.devin.approve_merge(a)
                a = self._follow(a, {FixResult.merged, FixResult.failed})
                if a.result == FixResult.failed:
                    return self._emit(a, "merge failed"), replay
            self._emit(a, f"merged {a.pr_url}; rebuilding {self.devin.base_branch}")
            self.rebuild(self.devin.base_branch)
            replay = self.replay(finding, f"round{a.round}")
            fixed = not replay.still_there
            a = a.model_copy(
                update={
                    "result": FixResult.fixed if fixed else FixResult.not_fixed,
                    "finished_at": _now(),
                }
            )
            self._emit(a, ("FIXED: " if fixed else "NOT FIXED: ") + replay.note)
            if fixed or a.round >= 2:
                return a, replay
            merged = a.model_copy(update={"result": FixResult.merged})  # old PR becomes stale
            a = self._emit(self.devin.send_feedback(merged, replay.note), "feedback round sent")


def add_comparison(a: FixAttempt, bug: KnownBug | None, assess: bool = True) -> FixAttempt:
    """Attach the upstream comparison (needs a PR and a bug with an upstream fix commit)."""
    if not (a.pr_url and bug and bug.upstream_fix_ref):
        return a
    if a.result not in (FixResult.fixed, FixResult.not_fixed):
        return a
    c = compare(
        pr_diff(a.pr_url),
        upstream_diff(bug.upstream_fix_ref),
        bug.upstream_fix_ref,
        fixed=a.result == FixResult.fixed,
        assess=assess,
    )
    return a.model_copy(update={"upstream_fix_ref": bug.upstream_fix_ref, "comparison": c})


def attach_clip(finding: Finding, replay: Replay | None) -> None:
    if replay and replay.clip:
        finding.evidence.clip = Clip(path=str(replay.clip), start_s=0.0, end_s=replay.duration_s)


def main(argv: list[str] | None = None) -> int:
    """python -m agents.fix_loop FINDING_JSON --bug KB1 --script qa/kb1_kb2_medikit.txt ..."""
    import argparse
    import json

    from agents.oracles import load_known_bugs
    from insights.fix_compare import render_html

    p = argparse.ArgumentParser(prog="python -m agents.fix_loop")
    p.add_argument("finding", type=Path, help="Finding JSON (verified, known_bug_ref set)")
    p.add_argument("--bug", help="known bug id (default: finding.known_bug_ref)")
    p.add_argument("--script", type=Path, required=True, help="QA script, relative to the fork")
    p.add_argument("--map", nargs=2, type=int, default=[1, 1], metavar=("EPISODE", "MAP"))
    p.add_argument("--base", required=True, help="fork branch the fix merges into (qa-run/...)")
    p.add_argument("--attempt", type=Path, help="resume: FixAttempt JSON of a running session")
    p.add_argument("--out", type=Path, default=Path("recordings/fix_loop"))
    p.add_argument("--no-merge", action="store_true", help="stop at pr_open (no approval)")
    a = p.parse_args(argv)

    finding = Finding.model_validate_json(a.finding.read_text())
    bug_id = a.bug or finding.known_bug_ref
    bug = next((b for b in load_known_bugs() if b.id == bug_id), None)
    if bug is None:
        raise SystemExit(f"unknown bug {bug_id}")
    cfg = LauncherConfig.from_env()
    devin = DevinClient.from_env(base_branch=a.base)
    a.out.mkdir(parents=True, exist_ok=True)
    state = a.out / "fix_attempt.json"

    def save(x: FixAttempt) -> None:
        state.write_text(x.model_dump_json(indent=2))
        print(f"[{x.result}] {x.pr_url or x.devin_session_url or ''}", flush=True)

    loop = FixLoop(
        devin=devin,
        replay=ScriptReplay(Game(cfg, a.out), bug, cfg.fork_dir / a.script, *a.map),
        rebuild=lambda ref: pull_and_rebuild(cfg, ref),
        approve=lambda x: not a.no_merge,
        on_update=save,
    )
    attempt = FixAttempt.model_validate_json(a.attempt.read_text()) if a.attempt else None
    result, replay = loop.run(finding, attempt)
    result = add_comparison(result, bug)
    attach_clip(finding, replay)
    save(result)
    if result.comparison:
        page = render_html(result.comparison, f"{bug.id}: {bug.title}")
        (a.out / "fix_compare.html").write_text(page)
    (a.out / "fix_loop.log").write_text("\n".join(loop.log) + "\n")
    print("\n".join(loop.log))
    summary = {
        "result": result.result,
        "clip": str(replay.clip) if replay else None,
        "comparison": result.comparison.summary if result.comparison else None,
    }
    print(json.dumps(summary, indent=2))
    return 0 if result.result == FixResult.fixed else 1


if __name__ == "__main__":
    raise SystemExit(main())
