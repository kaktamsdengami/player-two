"""Kid mode in the browser: Doom (Chocolate Doom in WebAssembly + Freedoom) on the page, Pixel
watches the canvas (Holo), talks (ElevenLabs Chris) and listens (Gladia live, open mic).

The keys stay on this server; the page only gets lines, audio and a one-time Gladia socket URL.
A small budget keeps a public link from eating the credits.

    uv run uvicorn voice.kid_web:app --host 127.0.0.1 --port 8010
    cloudflared tunnel --url http://127.0.0.1:8010   # public https link for the jury
"""

from __future__ import annotations

import base64
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from voice import commentator as c

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "web" / "kid"
WAD_CANDIDATES = ("data/freedoom1.wad", "freedoom1.wad")
STALL_S = 2.5  # a healthy answer takes 0.3-0.9 s; past this the call is stuck, ask again
MAX_IMAGE = 400_000  # a 480-wide JPEG is ~30 KB
IMAGE_MAGIC = ((b"\xff\xd8\xff", ".jpg"), (b"\x89PNG\r\n\x1a\n", ".png"))


class Budget:
    """Per-client minimum gap and a total cap per kind of call (lines, voice, listen)."""

    def __init__(self, total: int, gap_s: float, name: str = "Pixel") -> None:
        self.total, self.gap_s, self.used, self.name = total, gap_s, 0, name
        self.last: dict[str, float] = {}
        self.lock = threading.Lock()

    def take(self, who: str) -> None:
        now = time.monotonic()
        with self.lock:
            if self.used >= self.total:
                raise HTTPException(429, f"{self.name} is resting: the demo budget is used up")
            if now - self.last.get(who, -1e9) < self.gap_s:
                raise HTTPException(429, "slow down")
            self.used += 1
            self.last[who] = now


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


class LineIn(BaseModel):
    image: str = Field(..., description="data:image/jpeg;base64,... of the game canvas")
    recent: list[str] = Field(default_factory=list, max_length=20)
    chat: list[str] = Field(default_factory=list, max_length=80)
    question: str = Field("", max_length=300)
    age: int = Field(8, ge=4, le=14)
    level: str = Field("E1M1", max_length=10)


def _wad() -> Path:
    if os.environ.get("P2_KID_WAD"):
        return Path(os.environ["P2_KID_WAD"])
    for p in WAD_CANDIDATES:
        if (ROOT / p).is_file():
            return ROOT / p
    raise HTTPException(404, "no Freedoom WAD: set P2_KID_WAD")


