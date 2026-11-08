"""Kid mode (T21): a friendly buddy watches the game window and talks to the child.

Every ~3 s: a small JPEG of the window (Pillow) -> the fast H vision model writes one short line ->
ElevenLabs speaks it. It never talks over itself: a new line waits until the last one has been
played and `MIN_GAP_S` has passed. Each line is logged with its latency to `<out>/comments.jsonl`.

    python -m voice.commentator --window "Chocolate Doom" --minutes 2 --age 8
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

MODELS_URL = "https://api.hcompany.ai/v1/chat/completions"
MODEL = "holo4-35b-a3b"  # H's fastest vision model
PROMPT = Path(__file__).resolve().parent.parent / "agents" / "prompts" / "kid.md"
EVERY_S = 3.0
MIN_GAP_S = 6.0
RECENT = 4
GONE_S = 30.0  # the window missing this long = the game was closed, not minimised
MAX_AGE_S = 3.0  # a line about a frame older than this is dropped, not said
_http: httpx.Client | None = None


def _post(url: str, headers: dict, json: dict, timeout: float) -> httpx.Response:
    global _http
    _http = _http or httpx.Client()  # one TLS connection for the whole run
    return _http.post(url, headers=headers, json=json, timeout=timeout)


SHOT_W = 480  # small enough to be fast, big enough to read the status-bar numbers


def _env() -> None:
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True))
    except ImportError:
        pass


def prompt(age: int, language: str, recent: list[str], level: str = "", question: str = "") -> str:
    text = PROMPT.read_text(encoding="utf-8")
    lines = "\n".join(f"- {r}" for r in recent[-RECENT:]) or "(nothing yet)"
    return (
        text.replace("{age}", str(age))
        .replace("{map}", level or "unknown, guess it from the screen")
        .replace("{language}", language)
        .replace("{recent}", lines)
        .replace("{question}", f'"{question}"' if question else "(nothing)")
    )


def comment(
    shot: Path,
    recent: list[str],
    age: int = 8,
    language: str = "English",
    timeout: float = 30,
    level: str = "",
    question: str = "",
) -> str:
    """One line for the child about this screenshot, or "" when the model says SKIP."""
    _env()
    img = base64.b64encode(shot.read_bytes()).decode()
    mime = "jpeg" if shot.suffix.lower() in (".jpg", ".jpeg") else "png"
    body = {
        "model": os.environ.get("P2_KID_MODEL", MODEL),
        "temperature": 0.7,
        "max_tokens": 600,  # a reasoning model: a small cap is all spent thinking, no answer
        "chat_template_kwargs": {"enable_thinking": False},  # faster when the API honours it
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{img}"}},
            {"type": "text", "text": prompt(age, language, recent, level, question)},
        ]}],
    }  # fmt: skip
    headers = {"Authorization": f"Bearer {os.environ['HAI_API_KEY']}"}
    r = _post(MODELS_URL, headers=headers, json=body, timeout=timeout)
    if r.status_code == 400:  # the switch is not accepted: plain call
        body.pop("chat_template_kwargs")
        r = _post(MODELS_URL, headers=headers, json=body, timeout=timeout)
    r.raise_for_status()
    choice = r.json()["choices"][0]
    content = choice["message"].get("content")
    if content is None and choice.get("finish_reason") == "length":
        raise ValueError("the model used all max_tokens on reasoning: no line")
    text = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip().strip('"')
    return "" if not text or text.upper().startswith("SKIP") else text


def on_top(handle: int) -> bool:
    """Is this window the foreground one? Linux test desktops (Xvfb) have nothing else."""
    if not sys.platform.startswith("win"):
        return True
    import ctypes

    return ctypes.windll.user32.GetForegroundWindow() == handle


class StreamVoice:
    """ElevenLabs streaming TTS piped into ffplay: the voice starts with the first audio chunk
    instead of after the whole mp3. `say()` returns once audio is playing; `busy()` until done."""

    URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"

    def __init__(self) -> None:
        from voice import tts

        self.tts = tts
        self.exe = shutil.which("ffplay")
        self.http = httpx.Client(timeout=30)
        self.proc: subprocess.Popen | None = None
        self.feeder: threading.Thread | None = None

    def busy(self) -> bool:
        return bool(
            (self.feeder and self.feeder.is_alive()) or (self.proc and self.proc.poll() is None)
        )

    def say(self, text: str, out: Path) -> Path:
        _env()
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key or not self.exe:
            raise RuntimeError("streaming voice needs ELEVENLABS_API_KEY and ffplay")
        voice = os.environ.get("ELEVENLABS_VOICE_ID", self.tts.DEFAULT_VOICE)
        model = os.environ.get("ELEVENLABS_MODEL", self.tts.DEFAULT_MODEL)
        req = self.http.build_request(
            "POST", self.URL.format(voice=voice), headers={"xi-api-key": key},
            params={"output_format": "mp3_44100_128"}, json={"text": text, "model_id": model},
        )  # fmt: skip
        r = self.http.send(req, stream=True)
        if r.status_code >= 400:
            r.read()
            r.close()
            r.raise_for_status()
        chunks = r.iter_bytes()
        first = next(chunks, b"")
        cmd = [self.exe, "-nodisp", "-autoexit", "-loglevel", "quiet", "-probesize", "32",
               "-analyzeduration", "0", "-fflags", "nobuffer", "-i", "-"]  # fmt: skip
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        proc = self.proc

        def feed() -> None:
            with out.open("wb") as f:
                try:
                    for chunk in _chain(first, chunks):
                        f.write(chunk)
                        proc.stdin.write(chunk)
                except (OSError, httpx.HTTPError) as e:
                    print(f"voice stream broke: {e}", file=sys.stderr)
                finally:
                    r.close()
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass

        self.feeder = threading.Thread(target=feed, daemon=True)
        self.feeder.start()
        return out

    def __call__(self, path: Path) -> None:  # already playing since say()
        pass


def _chain(first: bytes, rest: Any) -> Any:
    yield first
    yield from rest


def grab_window(win: Any, out: Path) -> Path:
    """The window's pixels as a small JPEG. Pillow takes ~0.05 s; spawning ffmpeg takes ~3 s."""
    try:
        from PIL import ImageGrab

        box = (win.x, win.y, win.x + win.width, win.y + win.height)
        img = ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")
    except (ImportError, OSError):  # no Pillow / no grab backend: the slow full-size PNG
        from launcher.capture import screenshot

        return screenshot(win, out.with_suffix(".png"))
    img.thumbnail((SHOT_W, SHOT_W))
    img.save(out, "JPEG", quality=75)
    return out


