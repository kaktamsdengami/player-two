import json

from launcher.config import LauncherConfig
from launcher.game import Game
from launcher.replay import LABEL, command, replay_script


def _ev(tic, type_, **data):
    return {"tic": tic, "t": tic / 35, "map": "E3M1", "type": type_, "data": data}


def test_replay_script_types_cheats_again_after_the_start_state(tmp_path):
    (tmp_path / "qa_start.txt").write_text("1 god\n")
    events = [_ev(130, "key", key=107), _ev(124, "key", key=105), _ev(140, "player")]
    (tmp_path / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    out = replay_script(tmp_path, tmp_path / "s.txt").read_text().splitlines()
    assert out == ["1 god", "124 key 105", "130 key 107"]


def test_replay_script_without_start_or_keys(tmp_path):
    (tmp_path / "events.jsonl").write_text("")
    assert replay_script(tmp_path, tmp_path / "s.txt").read_text() == ""


def test_replay_command_plays_the_demo_at_game_speed(tmp_path):
    cfg = LauncherConfig(
        fork_dir=tmp_path, exe=tmp_path / "doom", iwad=tmp_path / "f.wad", runs_dir=tmp_path
    )
    game = Game(cfg, tmp_path / "replay")
    cmd = command(cfg, game, tmp_path / "agent.lmp", tmp_path / "s.txt")
    assert cmd[cmd.index("-playdemo") + 1] == str((tmp_path / "agent.lmp").resolve())
    assert "-qa-tics" not in cmd and "-warp" not in cmd and "-nosound" in cmd
    assert cmd[cmd.index("-qa-script") + 1] == str(tmp_path / "s.txt")
    assert "game speed" in LABEL


def test_replay_script_prefers_the_demo_rounds_log(tmp_path):
    (tmp_path / "events.jsonl").write_text(json.dumps(_ev(50, "key", key=120)) + "\n")
    (tmp_path / "agent_events.jsonl").write_text(json.dumps(_ev(9, "key", key=105)) + "\n")
    assert replay_script(tmp_path, tmp_path / "s.txt").read_text() == "9 key 105\n"
