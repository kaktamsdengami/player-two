import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agents import oracles
from agents.verifier import judge
from app.contracts import Finding, GameEvent

LOGS = Path(__file__).parent / "fixtures" / "qa_logs"
BUGS = {b.id: b for b in oracles.load_known_bugs()}


def _log(name: str) -> list[dict]:
    return [json.loads(x) for x in (LOGS / name).read_text().splitlines() if x.strip()]


def _events(rows: list[dict]) -> list[GameEvent]:
    return [GameEvent.model_validate(r) for r in rows]


def _proven(rows: list[dict]) -> set[str]:
    return {p.bug.id for p in oracles.proven(_events(rows), list(BUGS.values()))}


def _drop(rows, pred):
    return [r for r in rows if not pred(r)]


# Positive: the recorded QA-build logs (fork qa/ scripts). Negative: the same log edited to what a
# fixed build would write at that point.
E1M1, E3M1 = "kb1_kb2_e1m1.jsonl", "kb3_e3m1.jsonl"


def test_recorded_logs_prove_their_bugs():
    assert _proven(_log(E1M1)) == {"KB1", "KB2"}
    assert _proven(_log(E3M1)) == {"KB3", "KB4"}  # E3M1 line 582 is a real long-wall error


def test_kb1_negative_fixed_message():
    rows = _log(E1M1)
    for r in rows:
        if r["type"] == "pickup":
            r["data"]["message"] = "Took a large health refill. Never give up!"
    assert "KB1" not in _proven(rows)


def test_kb1_negative_not_low_health():
    rows = _log(E1M1)
    for r in rows:
        if r["type"] == "pickup":
            r["data"]["health_before"] = 60
    assert "KB1" not in _proven(rows)


def test_kb2_negative_ouch_face_shown():
    rows = _log(E1M1)
    dmg = next(r for r in rows if r["type"] == "damage")
    ouch = {**dmg, "tic": dmg["tic"] + 1, "type": "face",
            "data": {"index": 7, "kind": "ouch", "health_delta": -30}}  # fmt: skip
    assert "KB2" not in _proven(rows + [ouch])


def test_kb2_negative_small_hit():
    rows = _log(E1M1)
    for r in rows:
        if r["type"] == "damage":
            r["data"]["amount"] = 10
    assert "KB2" not in _proven(rows)


def test_kb3_negative_sky_uses_colormap():
    rows = _drop(_log(E3M1), lambda r: r["data"].get("flag") == "sky_ignores_colormap")
    assert "KB3" not in _proven(rows)


def test_kb3_negative_no_invulnerability():
    rows = _drop(_log(E3M1), lambda r: r["type"] == "powerup")
    assert "KB3" not in _proven(rows)


def test_kb4_negative_short_wall():
    # E1M1 logs a 512-unit wall with 0.5 % error: below the long-wall threshold.
    assert "KB4" not in _proven(_log(E1M1))
    rows = _drop(_log(E3M1), lambda r: r["data"].get("flag") == "wall_distance_error")
    assert "KB4" not in _proven(rows)


def _finding(title, expected, actual):
    return Finding(
        id="F1", session_id="s", title=title, location="E3M1 start", steps=["start"],
        expected=expected, actual=actual, reported_at=datetime.now(UTC),
    )  # fmt: skip


SKY = _finding(
    "Red sky ignores the invulnerability effect",
    "Everything, including the sky, turns grey/inverted while invulnerable",
    "Walls and floor went white-grey but the sky stayed red",
)


def test_judge_matches_the_bug_the_tester_saw():
    v = judge(SKY, _events(_log(E3M1)), list(BUGS.values()))
    assert {p.bug.id for p in v.proofs} == {"KB3", "KB4"}
    assert v.matched.id == "KB3"
    assert SKY.status == "verified" and SKY.known_bug_ref == "KB3"
    assert any(e.type == "render" for e in SKY.evidence.log_excerpt)


@pytest.mark.parametrize(
    ("finding", "log", "ref"),
    [
        (_finding("Status bar face does not react to a big hit",
                  "A shocked ouch face after losing 30 health at once",
                  "The face stayed normal / rampage"), E1M1, "KB2"),
        (_finding("Medikit message ignores low health",
                  "The special 'never give up' medikit message when health is very low",
                  "Only the plain 'Took a large health refill.' message"), E1M1, "KB1"),
        (_finding("Long wall bends when turning",
                  "Wall edges stay straight", "The long wall wobbles and jitters"), E3M1, "KB4"),
    ],
)  # fmt: skip
def test_judge_each_bug(finding, log, ref):
    assert judge(finding, _events(_log(log)), list(BUGS.values())).matched.id == ref


