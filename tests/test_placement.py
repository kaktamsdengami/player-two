import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from app.contracts import AgentNote, PlacementSpot
from insights import linkup, placement
from insights.placement import Sighting

NOW = datetime(2026, 11, 7, tzinfo=UTC)


def _ask(sources_named: bool = False):
    def ask(q, schema):
        assert "candidates" in schema["properties"]
        return {
            "data": {"candidates": [
                {"name": "Red Bull", "rationale": "esports", "source_url": "https://rb.example/g"},
                {"name": "Logitech", "rationale": "gear", "source_url": "javascript:alert(1)"},
                {"name": "NoSource", "rationale": "no link anywhere"},
            ]},
            "sources": [{"name": "Logitech G esports", "url": "https://lg.example/esports",
                         "snippet": "Logitech sponsors teams"}],
        }  # fmt: skip

    return ask


def test_spots_merge_score_and_rank():
    seen = [
        Sighting("Large red rock wall", "wall", "start area", 0.9, 0, "f1.png"),
        Sighting("red rock wall", "wall", "start area", 0.7, 5, "f2.png"),
        Sighting("the red rock wall", "wall", "corridor", 0.8, 10, "f3.png"),
        Sighting("Computer screen", "screen", "control room", 0.6, 10, "f3.png"),
        Sighting("Weird", "bogus", "x", 0.1, 0, None),
    ]
    out = placement.spots(seen, "s1", every_s=5, top=2)
    assert [s.id for s in out] == ["spot-1", "spot-2"]
    wall = out[0]
    assert wall.name == "Large red rock wall" and wall.screen_time_s == 15
    assert wall.visibility == 0.8 and wall.location == "start area" and wall.screenshot == "f1.png"
    assert out[1].surface == "screen"
    assert all(PlacementSpot.model_validate(s.model_dump()) for s in out)
    assert "No brand deal" in wall.disclaimer


def test_brands_keep_only_sourced_http_candidates():
    spot = placement.spots([Sighting("screen", "screen", "lab", 0.5, 0, None)], "s")[0]
    got = placement.brands(spot, _ask())
    assert [b.name for b in got] == ["Red Bull", "Logitech"]
    assert got[0].sources[0].url == "https://rb.example/g"
    assert got[1].sources[0].url == "https://lg.example/esports"  # fell back to a naming source


def test_sightings_skip_bad_frames_and_clamp():
    def detect(p: Path):
        if p.name == "bad.png":
            raise RuntimeError("boom")
        return [{"name": "Poster", "surface": "POSTER", "visibility": 3}, {"surface": "wall"},
                {"name": "Sign", "visibility": "high"}]  # fmt: skip

    out = placement.sightings([(0, Path("bad.png")), (5, Path("ok.png"))], detect)
    assert len(out) == 2 and out[0].surface == "poster" and out[0].visibility == 1.0
    assert out[1].visibility == 0.5


def test_notes_tagged_placement_become_spots():
    notes = [
        AgentNote(session_id="s", ts=NOW, t_session_s=12, text="Big blank screen by the exit",
                  tags=["placement"], location="exit room"),
        AgentNote(session_id="s", ts=NOW, t_session_s=20, text="odd door", tags=["confusing"]),
    ]  # fmt: skip
    out = placement.from_notes(notes)
    assert len(out) == 1 and out[0].location == "exit room"


def test_scout_cli_on_a_run(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    note = AgentNote(
        session_id="h1", ts=NOW, t_session_s=3, text="Billboard wall", tags=["placement"]
    )
    (run / "tester_run.json").write_text(
        json.dumps({"session_id": "h1", "notes": [note.model_dump(mode="json")]})
    )
    monkeypatch.setattr(placement.linkup, "structured", _ask())
    assert placement.main([str(run)]) == 0
    out = json.loads((run / "placement.json").read_text())
    assert out[0]["session_id"] == "h1" and len(out[0]["brand_candidates"]) == 2


def test_detect_request_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("HAI_API_KEY", "k")
    f = tmp_path / "f.png"
    f.write_bytes(b"png")
    content = 'Sure: {"spots": [{"name": "Crate", "surface": "item", "visibility": 0.4}]}'
    with respx.mock:
        route = respx.post(placement.MODELS_URL).respond(
            json={"choices": [{"message": {"content": content}}]}
        )
        assert placement.detect(f)[0]["name"] == "Crate"
        body = json.loads(route.calls[0].request.content)
        assert body["messages"][0]["content"][0]["image_url"]["url"].startswith(
            "data:image/png;base64,"
        )
        assert route.calls[0].request.headers["authorization"] == "Bearer k"


def test_linkup_structured_request(monkeypatch):
    monkeypatch.setenv("LINKUP_API_KEY", "k")
    with respx.mock:
        route = respx.post(linkup.URL).mock(
            return_value=httpx.Response(200, json={"data": {}, "sources": []})
        )
        linkup.structured("q", {"type": "object"})
        body = json.loads(route.calls[0].request.content)
        assert body["outputType"] == "structured" and body["includeSources"] is True
        assert json.loads(body["structuredOutputSchema"]) == {"type": "object"}


def test_frames_drop_leftovers_from_an_earlier_pass(tmp_path, monkeypatch):
    out = tmp_path / "placement"
    out.mkdir()
    (out / "frame_0009.png").write_bytes(b"old")

    def fake_run(cmd, check):
        (out / "frame_0001.png").write_bytes(b"new")

    monkeypatch.setattr(placement.subprocess, "run", fake_run)
    assert [p.name for _, p in placement.frames(tmp_path / "r.mp4", out)] == ["frame_0001.png"]
