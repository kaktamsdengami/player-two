"""`python -m launcher demo|build|fetch|query|clip`: local game controller for PLAYER TWO."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from app.contracts import LogSignature
from launcher import build as b
from launcher import capture
from launcher.config import LauncherConfig, Speed
from launcher.game import Game
from launcher.log import EventLog


def _run_dir(cfg: LauncherConfig, name: str) -> Path:
    return cfg.runs_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{name}"


def demo(cfg: LauncherConfig, seconds: float, speed: Speed) -> dict:
    exe = b.build(cfg)
    game = Game(cfg, _run_dir(cfg, "demo").resolve())
    # Something visible inside the 10 s: invulnerability after ~3 s of game time.
    script = game.run_dir / "demo_script.txt"
    script.write_text("105 give invulnerability\n")
    win = game.start(speed=speed, script=script)
    if win is None:
        game.stop()
        raise RuntimeError("game window did not appear")
    try:
        time.sleep(1.0)
        shot = capture.screenshot(win, game.run_dir / "start.png")
        rec = capture.record(win, game.run_dir / "recording.mp4", cfg.fps)
        try:
            time.sleep(seconds)
        finally:
            rec.stop()
    finally:
        game.stop()
    powerups = [e for e in game.log.since() if e.type == "powerup"]
    clip = None
    if powerups:
        start, end = capture.clip_window(powerups[0].t or 0, game.started_at, rec.started_at, 2, 3)
        clip = capture.cut_clip(
            rec.path, start, end, game.run_dir / "clip_powerup.mp4",
            label=capture.label_text(speed.factor),
        )  # fmt: skip
    return {
        "exe": str(exe),
        "window": f"{win.title} {win.width}x{win.height}+{win.x}+{win.y}",
        "screenshot": str(shot),
        "recording": str(rec.path),
        "clip": str(clip) if clip else None,
        "event_log": str(game.log_path),
        "events": len(game.log.events),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m launcher")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="build, start, record N s, cut a clip, stop, print paths")
    d.add_argument("--seconds", type=float, default=10.0)
    d.add_argument("--speed", default="normal", help="normal | step[:N] | slow[:K]")
    sub.add_parser("build", help="build the fork (Linux)")
    f = sub.add_parser("fetch", help="download the Windows CI build of a ref")
    f.add_argument("--ref", default=b.QA_BRANCH)
    f.add_argument("--dest", type=Path, default=Path("game"))
    q = sub.add_parser("query", help="has a LogSignature (yaml/json file) happened since t?")
    q.add_argument("log", type=Path)
    q.add_argument("signature", type=Path)
    q.add_argument("--since", type=float, default=None)
    c = sub.add_parser("clip", help="cut [start, end] seconds out of a recording")
    c.add_argument("src", type=Path)
    c.add_argument("start", type=float)
    c.add_argument("end", type=float)
    c.add_argument("out", type=Path)
    c.add_argument("--speed", type=float, default=1.0)
    c.add_argument("--label", action="store_true", help='add "RECORDED · N× speed"')
    r = sub.add_parser("replay", help="play <run_dir>/agent.lmp at game speed and record it")
    r.add_argument("run_dir", type=Path)
    r.add_argument("--no-video", action="store_true")
    a = p.parse_args(argv)

    cfg = LauncherConfig.from_env()
    if a.cmd == "demo":
        out = demo(cfg, a.seconds, Speed.parse(a.speed))
    elif a.cmd == "replay":
        from launcher.replay import replay

        out = replay(cfg, a.run_dir.resolve(), video=not a.no_video)
    elif a.cmd == "build":
        out = {"exe": str(b.build(cfg))}
    elif a.cmd == "fetch":
        out = {"exe": str(b.fetch_ci_build(a.dest, a.ref))}
    elif a.cmd == "query":
        sig = LogSignature.model_validate(yaml.safe_load(a.signature.read_text()))
        hits = EventLog(a.log).happened(sig, a.since)
        out = {"happened": hits is not None, "events": [e.model_dump() for e in hits or []]}
    else:
        label = capture.label_text(a.speed) if a.label else None
        out = {"clip": str(capture.cut_clip(a.src, a.start, a.end, a.out, speed=a.speed,
                                            label=label))}  # fmt: skip
    print(json.dumps(out, indent=2))
    return 1 if "video_error" in out else 0


if __name__ == "__main__":
    sys.exit(main())
