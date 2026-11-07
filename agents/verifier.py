"""Verifier (T08): reset, replay a finding, check the hidden log oracle, cut the clip, match.

For each `Finding`:
1. Reset the game to the start of the map.
2. Replay: the tester's own demo (`agent.lmp`, exact inputs per tic) when the run recorded one;
   else its key presses from the action log, or a follow-up to the H session.
3. Check the replay's event log with the oracles (`agents.oracles`).
4. Cut a clip of +-5 s around the first proving event.
5. Status verified (a known signature fired and the finding is about it, or the H replay saw it
   again) or suspected; `known_bug_ref` is the matched `KnownBug.id`, None for a new bug.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.oracles import Proof, load_known_bugs, match, proven
from app.contracts import AgentAction, Clip, Finding, FindingStatus, GameEvent, KnownBug
from launcher import capture
from launcher.config import Speed
from launcher.game import Game
from launcher.log import EventLog

CLIP_BEFORE = CLIP_AFTER = 5.0
KEY_ALIASES = {"ctrl": "ctrlleft", "control": "ctrlleft", "alt": "altleft", "shift": "shiftleft",
               "arrowup": "up", "arrowdown": "down", "arrowleft": "left", "arrowright": "right",
               "return": "enter", "spacebar": "space"}  # fmt: skip


def press_keys(keys: Sequence[str], hold_s: float = 0.15) -> None:
    """Default key sender (pyautogui works on X11 and Windows)."""
    import pyautogui

    names = [KEY_ALIASES.get(k.lower(), k.lower()) for k in keys]
    if len(names) == 1 and len(names[0]) > 1 and names[0] not in pyautogui.KEYBOARD_KEYS:
        pyautogui.write(names[0], interval=0.05)  # typed text, e.g. a debug code
        return
    for n in names:
        pyautogui.keyDown(n)
    time.sleep(hold_s)
    for n in reversed(names):
        pyautogui.keyUp(n)


@dataclass
class Verdict:
    finding: Finding
    proofs: list[Proof] = field(default_factory=list)
    matched: KnownBug | None = None
    replay: str = "none"  # demo | actions | h_session | none
    clip: Path | None = None

    def summary(self) -> dict[str, Any]:
        f = self.finding
        return {
            "finding": f.id,
            "title": f.title,
            "status": f.status,
            "known_bug_ref": f.known_bug_ref,
            "proven": [p.bug.id for p in self.proofs],
            "replay": self.replay,
            "clip": str(self.clip) if self.clip else None,
        }


@dataclass
class Verifier:
    game: Game
    episode: int
    map_: int
    speed: Speed
    bugs: list[KnownBug] = field(default_factory=load_known_bugs)
    press: Callable[..., None] = press_keys
    step_wait_s: float = 1.2  # one frame-step (up to 35 tics) plus margin
    record: bool = True

    def replay_actions(self, actions: list[AgentAction], until_s: float | None) -> None:
        for a in actions:
            if until_s is not None and a.t_session_s > until_s:
                break
            if a.keys and a.kind in ("key_press", "key_hold", "type_text"):
                if a.kind == "key_hold" and a.duration_ms:
                    self.press(a.keys, hold_s=a.duration_ms / 1000)
                else:
                    self.press(a.keys)
                time.sleep(self.step_wait_s)

    def verify(
        self,
        finding: Finding,
        actions: list[AgentAction] | None = None,
        h_replay: Callable[[Finding], bool] | None = None,
        out_dir: Path | None = None,
        demo: Path | None = None,
    ) -> Verdict:
        out_dir = out_dir or self.game.run_dir / "verify"
        out_dir.mkdir(parents=True, exist_ok=True)
        if demo and (demo / "agent.lmp").exists():
            return self.verify_demo(finding, demo, out_dir)
        win = self.game.reset(self.episode, self.map_, self.speed)
        if win is None:
            raise RuntimeError("game window did not appear for the replay")
        rec, rec_started = None, time.time()
        if self.record:
            rec = capture.record(win, out_dir / f"{finding.id}_replay.mp4", self.game.cfg.fps)
        seen_by_h = False
        try:
            actions = actions or []
            mine = [a for a in actions if a.session_id == finding.session_id]
            if not mine and len({a.session_id for a in actions}) == 1:
                mine = actions  # one tester run whose finding ids predate its H session id
            if mine and any(a.keys for a in mine):
                v_replay = "actions"
                self.replay_actions(mine, finding.t_session_s)
            elif h_replay:
                v_replay = "h_session"
                seen_by_h = bool(h_replay(finding))
            else:
                v_replay = "none"
            time.sleep(self.step_wait_s)
        finally:
            if rec:
                rec.stop()
            self.game.stop()
        events = self.game.log.since()
        verdict = judge(finding, events, self.bugs, seen_by_h)
        verdict.replay = v_replay
        if rec and verdict.matched:
            ev = next(x for x in verdict.proofs if x.bug is verdict.matched).first
            start, end = capture.clip_window(
                ev.t or 0.0, self.game.started_at, rec_started, CLIP_BEFORE, CLIP_AFTER
            )
            verdict.clip = capture.cut_clip(rec.path, start, end, out_dir / f"{finding.id}.mp4")
            finding.evidence.clip = Clip(path=str(verdict.clip), start_s=0.0, end_s=end - start)
        return verdict

    def verify_demo(self, finding: Finding, run_dir: Path, out_dir: Path) -> Verdict:
        """Replay the tester's own demo (exact inputs per tic) instead of re-pressing its keys:
        H holds keys for wall-clock time, so a key re-press replay drifts in frame-step."""
        from launcher.replay import replay

        out = replay(self.game.cfg, run_dir, video=self.record)
        verdict = judge(finding, EventLog(Path(out["events"])).poll(), self.bugs)
        verdict.replay = "demo"
        if verdict.matched and out.get("rec_started_at"):
            ev = next(x for x in verdict.proofs if x.bug is verdict.matched).first
            start, end = capture.clip_window(
                ev.t or 0.0, out["game_started_at"], out["rec_started_at"], CLIP_BEFORE, CLIP_AFTER
            )
            verdict.clip = capture.cut_clip(
                Path(out["video"]), start, end, out_dir / f"{finding.id}.mp4"
            )
            finding.evidence.clip = Clip(path=str(verdict.clip), start_s=0.0, end_s=end - start)
        return verdict


def judge(
    finding: Finding, events: list[GameEvent], bugs: list[KnownBug], seen_by_h: bool = False
) -> Verdict:
    """Oracle verdict on a finished replay log. Mutates the finding's status/ref/evidence."""
    proofs = proven(events, bugs)
    hit = match(finding, proofs)
    if hit:
        finding.status = FindingStatus.verified
        finding.known_bug_ref = hit.bug.id
        finding.evidence.log_excerpt = hit.hits
    else:
        finding.status = FindingStatus.verified if seen_by_h else FindingStatus.suspected
        finding.known_bug_ref = None
    return Verdict(finding, proofs, hit.bug if hit else None)


