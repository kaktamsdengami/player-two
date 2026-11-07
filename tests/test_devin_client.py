import json
from datetime import UTC, datetime

import httpx
import pytest

from app.contracts import Evidence, Finding, FixResult, GameEvent
from devin.client import DevinClient, DevinError, render_prompt, result_from_session

ORG = "org-test"
BASE = f"https://api.devin.ai/v3/organizations/{ORG}/sessions"


def _finding() -> Finding:
    ev = GameEvent.model_validate(
        json.loads(open("docs/api-mock.json").read())["GET /api/findings"][0]["evidence"][
            "log_excerpt"
        ][0]
    )
    return Finding(
        id="F-1",
        session_id="s-1",
        title="Ouch face never shows on big hits",
        location="E1M1, near the barrels",
        steps=["warp to E1M1", "shoot the barrel next to you"],
        expected="ouch face",
        actual="normal pain face",
        evidence=Evidence(log_excerpt=[ev]),
        status="verified",
        reported_at=datetime(2026, 11, 7, tzinfo=UTC),
    )


def _session(status="running", prs=(), detail="working", acus=1.5):
    return {
        "session_id": "devin-abc",
        "url": "https://app.devin.ai/sessions/abc",
        "status": status,
        "status_detail": detail,
        "tags": [],
        "org_id": ORG,
        "created_at": 0,
        "updated_at": 0,
        "acus_consumed": acus,
        "pull_requests": [{"pr_url": u, "pr_state": s} for u, s in prs],
    }


class FakeDevin:
    """Records requests and serves a scripted sequence of session states."""

    def __init__(self, states):
        self.states = list(states)
        self.requests: list[tuple[str, str, dict | None]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, str(request.url), body))
        assert request.headers["authorization"] == "Bearer k"
        if request.url.path.endswith("/messages") and request.method == "POST":
            return httpx.Response(200, json={})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"items": [{"message": "hi", "source": "devin"}]})
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return httpx.Response(200, json=state)


def _client(fake) -> DevinClient:
    return DevinClient("k", ORG, client=httpx.Client(transport=httpx.MockTransport(fake)))


def test_prompt_contains_repro_log_and_instruction():
    p = render_prompt(_finding(), file_hints=["src/doom/st_stuff.c"])
    for part in [
        "Ouch face never shows",
        "1. warp to E1M1",
        "2. shoot the barrel",
        "normal pain face",
        "src/doom/st_stuff.c",
        "regression test",
        "Fix in source, add a regression test if the codebase allows it, open a PR.",
        '"type":',
    ]:
        assert part in p
    assert "known_bug" not in p


def test_create_session_request_and_attempt():
    fake = FakeDevin([_session(status="new", detail=None, acus=0)])
    attempt = _client(fake).create_fix_session(_finding(), file_hints=["src/doom/st_stuff.c"])
    method, url, body = fake.requests[0]
    assert (method, url) == ("POST", BASE)
    assert body["repos"] == ["kaktamsdengami/chocolate-doom"]
    assert "finding:F-1" in body["tags"]
    assert body["max_acu_limit"] == 10
    assert attempt.devin_session_id == "devin-abc"
    assert attempt.result == FixResult.queued
    assert attempt.round == 1


def test_follow_reports_changes_and_extracts_pr():
    pr = "https://github.com/kaktamsdengami/chocolate-doom/pull/7"
    fake = FakeDevin(
        [
            _session(status="new", detail=None),
            _session(),
            _session(acus=2.0),
            _session(prs=[(pr, "open")], acus=3.0),
        ]
    )
    dc = _client(fake)
    attempt = dc.create_fix_session(_finding())
    seen = []
    attempt = dc.follow(attempt, seen.append, sleep=lambda s: None)
    assert attempt.result == FixResult.pr_open
    assert attempt.pr_url == pr
    assert attempt.acus == 3.0
    assert [a.result for a in seen] == ["working", "working", "pr_open"]
    assert all(r[1] == f"{BASE}/devin-abc" for r in fake.requests[1:])


def test_follow_timeout():
    fake = FakeDevin([_session()])
    dc = _client(fake)
    attempt = dc.create_fix_session(_finding())
    with pytest.raises(DevinError):
        dc.follow(attempt, timeout_s=30, poll_s=15, sleep=lambda s: None)


def test_approve_merge_then_merged():
    pr = "https://github.com/kaktamsdengami/chocolate-doom/pull/7"
    fake = FakeDevin([_session(prs=[(pr, "open")]), _session(prs=[(pr, "merged")])])
    dc = _client(fake)
    attempt = dc.create_fix_session(_finding())
    dc.approve_merge(attempt)
    method, url, body = fake.requests[-1]
    assert (method, url) == ("POST", f"{BASE}/devin-abc/messages")
    assert pr in body["message"] and "Merge" in body["message"]
    attempt = dc.follow(attempt, sleep=lambda s: None)
    assert attempt.result == FixResult.merged
    assert attempt.finished_at is not None


def test_approve_without_pr_refused():
    dc = _client(FakeDevin([_session()]))
    with pytest.raises(DevinError):
        dc.approve_merge(dc.create_fix_session(_finding()))


def test_feedback_round_once():
    pr = "https://github.com/kaktamsdengami/chocolate-doom/pull/7"
    fake = FakeDevin([_session(prs=[(pr, "open")])])
    dc = _client(fake)
    attempt = dc.create_fix_session(_finding())
    attempt = dc.send_feedback(attempt, "face still normal after the barrel blast")
    assert attempt.round == 2 and attempt.result == FixResult.working
    assert "Not fixed" in fake.requests[-1][2]["message"]
    assert "barrel blast" in fake.requests[-1][2]["message"]
    with pytest.raises(DevinError):
        dc.send_feedback(attempt, "again")


def test_messages_and_http_error():
    dc = _client(FakeDevin([_session()]))
    assert dc.messages("devin-abc")[0]["message"] == "hi"
    bad = DevinClient(
        "k", ORG, client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    )
    with pytest.raises(DevinError) as e:
        bad.get_session("devin-x")
    assert "403" in str(e.value) and "k" not in str(e.value).split("HTTP")[0].split()[-1]


@pytest.mark.parametrize(
    "session,expected",
    [
        (_session(status="error", detail=None), "failed"),
        (_session(status="suspended", detail="out_of_credits"), "failed"),
        (_session(status="suspended", detail="inactivity"), "working"),
        (_session(status="running", detail="finished"), "failed"),
        (_session(status="exit", detail=None), "failed"),
        (_session(prs=[("u", "closed")]), "working"),
        (_session(prs=[("u", None)]), "pr_open"),
    ],
)
def test_status_mapping(session, expected):
    assert result_from_session(session)[0] == expected


def test_from_env_requires_both(monkeypatch):
    monkeypatch.delenv("DEVIN_ORG_ID", raising=False)
    monkeypatch.setenv("DEVIN_API_KEY", "k")
    with pytest.raises(DevinError):
        DevinClient.from_env()
