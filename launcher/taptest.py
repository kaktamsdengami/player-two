"""Frame-step pre-flight: a 0 ms key tap must advance the game by one full step.

    python -m launcher.taptest [--taps 4] [--tics 35]

Starts the QA build in frame-step mode, sends key-down + key-up with no delay (like a
computer-use agent does), and checks that the game clock moves one step per tap.
Exit code 0 = PASS. Run it on the stage laptop before an H session.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from launcher.config import LauncherConfig, Speed
from launcher.game import Game
from launcher.window import IS_WINDOWS

KEYS = ["up", "right", "up", "left"]
_WIN = {"up": (0x26, 0x48), "right": (0x27, 0x4D), "left": (0x25, 0x4B)}  # VK, scancode
_X11 = {"up": "Up", "right": "Right", "left": "Left"}


def tap(key: str) -> None:
    """Key-down and key-up back to back (0 ms hold)."""
    if IS_WINDOWS:
        import ctypes

        vk, scan = _WIN[key]
        ext = 0x1  # KEYEVENTF_EXTENDEDKEY: arrows are extended keys
        ctypes.windll.user32.keybd_event(vk, scan, ext, 0)
        ctypes.windll.user32.keybd_event(vk, scan, ext | 0x2, 0)  # KEYEVENTF_KEYUP
    else:
        k = _X11[key]
        subprocess.run(
            ["xdotool", "keydown", "--delay", "0", k, "keyup", "--delay", "0", k], check=True
        )


def last_tic(log: Path) -> int:
    tic = -1
    if log.exists():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                tic = max(tic, int(json.loads(line).get("tic", -1)))
            except (ValueError, AttributeError):
                continue
    return tic


def run(cfg: LauncherConfig, taps: int = 4, tics: int = 35, settle: float = 2.0) -> list[int]:
    """Returns the game tic after each tap (index 0 = before the first tap)."""
    with tempfile.TemporaryDirectory(prefix="p2-taptest-") as d:
        game = Game(cfg, Path(d))
        try:
            if game.start(speed=Speed.parse(f"step:{tics}")) is None:
                raise RuntimeError("game window not found")
            end = time.monotonic() + 15  # first launch can be slow (config, shaders)
            while last_tic(game.log_path) < 1 and time.monotonic() < end:
                time.sleep(0.2)
            game.window()  # focus again once the first frame is drawn
            time.sleep(settle)
            seen = [last_tic(game.log_path)]
            for i in range(taps):
                game.window()  # keep it in front
                tap(KEYS[i % len(KEYS)])
                time.sleep(settle)
                seen.append(last_tic(game.log_path))
            return seen
        finally:
            game.stop()


def passed(seen: list[int], tics: int) -> bool:
    """Every tap moved the clock by one step: not frozen, not free-running, not counted twice.
    Steps end on whole multiples of the step time, so the first one (after the one or two tics
    the QA build runs on level entry) and rounding may be up to 2 tics short or long."""
    steps = zip(seen, seen[1:], strict=False)
    return len(seen) > 1 and all(abs(b - a - tics) <= 2 for a, b in steps)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m launcher.taptest")
    p.add_argument("--taps", type=int, default=4)
    p.add_argument("--tics", type=int, default=35)
    a = p.parse_args(argv)
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True))  # P2_GAME_EXE / P2_IWAD may live in .env
    seen = run(LauncherConfig.from_env(), a.taps, a.tics)
    ok = passed(seen, a.tics)
    print(f"tic after each 0 ms tap: {seen} -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
