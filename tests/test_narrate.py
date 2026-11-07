import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.contracts import Clip, Finding, Narration
from voice import narrate, tts


def _finding(clip=True):
    f = Finding(
        id="F1", session_id="s", title="Sky ignores invulnerability", location="E3M1, start area",
        steps=["start", "idbehold v"], expected="The sky turns grey with the rest of the view",
        actual="the walls go grey but the sky stays red", reported_at=datetime.now(UTC),
        status="verified", known_bug_ref="KB3",
    )  # fmt: skip
    if clip:
        f.evidence.clip = Clip(path="F1.mp4", start_s=0, end_s=10)
    return f


def _fake_tts(text: str, out: Path) -> tts.Speech:
    out.write_bytes(b"mp3")
    return tts.Speech(out, len(text) * 0.05, [i * 0.05 for i in range(len(text))])


def test_narration_text_and_cues(tmp_path):
    n = narrate.narrate(_finding(), tmp_path, bug_at_s=5.0, tts=_fake_tts)
    Narration.model_validate_json(n.model_dump_json())
    assert n.text.startswith("Look at this, in E3M1, start area.")
    assert "The walls go grey but the sky stays red." in n.text
    assert n.text.endswith("Want me to fix it?")
    assert [c.clip_s for c in n.cues] == [0.0, 5.0, 5.0, 10.0]
    ats = [c.at_s for c in n.cues]
    assert ats == sorted(ats) and ats[0] == 0.0
    # each cue starts exactly where its sentence starts in the spoken text
    for c in n.cues:
        assert c.at_s == round(n.text.index(c.text) * 0.05, 3)
    assert n.duration_s == len(n.text) * 0.05 and Path(n.audio_path).exists()


def test_cues_without_clip_use_default_window(tmp_path):
    n = narrate.narrate(_finding(clip=False), tmp_path, tts=_fake_tts)
    assert n.cues[-1].clip_s == 10.0


def test_status_lines(tmp_path):
    n = narrate.status_line("fixing", tmp_path, "F1", tts=_fake_tts)
    assert n.text.startswith("Devin is on it") and n.cues == [] and n.finding_id == "F1"


def test_elevenlabs_request_and_alignment(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"] = str(req.url), req.headers["xi-api-key"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={
            "audio_base64": base64.b64encode(b"ID3audio").decode(),
            "alignment": {"characters": list("Hi."),
                          "character_start_times_seconds": [0.0, 0.1, 0.2],
                          "character_end_times_seconds": [0.1, 0.2, 0.35]},
        })  # fmt: skip

    s = tts.speak(
        "Hi.", tmp_path / "a.mp3", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert "/text-to-speech/JBFqnCBsd6RMkjVDRZzb/with-timestamps" in seen["url"]
    assert seen["key"] == "test-key" and seen["body"]["model_id"] == "eleven_flash_v2_5"
    assert s.path.read_bytes() == b"ID3audio" and s.duration_s == 0.35
    assert s.time_of("Hi.", 2) == 0.2 and s.time_of("Hi.", 99) == 0.2
