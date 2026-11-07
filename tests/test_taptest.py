import os
import shutil
import sys

import pytest

from launcher.config import LauncherConfig
from launcher.taptest import passed, run


def test_passed_needs_one_step_per_tap():
    assert passed([1, 35, 70, 105, 140], 35)
    assert passed([2, 35, 70, 105, 140], 35)  # level entry ran two tics
    assert not passed([1, 35, 35, 35, 35], 35)  # frozen after the first step (stage run 1)
    assert not passed([1], 35)
    assert not passed([5, 5, 5], 1) and not passed([5, 5, 5], 2)  # frozen, tiny step
    assert passed([2, 3, 4], 1)
    assert not passed([1, 71, 141], 35)  # clock runs on its own (no frame-step)
    assert not passed([1, 35, 105], 35)  # one tap counted twice


def test_zero_ms_tap_advances_the_game():
    cfg = LauncherConfig.from_env()
    if not cfg.exe.exists() or not cfg.iwad.exists():
        pytest.skip("QA build or IWAD not installed")
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") and shutil.which("xdotool")
    ):
        pytest.skip("needs an X display and xdotool")
    seen = run(cfg, taps=3)
    assert passed(seen, 35), seen