def test_unproven_or_unrelated_stays_suspected():
    door = _finding("Door clips through ceiling", "Door opens cleanly", "Door texture tears")
    v = judge(door, _events(_log(E3M1)), list(BUGS.values()))
    assert v.matched is None and door.status == "suspected" and door.known_bug_ref is None
    clean = _drop(_log(E3M1), lambda r: r["type"] == "render")
    v = judge(SKY, _events(clean), list(BUGS.values()))
    assert v.proofs == [] and SKY.status == "suspected" and SKY.known_bug_ref is None


def test_new_bug_seen_again_by_h_replay_is_verified_new():
    door = _finding("Door clips through ceiling", "Door opens cleanly", "Door texture tears")
    judge(door, _events(_log(E3M1)), list(BUGS.values()), seen_by_h=True)
    assert door.status == "verified" and door.known_bug_ref is None


def test_replay_holds_for_recorded_duration():
    from datetime import UTC, datetime

    from agents.verifier import Verifier
    from app.contracts import AgentAction

    calls = []
    v = Verifier.__new__(Verifier)
    v.press, v.step_wait_s = (lambda keys, **kw: calls.append((keys, kw))), 0.0
    now = datetime.now(UTC)
    acts = [
        AgentAction(
            session_id="s",
            step=1,
            ts=now,
            t_session_s=1,
            kind="key_hold",
            keys=["up"],
            duration_ms=900,
        ),
        AgentAction(
            session_id="s", step=2, ts=now, t_session_s=2, kind="key_press", keys=["space"]
        ),
        AgentAction(session_id="s", step=3, ts=now, t_session_s=9, kind="key_press", keys=["left"]),
    ]
    v.replay_actions(acts, until_s=5)
    assert calls == [(["up"], {"hold_s": 0.9}), (["space"], {})]


def test_verifier_replays_the_tester_demo(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import launcher.replay
    from agents.verifier import Verifier

    (tmp_path / "agent.lmp").write_bytes(b"\0" * 20)
    log = tmp_path / "replay_events.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in _log(E3M1)))
    calls = []

    def fake_replay(cfg, run_dir, video=True):
        calls.append((run_dir, video))
        return {"events": str(log), "game_started_at": 0.0}

    monkeypatch.setattr(launcher.replay, "replay", fake_replay)
    v = Verifier(SimpleNamespace(cfg=None, run_dir=tmp_path), 3, 1, None, list(BUGS.values()),
                 record=False)  # fmt: skip
    f = SKY.model_copy(deep=True)
    verdict = v.verify(f, [], out_dir=tmp_path / "verify", demo=tmp_path)
    assert calls == [(tmp_path, False)]
    assert verdict.replay == "demo" and verdict.matched.id == "KB3"
    assert f.status == "verified"


def test_demo_verdict_ignores_events_after_the_report(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import launcher.replay
    from agents.verifier import Verifier

    rows = _log(E3M1)
    for r in rows:  # the power-up 100 tics later, past any signature window
        r["tic"] += 100
        r["t"] = (r.get("t") or 0) + 100 / 35
    (tmp_path / "agent.lmp").write_bytes(b"\0" * 20)
    (tmp_path / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(
        launcher.replay, "replay", lambda cfg, d, video=True: {"events": str(d / "events.jsonl")}
    )
    v = Verifier(SimpleNamespace(cfg=None, run_dir=tmp_path), 3, 1, None, list(BUGS.values()),
                 record=False)  # fmt: skip
    f = SKY.model_copy(deep=True)
    before = f.reported_at.timestamp() - 1.0  # reported 1 s after launch, ~65 tics before it
    verdict = v.verify(f, [], out_dir=tmp_path / "v", demo=tmp_path, demo_started_at=before)
    assert verdict.matched is None
    f = SKY.model_copy(deep=True)
    verdict = v.verify(f, [], out_dir=tmp_path / "v", demo=tmp_path, demo_started_at=0.0)
    assert verdict.matched.id == "KB3"
