"""Launcher settings. Every stage choice (window, speed, map, sound) is one field here."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
DEFAULT_STEP = 8  # frame-step tics per key press (~0.23 s): fine turns and stops
START_MODES = ("god", "tough", "off")  # QA start: god mode, 999 health (damage still works), none
FREEDOOM_SHA256 = "7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d"


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ[name]).expanduser() if os.environ.get(name) else default


def _start_mode(value: str) -> str:
    v = value.strip().lower()
    if v not in START_MODES:
        raise ValueError(f"P2_GOD must be one of {', '.join(START_MODES)}, got {value!r}")
    return v


def _default_exe(fork: Path) -> Path:
    return fork / ("chocolate-doom.exe" if IS_WINDOWS else "src/chocolate-doom")


@dataclass
class Speed:
    """`tics` = frame-step (game frozen until a key press, then N tics); `slowmo` = 1/K speed."""

    tics: int | None = DEFAULT_STEP
    slowmo: int | None = None

    @classmethod
    def parse(cls, text: str) -> Speed:
        """`normal`, `step` (DEFAULT_STEP tics), `step:N`, `slow:K`."""
        kind, _, n = text.partition(":")
        if kind == "normal":
            return cls(None, None)
        if kind == "step":
            return cls(int(n or DEFAULT_STEP), None)
        if kind == "slow":
            return cls(None, int(n or 4))
        raise ValueError(f"speed must be normal, step[:N] or slow[:K], got {text!r}")

    def spec(self) -> str:
        """Explicit form for run records: parses back to the same speed if defaults change."""
        if self.tics:
            return f"step:{self.tics}"
        return f"slow:{self.slowmo}" if self.slowmo and self.slowmo > 1 else "normal"

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


@dataclass(frozen=True)
class Preset:
    """A reproducible QA start: map, extra QA-script lines at tic 1, a suggested test plan."""

    map: tuple[int, int]
    lines: tuple[str, ...]
    plan: str = ""


PRESETS = {
    # E3M1 has no invulnerability sphere: put one a few steps ahead of the start, under the red sky
    "stage-kb3": Preset(
        map=(3, 1),
        lines=("1 spawn 2022 -100 -224",),
        plan="Test power-ups, especially invulnerability, and check that the whole screen, "
        "including the sky, renders correctly while a power-up is active.",
    ),
}


def _preset(name: str) -> str:
    if name and name not in PRESETS:
        raise ValueError(f"unknown preset {name!r}: {', '.join(PRESETS)}")
    return name


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
    start: str = "tough"  # START_MODES; applied on every launch without a QA script
    preset: str = ""  # PRESETS key: extra start lines (e.g. a spawned power-up)

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
            start=_start_mode(os.environ.get("P2_GOD", "tough")),
            preset=_preset(os.environ.get("P2_PRESET", "")),
        )

    def extraconfig(self) -> str:
        """chocolate-doom.cfg overrides: fixed window size and position, no ENDOOM wait on quit."""
        x, y = self.position
        return (
            f"fullscreen {int(self.fullscreen)}\n"
            f"window_width {self.width}\n"
            f"window_height {self.height}\n"
            f'window_position "{x},{y}"\n'
            "show_endoom 0\n"
        )
