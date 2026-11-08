"""T33: Holo plays Doom in the browser.

The page runs Doom (WebAssembly), pauses it, posts a small JPEG of the canvas to
`POST /api/holo/act` and gets back one move from H's `holo4-35b-a3b` as strict JSON (thought, keys,
hold_ms, aim). The key stays on the server; per-client gaps and a global cap (`P2_HOLO_MAX_ACTS`)
bound the cost. When
the cap is reached or the key is missing, the page switches to a RECORDED run (see web/jury/).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from voice import commentator as c
from voice.kid_web import IMAGE_MAGIC, MAX_IMAGE, Budget

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "agents" / "prompts" / "holo_play.md"
log = logging.getLogger(__name__)
MODELS = "holo4-35b-a3b,holo4-27b,holo3-1-35b-a3b"
KEYS = {
    "up", "down", "left", "right", "strafe_left", "strafe_right", "run", "fire", "use",
    "w1", "w2", "w3", "w4", "w5", "w6", "w7",
}  # fmt: skip
STATUSES = {"ok", "dead", "menu", "stuck"}
HOLD_MIN, HOLD_MAX = 100, 1500
TIMEOUT_S = 9.0
JSON_RE = re.compile(r"\{.*\}", re.S)
# ElevenLabs premade "Eric": a friendly guy; flash = fastest first audio for a live commentary
HOLO_VOICE = "cjVigY5qzO86Huf0OWal"
HOLO_TTS_MODEL = "eleven_flash_v2_5"
_http: httpx.Client | None = None


class ActIn(BaseModel):
    image: str = Field(..., description="data:image/jpeg;base64,... of the game canvas")
    prev_image: str = Field("", description="the view before the last move, same format (optional)")
    recent: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    instruction: str = Field("", max_length=240)
    step: int = Field(0, ge=0)
    stalled: bool = False


class Move(BaseModel):
    thought: str = ""
    keys: list[str] = Field(default_factory=lambda: ["up"])
    hold_ms: int = 500
    aim: dict[str, int] | None = None
    status: str = "ok"


def _client() -> httpx.Client:
    global _http
    _http = _http or httpx.Client(timeout=TIMEOUT_S)
    return _http


def model_names() -> list[str]:
    """Models to rotate over. H's Models API limits each model separately (tier_1: 30 RPM per
    model), so three models give three buckets; the first (fastest) is preferred."""
    return [m for m in (os.environ.get("P2_HOLO_MODELS") or MODELS).split(",") if m.strip()]


def model_name() -> str:
    return model_names()[0]


class RateLimited(Exception):
    def __init__(self, model: str, retry_after: float) -> None:
        super().__init__(f"{model}: rate limited, retry in {retry_after:.0f}s")
        self.model, self.retry_after = model, retry_after


class Pool:
    """Per-model sliding-minute budgets so we stop before H's 429 and spread load over models.
    `reserve` keeps part of the first model's budget for priority callers (the shared stream)."""

    def __init__(self, models: list[str], rpm: int, reserve: int) -> None:
        self.models, self.rpm, self.reserve = models, rpm, reserve
        self.calls: dict[str, deque[float]] = {m: deque() for m in models}
        self.blocked: dict[str, float] = dict.fromkeys(models, 0.0)

    def _prune(self, m: str, now: float) -> None:
        q = self.calls[m]
        while q and q[0] < now - 60:
            q.popleft()

    def pick(self, priority: bool, skip: set[str]) -> str | None:
        now = time.monotonic()
        for i, m in enumerate(self.models):
            if m in skip or self.blocked[m] > now:
                continue
            self._prune(m, now)
            room = self.rpm - len(self.calls[m]) - (0 if priority or i else self.reserve)
            if room > 0:
                self.calls[m].append(now)
                return m
        return None

    def wait_s(self) -> float:
        now = time.monotonic()
        waits = []
        for m in self.models:
            self._prune(m, now)
            waits.append(
                max(self.blocked[m] - now, (self.calls[m][0] + 60 - now) if self.calls[m] else 0)
            )
        return max(1.0, min(waits)) if waits else 60.0

    def block(self, m: str, seconds: float) -> None:
        self.blocked[m] = time.monotonic() + min(seconds, 90)

    def snapshot(self) -> dict[str, int]:
        now = time.monotonic()
        out = {}
        for m in self.models:
            self._prune(m, now)
            out[m] = len(self.calls[m])
        return out


def have_key() -> bool:
    c._env()
    return bool(os.environ.get("HAI_API_KEY"))


def decode_image(data_url: str) -> tuple[bytes, str]:
    head, _, data = data_url.partition(",")
    if not head.startswith("data:image/") or len(data) > MAX_IMAGE:
        raise HTTPException(400, "send a small JPEG data URL")
    try:
        raw = base64.b64decode(data, validate=True)
    except ValueError as e:
        raise HTTPException(400, "bad base64") from e
    mime = next((s for magic, s in IMAGE_MAGIC if raw.startswith(magic)), None)
    if not mime:
        raise HTTPException(400, "send a JPEG or PNG")
    return raw, "jpeg" if mime == ".jpg" else "png"


