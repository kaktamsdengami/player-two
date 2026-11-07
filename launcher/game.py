"""Start, stop and reset the QA build at a fixed window size, map and speed."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from launcher.config import PRESETS, LauncherConfig, Speed
from launcher.log import EventLog
from launcher.window import Window, find_window, foreground


@dataclass
class Game:
    cfg: LauncherConfig
    run_dir: Path
    proc: subprocess.Popen | None = None
    started_at: float = 0.0  # wall clock at launch; GameEvent.t counts from about here
    extra_args: list[str] = field(default_factory=list)  # e.g. ["-qa-trace", "1"]
    log: EventLog = field(init=False)

    def __post_init__(self) -> None:
        self.run_dir = Path(self.run_dir).resolve()  # the game runs with cwd=run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log = EventLog(self.log_path)

    @property
    def log_path(self) -> Path:
        return self.run_dir / "events.jsonl"

    def command(
        self,
        episode: int,
        map_: int,
        speed: Speed,
        script: Path | None = None,
        record: Path | None = None,
    ) -> list[str]:
        c = self.cfg
        extra = self.run_dir / "launcher.cfg"
        extra.write_text(c.extraconfig())
        exe, iwad = Path(c.exe).resolve(), Path(c.iwad).resolve()
        cmd = [str(exe), "-iwad", str(iwad), "-warp", str(episode), str(map_),
               "-skill", str(c.skill), "-nomouse", "-nograbmouse",
               "-fullscreen" if c.fullscreen else "-window",
               "-extraconfig", str(extra), "-qa-log", str(self.log_path),
               *speed.args()]  # fmt: skip
        cmd += self.extra_args
        if not c.sound:
            cmd.append("-nosound")
        if record:  # vanilla demo (.lmp appended): the agent's inputs per tic, for replays
            cmd += ["-record", str(record), "-maxdemo", "4096"]
        if script is None:
            script = self.start_script()
        if script:
            cmd += ["-qa-script", str(script)]
        return cmd

    def start_script(self) -> Path | None:
        """QA start state for free play (replay scripts set their own)."""
        line = {"god": "1 god", "tough": "1 health 999"}.get(self.cfg.start)
        lines = [line] if line else []
        if self.cfg.preset:
            lines += PRESETS[self.cfg.preset].lines
        if not lines:
            return None
        path = self.run_dir / "qa_start.txt"
        path.write_text("".join(x + "\n" for x in lines))
        return path

    def start(
        self,
        episode: int | None = None,
        map_: int | None = None,
        speed: Speed | None = None,
        script: Path | None = None,
        wait_window: float = 10.0,
        record: Path | None = None,
    ) -> Window | None:
        """Launch, wait for the window, put it in front. Returns the window (None if not seen)."""
        self.stop()
        if self.log_path.exists():
            self.log_path.unlink()
        self.log = EventLog(self.log_path)
        c = self.cfg
        cmd = self.command(episode or c.episode, map_ or c.map, speed or c.speed, script, record)
        self.started_at = time.time()
        self.proc = subprocess.Popen(
            cmd, cwd=self.run_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return self.window(wait_window)

    def window(self, wait: float = 0.0) -> Window | None:
        end = time.monotonic() + wait
        while True:
            win = find_window(self.cfg.window_title)
            if win or time.monotonic() >= end or not self.running:
                break
            time.sleep(0.2)
        if win:
            foreground(win)
        return win

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.running:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)
        self.proc = None

    def reset(self, episode: int, map_: int, speed: Speed | None = None) -> Window | None:
        """Back to the start of a map (the QA build has no in-game reset: relaunch, ~1 s)."""
        return self.start(episode, map_, speed)
