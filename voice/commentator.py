"""Kid mode (T21): a friendly buddy watches the game window and talks to the child.

Every ~3 s: a screenshot of the window -> the fast H vision model writes one short line ->
ElevenLabs speaks it. It never talks over itself: a new line waits until the last one has been
played and `MIN_GAP_S` has passed. Each line is logged with its latency to `<out>/comments.jsonl`.

    python -m voice.commentator --window "Chocolate Doom" --minutes 2 --age 8
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import statistics
import subprocess
import sys
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


def _env() -> None:
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True))
    except ImportError:
        pass


def prompt(age: int, language: str, recent: list[str]) -> str:
    text = PROMPT.read_text(encoding="utf-8")
    lines = "\n".join(f"- {r}" for r in recent[-RECENT:]) or "(nothing yet)"
    return (
        text.replace("{age}", str(age)).replace("{language}", language).replace("{recent}", lines)
    )


def comment(
    shot: Path, recent: list[str], age: int = 8, language: str = "English", timeout: float = 30
) -> str:
    """One line for the child about this screenshot, or "" when the model says SKIP."""
    _env()
    img = base64.b64encode(shot.read_bytes()).decode()
    body = {
        "model": os.environ.get("P2_KID_MODEL", MODEL),
        "temperature": 0.7,
        "max_tokens": 60,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
            {"type": "text", "text": prompt(age, language, recent)},
        ]}],
    }  # fmt: skip
    headers = {"Authorization": f"Bearer {os.environ['HAI_API_KEY']}"}
    r = httpx.post(MODELS_URL, headers=headers, json=body, timeout=timeout)
    r.raise_for_status()
    text = (r.json()["choices"][0]["message"]["content"] or "").strip().strip('"')
    return "" if not text or text.upper().startswith("SKIP") else text


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


def run(
    grab: Callable[[Path], Path | None],
    out: Path,
    seconds: float,
    ask: Callable[[Path, list[str]], str],
    say: Callable[[str, Path], Any] | None,
    speaker: Any,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "comments.jsonl").open("a", encoding="utf-8")
    rows: list[dict[str, Any]] = []
    recent: list[str] = []
    start, last = clock(), -MIN_GAP_S
    try:
        while clock() - start < seconds:
            t0 = clock()
            if speaker.busy() or t0 - last < MIN_GAP_S:
                sleep(0.5)
                continue
            shot = grab(out / f"shot_{len(rows):03d}.png")
            if shot is None:  # window gone (minimised or closed)
                sleep(EVERY_S)
                continue
            try:
                text = ask(shot, recent)
            except (httpx.HTTPError, KeyError, ValueError) as e:
                print(f"comment failed: {e}", file=sys.stderr)
                sleep(EVERY_S)
                continue
            t_text = clock()
            row: dict[str, Any] = {"i": len(rows), "t": round(t0 - start, 2), "shot": shot.name,
                                   "text": text, "vision_s": round(t_text - t0, 2)}  # fmt: skip
            if text:
                if say:
                    audio = say(text, out / f"say_{len(rows):03d}.mp3")
                    row["tts_s"] = round(clock() - t_text, 2)
                    speaker(getattr(audio, "path", audio))
                row["latency_s"] = round(clock() - t0, 2)  # screenshot -> voice starts
                recent.append(text)
                last = clock()
            rows.append(row)
            log.write(json.dumps(row) + "\n")
            log.flush()
            print(json.dumps(row), flush=True)
            sleep(max(0.0, EVERY_S - (clock() - t0)))
    finally:
        log.close()
    return rows


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lat = [r["latency_s"] for r in rows if "latency_s" in r]
    return {
        "screens": len(rows),
        "spoken": len(lat),
        "skipped": sum(1 for r in rows if not r["text"]),
        "latency_median_s": round(statistics.median(lat), 2) if lat else None,
        "latency_max_s": max(lat, default=None),
    }


def main(argv: list[str] | None = None) -> int:
    from launcher.capture import screenshot
    from launcher.window import find_window

    p = argparse.ArgumentParser(prog="python -m voice.commentator")
    p.add_argument("--window", default="Chocolate Doom", help="part of the game window title")
    p.add_argument("--minutes", type=float, default=2)
    p.add_argument("--age", type=int, default=8)
    p.add_argument("--language", default="English")
    p.add_argument("--no-voice", action="store_true", help="write the lines, do not speak them")
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    out = a.out or Path("recordings") / f"kid-{datetime.now():%Y%m%d-%H%M%S}"

    def grab(path: Path) -> Path | None:
        win = find_window(a.window)
        return screenshot(win, path) if win else None

    say = None
    if not a.no_voice:
        from voice.tts import speak

        say = speak

    def ask(shot: Path, recent: list[str]) -> str:
        return comment(shot, recent, a.age, a.language)

    rows = run(grab, out, a.minutes * 60, ask, say, Speaker())
    s = summary(rows)
    (out / "summary.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
