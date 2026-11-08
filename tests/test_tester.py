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


class _Sessions:
    def __init__(self, items):
        self.items, self.cancelled, self.listed = items, [], None

    def list_sessions(self, **kw):
        self.listed = kw
        return type("Page", (), {"items": self.items})()

    def cancel_session(self, id):
        self.cancelled.append(id)


def _session(id, status):
    return type("S", (), {"id": id, "status": status})()


def test_failed_create_cancels_the_orphan_h_session(monkeypatch):
    import httpx
    import pytest

    from agents import tester as t

    class Client:
        sessions = _Sessions([_session("orphan", "running"), _session("old", "completed")])

        def start_session(self, **kw):
            raise httpx.ReadTimeout("The read operation timed out")

    monkeypatch.setattr(t, "quota", lambda: {"available": 3})
    monkeypatch.setattr(t, "forbid_shell", lambda: None)  # needs a display on CI
    run = t.Tester(client=Client())
    with pytest.raises(httpx.ReadTimeout):
        run.start("play")
    assert Client.sessions.cancelled == ["orphan"]
    assert Client.sessions.listed["agent"] == t.AGENT_NAME
    run.stop()  # no handle: stop sweeps again instead of doing nothing
    assert Client.sessions.cancelled == ["orphan", "orphan"]


def test_follow_reconnects_after_a_stream_timeout(monkeypatch):
    import httpx

    from agents import tester as t

    class Handle:
        id = "h1"

        def __init__(self):
            self.calls = []

        def stream(self, from_index=0):
            self.calls.append(from_index)
            if len(self.calls) == 1:
                yield object()
                raise httpx.ReadTimeout("slow first step")
            yield object()

        def wait_for_completion(self):
            return type("R", (), {"status": "completed", "answer": None})()

    monkeypatch.setattr(t, "forbid_shell", lambda: None)
    run = t.Tester(client=object())
    run.handle = Handle()
    run.run = t.TesterRun("h1", None, "running", None, run.tools)
    run.follow()
    assert run.handle.calls == [0, 1] and run.run.events == 2


def test_stage_presets_require_the_sphere_before_finishing():
    from launcher.config import PRESETS

    assert PRESETS["stage-play"].goal == PRESETS["stage-kb3"].goal == "powerup"
    assert "final answer" in PRESETS["stage-play"].plan


def test_follow_gives_up_after_the_stream_retries(monkeypatch):
    import httpx
    import pytest

    from agents import tester as t

    class Handle:
        id = "h1"

        def stream(self, from_index=0):
            raise httpx.ReadTimeout("still nothing")
            yield

        def wait_for_completion(self):
            raise AssertionError("must not block on a dead stream")

    monkeypatch.setattr(t, "forbid_shell", lambda: None)
    run = t.Tester(client=object())
    run.handle = Handle()
    run.run = t.TesterRun("h1", None, "running", None, run.tools)
    with pytest.raises(httpx.ReadTimeout):
        run.follow()
