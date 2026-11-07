"""Launcher settings. Every stage choice (window, speed, map, sound) is one field here."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
FREEDOOM_SHA256 = "7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d"


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ[name]).expanduser() if os.environ.get(name) else default


def _default_exe(fork: Path) -> Path:
    return fork / ("chocolate-doom.exe" if IS_WINDOWS else "src/chocolate-doom")


@dataclass
class Speed:
    """`tics` = frame-step (game frozen until a key press, then N tics); `slowmo` = 1/K speed."""

    tics: int | None = 35
    slowmo: int | None = None

    @classmethod
    def parse(cls, text: str) -> Speed:
        """`normal`, `step` (35 tics), `step:N`, `slow:K`."""
        kind, _, n = text.partition(":")
        if kind == "normal":
            return cls(None, None)
        if kind == "step":
            return cls(int(n or 35), None)
        if kind == "slow":
            return cls(None, int(n or 4))
        raise ValueError(f"speed must be normal, step[:N] or slow[:K], got {text!r}")

    def args(self) -> list[str]:
        out: list[str] = []
        if self.tics:
            out += ["-qa-tics", str(self.tics)]
        if self.slowmo and self.slowmo > 1:
            out += ["-qa-slowmo", str(self.slowmo)]
        return out

    @property
    def factor(self) -> float:
        """Real seconds per game second, for the "RECORDED · N× speed" label (frame-step: 1)."""
        return float(self.slowmo or 1)


@dataclass
class LauncherConfig:
    fork_dir: Path
    exe: Path
    iwad: Path
    runs_dir: Path
    episode: int = 3
    map: int = 1
    skill: int = 3
    speed: Speed = field(default_factory=Speed)
    fullscreen: bool = False
    width: int = 1066
    height: int = 800
    position: tuple[int, int] = (0, 0)
    sound: bool = False
    fps: int = 30
    window_title: str = "Chocolate Doom"

    @classmethod
    def from_env(cls) -> LauncherConfig:
        fork = _env_path("P2_GAME_DIR", Path.home() / "cd-fork")
        return cls(
            fork_dir=fork,
            exe=_env_path("P2_GAME_EXE", _default_exe(fork)),
            iwad=_env_path(
                "P2_IWAD", Path.home() / "freedoom" / "freedoom-0.13.0" / "freedoom1.wad"
            ),
            runs_dir=_env_path("P2_RUNS_DIR", Path("recordings")),
            fullscreen=os.environ.get("P2_FULLSCREEN", "0") == "1",
        )

    def extraconfig(self) -> str:
        """chocolate-doom.cfg overrides: fixed window size and position."""
        x, y = self.position
        return (
            f"fullscreen {int(self.fullscreen)}\n"
            f"window_width {self.width}\n"
            f"window_height {self.height}\n"
            f'window_position "{x},{y}"\n'
        )
