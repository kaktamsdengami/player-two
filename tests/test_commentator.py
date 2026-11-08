import json
from pathlib import Path

from voice import commentator as c


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Quiet:
    def __init__(self):
        self.played = []

    def busy(self):
        return False

    def __call__(self, path):
        self.played.append(path)


def test_lines_are_rate_limited_logged_and_spoken(tmp_path):
    clock, speaker, said = Clock(), Quiet(), []

    def grab(p: Path) -> Path:
        p.write_bytes(b"png")
        clock.t += 0.2
        return p

    answers = iter(["Look, a green armour!", "", "Oh, a door over there.", "Keep going!"] * 5)

    def ask(shot, recent):
        clock.t += 1.0
        return next(answers)

    def say(text, out):
        clock.t += 0.5
        said.append(text)
        return out

    rows = c.run(grab, tmp_path, 30, ask, say, speaker, clock, clock.sleep)
    spoken = [r for r in rows if r["text"]]
    assert said[:2] == ["Look, a green armour!", "Oh, a door over there."]
    assert all(b["t"] - a["t"] >= c.MIN_GAP_S for a, b in zip(spoken, spoken[1:], strict=False))
    assert spoken[0]["latency_s"] == 1.7 and len(speaker.played) == len(said)
    assert (tmp_path / "comments.jsonl").read_text().count("\n") == len(rows)
    s = c.summary(rows)
    assert s["spoken"] == len(said) and s["skipped"] >= 1 and s["latency_median_s"] == 1.7


def test_waits_while_the_last_line_is_still_playing(tmp_path):
    clock = Clock()

    class Busy(Quiet):
        def busy(self):
            return True

    rows = c.run(lambda p: p, tmp_path, 5, lambda s, r: "hi", None, Busy(), clock, clock.sleep)
    assert rows == []


def test_prompt_fills_age_language_and_recent_lines():
    text = c.prompt(7, "French", ["Bravo!", "Une porte!"])
    assert "7 years old" in text and "Speak French" in text and "- Une porte!" in text
    assert "{" not in text


def test_speech_failure_keeps_going_and_silent_mode_is_not_spoken(tmp_path):
    clock = Clock()

    def grab(p):
        p.write_bytes(b"png")
        return p

    def broken(text, out):
        raise RuntimeError("tts down")

    rows = c.run(grab, tmp_path, 20, lambda s, r: "hello", broken, Quiet(), clock, clock.sleep)
    assert len(rows) >= 2 and all("speech failed" in r["error"] for r in rows)
    words = iter(["door", "imp", "key", "armour", "stairs", "exit", "ammo", "switch"] * 3)
    silent = c.run(grab, tmp_path / "s", 20, lambda s, r: next(words), None, Quiet(), clock,
                   clock.sleep)  # fmt: skip
    s = c.summary(silent)
    assert s["spoken"] == 0 and s["lines"] == len(silent) and s["latency_median_s"] is None


def test_reused_out_dir_keeps_numbering(tmp_path):
    clock = Clock()

    def grab(p):
        p.write_bytes(b"png")
        return p

    first = c.run(grab, tmp_path, 10, lambda s, r: "a", None, Quiet(), clock, clock.sleep)
    again = c.run(grab, tmp_path, 10, lambda s, r: "b", None, Quiet(), clock, clock.sleep)
    assert again[0]["i"] == len(first) and again[0]["shot"] == f"shot_{len(first):03d}.jpg"


class Resp:
    def __init__(self, status, content, finish="stop"):
        self.status_code = status
        self._j = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise c.httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return self._j


def test_comment_drops_the_thinking_switch_on_400_and_flags_empty_reasoning(tmp_path, monkeypatch):
    monkeypatch.setenv("HAI_API_KEY", "k")
    shot = tmp_path / "s.png"
    shot.write_bytes(b"png")
    bodies = []
    replies = iter([Resp(400, None), Resp(200, "<think>hm</think> Look, green armour!")])

    def post(url, headers, json, timeout):
        bodies.append(dict(json))
        return next(replies)

    monkeypatch.setattr(c, "_post", post)
    assert c.comment(shot, []) == "Look, green armour!"
    assert "chat_template_kwargs" in bodies[0] and "chat_template_kwargs" not in bodies[1]
    assert bodies[0]["max_tokens"] >= 400
    monkeypatch.setattr(c, "_post", lambda *a, **k: Resp(200, None, "length"))
    import pytest

    with pytest.raises(ValueError):
        c.comment(shot, [])