class Speaker:
    """Plays mp3 files with ffplay in the background; `busy()` while one is playing."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.exe = shutil.which("ffplay")

    def busy(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def __call__(self, path: Path) -> None:
        if not self.exe:
            print("ffplay not found: lines are written but not played", file=sys.stderr)
            return
        cmd = [self.exe, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL)


class _Retry(str):
    """A question put back after its answer failed: it is not put back a second time."""


class GameClosed(Exception):
    """The game window is gone: the run ends and the summary is written."""


def run(
    grab: Callable[[Path], Path | None],
    out: Path,
    seconds: float,
    ask: Callable[[Path, list[str]], str],
    say: Callable[[str, Path], Any] | None,
    speaker: Any,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    heard: list[str] | None = None,
) -> list[dict[str, Any]]:
    """`heard`: what the child said (filled by the voice listener); answered before the gap."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / "comments.jsonl"
    n0 = path.read_text(encoding="utf-8").count("\n") if path.exists() else 0  # a reused --out
    log = path.open("a", encoding="utf-8")
    rows: list[dict[str, Any]] = []
    recent: list[str] = []
    start, last = clock(), -MIN_GAP_S

    def requeue(q: str) -> None:  # a question that got no answer is asked once more
        if q and not isinstance(q, _Retry) and heard is not None and not heard:
            heard.append(_Retry(q))

    try:
        while clock() - start < seconds:
            t0 = clock()
            q = heard[-1] if heard else ""
            if speaker.busy() or (not q and t0 - last < MIN_GAP_S):
                sleep(0.1 if q else 0.5)
                continue
            n = n0 + len(rows)
            try:
                shot = grab(out / f"shot_{n:03d}.jpg")
            except GameClosed:
                print("game window closed: stopping", file=sys.stderr)
                break
            if shot is None:  # window gone, minimised or covered
                sleep(EVERY_S)
                continue
            t_shot = clock()
            if q:
                heard.clear()
            try:
                text = ask(shot, recent, q) if q else ask(shot, recent)
            except (httpx.HTTPError, KeyError, ValueError) as e:
                print(f"comment failed: {e}", file=sys.stderr)
                requeue(q)
                sleep(EVERY_S)
                continue
            t_text = clock()
            row: dict[str, Any] = {"i": n, "t": round(t0 - start, 2), "shot": shot.name,
                                   "text": text, "grab_s": round(t_shot - t0, 2),
                                   "vision_s": round(t_text - t_shot, 2)}  # fmt: skip
            if q:
                row["heard"] = q
            if text:
                if say:
                    try:
                        if clock() - t_shot > MAX_AGE_S:  # the screen has moved on
                            raise RuntimeError(f"dropped: frame {clock() - t_shot:.1f} s old")
                        audio = say(text, out / f"say_{n:03d}.mp3")
                        row["tts_s"] = round(clock() - t_text, 2)
                        speaker(getattr(audio, "path", audio))
                        row["latency_s"] = round(clock() - t0, 2)  # screenshot -> voice
                    except (httpx.HTTPError, RuntimeError, OSError) as e:
                        row["error"] = str(e) if "dropped" in str(e) else f"speech failed: {e}"
                        print(row["error"], file=sys.stderr)
                        if "dropped" in row["error"]:
                            requeue(q)
                if "error" not in row:  # an unheard line may be said again later
                    recent.append(text)
                    last = clock()
            rows.append(row)
            log.write(json.dumps(row) + "\n")
            log.flush()
            print(json.dumps(row), flush=True)
            while clock() - t0 < EVERY_S and not heard:  # a question cuts the wait
                sleep(0.1)
    except KeyboardInterrupt:  # Ctrl+C still writes summary.json
        print("stopped", file=sys.stderr)
    finally:
        log.close()
    return rows


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lat = [r["latency_s"] for r in rows if "latency_s" in r]
    vis = [r["vision_s"] for r in rows]
    return {
        "screens": len(rows),
        "lines": sum(1 for r in rows if r["text"]),
        "spoken": len(lat),
        "vision_median_s": round(statistics.median(vis), 2) if vis else None,
        "skipped": sum(1 for r in rows if not r["text"]),
        "latency_median_s": round(statistics.median(lat), 2) if lat else None,
        "latency_max_s": max(lat, default=None),
    }


