"""Text to speech: ElevenLabs (team decision, replaces edge-tts from T01) with word timings.

`speak(text, out)` writes an mp3 and returns per-word start times, used to sync the clip.
Needs ELEVENLABS_API_KEY. Optional: ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # premade "George": calm, clear narrator
DEFAULT_MODEL = "eleven_flash_v2_5"  # cheapest per character, low latency


@dataclass(frozen=True)
class Speech:
    path: Path
    duration_s: float
    char_starts: list[float]  # start time of every character of the text, in seconds

    def time_of(self, text: str, offset: int) -> float:
        """Audio time where the character at `offset` of the spoken text starts."""
        if not self.char_starts:
            return 0.0
        return self.char_starts[min(max(offset, 0), len(self.char_starts) - 1)]


def speak(
    text: str,
    out: Path,
    voice: str | None = None,
    model: str | None = None,
    client: httpx.Client | None = None,
) -> Speech:
    key = os.environ["ELEVENLABS_API_KEY"]
    voice = voice or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE)
    body = {"text": text, "model_id": model or os.environ.get("ELEVENLABS_MODEL", DEFAULT_MODEL)}
    http = client or httpx.Client(timeout=60)
    r = http.post(
        f"{API}/text-to-speech/{voice}/with-timestamps",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": key},
        json=body,
    )
    r.raise_for_status()
    data = r.json()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment") or {}
    starts = [float(x) for x in al.get("character_start_times_seconds", [])]
    ends = [float(x) for x in al.get("character_end_times_seconds", [])]
    return Speech(out, max(ends, default=0.0), starts)
