"""Find and foreground the game window; return its screen rectangle for capture."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from launcher.config import IS_WINDOWS


@dataclass
class Window:
    handle: int
    title: str
    x: int
    y: int
    width: int
    height: int


def find_window(title_part: str) -> Window | None:
    return _find_win32(title_part) if IS_WINDOWS else _find_x11(title_part)


def foreground(win: Window) -> None:
    if IS_WINDOWS:
        import ctypes

        user32 = ctypes.windll.user32
        user32.ShowWindow(win.handle, 9)  # SW_RESTORE
        user32.SetForegroundWindow(win.handle)
    else:
        subprocess.run(["xdotool", "windowactivate", "--sync", str(win.handle)], check=False)


def refocus(win: Window) -> bool:
    """Give the game the keyboard back if something else took it (e.g. a click on the dashboard
    beside the game). True when it had to. Windows only: X11 test desktops have nothing else."""
    if not IS_WINDOWS:
        return False
    import ctypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    fg = user32.GetForegroundWindow()
    if not fg or fg == win.handle:
        return False
    # Windows refuses SetForegroundWindow from a background process unless it shares input
    # with the current foreground thread.
    other = user32.GetWindowThreadProcessId(fg, None)
    me = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(me, other, True)
    try:
        user32.ShowWindow(win.handle, 9)  # SW_RESTORE
        user32.SetForegroundWindow(win.handle)
        user32.BringWindowToTop(win.handle)
    finally:
        user32.AttachThreadInput(me, other, False)
    return True


def _find_x11(title_part: str) -> Window | None:
    env = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}
    out = subprocess.run(
        ["xdotool", "search", "--onlyvisible", "--name", title_part],
        capture_output=True, text=True, env=env,
    ).stdout.split()  # fmt: skip
    if not out:
        return None
    wid = out[0]
    title = subprocess.run(
        ["xdotool", "getwindowname", wid], capture_output=True, text=True, env=env
    ).stdout.strip()
    geo = subprocess.run(
        ["xdotool", "getwindowgeometry", "--shell", wid], capture_output=True, text=True, env=env
    ).stdout
    g = dict(line.split("=", 1) for line in geo.split() if "=" in line)
    return Window(int(wid), title, int(g["X"]), int(g["Y"]), int(g["WIDTH"]), int(g["HEIGHT"]))


def _find_win32(title_part: str) -> Window | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[Window] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if title_part in buf.value:
            r = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            pt = wintypes.POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(pt))
            found.append(Window(hwnd, buf.value, pt.x, pt.y, r.right, r.bottom))
            return False
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else None