def create_app() -> FastAPI:
    c._env()
    lines = Budget(_int("P2_KID_MAX_LINES", 4000), 1.5)
    voice = Budget(_int("P2_KID_MAX_SAYS", 2000), 1.0)
    ears = Budget(_int("P2_KID_MAX_LISTENS", 600), 2.0)
    http = httpx.Client(timeout=30)
    app = FastAPI(title="PLAYER TWO kid mode")

    def who(req: Request) -> str:
        ip = req.headers.get("cf-connecting-ip") or (req.client.host if req.client else "?")
        return f"{ip}/{req.query_params.get('c', '')[:32]}"  # one jury wifi = one IP, many tabs

    @app.get("/doom1.wad")
    def wad() -> FileResponse:
        return FileResponse(_wad(), media_type="application/octet-stream")

    @app.get("/api/kid/hello")
    def hello() -> dict:
        return {"hello": c.HELLO, "bye": c.BYE, "voice": c.kid_voice(), "model": c.kid_tts_model()}

    def _comment(shot: Path, body: LineIn) -> str:
        """One Models call, retried once when it stalls: a stalled call used to cost the whole
        VISION_TIMEOUT_S and then say nothing, the main "Pixel is slow" complaint."""
        kw = dict(age=body.age, level=body.level, question=body.question, chat=body.chat)
        try:
            return c.comment(shot, body.recent, timeout=STALL_S, **kw)
        except httpx.TimeoutException:
            return c.comment(shot, body.recent, timeout=c.VISION_TIMEOUT_S, **kw)

    @app.post("/api/kid/line")
    def line(body: LineIn, req: Request) -> dict:
        t_in = time.monotonic()
        head, _, data = body.image.partition(",")
        if not head.startswith("data:image/") or len(data) > MAX_IMAGE:
            raise HTTPException(400, "send a small JPEG data URL")
        try:
            raw = base64.b64decode(data, validate=True)
        except ValueError as e:
            raise HTTPException(400, "bad base64") from e
        suffix = next((s for magic, s in IMAGE_MAGIC if raw.startswith(magic)), None)
        if not suffix:
            raise HTTPException(400, "send a JPEG or PNG")
        lines.take(who(req))
        with tempfile.TemporaryDirectory() as d:
            shot = Path(d) / f"shot{suffix}"
            shot.write_bytes(raw)
            t0 = time.monotonic()
            try:
                text = _comment(shot, body)
            except (httpx.HTTPError, ValueError, KeyError) as e:
                return {"text": "", "skipped": f"vision: {type(e).__name__}",
                        "vision_s": round(time.monotonic() - t0, 2)}  # fmt: skip
        timing = {"vision_s": round(time.monotonic() - t0, 2),
                  "server_s": round(time.monotonic() - t_in, 2)}  # fmt: skip
        recent = body.recent[-c.RECENT :]
        if (
            text
            and not body.question
            and (c.BOT.search(text) or any(c.similar(text, r) >= c.SAME for r in recent))
        ):
            return {"text": "", "skipped": "repeat", **timing}
        return {"text": text, **timing}

    @app.get("/api/kid/say")
    def say(text: str, req: Request) -> StreamingResponse:
        voice.take(who(req))
        t0 = time.monotonic()
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise HTTPException(503, "no ELEVENLABS_API_KEY on the server")
        r = http.send(
            http.build_request(
                "POST", c.StreamVoice.URL.format(voice=c.kid_voice()),
                headers={"xi-api-key": key}, params={"output_format": "mp3_44100_128"},
                json={"text": c.spoken(text[:400]), "model_id": c.kid_tts_model(),
                      "voice_settings": c.voice_settings()},
            ),
            stream=True,
        )  # fmt: skip
        if r.status_code >= 400:
            r.read()
            r.close()
            raise HTTPException(502, f"ElevenLabs HTTP {r.status_code}")

        chunks = r.iter_bytes()
        try:  # wait for the first audio here: its delay goes in a header
            first = next(chunks, b"")
        except httpx.HTTPError as e:
            r.close()
            raise HTTPException(504, f"ElevenLabs stalled: {type(e).__name__}") from e
        first_ms = round((time.monotonic() - t0) * 1000)

        def audio() -> Iterator[bytes]:
            try:
                yield first
                yield from chunks
            finally:
                r.close()

        headers = {"Cache-Control": "no-store", "X-First-Audio-Ms": str(first_ms)}
        return StreamingResponse(audio(), media_type="audio/mpeg", headers=headers)

    @app.post("/api/kid/listen")
    def listen(req: Request) -> dict:
        """A Gladia live session for the open mic: the page streams 16 kHz PCM to it and opens a
        new one when Gladia ends it."""
        ears.take(who(req))
        from voice.listen import SAMPLE_RATE, start_session

        key = os.environ.get("GLADIA_API_KEY")
        if not key:
            raise HTTPException(503, "no GLADIA_API_KEY on the server")
        try:
            s = start_session(key, http=http)
        except RuntimeError as e:
            raise HTTPException(502, str(e)) from e
        return {"url": s["url"], "sample_rate": SAMPLE_RATE}

    app.mount("/", StaticFiles(directory=PAGE, html=True), name="kid")
    return app


app = create_app()
