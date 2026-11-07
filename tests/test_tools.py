from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

from agents import tester
from agents.tools import NO_ANSWER, TesterTools
from app.contracts import ActionKind, Finding

ROOT = Path(__file__).resolve().parents[1]


def _finding_args(**over):
    args = {
        "title": "Sky keeps its colours under the power-up",
        "location": "E3M1, start area",
        "steps": ["Start E3M1", "Type idbehold v", "Look at the sky"],
        "expected": "The whole screen changes",
        "actual": "Only the walls change",
    }
    return args | over


def test_report_finding_is_a_valid_finding():
    seen = []
    t = TesterTools(session_id="s1", started_at=0, on_finding=seen.append)
    r = t.report_finding(**_finding_args(severity="high"))
    assert r == {"ok": True, "finding_id": "F1"}
    f = t.findings[0]
    assert isinstance(f, Finding) and seen == [f]
    assert f.session_id == "s1" and f.severity == "high" and f.status == "suspected"
    assert f.known_bug_ref is None and f.t_session_s > 0
    Finding.model_validate_json(f.model_dump_json())


def test_bad_finding_returns_an_error_instead_of_raising():
    t = TesterTools()
    r = t.report_finding(**_finding_args(steps=["  "]))
    assert r["ok"] is False and "steps" in r["error"]
    r = t.report_finding(**_finding_args(severity="apocalyptic"))
    assert r["ok"] is False and "severity" in r["error"]
    assert t.findings == []


def test_note_and_ask_developer():
    t = TesterTools(session_id="s1", answer=lambda q: "yes, intended" if "door" in q else None)
    assert t.note("Dark corridor is confusing", tags=["confusing"]) == {"ok": True}
    assert t.notes[0].tags == ["confusing"] and t.notes[0].session_id == "s1"
    assert t.ask_developer("Is the door supposed to stay shut?") == {"answer": "yes, intended"}
    assert t.ask_developer("Anything else?") == {"answer": NO_ANSWER}
    assert len(t.questions) == 2


def test_tool_schemas_hide_verifier_fields():
    defs = {x.name: x.definition() for x in TesterTools().tools()}
    assert set(defs) == {"report_finding", "note", "ask_developer"}
    props = defs["report_finding"]["input_schema"]["properties"]
    assert {"title", "location", "steps", "expected", "actual"} <= set(props)
    assert not {"known_bug_ref", "status", "evidence", "session_id"} & set(props)
    assert all(d["description"] for d in defs.values())


def test_prompt_never_leaks_the_known_bug_list():
    prompt = tester.PROMPT.read_text().lower()
    spec = tester.agent_spec(TesterTools())
    assert spec["environments"] == [{"id": "desktop", "kind": "desktop", "host": "user_device"}]
    text = (spec["instructions"] + spec["description"]).lower()
    assert "known_bugs" not in text and "event log" not in text
    bugs = yaml.safe_load((ROOT / "eval" / "known_bugs.yaml").read_text())
    bugs = bugs["bugs"] if isinstance(bugs, dict) else bugs
    for b in bugs:
        assert b["id"].lower() not in prompt
        assert b["title"].lower() not in prompt


def test_policy_steps_become_timestamped_actions():
    ts = datetime(2026, 11, 7, 20, 0, 10, tzinfo=UTC)
    ev = SimpleNamespace(
        timestamp=ts,
        data={
            "tool_reqs": [
                {"tool_name": "press_key", "args": {"keys": ["up"]}},
                {"tool_name": "report_finding", "args": {"title": "x"}},
                {"tool_name": "hold_key", "args": {"key": "left", "duration": 1}},
            ]
        },
    )
    acts = tester.to_action("s1", 3, ts.timestamp() - 10, ev)
    assert [a.kind for a in acts] == [
        ActionKind.key_press,
        ActionKind.tool_call,
        ActionKind.key_hold,
    ]
    assert acts[0].keys == ["up"] and acts[2].keys == ["left"]
    assert all(a.t_session_s == 10 and a.step == 3 for a in acts)
    assert tester.to_action("s1", 0, 0, SimpleNamespace(data={"kind": "observation_event"})) == []


