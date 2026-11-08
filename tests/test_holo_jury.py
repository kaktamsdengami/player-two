"""T33 jury site: /api/holo/act with a mocked Holo, caps, image checks; /api/live hub."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

import app.routes_holo as rh
from app.main import create_app

JPEG = base64.b64encode(bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")).decode()
IMG = "data:image/jpeg;base64," + JPEG


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HAI_API_KEY", "test-key")
    return TestClient(create_app())


def mock_holo(answer: str):
    def fake(raw: bytes, mime: str, text: str, model: str):
        assert mime == "jpeg" and raw[:2] == b"\xff\xd8"
        fake.prompts.append(text)
        return answer, {"total_tokens": 42}

    fake.prompts = []
    return fake


def test_act_returns_a_normalized_move(client, monkeypatch):
    fake = mock_holo(
        json.dumps(
            {
                "thought": "imp ahead",
                "keys": ["fire", "UP", "bogus"],
                "hold_ms": 99999,
                "aim": {"x": 9000, "y": -5},
                "status": "ok",
            }
        )
    )
    monkeypatch.setattr(rh, "ask_holo", fake)
    r = client.post(
        "/api/holo/act?c=t1",
        json={
            "image": IMG,
            "recent": [{"keys": ["up"]}],
            "instruction": "find the exit",
            "step": 3,
        },
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["thought"] == "imp ahead"
    assert j["keys"] == ["fire", "up"]  # unknown keys dropped, case fixed
    assert rh.HOLD_MIN <= j["hold_ms"] <= rh.HOLD_MAX
    assert j["status"] == "ok" and j["model"] and j["latency_ms"] >= 0
    assert j["aim"] is None or (0 <= j["aim"]["x"] and 0 <= j["aim"]["y"])
    assert "find the exit" in fake.prompts[0]


def test_act_without_key_is_503_recorded(monkeypatch):
    monkeypatch.delenv("HAI_API_KEY", raising=False)
    c = TestClient(create_app())
    r = c.post("/api/holo/act", json={"image": IMG})
    assert r.status_code == 503
    assert c.get("/api/holo/status").json()["live"] is False


@pytest.mark.parametrize(
    "image",
    [
        "data:image/jpeg;base64,!!!",
        "data:text/plain;base64," + JPEG,
        "not a data url",
        "data:image/jpeg;base64,",
    ],
)
def test_act_rejects_bad_images(client, image):
    r = client.post("/api/holo/act", json={"image": image})
    assert r.status_code in (400, 413, 415, 422), (image[:30], r.status_code, r.text[:80])


def test_bad_model_answer_is_a_502_the_engine_recovers_from(client, monkeypatch):
    monkeypatch.setattr(rh, "ask_holo", mock_holo("I cannot play games, sorry"))
    r = client.post("/api/holo/act", json={"image": IMG})
    assert r.status_code == 502  # holo-doom.js then makes a local move and retries next step
    assert client.get("/api/holo/status").json()["errors"] >= 1


def test_status_shape(client):
    j = client.get("/api/holo/status").json()
    assert j["live"] is True and set(j["models"]) == set(rh.model_names()) and j["rpm"] > 0


def test_live_hub_push_and_fanout(client, monkeypatch):
    monkeypatch.setenv("P2_LIVE_BROADCAST", "0")
    assert client.get("/api/live/status").json()["live"] is False
    with client.websocket_connect("/api/live/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["viewers"] == 1
        r = client.post(
            "/api/live/push",
            json={"type": "step", "step": 1, "keys": ["up"], "thought": "go", "frame": None},
        )
        assert r.status_code == 200 and r.json()["viewers"] == 1
        assert ws.receive_json()["thought"] == "go"
    st = client.get("/api/live/status").json()
    assert st["live"] is True and st["pushes"] == 1
    # late joiners get the history
    with client.websocket_connect("/api/live/ws") as ws:
        assert ws.receive_json()["history"][0]["thought"] == "go"


def test_live_push_refused_from_outside(client):
    r = client.post("/api/live/push", json={"step": 1}, headers={"cf-connecting-ip": "1.2.3.4"})
    assert r.status_code == 403