def main(argv: list[str] | None = None) -> int:
    """python -m agents.verifier RUN_DIR: verify every finding of a tester run (agents.tester)."""
    import argparse
    import json

    from launcher.config import LauncherConfig

    p = argparse.ArgumentParser(prog="python -m agents.verifier")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--map", nargs=2, type=int, metavar=("EPISODE", "MAP"),
                   help="default: the tester run's map (else E3M1)")  # fmt: skip
    p.add_argument("--speed", help="default: the tester run's speed")
    a = p.parse_args(argv)
    run = json.loads((a.run_dir / "tester_run.json").read_text())
    actions_file = a.run_dir / "actions.jsonl"
    actions = [
        AgentAction.model_validate_json(x)
        for x in (actions_file.read_text().splitlines() if actions_file.exists() else [])
        if x.strip()
    ]
    cfg = LauncherConfig.from_env()
    cfg.start = run.get("start", "off")  # replay in the tester's start state (older runs: none)
    cfg.preset = run.get("preset") or ""  # same spawned items as the tester run
    a.map = a.map or run.get("map") or [3, 1]
    v = Verifier(
        Game(cfg, a.run_dir / "verify"),
        a.map[0],
        a.map[1],
        Speed.parse(a.speed or run.get("speed", "step:35")),  # runs before 12-tic steps
    )
    out = []
    for raw in run["findings"]:
        f = Finding.model_validate(raw)
        verdict = v.verify(f, actions, out_dir=a.run_dir / "verify" / f.id, demo=a.run_dir)
        out.append(verdict.summary() | {"finding_full": f.model_dump(mode="json")})
    (a.run_dir / "verdicts.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps([o | {"finding_full": None} for o in out], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
