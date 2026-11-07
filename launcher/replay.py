"""Play an agent session back at game speed from its Doom demo.

    python -m launcher replay <run_dir> [--no-video]

The tester records `<run_dir>/agent.lmp` (vanilla demo: the agent's inputs per tic). Frame-step
only pauses the game clock, so `-playdemo` shows the session as if a human played it in real time.
Typed letters (cheat codes) and the QA start state are not in a demo: they come back through a
QA script built from the run's QA log, so the replay stays in sync.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from launcher import capture
from launcher.config import LauncherConfig
from launcher.game import Game
from launcher.log import EventLog

LABEL = "Agent session · replayed at game speed"


def replay_script(run_dir: Path, out: Path) -> Path:
    """QA start lines + every letter the agent typed in the level, at the same tic."""
    start = run_dir / "qa_start.txt"
    lines = start.read_text().splitlines() if start.exists() else []
    log = run_dir / "agent_events.jsonl"  # the demo's own round, if later rounds reused the dir
    events = EventLog(log if log.exists() else run_dir / "events.jsonl").poll()
    lines += [f"{e.tic} key {e.data['key']}" for e in events if e.type == "key" and "key" in e.data]
    lines.sort(key=lambda x: int(x.split()[0]))
    out.write_text("".join(x + "\n" for x in lines))
    return out


def command(cfg: LauncherConfig, game: Game, lmp: Path, script: Path) -> list[str]:
    extra = game.run_dir / "launcher.cfg"
    extra.write_text(cfg.extraconfig())
    cmd = [str(Path(cfg.exe).resolve()), "-iwad", str(Path(cfg.iwad).resolve()),
           "-playdemo", str(lmp.resolve()), "-nomouse", "-nograbmouse",
           "-fullscreen" if cfg.fullscreen else "-window", "-extraconfig", str(extra),
           "-qa-log", str(game.log_path), "-qa-script", str(script)]  # fmt: skip
    return cmd if cfg.sound else [*cmd, "-nosound"]


def replay(cfg: LauncherConfig, run_dir: Path, video: bool = True) -> dict:
    lmp = run_dir / "agent.lmp"
    if not lmp.exists():
        raise FileNotFoundError(f"no demo at {lmp} (was the run recorded with -record?)")
    game = Game(cfg, run_dir / "replay")
    if game.log_path.exists():
        game.log_path.unlink()
    script = replay_script(run_dir, game.run_dir / "replay_script.txt")
    tics = max(0, (lmp.stat().st_size - 14) // 4)  # vanilla header 13 bytes, 4 bytes per tic
    game.started_at = time.time()
    game.proc = subprocess.Popen(
        command(cfg, game, lmp, script), cwd=game.run_dir,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    win = game.window(10.0)
    rec = capture.record(win, game.run_dir / "raw.mp4", cfg.fps) if video and win else None
    try:
        game.proc.wait(tics / 35 + 30)  # -playdemo quits when the demo ends
    except subprocess.TimeoutExpired:
        pass
    finally:
        if rec:
            rec.stop()
        game.stop()
    out = {"demo": str(lmp), "tics": tics, "events": str(game.log_path),
           "game_started_at": game.started_at, "label": LABEL}  # fmt: skip
    meta = run_dir / "replay.json"
    if rec:
        out |= {"video": str(rec.path), "rec_started_at": rec.started_at}
        meta.write_text(
            json.dumps(out, indent=2)
        )  # the raw video is usable even if labelling fails
        final = run_dir / "agent_replay.mp4"
        try:
            capture.cut_clip(rec.path, 0, 24 * 3600, final, label=LABEL)
            out["video"] = str(final)
        except (subprocess.CalledProcessError, OSError) as e:
            out["label_error"] = str(e)
    meta.write_text(json.dumps(out, indent=2))
    return out
