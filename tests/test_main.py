def test_start_passes_plan_and_preset(tmp_path):
    from app.main import Runtime

    rt = Runtime(tmp_path)
    seen = {}

    def new(mode=None, plan=None, preset=None):
        seen.update(mode=mode, plan=plan, preset=preset)
        raise RuntimeError("stop here")

    rt.new = new
    try:
        rt.start("live", "power-ups", "stage-kb3")
    except Exception:  # noqa: BLE001
        pass
    assert seen == {"mode": "live", "plan": "power-ups", "preset": "stage-kb3"}


def test_transcript_needs_a_session(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import Runtime, create_app

    c = TestClient(create_app(Runtime(tmp_path)))
    r = c.post("/api/transcript", json={"text": "fix it", "final": True})
    assert r.status_code == 409


def test_transcript_after_the_session_ended_is_dropped(tmp_path):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.main import Runtime, create_app

    rt = Runtime(tmp_path)
    seen = []
    rt.current = SimpleNamespace(
        info=SimpleNamespace(state="done"), publish=lambda *a: seen.append(a)
    )
    c = TestClient(create_app(rt))
    assert c.post("/api/transcript", json={"text": "hi", "final": True}).status_code == 409
    rt.current.info.state = "exploring"
    assert c.post("/api/transcript", json={"text": "hi", "final": True}).status_code == 200
    assert len(seen) == 1


def test_ptt_is_held_by_the_backend_and_echoed_to_the_dashboard(tmp_path):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.main import Runtime, create_app

    rt = Runtime(tmp_path)
    seen = []
    rt.current = SimpleNamespace(
        info=SimpleNamespace(state="awaiting_approval"), publish=lambda *a: seen.append(a)
    )
    c = TestClient(create_app(rt))
    assert c.get("/api/ptt").json() == {"on": False}
    assert c.post("/api/ptt", json={"on": True}).json() == {"on": True}
    assert c.get("/api/ptt").json() == {"on": True}
    assert seen[-1][1].text.startswith("[push-to-talk ON")
    c.post("/api/ptt", json={"on": False})
    assert seen[-1][1].text == "[push-to-talk OFF]"


def test_ptt_goes_off_when_the_run_ends(tmp_path):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.main import Runtime, create_app

    rt = Runtime(tmp_path)
    rt.current = SimpleNamespace(info=SimpleNamespace(state="exploring"), publish=lambda *a: None)
    c = TestClient(create_app(rt))
    c.post("/api/ptt", json={"on": True})
    rt.current.info.state = "stopped"
    assert c.get("/api/ptt").json() == {"on": False}
    assert c.post("/api/ptt", json={"on": True}).json() == {"on": False}


def test_public_tunnel_link_is_view_only():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    hdr = {"cf-connecting-ip": "203.0.113.7"}
    r = client.post("/api/intent", json={"intent": "fix", "source": "button"}, headers=hdr)
    assert r.status_code == 403
    assert client.post("/api/stop", json={}, headers=hdr).status_code == 403
    assert client.get("/api/session", headers=hdr).status_code == 200


def test_screen_serves_the_game_window_to_viewers(tmp_path):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.main import Runtime, create_app

    rt = Runtime(tmp_path)
    c = TestClient(create_app(rt))
    assert c.get("/api/screen").status_code == 404  # no run
    calls = []

    def grab(out):
        calls.append(out)
        out.write_bytes(b"\xff\xd8jpg")
        return out

    rt.current = SimpleNamespace(deps=SimpleNamespace(screen=grab))
    r = c.get("/api/screen")
    assert r.status_code == 200 and r.content == b"\xff\xd8jpg"
    assert r.headers["content-type"] == "image/jpeg"
    c.get("/api/screen")
    assert len(calls) == 1  # one grab a second, shared by every viewer
