"""Screenshots, window recording and clips with ffmpeg (x11grab on Linux, gdigrab on Windows)."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from launcher.config import IS_WINDOWS
from launcher.window import Window


def grab_input(win: Window, fps: int, windows: bool = IS_WINDOWS) -> list[str]:
    w, h = win.width - win.width % 2, win.height - win.height % 2  # libx264 needs even sizes
    if windows:
        return ["-f", "gdigrab", "-framerate", str(fps), "-offset_x", str(win.x),
                "-offset_y", str(win.y), "-video_size", f"{w}x{h}", "-i", "desktop"]  # fmt: skip
    display = os.environ.get("DISPLAY", ":0")
    return ["-f", "x11grab", "-framerate", str(fps), "-video_size", f"{w}x{h}",
            "-i", f"{display}+{win.x},{win.y}"]  # fmt: skip


def screenshot(win: Window, out: Path) -> Path:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *grab_input(win, 1),
           "-frames:v", "1", str(out)]  # fmt: skip
    subprocess.run(cmd, check=True)
    return out


@dataclass
class Recording:
    path: Path
    started_at: float  # wall clock (time.time()) of the first frame, roughly
    proc: subprocess.Popen | None = None

    def stop(self) -> Path:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.communicate(b"q", timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(5)
        return self.path


def record(win: Window, out: Path, fps: int = 30) -> Recording:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *grab_input(win, fps),
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)]  # fmt: skip
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    return Recording(out, time.time(), proc)


def clip_window(
    event_t: float, game_started_at: float, rec_started_at: float, before=5.0, after=5.0
) -> tuple[float, float]:
    """Game time of an event (GameEvent.t) -> [start, end] seconds inside the recording."""
    at = event_t + game_started_at - rec_started_at
    return max(0.0, at - before), max(0.0, at + after)


def label_text(speed: float) -> str:
    return f"RECORDED · {speed:g}× speed" if speed != 1 else "RECORDED"


FONTS = (
    "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial.ttf",
)  # fmt: skip


def default_font() -> str | None:
    """A TTF for drawtext: ffmpeg builds on Windows have no fontconfig, so name a file."""
    env = os.environ.get("P2_FONT")
    if env:
        return env
    return next((f for f in FONTS if Path(f).exists()), None)


def cut_args(
    src: Path, start: float, end: float, out: Path, speed: float = 1.0, label: str | None = None,
    fontfile: str | None = None,
) -> list[str]:  # fmt: skip
    """ffmpeg command for a clip: [start, end] of `src`, sped up by `speed`, optional label."""
    filters = []
    if speed != 1:
        filters.append(f"setpts=PTS/{speed:g}")
    if label:
        fontfile = fontfile or default_font()
        path = (fontfile or "").replace("\\", "/").replace(":", r"\:")  # C\:/Windows/...
        font = f"fontfile='{path}':" if fontfile else ""
        text = label.replace(":", r"\:").replace("'", "")
        filters.append(
            f"drawtext={font}text='{text}':x=w-tw-24:y=24:fontsize=h/18:"
            "fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10"
        )
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}",
           "-to", f"{end:.3f}", "-i", str(src)]  # fmt: skip
    if filters:
        cmd += ["-vf", ",".join(filters)]
    return cmd + ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", str(out)]


def cut_clip(src: Path, start: float, end: float, out: Path, **kw) -> Path:
    subprocess.run(cut_args(src, start, end, out, **kw), check=True)
    return out
