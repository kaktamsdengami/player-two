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

    answers = iter(["Look, a green armour!", "", "Nice shot!", "Keep going!"] * 5)

    def ask(shot, recent):
        clock.t += 1.0
        return next(answers)

    def say(text, out):
        clock.t += 0.5
        said.append(text)
        return out

    rows = c.run(grab, tmp_path, 30, ask, say, speaker, clock, clock.sleep)
    spoken = [r for r in rows if r["text"]]
    assert said[:2] == ["Look, a green armour!", "Nice shot!"]
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
