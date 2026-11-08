"""Gladia real-time STT -> VoiceIntent.

    python -m voice.listen --mic             # push-to-talk (default): Enter toggles sending audio
    python -m voice.listen --mic --open-mic  # always on: every transcript reaches the agent
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


def default_languages() -> list[str]:
    """P2_VOICE_LANGS (comma list), default English only: live code switching en+fr heard French
    commands as English nonsense on the stage mic."""
    return [x.strip() for x in os.environ.get("P2_VOICE_LANGS", "en").split(",") if x.strip()]


def init_config(languages: list[str] | None = None) -> dict:
    languages = languages or default_languages()
    return {
        "encoding": "wav/pcm",
        "sample_rate": SAMPLE_RATE,
        "bit_depth": 16,
        "channels": 1,
        "language_config": {"languages": languages, "code_switching": len(languages) > 1},
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
            for i, chunk in enumerate(chunks):
                ws.send(chunk)
                if i == 0:  # mic and Gladia are both up: phrases said before this are lost
                    print("voice: listening, speak now", file=sys.stderr, flush=True)
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


def sync_ptt(get: Callable[[], bool], talking: threading.Event) -> None:
    """Follow the dashboard's Talk button; the mic stays muted while the backend is unreachable."""
    try:
        on = get()
    except (httpx.HTTPError, ValueError):
        on = False
    if on != talking.is_set():
        talking.set() if on else talking.clear()
        print("PTT", "ON" if on else "OFF", file=sys.stderr)


def mic_chunks(talking: threading.Event) -> Iterable[bytes]:
    """Mic audio while `talking` is set, silence otherwise (keeps the Gladia stream alive)."""
    import queue

    import sounddevice as sd  # local-only dependency (stage laptop)

    q: queue.Queue[bytes] = queue.Queue()
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
    ap.add_argument("--ptt", action="store_true", help="push-to-talk (default with --mic)")
    ap.add_argument("--open-mic", action="store_true", help="no push-to-talk: room talk steers")
    ap.add_argument(
        "--lang", action="append", help="expected language(s), default $P2_VOICE_LANGS or en"
    )
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

    token = os.environ.get("P2_CONTROL_TOKEN")
    headers = {"X-P2-Token": token} if token else {}

    def post(path: str, body: dict) -> None:
        if not args.post:
            return
        try:
            r = httpx.post(f"{args.post.rstrip('/')}{path}", json=body, headers=headers, timeout=5)
        except httpx.HTTPError as e:
            print(f"voice: {path} failed: {e}", file=sys.stderr)
            return
        if r.status_code >= 400:
            print(f"voice: {path} rejected: HTTP {r.status_code}", file=sys.stderr)

    def on_intent(intent: VoiceIntent) -> None:
        post("/api/intent", intent.model_dump(mode="json"))

    def on_transcript(text: str, final: bool, lang: str | None) -> None:
        if final:
            post("/api/transcript", {"text": text, "final": True, "language": lang})
            intent = parse_intent(text, language=lang)
            out = {"transcript": text, "language": lang, "intent": intent and intent.model_dump()}
            print(json.dumps(out, ensure_ascii=False), flush=True)

    listener = Listener(key, on_intent, on_transcript, languages=args.lang)

    talking = threading.Event()
    if args.mic and args.open_mic:
        talking.set()
    elif args.mic and args.post:
        # The backend holds the push-to-talk state: the dashboard's Talk button and Enter here
        # both set it, and this listener follows it.
        url = f"{args.post.rstrip('/')}/api/ptt"

        def get() -> bool:
            return bool(httpx.get(url, headers=headers, timeout=2).json().get("on"))

        def follow() -> None:
            while True:
                sync_ptt(get, talking)
                time.sleep(0.25)

        def flip() -> None:
            post("/api/ptt", {"on": not talking.is_set()})

        threading.Thread(target=follow, daemon=True).start()
        print("push-to-talk: the dashboard's Talk button (or Enter here)", file=sys.stderr)
    elif args.mic:

        def flip() -> None:
            talking.clear() if talking.is_set() else talking.set()
            print("PTT", "ON" if talking.is_set() else "OFF", file=sys.stderr)

        print("push-to-talk: press Enter to start/stop talking", file=sys.stderr)
    if args.mic and not args.open_mic:

        def keys() -> None:
            for _ in sys.stdin:
                flip()

        threading.Thread(target=keys, daemon=True).start()
    chunks = mic_chunks(talking) if args.mic else wav_chunks(args.wav)
    try:
        listener.run(chunks)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
