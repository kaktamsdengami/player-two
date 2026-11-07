import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.contracts import EventMatch, GameEvent, LogSignature
from launcher import capture
from launcher.config import LauncherConfig, Speed
from launcher.game import Game
from launcher.log import EventLog, signature_hits
from launcher.window import Window

LOGS = Path(__file__).parent / "fixtures" / "qa_logs"
KB1_KB2 = LOGS / "kb1_kb2_e1m1.jsonl"  # medikit at health 20, then 30 damage (QA script)
KB3 = LOGS / "kb3_e3m1.jsonl"  # invulnerability on E3M1

LOW_HEALTH_MEDIKIT = LogSignature(
    description="medikit picked up below 25 health shows the normal message",
    all_of=[
        EventMatch(
            type="pickup",
            where={
                "data.sprite": "MEDI",
                "data.health_before": {"lt": 25},
                "data.message": "Took a large health refill.",
            },
        )
    ],
)
NO_OUCH = LogSignature(
    description="big hit without the ouch face",
    all_of=[
        EventMatch(type="damage", where={"data.amount": {"gt": 20}}),
        EventMatch(type="face", where={"data.health_delta": {"lt": -20}}),
    ],
    none_of=[EventMatch(type="face", where={"data.kind": "ouch"})],
    within_tics=5,
)
SKY = LogSignature(
    description="sky drawn without the invulnerability colormap",
    all_of=[EventMatch(type="render", where={"data.flag": "sky_ignores_colormap"})],
)


def test_signatures_on_recorded_logs():
    medikit, sky = EventLog(KB1_KB2), EventLog(KB3)
    hit = medikit.happened(LOW_HEALTH_MEDIKIT)
    assert hit and hit[0].tic == 3 and hit[0].data["health_before"] == 20
    dmg, face = medikit.happened(NO_OUCH)
    assert (dmg.tic, face.tic, face.data["kind"]) == (72, 73, "rampage")
    assert medikit.happened(SKY) is None
    assert sky.happened(SKY) and sky.happened(LOW_HEALTH_MEDIKIT) is None


def test_happened_since_game_time():
    log = EventLog(KB1_KB2)
    pickup_t = log.find(EventMatch(type="pickup"))[0].t
    assert log.happened(LOW_HEALTH_MEDIKIT, since_t=pickup_t)
    assert log.happened(LOW_HEALTH_MEDIKIT, since_t=pickup_t + 0.001) is None
    assert log.happened(NO_OUCH, since_t=pickup_t + 0.001)  # the hit comes later


def test_none_of_and_window():
    events = EventLog(KB1_KB2).since()
    ouch = NO_OUCH.model_copy(
        update={"none_of": [EventMatch(type="face", where={"data.kind": "rampage"})]}
    )
    assert signature_hits(ouch, events) is None
    far = NO_OUCH.model_copy(update={"within_tics": None, "none_of": []})
    assert signature_hits(far, events)
    tight = LogSignature(
        description="pickup and damage within 10 tics",
        all_of=[EventMatch(type="pickup"), EventMatch(type="damage")],
        within_tics=10,
    )
    assert signature_hits(tight, events) is None  # 69 tics apart


def test_ops():
    log = EventLog(KB1_KB2)
    assert log.find(EventMatch(type="face", where={"data.kind": {"in": ["rampage", "ouch"]}}))
    assert log.find(EventMatch(type="pickup", where={"actor.type": {"ne": "MISC11"}})) == []
    assert log.find(EventMatch(type="pickup", where={"data.nope": {"exists": False}}))
    assert log.find(EventMatch(type="pickup", where={"player.health": {"ge": 45, "le": 45}}))


def test_tail_reads_only_complete_lines(tmp_path):
    lines = KB1_KB2.read_text().splitlines(keepends=True)
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    assert log.poll() == []  # not written yet
    path.write_text("".join(lines[:5]) + lines[5][:30])  # game is mid-write
    assert len(log.poll()) == 5
    with path.open("a") as f:
        f.write(lines[5][30:] + "".join(lines[6:]))
    assert len(log.poll()) == len(lines) - 5
    assert [e.tic for e in log.tail(2)] == [json.loads(x)["tic"] for x in lines[-2:]]
    assert "damage" in [e.type for e in log.since(tic=72)]
    assert all(e.tic >= 72 for e in log.since(tic=72))


def test_speed_parse():
    assert Speed.parse("normal").args() == []
    assert Speed.parse("step").args() == ["-qa-tics", "8"]
    for spec in ("step:12", "slow:4", "normal"):
        assert Speed.parse(spec).spec() == spec
    assert Speed.parse("step").spec() == "step:8"
    assert Speed.parse("step:10").args() == ["-qa-tics", "10"]
    assert Speed.parse("slow:4").args() == ["-qa-slowmo", "4"] and Speed.parse("slow:4").factor == 4
    with pytest.raises(ValueError):
        Speed.parse("fast")


def _cfg(tmp_path, **kw):
    return LauncherConfig(
        fork_dir=tmp_path, exe=tmp_path / "doom", iwad=tmp_path / "f.wad", runs_dir=tmp_path, **kw
    )