def test_hold_keeps_its_duration():
    from types import SimpleNamespace

    from agents.tester import to_action

    ev = SimpleNamespace(
        data={"tool_reqs": [{"tool_name": "hold_key", "args": {"keys": ["up"], "duration": 1.5}}]}
    )
    (a,) = to_action("s", 1, 0.0, ev)
    assert a.kind == "key_hold" and a.duration_ms == 1500


def test_retry_backs_off_on_transient_errors_only():
    import httpx
    import pytest

    from agents.tester import with_retry

    req = httpx.Request("GET", "https://h.example/q")
    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise httpx.HTTPStatusError("busy", request=req, response=httpx.Response(503))
        return "ok"

    assert with_retry(flaky, sleep=sleeps.append) == "ok" and sleeps == [2.0, 4.0]

    def denied():
        raise httpx.HTTPStatusError("no", request=req, response=httpx.Response(401))

    with pytest.raises(httpx.HTTPStatusError):
        with_retry(denied, sleep=sleeps.append)


def test_choose_region_falls_back_then_reports_busy(monkeypatch):
    import pytest

    from agents.tester import REGIONS, HBusyError, choose_region

    monkeypatch.setenv("HAI_BASE_URL", REGIONS[0])
    free = {REGIONS[0]: 1, REGIONS[1]: 2}
    assert choose_region(2, lambda u: {"available": free[u]}) == REGIONS[1]
    free[REGIONS[1]] = 0
    with pytest.raises(HBusyError, match="retry"):
        choose_region(2, lambda u: {"available": free[u]})


def test_choose_region_skips_a_region_whose_quota_fails(monkeypatch):
    import httpx

    from agents.tester import REGIONS, choose_region

    monkeypatch.setenv("HAI_BASE_URL", REGIONS[0])

    def q(url):
        if url == REGIONS[0]:
            raise httpx.ReadTimeout("slow")
        return {"available": 3}

    assert choose_region(2, q) == REGIONS[1]


def test_choose_region_raises_auth_errors_instead_of_busy(monkeypatch):
    import httpx
    import pytest

    from agents.tester import REGIONS, choose_region

    monkeypatch.setenv("HAI_BASE_URL", REGIONS[0])
    resp = httpx.Response(401, request=httpx.Request("GET", REGIONS[0]))

    def q(url):
        raise httpx.HTTPStatusError("unauthorized", request=resp.request, response=resp)

    with pytest.raises(httpx.HTTPStatusError):
        choose_region(2, q)


def test_choose_region_skips_a_region_returning_404(monkeypatch):
    import httpx

    from agents.tester import REGIONS, choose_region

    monkeypatch.setenv("HAI_BASE_URL", REGIONS[0])

    def q(url):
        if url == REGIONS[0]:
            resp = httpx.Response(404, request=httpx.Request("GET", url))
            raise httpx.HTTPStatusError("nf", request=resp.request, response=resp)
        return {"available": 2}

    assert choose_region(2, q) == REGIONS[1]


def test_choose_region_raises_on_rejected_request(monkeypatch):
    import httpx
    import pytest

    from agents.tester import REGIONS, choose_region

    monkeypatch.setenv("HAI_BASE_URL", REGIONS[0])
    resp = httpx.Response(422, request=httpx.Request("GET", REGIONS[0]))

    def q(url):
        raise httpx.HTTPStatusError("bad", request=resp.request, response=resp)

    with pytest.raises(httpx.HTTPStatusError):
        choose_region(2, q)


def test_quota_404_is_not_retried():
    import httpx

    from agents.tester import with_retry

    calls = []
    resp = httpx.Response(404, request=httpx.Request("GET", "http://x"))

    def f():
        calls.append(1)
        raise httpx.HTTPStatusError("nf", request=resp.request, response=resp)

    try:
        with_retry(f, sleep=lambda s: None)
    except httpx.HTTPStatusError:
        pass
    assert len(calls) == 1


def test_choose_region_skips_a_region_returning_408(monkeypatch):
    import httpx

    from agents.tester import REGIONS, choose_region

    monkeypatch.setenv("HAI_BASE_URL", REGIONS[0])

    def q(url):
        if url == REGIONS[0]:
            resp = httpx.Response(408, request=httpx.Request("GET", url))
            raise httpx.HTTPStatusError("timeout", request=resp.request, response=resp)
        return {"available": 2}

    assert choose_region(2, q) == REGIONS[1]
