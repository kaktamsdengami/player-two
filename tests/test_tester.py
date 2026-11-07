def test_shell_is_refused_on_the_local_desktop():
    import os
    import sys

    import pytest

    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("hai_drivers' desktop driver needs an X display")
    driver = pytest.importorskip("hai_drivers.desktop.local.driver")
    LocalDesktopDriver = driver.LocalDesktopDriver

    from agents.tester import SHELL_REFUSED, forbid_shell

    forbid_shell()
    r = LocalDesktopDriver.run_command(object(), ["cat", "events.jsonl"])
    assert r.returncode != 0 and r.stderr == SHELL_REFUSED and not r.stdout


def test_hai_regions_restricts_fallback(monkeypatch):
    import pytest

    from agents.tester import HBusyError, choose_region

    monkeypatch.setenv("HAI_BASE_URL", "https://agp.hcompany.ai")
    monkeypatch.setenv("HAI_REGIONS", "https://agp.hcompany.ai/, ")
    seen = []

    def q(url):
        seen.append(url)
        return {"available": 0}

    with pytest.raises(HBusyError):
        choose_region(quota_fn=q)
    assert seen == ["https://agp.hcompany.ai"]


def test_tester_model_switch(monkeypatch):
    from agents import tester
    from agents.tools import TesterTools

    monkeypatch.delenv("P2_TESTER_MODEL", raising=False)
    assert tester.agent_spec(TesterTools(), "x")["model"] == "holo4-35b-a3b"
    monkeypatch.setenv("P2_TESTER_MODEL", "holo4-27b")
    assert tester.agent_spec(TesterTools(), "x")["model"] == "holo4-27b"


def test_plan_appends_focus_area():
    from agents.tester import DEFAULT_TASK, with_plan

    assert with_plan(DEFAULT_TASK, None) == DEFAULT_TASK
    assert with_plan("Play.", " power-ups ").endswith(
        "The developer asks you to focus on: power-ups"
    )