def test_game_command(tmp_path):
    game = Game(_cfg(tmp_path), tmp_path / "run")
    cmd = game.command(3, 1, Speed(), script=tmp_path / "s.txt")
    joined = " ".join(cmd)
    assert "-warp 3 1" in joined and "-skill 3" in joined and "-qa-tics 8" in joined
    assert "-nomouse" in cmd and "-window" in cmd and "-nosound" in cmd
    assert cmd[cmd.index("-qa-log") + 1] == str(game.log_path)
    assert cmd[cmd.index("-qa-script") + 1] == str(tmp_path / "s.txt")
    extra = Path(cmd[cmd.index("-extraconfig") + 1]).read_text()
    assert 'window_position "0,0"' in extra and "window_width 1066" in extra
    assert "show_endoom 0" in extra and "-record" not in cmd
    rec = game.command(3, 1, Speed(), record=tmp_path / "run" / "agent")
    assert rec[rec.index("-record") + 1] == str(tmp_path / "run" / "agent")
    full = Game(_cfg(tmp_path, fullscreen=True, sound=True), tmp_path / "run2")
    cmd = full.command(1, 7, Speed.parse("slow:2"))
    assert "-fullscreen" in cmd and "-nosound" not in cmd and "-qa-slowmo" in cmd


def test_capture_args():
    win = Window(1, "Freedoom: Phase 1 - Chocolate Doom 3.1.1", 880, 721, 801, 600)
    linux = capture.grab_input(win, 30, windows=False)
    assert linux[linux.index("-video_size") + 1] == "800x600"
    assert linux[-1].endswith("+880,721")
    win32 = capture.grab_input(win, 30, windows=True)
    assert "gdigrab" in win32 and win32[-1] == "desktop" and "-offset_y" in win32
    assert capture.clip_window(3.2, 100.0, 101.0, 5, 5) == (0.0, pytest.approx(7.2))
    assert capture.clip_window(20.0, 100.0, 101.0) == (14.0, 24.0)
    args = capture.cut_args(
        Path("r.mp4"), 1, 4, Path("c.mp4"), speed=4, label="RECORDED · 4× speed"
    )
    vf = args[args.index("-vf") + 1]
    assert vf.startswith("setpts=PTS/4,drawtext=") and "RECORDED · 4× speed" in vf
    assert capture.label_text(4) == "RECORDED · 4× speed" and capture.label_text(1) == "RECORDED"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_cut_clip_real(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
         "-t", "4", "-pix_fmt", "yuv420p", str(src)],
        check=True,
    )  # fmt: skip
    out = capture.cut_clip(src, 1, 3, tmp_path / "c.mp4", speed=2, label="RECORDED · 2× speed")
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert float(dur) == pytest.approx(1.0, abs=0.25)


def _ev(tic: int, type_: str, **data) -> GameEvent:
    return GameEvent.model_validate({"tic": tic, "t": tic / 35, "type": type_, "data": data})


def test_signature_window_is_order_independent():
    sig = LogSignature(
        description="a and b close together",
        all_of=[EventMatch(type="a"), EventMatch(type="b")],
        within_tics=20,
    )
    hits = signature_hits(sig, [_ev(10, "b"), _ev(15, "a")])
    assert hits is not None and [e.type for e in hits] == ["a", "b"]
    assert signature_hits(sig, [_ev(10, "b"), _ev(40, "a")]) is None


def test_open_none_of_window_is_not_proof_yet(tmp_path):
    sig = LogSignature(
        description="a without c nearby",
        all_of=[EventMatch(type="a")],
        none_of=[EventMatch(type="c")],
        within_tics=35,
    )
    assert signature_hits(sig, [_ev(10, "a"), _ev(20, "x")], until_tic=20) is None
    assert signature_hits(sig, [_ev(10, "a"), _ev(50, "x")], until_tic=50) is not None
    assert signature_hits(sig, [_ev(10, "a"), _ev(30, "c")]) is None
    log_path = tmp_path / "events.jsonl"
    log_path.write_text(
        _ev(10, "a").model_dump_json() + "\n" + _ev(20, "x").model_dump_json() + "\n"
    )
    assert EventLog(log_path).wait_for(sig, timeout=0) is None


@pytest.mark.parametrize(("mode", "line"), [("god", "1 god"), ("tough", "1 health 999")])
def test_start_mode_script(tmp_path, mode, line):
    game = Game(_cfg(tmp_path, start=mode), tmp_path / "run")
    cmd = game.command(3, 1, Speed())
    assert Path(cmd[cmd.index("-qa-script") + 1]).read_text().strip() == line
    replay = game.command(3, 1, Speed(), script=tmp_path / "kb.txt")
    assert replay[replay.index("-qa-script") + 1] == str(tmp_path / "kb.txt")


def test_start_mode_off_and_env(tmp_path, monkeypatch):
    assert "-qa-script" not in Game(_cfg(tmp_path, start="off"), tmp_path / "r").command(
        3, 1, Speed()
    )
    monkeypatch.setenv("P2_GOD", "Tough")
    assert LauncherConfig.from_env().start == "tough"
    monkeypatch.setenv("P2_GOD", "yes")
    with pytest.raises(ValueError):
        LauncherConfig.from_env()
