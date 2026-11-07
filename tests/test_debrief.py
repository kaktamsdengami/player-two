import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from app.contracts import Citation, DebriefReport, Finding, FindingStatus
from insights import debrief, linkup

FIX = Path(__file__).parent / "fixtures" / "qa_logs"


def ev(tic, typ, x, y, m="E1M1", **data):
    p = {"x": x, "y": y, "z": 0, "angle": 0, "health": 100, "armor": 0, "sector": 1}
    return json.dumps({"tic": tic, "t": tic / 35, "map": m, "type": typ, "player": p, "data": data})


def finding(**kw):
    base = dict(
        id="f-1",
        session_id="s",
        title="Sky stays red under invulnerability",
        location="E3M1, start area",
        steps=["Type iddqd"],
        expected="The whole view, sky included, turns inverse grey.",
        actual="The walls turn grey but the sky stays red.",
        reported_at=datetime(2026, 11, 7, tzinfo=UTC),
    )
    return Finding(**(base | kw))


def run_dir(tmp_path, lines, notes=(), findings=(), verdicts=None):
    (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\nnot json\n")
    summary = {
        "session_id": "h-123",
        "notes": list(notes),
        "findings": [f.model_dump(mode="json") for f in findings],
    }
    (tmp_path / "tester_run.json").write_text(json.dumps(summary))
    if verdicts is not None:
        (tmp_path / "verdicts.json").write_text(json.dumps(verdicts))
    return tmp_path


def test_heatmap_counts_deaths_and_level_restarts():
    events = [
        debrief.GameEvent.model_validate_json(x)
        for x in [
            ev(0, "level", 0, 0),
            ev(10, "death", 300, 300),
            ev(11, "level", 0, 0),
            ev(20, "death", 310, 290),
            ev(21, "level", 0, 0),
            ev(30, "level", 1000, 0, m="E1M2"),
        ]
    ]
    bounds, cells = debrief.heatmap(events)
    assert bounds == (0, 0, 1000, 300)
    hot = next(c for c in cells if (c.x, c.y) == (320.0, 320.0))
    assert hot.deaths == 2 and hot.retries == 0
    start = next(c for c in cells if (c.x, c.y) == (64.0, 64.0))
    assert start.retries == 2 and start.deaths == 0
    assert sum(c.retries for c in cells) == 2  # first entry into E1M2 is not a retry


def test_build_validates_and_uses_verified_findings(tmp_path):
    f = finding()
    verified = finding(status=FindingStatus.verified, known_bug_ref="KB3")
    note = {
        "session_id": "h-123",
        "ts": "2026-11-07T20:00:00Z",
        "t_session_s": 12,
        "text": "Hard to tell which corridor leads out",
        "tags": ["confusing"],
    }
    d = run_dir(
        tmp_path,
        [ev(0, "level", 0, 0, m="E3M1"), ev(70, "player", 64, 32, m="E3M1")],
        notes=[note],
        findings=[f],
        verdicts=[{"finding": "f-1", "finding_full": verified.model_dump(mode="json")}],
    )
    queries = []

    def search(q):
        queries.append(q)
        return [
            Citation(title="A", url="https://a.example/x"),
            Citation(title="A2", url="https://a.example/y"),
            Citation(title="B", url="https://b.example/z"),
        ]

    r = DebriefReport.model_validate_json(debrief.build(d, search=search).model_dump_json())
    assert r.session_id == "h-123" and r.maps == ["E3M1"] and r.duration_s == 2.0
    assert r.notes[0].tags == ["confusing"]
    assert r.suggestions[0].finding_id == "f-1"
    assert r.suggestions[0].suggestion == (
        "E3M1, start area: The walls turn grey but the sky stays red. "
        "Change it so that the whole view, sky included, turns inverse grey."
    )
    assert [c.url for c in r.references] == ["https://a.example/x", "https://b.example/z"]
    assert "wayfinding" in queries[0]


def test_suggested_change_wins_and_linkup_failure_is_not_fatal(tmp_path):
    d = run_dir(tmp_path, [], findings=[finding(suggested_change="Apply the colormap to the sky")])

    def boom(q):
        raise httpx.ConnectError("down")

    r = debrief.build(d, search=boom)
    assert r.suggestions[0].suggestion == "Apply the colormap to the sky."
    assert r.references == [] and r.heatmap == [] and r.map_bounds is None


def test_real_kb3_log():
    lines = (FIX / "kb3_e3m1.jsonl").read_text().splitlines()
    events = [debrief.GameEvent.model_validate_json(x) for x in lines]
    bounds, cells = debrief.heatmap(events)
    assert bounds is not None and cells == []


def test_cli_writes_debrief(tmp_path, capsys):
    d = run_dir(tmp_path, [ev(0, "level", 0, 0), ev(5, "death", 10, 10)])
    assert debrief.main([str(d), "--no-linkup"]) == 0
    r = DebriefReport.model_validate_json((d / "debrief.json").read_text())
    assert r.heatmap[0].deaths == 1
    assert "friction: {'deaths': 1, 'retries': 0}" in capsys.readouterr().out


@respx.mock
def test_linkup_search(monkeypatch):
    monkeypatch.setenv("LINKUP_API_KEY", "k")
    route = respx.post(linkup.URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"type": "text", "name": "Doc", "url": "https://d.example", "content": "a\nb"},
                    {"type": "image", "name": "no url"},
                ]
            },
        )
    )
    hits = linkup.search("q")
    assert hits == [Citation(title="Doc", url="https://d.example", snippet="a b")]
    body = json.loads(route.calls[0].request.content)
    assert body == {"q": "q", "depth": "standard", "outputType": "searchResults"}
    assert route.calls[0].request.headers["authorization"] == "Bearer k"


def test_search_drops_non_http_urls(monkeypatch):
    monkeypatch.setenv("LINKUP_API_KEY", "k")
    results = [
        {"name": "bad", "url": "javascript:alert(1)"},
        {"name": "ok", "url": "https://a.b/c"},
    ]
    with respx.mock:
        respx.post(linkup.URL).respond(json={"results": results})
        assert [c.url for c in linkup.search("q")] == ["https://a.b/c"]