def jpeg_size(raw: bytes) -> tuple[int, int]:
    """Width and height from the JPEG SOF marker (no Pillow needed); (0, 0) when not found."""
    i = 2
    while i + 9 < len(raw) and raw[i] == 0xFF:
        marker, length = raw[i + 1], int.from_bytes(raw[i + 2 : i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            w, h = raw[i + 7 : i + 9], raw[i + 5 : i + 7]
            return int.from_bytes(w, "big"), int.from_bytes(h, "big")
        i += 2 + length
    return 0, 0


def prompt(recent: list[dict[str, Any]], instruction: str, w: int, h: int, stalled: bool) -> str:
    lines = []
    for r in recent[-8:]:
        keys = "+".join(str(k) for k in (r.get("keys") or []))
        thought = str(r.get("thought", ""))[:80]
        lines.append(f"- {keys or '(none)'} {r.get('hold_ms', '')}ms: {thought}")
    burst = 0
    for r in reversed(recent):
        if "fire" not in (r.get("keys") or []):
            break
        burst += 1
    if burst >= 3:
        lines.append(
            f"- (you have fired for {burst} moves in a row. Look at the CURRENT view again: "
            "is a live monster really there? If not, you are shooting a wall or a corpse: "
            "stop firing and move on)"
        )
    if stalled:
        lines.append(
            "- (the view has not changed for several moves: you are STUCK against something. "
            "Hold `left` 900 ms to turn around, or `use` if a door or panel is in front)"
        )
    ask = ""
    if instruction.strip():
        ask = (
            f"THE AUDIENCE ASKS YOU TO: **{instruction.strip()}**. Do it now, make it your "
            "priority, and say in your thought how you follow it."
        )
    return (
        PROMPT.read_text(encoding="utf-8")
        .replace("{instruction}", ask)
        .replace("{recent}", "\n".join(lines) or "(none yet: the game just started)")
        .replace("{w}", str(w or 480))
        .replace("{h}", str(h or 300))
        .replace("{cx}", str((w or 480) // 2))
    )


def parse_move(text: str, w: int, h: int) -> Move:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = JSON_RE.search(text)
    if not m:
        raise ValueError("no JSON in the answer")
    data = json.loads(m.group(0))
    keys = data.get("keys") or []
    if isinstance(keys, str):
        keys = [keys]
    keys = [str(k).lower().replace("arrow", "").replace("ctrl", "fire").replace("space", "use")
            for k in keys]  # fmt: skip
    keys = [k for k in dict.fromkeys(keys) if k in KEYS] or ["up"]
    try:
        hold = int(data.get("hold_ms", 500))
    except (TypeError, ValueError):
        hold = 500
    aim = data.get("aim") if isinstance(data.get("aim"), dict) else None
    if aim is not None:
        try:
            aim = {"x": max(0, min(int(aim.get("x", 0)), w or 10**6)),
                   "y": max(0, min(int(aim.get("y", 0)), h or 10**6))}  # fmt: skip
        except (TypeError, ValueError):
            aim = None
    status = str(data.get("status", "ok")).lower()
    return Move(
        thought=str(data.get("thought", "")).strip().strip('"')[:160],
        keys=keys,
        hold_ms=max(HOLD_MIN, min(hold, HOLD_MAX)),
        aim=aim,
        status=status if status in STATUSES else "ok",
    )


def ask_holo(
    raw: bytes,
    mime: str,
    text: str,
    model: str,
    prev: tuple[bytes, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """One Models API call; returns the answer text and the usage block."""

    def image(data: bytes, kind: str) -> dict[str, Any]:
        b64 = base64.b64encode(data).decode()
        return {"type": "image_url", "image_url": {"url": f"data:image/{kind};base64,{b64}"}}

    content: list[dict[str, Any]] = []
    if prev:
        content += [
            {"type": "text", "text": "PREVIOUS view (before your last move):"},
            image(*prev),
        ]
        content.append({"type": "text", "text": "CURRENT view (now):"})
    content += [image(raw, mime), {"type": "text", "text": text}]
    body = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": 300,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "user", "content": content}],
    }
    headers = {"Authorization": f"Bearer {os.environ['HAI_API_KEY']}"}
    r = _client().post(c.MODELS_URL, headers=headers, json=body)
    if r.status_code == 400:
        body.pop("chat_template_kwargs")
        r = _client().post(c.MODELS_URL, headers=headers, json=body)
    if r.status_code >= 500:  # one retry on a transient upstream error
        time.sleep(0.3)
        r = _client().post(c.MODELS_URL, headers=headers, json=body)
    if r.status_code == 429:
        raise RateLimited(
            model, float(r.headers.get("retry-after") or r.headers.get("x-ratelimit-reset") or 60)
        )
    r.raise_for_status()
    j = r.json()
    choice = j["choices"][0]
    content = choice["message"].get("content")
    if content is None:
        raise ValueError(f"empty answer ({choice.get('finish_reason')})")
    return content, j.get("usage") or {}


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def create_router() -> APIRouter:
    acts = Budget(_int("P2_HOLO_MAX_ACTS", 8000), 0.4, "Holo")
    voice = Budget(_int("P2_HOLO_MAX_SAYS", 1500), 1.0, "Holo")
    stats = {"acts": 0, "errors": 0, "latency_ms": [], "started": time.time()}
    pool = Pool(model_names(), _int("P2_HOLO_RPM", 28), _int("P2_HOLO_RESERVE", 12))
    token = os.environ.get("P2_HOLO_PRIORITY_TOKEN", "")

    def priority(req: Request) -> bool:
        """The shared stream runs next to the server (localhost, not through the tunnel) or
        sends P2_HOLO_PRIORITY_TOKEN; it keeps the reserved part of the budget."""
        if token and req.query_params.get("p") == token:
            return True
        host = req.client.host if req.client else ""
        return host in ("127.0.0.1", "::1") and not req.headers.get("cf-connecting-ip")

    router = APIRouter(prefix="/api/holo", tags=["holo"])

    def who(req: Request) -> str:
        ip = req.headers.get("cf-connecting-ip") or (req.client.host if req.client else "?")
        return f"{ip}/{req.query_params.get('c', '')[:32]}"

    @router.get("/status")
    def status() -> dict:
        lat = stats["latency_ms"][-50:]
        return {
            "live": have_key() and acts.used < acts.total,
            "model": model_name(),
            "used": acts.used,
            "cap": acts.total,
            "errors": stats["errors"],
            "last_error": stats.get("last_error"),
            "models": pool.snapshot(),
            "rpm": pool.rpm,
            "latency_ms_median": sorted(lat)[len(lat) // 2] if lat else None,
            "voice": bool(os.environ.get("ELEVENLABS_API_KEY")) and voice.used < voice.total,
        }

    @router.post("/act")
    def act(body: ActIn, req: Request) -> dict:
        if not have_key():
            raise HTTPException(503, "no HAI_API_KEY on the server: recorded run")
        raw, mime = decode_image(body.image)
        prev = decode_image(body.prev_image) if body.prev_image else None
        w, h = jpeg_size(raw) if mime == "jpeg" else (0, 0)
        acts.take(who(req))
        t0 = time.monotonic()
        ask = prompt(body.recent, body.instruction, w, h, body.stalled)
        tried: set[str] = set()
        try:
            while True:
                model = pool.pick(priority(req), tried)
                if model is None:
                    wait = pool.wait_s()
                    raise HTTPException(
                        429,
                        {"busy": True, "retry_after": round(wait), "detail": "Holo is busy"},
                        headers={"Retry-After": str(round(wait))},
                    )
                try:
                    text, usage = ask_holo(raw, mime, ask, model, prev)
                    break
                except RateLimited as e:
                    pool.block(model, e.retry_after)
                    tried.add(model)
                    log.warning("holo %s", e)
            move = parse_move(text, w, h)
        except (httpx.HTTPError, ValueError, KeyError) as e:
            stats["errors"] += 1
            stats["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"
            log.warning("holo act failed: %s", stats["last_error"])
            raise HTTPException(502, f"holo: {type(e).__name__}: {str(e)[:120]}") from e
        ms = round((time.monotonic() - t0) * 1000)
        stats["acts"] += 1
        stats["latency_ms"].append(ms)
        del stats["latency_ms"][:-500]
        return {
            **move.model_dump(),
            "step": body.step,
            "latency_ms": ms,
            "model": model,
            "image": {"w": w, "h": h},
            "raw": text[:1200],
            "usage": {k: v for k, v in usage.items() if isinstance(v, int)},
        }

    @router.get("/say")
    def say(text: str, req: Request) -> StreamingResponse:
        voice.take(who(req))
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise HTTPException(503, "no ELEVENLABS_API_KEY on the server")
        http = _client()
        r = http.send(
            http.build_request(
                "POST",
                c.StreamVoice.URL.format(voice=os.environ.get("P2_HOLO_VOICE") or HOLO_VOICE),
                headers={"xi-api-key": key}, params={"output_format": "mp3_44100_128"},
                json={"text": c.spoken(text[:300]),
                      "model_id": os.environ.get("P2_HOLO_TTS_MODEL") or HOLO_TTS_MODEL,
                      "voice_settings": c.VOICE_SETTINGS},
            ),
            stream=True,
        )  # fmt: skip
        if r.status_code >= 400:
            r.read()
            r.close()
            raise HTTPException(502, f"ElevenLabs HTTP {r.status_code}")

        def chunks():
            try:
                yield from r.iter_bytes()
            finally:
                r.close()

        return StreamingResponse(chunks(), media_type="audio/mpeg",
                                 headers={"Cache-Control": "no-store"})  # fmt: skip

    return router
