import json
import threading
import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.contracts import (
    AgentAction,
    Finding,
    FindingStatus,
    FixAttempt,
    FixResult,
    Intent,
    Narration,
    SessionState,
    SseType,
    VoiceIntent,
)
from app.main import Runtime, create_app
from app.orchestrator import Deps, Orchestrator, Recorded, sse_format

NOW = datetime(2026, 11, 7, tzinfo=UTC)


def _finding(i="f1") -> Finding:
    return Finding(id=i, session_id="h1", title="Sky stays red under invulnerability",
                   location="E3M1 start", steps=["idkfa", "iddqd"], expected="sky inverted",
                   actual="sky red", reported_at=NOW)  # fmt: skip


class FakeExplorer:
    def __init__(self, orch_ref, block=False):
        self.ref, self.block, self.sent, self.stopped = orch_ref, block, [], threading.Event()

    def start(self, task):
        return "h1", "https://share/h1"

    def follow(self, on_action):
        on_action(AgentAction(session_id="h1", step=0, ts=NOW, t_session_s=1.0,
                              kind="key_press", keys=["up"], description="walk"))  # fmt: skip
        if not self.sent:
            self.ref[0].on_finding(_finding())
        if self.block:
            self.stopped.wait(30)

    def send(self, m):
        self.sent.append(m)

    def stop(self):
        self.stopped.set()


def _orch(tmp_path, verified=True, block=False, fix_result=FixResult.fixed):
    ref = []

    def verify(f, actions):
        assert actions and actions[0].keys == ["up"]
        st = FindingStatus.verified if verified else FindingStatus.suspected
        return f.model_copy(update={"status": st, "known_bug_ref": "KB3" if verified else None})

    def fix(f, update):
        a = FixAttempt(id="x1", finding_id=f.id, devin_session_id="d1", started_at=NOW,
                       result=FixResult.merged)  # fmt: skip
        update(a)
        return a.model_copy(update={"result": fix_result})

    def narrate(f, out):
        return Narration(finding_id=f.id, text="Look at the sky.", audio_path=str(out / "a.mp3"))

    o = Orchestrator(Deps(FakeExplorer(ref, block), verify, narrate, fix), tmp_path, rounds=2,
                     approval_timeout_s=5)  # fmt: skip
    ref.append(o)
    return o


def _states(o):
    return [e.data["state"] for e in o.bus.events if e.type == SseType.session_state]


def _wait(cond, s=5.0):
    end = time.monotonic() + s
    while time.monotonic() < end and not cond():
        time.sleep(0.05)
    assert cond()


def test_full_loop_publishes_every_state(tmp_path):
    o = _orch(tmp_path)
    o.start()
    _wait(lambda: o.info.state == SessionState.awaiting_approval)
    o.intent(VoiceIntent(intent=Intent.fix, source="button"))
    o._thread.join(5)
    assert _states(o) == ["exploring", "exploring", "verifying", "presenting",
                          "awaiting_approval", "fixing", "reverifying", "exploring",
                          "debriefing", "done"]  # fmt: skip
    assert o.store.findings["f1"].status == FindingStatus.fixed
    assert o.store.fixes["x1"].result == FixResult.fixed
    assert o.store.narrations[0].text == "Look at the sky."
    assert o.deps.explorer.sent  # follow-up to the same H session, no new session
    assert (tmp_path / "events.jsonl").read_text().count("\n") == len(o.bus.events)


def test_skip_does_not_fix_and_unverified_is_not_presented(tmp_path):
    o = _orch(tmp_path)
    o.start()
    _wait(lambda: o.info.state == SessionState.awaiting_approval)
    o.intent(VoiceIntent(intent=Intent.skip, source="button"))
    o._thread.join(5)
    assert "fixing" not in _states(o) and not o.store.fixes
    o2 = _orch(tmp_path / "b", verified=False)
    o2.start()
    o2._thread.join(5)
    assert "presenting" not in _states(o2) and _states(o2)[-1] == "done"


def test_stop_cancels_h_within_5s(tmp_path):
    o = _orch(tmp_path, block=True)
    o.start()
    _wait(lambda: len(o.store.actions) == 1)
    t0 = time.monotonic()
    o.stop()
    assert time.monotonic() - t0 < 5 and o.deps.explorer.stopped.is_set()
    o._thread.join(5)
    assert o.info.state == SessionState.stopped and _states(o)[-1] == "stopped"


def test_recorded_replay_is_marked_not_live(tmp_path):
    o = _orch(tmp_path)
    o.start()
    _wait(lambda: o.info.state == SessionState.awaiting_approval)
    o.intent(VoiceIntent(intent=Intent.fix, source="button"))
    o._thread.join(5)
    r = Recorded(tmp_path / "events.jsonl", tmp_path / "r", pace=0)
    r.start()
    r._thread.join(5)
    assert r.store.session.live is False and r.store.session.state == SessionState.done
    assert r.store.findings["f1"].status == FindingStatus.fixed


