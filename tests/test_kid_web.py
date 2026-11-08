import base64

import pytest
from fastapi.testclient import TestClient

from voice import commentator as c
from voice import kid_web

JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xfffake").decode()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("P2_KID_MAX_LINES", "3")
    return TestClient(kid_web.create_app())


def test_line_uses_the_kid_prompt_and_drops_repeats(client, monkeypatch):
    said = iter(["Hmm... a door over there.", "Hmm, a door over there.", "Your name is Sam."])
    monkeypatch.setattr(c, "comment", lambda shot, recent, **kw: next(said))
    r = client.post("/api/kid/line", json={"image": JPEG})
    assert r.json()["text"] == "Hmm... a door over there."
    kid_web.time.sleep(1.6)
    r = client.post("/api/kid/line", json={"image": JPEG, "recent": ["Hmm... a door over there."]})
    assert r.json()["text"] == "" and r.json()["skipped"] == "repeat" and "vision_s" in r.json()
    kid_web.time.sleep(1.6)
    r = client.post("/api/kid/line", json={"image": JPEG, "question": "What's my name?"})
    assert r.json()["text"] == "Your name is Sam."


def test_budget_gap_and_cap(client, monkeypatch):
    monkeypatch.setattr(c, "comment", lambda shot, recent, **kw: "")
    assert client.post("/api/kid/line", json={"image": JPEG}).status_code == 200
    assert client.post("/api/kid/line", json={"image": JPEG}).status_code == 429  # too fast
    b = kid_web.Budget(1, 0)
    b.take("a")
    with pytest.raises(kid_web.HTTPException):
        b.take("b")


def test_line_rejects_non_images(client):
    assert client.post("/api/kid/line", json={"image": "hello"}).status_code == 400
    text = "data:image/jpeg;base64," + base64.b64encode(b"not an image").decode()
    assert client.post("/api/kid/line", json={"image": text}).status_code == 400


def test_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Play with Pixel" in r.text
