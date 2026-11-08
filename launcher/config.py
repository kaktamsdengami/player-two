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
        plan="Test power-ups, especially invulnerability. Expected behaviour (from the developer): "
        "While invulnerable, the whole screen should be drawn inverted (white/grey), "
        "including the sky. Compare the sky with the walls: if the sky keeps its normal "
        "colour, report it.",
    ),
    # longer stage run: a shotgun, armour, a stimpack and a zombie on the way to the imps, then
    # the sphere at the far end of the first canyon (scripted walk: shotgun at tic 24, sphere ~200).
    # No zombies at the start spot: their damage flash read as the power-up on stage.
    "stage-play": Preset(
        map=(3, 1),
        lines=(
            "1 spawn 2001 -150 -224",
            "1 spawn 2018 -330 -120",
            "1 spawn 2011 -437 -25",
            "1 spawn 3004 -520 -40",
            "1 spawn 2022 -600 60",
        ),
        plan="Your only goal until you have it: the power-up, a glowing green sphere further "
        "along the canyon. 1) Turn to face the sphere and walk straight to it, over it. "
        "2) Shoot a monster only if it is already in the centre of the screen; never turn away "
        "from the sphere to chase or aim at monsters. 3) Judge the sky only after the pickup "
        "message "
        '"Vanguard of the gods!" appears at the top left and the screen turns white; a red '
        "flash is only damage, not the bug. Expected behaviour (from the developer): while "
        "invulnerable the whole screen should be drawn inverted (white/grey), including the "
        "sky. Compare the sky with the walls: if the sky keeps its normal colour, report it.",
    ),
}


def _window(value: str) -> tuple[int, int]:
    """P2_WINDOW=WxH (windowed mode, top-left corner); default 1066x800."""
    try:
        w, h = (int(x) for x in value.lower().split("x"))
    except ValueError:
        raise ValueError(f"P2_WINDOW={value!r}: expected WIDTHxHEIGHT, e.g. 960x720") from None
    return w, h


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
        width, height = _window(os.environ.get("P2_WINDOW", "1066x800"))
        return cls(
            fork_dir=fork,
            exe=_env_path("P2_GAME_EXE", _default_exe(fork)),
            iwad=_env_path(
                "P2_IWAD", Path.home() / "freedoom" / "freedoom-0.13.0" / "freedoom1.wad"
            ),
            runs_dir=_env_path("P2_RUNS_DIR", Path("recordings")),
            fullscreen=os.environ.get("P2_FULLSCREEN", "0") == "1",
            width=width,
            height=height,
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
