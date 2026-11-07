"""Narration (T12): a verified Finding -> short spoken explanation + cues synced with its clip.

The clip (T08) is cut +-5 s around the proving event, so the bug moment sits at `bug_at_s` in the
clip. Cues map audio time -> clip time: context while the voice sets the scene, the bug moment
when it says what is wrong, the end of the clip when it asks to fix it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from app.contracts import Finding, Narration, NarrationCue
from voice.tts import Speech, speak

STATUS_LINES = {
    "presented": "Found one. Want me to fix it?",
    "fixing": "Devin is on it. I'll replay the bug when the fix lands.",
    "fixed": "Fixed. Same steps, and the bug is gone.",
    "wontfix": "Okay, leaving that one as it is.",
    "still_broken": "The fix did not work: the bug is still there.",
}


def _sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip()).rstrip(".!?")
    return text[:1].upper() + text[1:] + "." if text else ""


def script(f: Finding) -> list[tuple[str, str]]:
    """(part, sentence) pairs: setup, bug, expected, ask."""
    where = f.location.strip().rstrip(".") or "here"
    return [
        ("setup", f"Look at this, in {where}."),
        ("bug", _sentence(f.actual)),
        (
            "expected",
            "It should be: " + _sentence(f.expected)[:1].lower() + _sentence(f.expected)[1:],
        ),
        ("ask", "Want me to fix it?"),
    ]


def cues_for(
    parts: list[tuple[str, str]], speech: Speech, clip_len_s: float, bug_at_s: float
) -> list[NarrationCue]:
    clip_at = {"setup": 0.0, "bug": bug_at_s, "expected": bug_at_s, "ask": clip_len_s}
    out, offset = [], 0
    for part, sentence in parts:
        out.append(
            NarrationCue(
                at_s=round(speech.time_of(sentence, offset), 3),
                clip_s=round(min(max(clip_at[part], 0.0), clip_len_s), 3),
                text=sentence,
            )
        )
        offset += len(sentence) + 1
    return out


def narrate(
    f: Finding,
    out_dir: Path,
    bug_at_s: float = 5.0,
    tts: Callable[[str, Path], Speech] = speak,
) -> Narration:
    parts = [(p, s) for p, s in script(f) if s]
    text = " ".join(s for _, s in parts)
    speech = tts(text, out_dir / f"{f.id}_narration.mp3")
    clip = f.evidence.clip
    clip_len = clip.end_s - clip.start_s if clip else 2 * bug_at_s
    return Narration(
        finding_id=f.id,
        text=text,
        audio_path=str(speech.path),
        duration_s=speech.duration_s,
        cues=cues_for(parts, speech, clip_len, min(bug_at_s, clip_len)),
    )


def status_line(status: str, out_dir: Path, finding_id: str | None = None, tts=speak) -> Narration:
    text = STATUS_LINES[status]
    speech = tts(text, out_dir / f"status_{status}.mp3")
    return Narration(
        finding_id=finding_id, text=text, audio_path=str(speech.path), duration_s=speech.duration_s
    )


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(prog="python -m voice.narrate")
    p.add_argument("finding_json", type=Path, help="a Finding (e.g. from verdicts.json)")
    p.add_argument("--out", type=Path, default=Path("recordings/narration"))
    a = p.parse_args()
    raw = json.loads(a.finding_json.read_text())
    raw = raw.get("finding_full", raw) if isinstance(raw, dict) else raw[0]["finding_full"]
    n = narrate(Finding.model_validate(raw), a.out)
    print(n.model_dump_json(indent=2))