def listen(heard: list[str], speaker: Any, language: str = "English") -> None:
    """Open mic -> Gladia; every final phrase goes to `heard`. The mic is muted while the buddy
    speaks, so it does not hear itself."""
    from voice.listen import Listener, mic_chunks

    _env()
    key = os.environ.get("GLADIA_API_KEY")
    if not key:
        raise SystemExit("--talk needs GLADIA_API_KEY")
    talking = threading.Event()

    def mute() -> None:
        while True:
            talking.clear() if speaker.busy() else talking.set()
            time.sleep(0.1)

    def on_transcript(text: str, final: bool, lang: str | None) -> None:  # noqa: ARG001
        if final and len(text.strip()) > 2:
            heard.append(text.strip())
            print(json.dumps({"heard": text.strip()}), flush=True)

    code = {"english": "en", "french": "fr"}.get(language.lower())
    listener = Listener(key, lambda intent: None, on_transcript, languages=[code] if code else None)
    threading.Thread(target=mute, daemon=True).start()
    threading.Thread(target=listener.run, args=(mic_chunks(talking),), daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    from launcher.window import find_window

    p = argparse.ArgumentParser(prog="python -m voice.commentator")
    p.add_argument("--window", default="Chocolate Doom", help="part of the game window title")
    p.add_argument("--minutes", type=float, default=2)
    p.add_argument("--age", type=int, default=8)
    p.add_argument("--language", default="English")
    p.add_argument("--talk", action="store_true", help="the child can talk to the buddy (mic)")
    p.add_argument("--map", default="", help="the level the child starts on, e.g. E1M1")
    p.add_argument("--no-voice", action="store_true", help="write the lines, do not speak them")
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    out = a.out or Path("recordings") / f"kid-{datetime.now():%Y%m%d-%H%M%S}"

    gone: list[float] = []  # when the window was last seen missing (minimised looks the same)

    def grab(path: Path) -> Path | None:
        win = find_window(a.window)
        if win is None:
            gone[:] = gone or [time.monotonic()]
            if time.monotonic() - gone[0] > GONE_S:
                raise GameClosed(a.window)
            return None
        gone.clear()
        # the capture is a screen rectangle: only send it when the game is on top
        return grab_window(win, path) if win and on_top(win.handle) else None

    say, speaker = None, Speaker()
    if not a.no_voice:
        if os.environ.get("P2_KID_STREAM", "1") == "1":
            speaker = StreamVoice()
            say = speaker.say
        else:
            from voice.tts import speak

            say = speak

    def ask(shot: Path, recent: list[str], question: str = "") -> str:
        return comment(shot, recent, a.age, a.language, level=a.map, question=question)

    heard: list[str] = []
    if a.talk:
        listen(heard, speaker, a.language)

    rows = run(grab, out, a.minutes * 60, ask, say, speaker, heard=heard)
    s = summary(rows)
    (out / "summary.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