def test_api_snapshot_intent_stop_and_media(tmp_path):
    rt = Runtime(tmp_path)
    rt.factory = lambda out: _orch(out)
    c = TestClient(create_app(rt))
    assert c.get("/api/session").json()["state"] == "idle"
    assert c.post("/api/session/start", json={"mode": "live"}).json()["live"] is True
    _wait(lambda: rt.current.info.state == SessionState.awaiting_approval)
    assert c.get("/api/findings").json()[0]["status"] == "presented"
    assert c.post("/api/intent", json={"intent": "fix", "source": "button"}).status_code == 200
    rt.current._thread.join(5)
    assert c.get("/api/session").json()["state"] == "done"
    assert c.get("/api/fixes").json()[0]["result"] == "fixed"
    assert c.post("/api/stop", json={}).status_code == 200
    (tmp_path / "clip.mp4").write_bytes(b"x")
    assert c.get(f"/media{tmp_path}/clip.mp4").content == b"x"
    assert c.get("/media/etc/passwd").status_code == 404
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / "keys.txt").write_text("SECRET=1")
    assert c.get(f"/media{tmp_path}/.env").status_code == 404
    assert c.get(f"/media{tmp_path}/keys.txt").status_code == 404
    assert c.post("/api/stop").status_code == 415  # bodyless cross-site POST
    form = {"content-type": "text/plain"}
    assert c.post("/api/stop", content="{}", headers=form).status_code == 415


def test_control_token(tmp_path, monkeypatch):
    monkeypatch.setenv("P2_CONTROL_TOKEN", "t0k")
    c = TestClient(create_app(Runtime(tmp_path)))
    assert c.post("/api/stop", json={}).status_code == 401
    assert c.post("/api/stop", json={}, headers={"X-P2-Token": "t0k"}).status_code == 200
    assert c.get("/api/plans").status_code == 200  # T18 billing router mounted


def test_sse_format():
    o = Orchestrator.__new__(Orchestrator)
    from app.orchestrator import Bus

    ev = Bus().publish(SseType.error, {"message": "m", "where": "w"}, "s")
    txt = sse_format(ev)
    assert txt.startswith(f"id: {ev.id}\nevent: error\ndata: {{") and txt.endswith("\n\n")
    assert Bus().publish(SseType.error, {}, "s").id > ev.id  # ids grow across sessions
    assert o is not None


def test_debrief_and_placement_run_at_the_end(tmp_path):
    from app.contracts import PlacementSpot

    o = _orch(tmp_path)
    seen = {}

    def debrief(run_dir):
        seen["summary"] = json.loads((run_dir / "tester_run.json").read_text())
        return {"session_id": "h1", "notes": []}

    def placement(run_dir):
        return [PlacementSpot(id="spot-1", session_id="h1", name="red wall", surface="wall",
                              location="start", screen_time_s=10, visibility=0.8)]  # fmt: skip

    o.deps.debrief, o.deps.placement = debrief, placement
    o.start()
    _wait(lambda: o.info.state == SessionState.awaiting_approval)
    o.intent(VoiceIntent(intent=Intent.skip, source="button"))
    o._thread.join(5)
    assert seen["summary"]["session_id"] == "h1"
    assert seen["summary"]["findings"][0]["id"] == "f1"
    assert o.store.debrief == {"session_id": "h1", "notes": []}
    assert o.store.placement[0]["name"] == "red wall"
    assert _states(o)[-2:] == ["debriefing", "done"]


def test_debrief_failure_does_not_fail_the_session(tmp_path):
    o = _orch(tmp_path)

    def boom(run_dir):
        raise RuntimeError("linkup down")

    o.deps.debrief = o.deps.placement = boom
    o.start()
    _wait(lambda: o.info.state == SessionState.awaiting_approval)
    o.intent(VoiceIntent(intent=Intent.skip, source="button"))
    o._thread.join(5)
    assert o.info.state == SessionState.done
    errs = [e.data["where"] for e in o.bus.events if e.type == SseType.error]
    assert errs == ["debrief", "placement"]


def test_control_token_from_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("P2_CONTROL_TOKEN", "")  # restored (unset) after the test
    monkeypatch.delenv("P2_CONTROL_TOKEN")
    (tmp_path / ".env").write_text("P2_CONTROL_TOKEN=fromfile\n")
    monkeypatch.chdir(tmp_path)
    c = TestClient(create_app(Runtime(tmp_path)))
    assert c.post("/api/stop", json={}).status_code == 401
    assert c.post("/api/stop", json={}, headers={"X-P2-Token": "fromfile"}).status_code == 200


def test_summary_is_written_without_insights_and_write_errors_are_not_fatal(tmp_path):
    o = _orch(tmp_path)
    o.deps.replay = {"speed": "step", "start": "tough"}
    o.start()
    _wait(lambda: o.info.state == SessionState.awaiting_approval)
    o.intent(VoiceIntent(intent=Intent.skip, source="button"))
    o._thread.join(5)
    summary = json.loads((tmp_path / "run" / "tester_run.json").read_text())
    assert summary["findings"] and summary["speed"] == "step" and summary["start"] == "tough"
    o2 = _orch(tmp_path / "b")
    o2.deps.run_dir = tmp_path / "file"
    o2.deps.run_dir.write_text("not a dir")
    o2.deps.debrief = lambda d: {"x": 1}
    o2.start()
    _wait(lambda: o2.info.state == SessionState.awaiting_approval)
    o2.intent(VoiceIntent(intent=Intent.skip, source="button"))
    o2._thread.join(5)
    assert o2.info.state == SessionState.done and o2.store.debrief is None


def test_stale_fix_intent_does_not_approve_a_later_finding(tmp_path):
    o = _orch(tmp_path)
    o.intent(VoiceIntent(intent=Intent.fix, source="voice"))  # said before any finding
    o.start()
    _wait(lambda: o.info.state == SessionState.awaiting_approval)
    time.sleep(0.5)
    assert o.info.state == SessionState.awaiting_approval
    o.intent(VoiceIntent(intent=Intent.skip, source="button"))
    o._thread.join(5)
    assert "fixing" not in _states(o) and not o.store.fixes
