"""Gladia real-time STT -> VoiceIntent.

    python -m voice.listen --mic             # default microphone (`pip install sounddevice`)
    python -m voice.listen --mic --ptt       # push-to-talk: Enter toggles sending audio
    python -m voice.listen --wav clip.wav    # stream a 16 kHz mono 16-bit WAV (repeatable check)

Each final transcript prints one JSON line `{"transcript": ..., "intent": VoiceIntent|null}`.
With `--post http://localhost:8000` the intent is also POSTed to /api/intent (T14).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import wave
from collections.abc import Callable, Iterable

import httpx

from app.contracts import VoiceIntent
from voice.intents import parse_intent

GLADIA_API = "https://api.gladia.io"
SAMPLE_RATE = 16000
CHUNK_MS = 100


def init_config(languages: list[str] | None = None) -> dict:
    return {
        "encoding": "wav/pcm",
        "sample_rate": SAMPLE_RATE,
        "bit_depth": 16,
        "channels": 1,
        "language_config": {"languages": languages or ["en", "fr"], "code_switching": True},
        "messages_config": {"receive_partial_transcripts": True},
    }


def start_session(
    api_key: str, languages: list[str] | None = None, http: httpx.Client | None = None
) -> dict:
    """POST /v2/live -> {"id", "url"} (the WebSocket URL carries its own token)."""
    http = http or httpx.Client(timeout=15)
    r = http.post(
        f"{GLADIA_API}/v2/live",
        headers={"x-gladia-key": api_key, "Content-Type": "application/json"},
        json=init_config(languages),
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Gladia init: HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def handle_message(raw: str | bytes) -> tuple[str, bool, str | None, float | None] | None:
    """Parse one WebSocket message: (text, is_final, language, confidence) for transcripts."""
    msg = json.loads(raw)
    if msg.get("type") != "transcript":
        return None
    data = msg.get("data") or {}
    utt = data.get("utterance") or {}
    text = (utt.get("text") or "").strip()
    if not text:
        return None
    return text, bool(data.get("is_final")), utt.get("language"), utt.get("confidence")


class Listener:
    """Streams audio chunks to Gladia and calls back on transcripts and intents."""

    def __init__(
        self,
        api_key: str,
        on_intent: Callable[[VoiceIntent], None],
        on_transcript: Callable[[str, bool, str | None], None] | None = None,
        languages: list[str] | None = None,
        finding_id: Callable[[], str | None] | None = None,
    ):
        self.api_key = api_key
        self.on_intent = on_intent
        self.on_transcript = on_transcript or (lambda text, final, lang: None)
        self.languages = languages
        self.finding_id = finding_id or (lambda: None)

    def dispatch(self, raw: str | bytes) -> VoiceIntent | None:
        parsed = handle_message(raw)
        if not parsed:
            return None
        text, final, lang, conf = parsed
        self.on_transcript(text, final, lang)
        if not final:
            return None
        intent = parse_intent(text, language=lang, confidence=conf, finding_id=self.finding_id())
        if intent:
            self.on_intent(intent)
        return intent

    def run(self, chunks: Iterable[bytes]) -> None:
        from websockets.sync.client import connect

        session = start_session(self.api_key, self.languages)
        with connect(session["url"]) as ws:
            reader = threading.Thread(target=self._read, args=(ws,), daemon=True)
            reader.start()
            for chunk in chunks:
                ws.send(chunk)
            ws.send(json.dumps({"type": "stop_recording"}))
            reader.join(timeout=30)

    def _read(self, ws) -> None:
        try:
            for raw in ws:
                try:
                    self.dispatch(raw)
                except Exception as e:  # one bad message or callback must not deafen the listener
                    print(f"voice: dropped message: {type(e).__name__}: {e}", file=sys.stderr)
        except Exception as e:  # connection closed mid-read
            print(f"gladia reader stopped: {type(e).__name__}", file=sys.stderr)


def wav_chunks(path: str, realtime: bool = True) -> Iterable[bytes]:
    with wave.open(path, "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise SystemExit(f"{path}: need 16 kHz mono 16-bit PCM WAV")
        n = SAMPLE_RATE * CHUNK_MS // 1000
        while frames := w.readframes(n):
            yield frames
            if realtime:
                time.sleep(CHUNK_MS / 1000)
    # trailing silence so endpointing closes the last utterance
    for _ in range(10):
        yield b"\x00\x00" * n
        if realtime:
            time.sleep(CHUNK_MS / 1000)


def mic_chunks(ptt: bool = False) -> Iterable[bytes]:
    import queue

    import sounddevice as sd  # local-only dependency (stage laptop)

    q: queue.Queue[bytes] = queue.Queue()
    talking = threading.Event()
    if not ptt:
        talking.set()
    else:

        def toggle() -> None:
            for _ in sys.stdin:
                talking.clear() if talking.is_set() else talking.set()
                print("PTT", "ON" if talking.is_set() else "OFF", file=sys.stderr)

        threading.Thread(target=toggle, daemon=True).start()
        print("push-to-talk: press Enter to start/stop talking", file=sys.stderr)
    silence = b"\x00\x00" * (SAMPLE_RATE * CHUNK_MS // 1000)

    def cb(indata, frames, t, status):  # noqa: ARG001
        q.put(bytes(indata) if talking.is_set() else silence)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=SAMPLE_RATE * CHUNK_MS // 1000,
        callback=cb,
    ):
        while True:
            yield q.get()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--mic", action="store_true")
    src.add_argument("--wav")
    ap.add_argument("--ptt", action="store_true", help="push-to-talk (Enter toggles)")
    ap.add_argument("--lang", action="append", help="expected language(s), default en+fr")
    ap.add_argument("--post", help="orchestrator base URL; POST each intent to /api/intent")
    args = ap.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    key = os.environ.get("GLADIA_API_KEY")
    if not key:
        print("missing env: GLADIA_API_KEY", file=sys.stderr)
        return 2

    def on_intent(intent: VoiceIntent) -> None:
        if args.post:
            r = httpx.post(
                f"{args.post.rstrip('/')}/api/intent", json=intent.model_dump(), timeout=5
            )
            if r.status_code >= 400:
                print(
                    f"voice: /api/intent rejected {intent.intent}: HTTP {r.status_code}",
                    file=sys.stderr,
                )

    def on_transcript(text: str, final: bool, lang: str | None) -> None:
        if final:
            intent = parse_intent(text, language=lang)
            out = {"transcript": text, "language": lang, "intent": intent and intent.model_dump()}
            print(json.dumps(out, ensure_ascii=False), flush=True)

    listener = Listener(key, on_intent, on_transcript, languages=args.lang)
    chunks = mic_chunks(args.ptt) if args.mic else wav_chunks(args.wav)
    try:
        listener.run(chunks)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