def test_grab_window_writes_a_small_jpeg(tmp_path, monkeypatch):
    from PIL import Image, ImageGrab

    monkeypatch.setattr(ImageGrab, "grab", lambda bbox, all_screens: Image.new("RGB", (1600, 1200)))
    win = type("W", (), {"x": 0, "y": 0, "width": 1600, "height": 1200})()
    out = c.grab_window(win, tmp_path / "s.jpg")
    assert Image.open(out).size == (c.SHOT_W, c.SHOT_W * 3 // 4)


def test_a_line_about_a_stale_frame_is_dropped(tmp_path):
    clock = Clock()
    quiet = Quiet()

    def slow_ask(shot, recent):
        clock.t += c.MAX_AGE_S + 1
        return "hi"

    def grab(p):
        p.write_bytes(b"jpg")
        return p

    rows = c.run(grab, tmp_path, 5, slow_ask, lambda t, p: p, quiet, clock, clock.sleep)
    assert (
        not quiet.played and rows[0]["error"].startswith("dropped") and "latency_s" not in rows[0]
    )


def test_prompt_knows_it_is_doom_and_the_level():
    text = c.prompt(8, "English", [], "E1M1")
    assert "Doom" in text and "Level: E1M1" in text and "Space" in text
    assert "guess it from the screen" in c.prompt(8, "English", [])


def test_stream_voice_pipes_chunks_to_the_player_and_the_file(tmp_path, monkeypatch):
    import os
    import stat

    player = tmp_path / "player"
    got = tmp_path / "got.mp3"
    player.write_text(f"#!/bin/sh\ncat > {got}\n")
    player.chmod(player.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    v = c.StreamVoice()
    v.exe = str(player)
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return c.httpx.Response(200, content=b"ID3" + b"x" * 5000)

    v.http = c.httpx.Client(transport=c.httpx.MockTransport(handler))
    out = v.say("Press Space!", tmp_path / "say.mp3")
    v.feeder.join(5)
    v.proc.wait(5)
    assert "/stream" in seen["url"] and not v.busy()
    assert out.read_bytes() == got.read_bytes() == b"ID3" + b"x" * 5000
    assert os.path.getsize(out) == 5003


def test_what_the_child_says_is_answered_right_away(tmp_path):
    clock, quiet, asked = Clock(), Quiet(), []
    heard = []

    def ask(shot, recent, question=""):
        asked.append(question)
        if len(asked) == 1:
            heard.append("how do I open this door?")  # said just after the first line
        return "answer" if question else "line"

    def grab(p):
        p.write_bytes(b"jpg")
        return p

    rows = c.run(grab, tmp_path, 3, ask, lambda t, p: p, quiet, clock, clock.sleep, heard=heard)
    assert asked[:2] == ["", "how do I open this door?"]  # no MIN_GAP_S wait for an answer
    assert rows[1]["heard"] == "how do I open this door?" and not heard
    assert '"how do I open this door?"' in c.prompt(
        8, "English", [], question="how do I open this door?"
    )


def test_the_run_ends_when_the_game_window_is_gone(tmp_path):
    clock, quiet = Clock(), Quiet()

    def grab(p):
        if clock.t > 10:
            raise c.GameClosed("Chocolate Doom")
        p.write_bytes(b"jpg")
        return p

    rows = c.run(grab, tmp_path, 1800, lambda s, r: "hi", lambda t, p: p, quiet, clock, clock.sleep)
    assert 1 <= len(rows) <= 3 and clock.t < 30  # not 30 minutes of polling


def test_an_unanswered_question_is_asked_once_more(tmp_path):
    clock, quiet, asked, heard = Clock(), Quiet(), [], ["where is the key?"]

    def ask(shot, recent, question=""):
        asked.append(question)
        if len(asked) <= 2:
            raise ValueError("no line")
        return "line"

    def grab(p):
        p.write_bytes(b"jpg")
        return p

    c.run(grab, tmp_path, 20, ask, lambda t, p: p, quiet, clock, clock.sleep, heard=heard)
    assert asked[:3] == ["where is the key?", "where is the key?", ""]  # retried once, not forever


def test_the_buddy_does_not_repeat_itself_or_talk_over_the_child(tmp_path):
    assert (
        c.similar("Walk up to that door and press Space!", "walk up to the door, press space")
        >= c.SAME
    )
    assert c.similar("Oh, a door over there.", "Grab that medikit on the left") < c.SAME
    assert c.similar("Grab that medikit on the left!", "Grab that medikit on the right!") < c.SAME
    clock, quiet = Clock(), Quiet()

    def grab(p):
        p.write_bytes(b"jpg")
        return p

    def ask(shot, recent):
        return "Walk up to that door and press Space!"

    rows = c.run(grab, tmp_path, 60, ask, lambda t, p: p, quiet, clock, clock.sleep,
                 child_speaking=lambda: 5 < clock.t < 40)  # fmt: skip
    assert len(quiet.played) == 1  # the same tip again is not spoken
    assert rows[1]["t"] >= 40 and rows[1]["repeat"] and not rows[1]["text"]


class Talking(Quiet):
    def __init__(self):
        super().__init__()
        self.on = True

    def busy(self):
        return self.on

    def stop(self):
        self.on = False


def test_the_child_cuts_the_buddy_off_but_its_own_echo_does_not():
    heard, speaker, at = [], Talking(), [0.0]
    on = c.ears(heard, speaker, ["Walk up to that door and press Space!"], at)
    on("walk up to that door", False, "en")  # the buddy heard through the speakers
    assert speaker.on and not heard and at[0] == 0.0
    on("wait how do", False, "en")
    assert not speaker.on and at[0] > 0  # cut off on the first words, before the final
    on("wait how do I open it", True, "en")
    assert heard == ["wait how do I open it"]
    on("Help", False, "en")  # one partial word: maybe noise
    on("Help!", True, "en")
    assert heard[-1] == "Help!"


def test_stream_voice_stop_kills_the_player(tmp_path, monkeypatch):
    import stat

    player = tmp_path / "player"
    player.write_text("#!/bin/sh\ncat > /dev/null; sleep 30\n")
    player.chmod(player.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    v = c.StreamVoice()
    v.exe = str(player)
    v.http = c.httpx.Client(
        transport=c.httpx.MockTransport(lambda r: c.httpx.Response(200, content=b"x" * 100))
    )
    v.say("hi", tmp_path / "say.mp3")
    v.feeder.join(5)
    assert v.busy()
    v.stop()
    assert not v.busy()  # at once, even if the download were still stalled
    v.proc.wait(5)


def test_the_buddy_keeps_it_short_and_remembers_the_talk():
    long = (
        "Hi there! I'm doing super well, thanks for asking! I'm really excited to play Doom"
        " with you. Ready?"
    )
    assert c.trim(long, 12) == "Hi there! I'm doing super well, thanks for asking!"
    assert c.trim("One very long sentence " * 10, 5).startswith("One")
    p = c.prompt(8, "English", [], "E1M1", "What did I ask first?", ["Child: Hi Pixel", "You: Hi!"])
    assert p.index("Child: Hi Pixel") < p.index('"What did I ask first?"')


def test_hello_and_goodbye_are_spoken_and_remembered(tmp_path):
    said, recent = [], []

    class Quiet:
        def busy(self):
            return False

        def __call__(self, path):
            said.append(path)

    c.greet(c.HELLO, lambda text, path: path, Quiet(), tmp_path / "hello.mp3", recent)
    assert said == [tmp_path / "hello.mp3"] and recent == [c.HELLO]
    c.greet(c.BYE, None, Quiet(), tmp_path / "bye.mp3", recent)  # --no-voice: silent
    assert recent == [c.HELLO]


def test_a_blank_kid_voice_means_the_default(monkeypatch):
    monkeypatch.setattr(c, "_env", lambda: None)
    monkeypatch.setenv("P2_KID_VOICE", "")
    assert c.kid_voice() == c.KID_VOICE
    monkeypatch.setenv("P2_KID_VOICE", "abc")
    assert c.kid_voice() == "abc"


def test_bot_phrases_are_never_said_and_names_are_remembered():
    assert c.BOT.search("Awesome! Let's keep going!")
    assert not c.BOT.search("hmm, I think the door is on the left")
    chat = [f"line {i}" for i in range(100)]
    kept = c.memory(chat)
    assert kept[:6] == chat[:6] and kept[-1] == "line 99" and len(kept) == c.CHAT + 7


def test_tts_text_has_no_ad_exclamations_and_openai_engine(monkeypatch):
    assert c.spoken("Hey Dmitry! Nice to meet you!!") == "Hey Dmitry. Nice to meet you."
    assert c.spoken("Ready? Go!") == "Ready? Go."
    monkeypatch.setattr(c, "_env", lambda: None)
    monkeypatch.setenv("P2_KID_TTS", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("P2_KID_VOICE", raising=False)
    v = c.StreamVoice()
    v.exe = "ffplay"
    req = v.request("hi")
    body = json.loads(req.content)
    assert req.url == c.StreamVoice.OPENAI_URL and body["voice"] == "coral"
    assert body["instructions"] == c.CALM and body["model"] == "gpt-4o-mini-tts"
