"""T14 FastAPI app: REST snapshot + SSE stream for the dashboard (docs/CONTRACTS.md).

uvicorn app.main:app --port 8000      # P2_MODE=live | recorded (default recorded)
P2_RECORDING=eval/runs/<run>/events.jsonl for RECORDED mode
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.contracts import SessionInfo, SseType, TranscriptPayload, VoiceIntent
from app.orchestrator import Orchestrator, Recorded, sse_format
from app.routes_billing import router as billing_router
from app.routes_holo import create_router as holo_router

ROOT = Path(__file__).resolve().parent.parent
MOCK = ROOT / "docs" / "api-mock.json"
DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
MEDIA_SUFFIXES = {
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".html",
}
DEV_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def control(request: Request) -> None:
    """Guard for endpoints that start, steer, stop or approve (a `fix` intent merges a PR).

    JSON only, so a cross-site form post needs a CORS preflight; and when `P2_CONTROL_TOKEN` is
    set (any deployment reachable from outside the laptop), the `X-P2-Token` header must match.
    """
    if request.headers.get("cf-connecting-ip"):  # came through the public Cloudflare tunnel
        raise HTTPException(403, "view only: the public link cannot start, steer or approve")
    if "application/json" not in request.headers.get("content-type", ""):
        raise HTTPException(415, "send JSON")
    token = os.environ.get("P2_CONTROL_TOKEN")
    if token and request.headers.get("x-p2-token") != token:
        raise HTTPException(401, "missing or wrong X-P2-Token")


class StartRequest(BaseModel):
    mode: str | None = None  # "live" | "recorded"
    plan: str | None = None  # developer's focus area for the tester ("Test plan")
    preset: str | None = None  # launcher PRESETS key, e.g. "stage-kb3"; "" = none; null = P2_PRESET


class PttPayload(BaseModel):
    on: bool


class Runtime:
    """Holds the current session (live orchestrator or RECORDED replay)."""

    def __init__(self, runs_dir: Path, mode: str = "recorded", recording: Path | None = None):
        self.runs_dir, self.mode, self.recording = runs_dir, mode, recording
        self.current: Orchestrator | Recorded | None = None
        self.factory = None  # tests inject a factory returning an Orchestrator
        self.ptt = False  # push-to-talk from the dashboard; the voice listener follows it

    def new(
        self, mode: str | None = None, plan: str | None = None, preset: str | None = None
    ) -> Orchestrator | Recorded:
        mode = mode or self.mode
        self.ptt = False
        out = self.runs_dir / datetime.now().strftime("%Y%m%d-%H%M%S-session")
        if self.factory:
            return self.factory(out)
        if mode == "recorded":
            if not self.recording or not self.recording.exists():
                raise HTTPException(409, "no recording configured (P2_RECORDING)")
            return Recorded(self.recording, out)
        from app.orchestrator import build_live

        return build_live(out, plan=plan, preset=preset)

    def start(
        self, mode: str | None = None, plan: str | None = None, preset: str | None = None
    ) -> Orchestrator | Recorded:
        if self.current and self.current.running:
            raise HTTPException(409, "a session is already running")
        try:
            self.current = self.new(mode, plan, preset)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - e.g. H busy, missing keys
            raise HTTPException(503, f"cannot start a live session: {e}") from e
        self.current.start()
        return self.current


def _mock(key: str) -> Any:
    return json.loads(MOCK.read_text())[key]


def create_app(rt: Runtime | None = None) -> FastAPI:
    try:  # P2_CONTROL_TOKEN / P2_CORS_ORIGINS may live in .env
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True))
    except ImportError:
        pass
    rt = rt or Runtime(
        Path(os.environ.get("P2_RUNS_DIR", "recordings")).resolve(),
        os.environ.get("P2_MODE", "recorded"),
        Path(os.environ["P2_RECORDING"]) if os.environ.get("P2_RECORDING") else None,
    )
    app = FastAPI(title="PLAYER TWO")
    app.state.rt = rt
    origins = [o.strip() for o in os.environ.get("P2_CORS_ORIGINS", DEV_ORIGINS).split(",")]
    app.add_middleware(CORSMiddleware, allow_origins=[o for o in origins if o],
                       allow_methods=["*"], allow_headers=["*"])  # fmt: skip
    app.include_router(billing_router)
    app.include_router(holo_router())

    def store():
        return rt.current.store if rt.current else None

    def dump(xs: Any) -> Any:
        return [x.model_dump(mode="json") for x in xs]

    @app.get("/api/session")
    def session() -> Any:
        s = store()
        if s and s.session:
            return s.session.model_dump(mode="json")
        idle = SessionInfo(id="idle", game="Chocolate Doom (QA build) + Freedoom",
                           build="player-two-qa", started_at=datetime.now(UTC),
                           live=False)  # fmt: skip
        return idle.model_dump(mode="json")

    @app.post("/api/session/start", dependencies=[Depends(control)])
    def start(req: StartRequest | None = None) -> Any:
        req = req or StartRequest()
        o = rt.start(req.mode, req.plan, req.preset)
        return {"started": True, "live": isinstance(o, Orchestrator)}

    @app.get("/api/actions")
    def actions() -> Any:
        return dump(store().actions) if store() else []

    @app.get("/api/notes")
    def notes() -> Any:
        return dump(store().notes) if store() else []

    @app.get("/api/findings")
    def findings() -> Any:
        return dump(store().findings.values()) if store() else []

    @app.get("/api/fixes")
    def fixes() -> Any:
        return dump(store().fixes.values()) if store() else []

    @app.get("/api/narrations")
    def narrations() -> Any:
        return dump(store().narrations) if store() else []

    @app.get("/api/debrief")
    def debrief() -> Any:
        return store().debrief if store() else None

    @app.get("/api/placement")
    def placement() -> Any:
        return store().placement if store() else []

    @app.get("/api/parent/profile")
    def parent_profile() -> Any:
        return _mock("GET /api/parent/profile")  # T21/T22 replace the mock

    @app.get("/api/parent/report")
    def parent_report() -> Any:
        return _mock("GET /api/parent/report")

    @app.post("/api/intent", dependencies=[Depends(control)])
    def intent(i: VoiceIntent) -> Any:
        if not rt.current:
            raise HTTPException(409, "no session")
        rt.current.intent(i)
        return {"ok": True}

    @app.post("/api/transcript", dependencies=[Depends(control)])
    def transcript(t: TranscriptPayload) -> Any:
        info = getattr(rt.current, "info", None)
        if not info or info.state in ("stopped", "done", "error"):
            raise HTTPException(409, "no running session")
        rt.current.publish(SseType.transcript, t)
        return {"ok": True}

    def live() -> bool:
        info = getattr(rt.current, "info", None)
        return bool(info) and info.state not in ("stopped", "done", "error")

    @app.get("/api/ptt")
    def ptt_state() -> Any:
        rt.ptt = rt.ptt and live()  # the mic goes quiet when the run ends, whatever the button said
        return {"on": rt.ptt}

    @app.post("/api/ptt", dependencies=[Depends(control)])
    def ptt(p: PttPayload) -> Any:
        rt.ptt = p.on and live()
        if live():
            text = "[push-to-talk ON: speak now]" if rt.ptt else "[push-to-talk OFF]"
            rt.current.publish(SseType.transcript, TranscriptPayload(text=text, final=True))
        return {"on": rt.ptt}

    @app.post("/api/stop", dependencies=[Depends(control)])
    def stop() -> Any:
        if rt.current:
            rt.current.stop()
        return {"ok": True}

    @app.get("/api/events")
    async def events(request: Request, last_event_id: int = -1) -> StreamingResponse:
        hdr = request.headers.get("last-event-id")
        last = int(hdr) if hdr and hdr.isdigit() else last_event_id

        async def gen():
            nonlocal last
            while not await request.is_disconnected():
                bus = rt.current.bus if rt.current else None
                for ev in bus.since(last) if bus else []:  # ids grow across sessions
                    last = ev.id
                    yield sse_format(ev)
                await asyncio.sleep(0.25)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})  # fmt: skip

    shot = {"at": 0.0, "jpg": b""}
    shot_lock = threading.Lock()

    @app.get("/api/screen")
    def screen() -> Response:
        """The game window right now (at most one grab a second, shared by every viewer):
        the jury sees Doom even if H's live view asks for a login."""
        grab = getattr(getattr(rt.current, "deps", None), "screen", None)
        with shot_lock:
            if grab and time.monotonic() - shot["at"] > 1.0:
                shot["at"] = time.monotonic()
                out = rt.runs_dir / "screen.jpg"
                try:
                    got = grab(out)  # the slow fallback writes a PNG next to it
                    shot["jpg"] = got.read_bytes() if got else b""
                except Exception:  # noqa: BLE001 - no frame this second
                    shot["jpg"] = b""
            jpg = shot["jpg"] if grab else b""
        if not jpg:
            raise HTTPException(404, "no game window")
        return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/media/{path:path}")
    def media(path: str) -> FileResponse:
        drive = len(path) > 1 and path[1] == ":"  # Windows: /media/C:/...
        p = Path(path if drive else "/" + path).resolve()
        roots = [
            rt.runs_dir.resolve(),
            (ROOT / "recordings").resolve(),
            (ROOT / "eval" / "runs").resolve(),
        ]
        ok = any(p.is_relative_to(r) for r in roots) and p.suffix.lower() in MEDIA_SUFFIXES
        if not ok or any(part.startswith(".") for part in p.parts) or not p.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(p)

    try:  # kid mode in the browser at /kid/: the same link and server as the dashboard
        from voice.kid_web import create_app as kid_app

        @app.get("/kid", include_in_schema=False)
        def kid_slash() -> RedirectResponse:
            return RedirectResponse("/kid/")  # the page uses relative URLs

        app.mount("/kid", kid_app(), name="kid")
    except ImportError:
        pass
    if (DIST / "index.html").is_file():  # built with VITE_API_BASE=same-origin: one link for all
        app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
    return app


app = create_app()


def main(argv: list[str] | None = None) -> int:
    import argparse

    import uvicorn

    p = argparse.ArgumentParser(prog="python -m app.main")
    p.add_argument("--mode", choices=["live", "recorded"], default=os.environ.get("P2_MODE"))
    p.add_argument("--recording", type=Path, help="events.jsonl for RECORDED mode")
    p.add_argument("--runs", type=Path, default=Path(os.environ.get("P2_RUNS_DIR", "recordings")))
    p.add_argument("--start", action="store_true", help="start a session right away")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    rt = Runtime(a.runs.resolve(), a.mode or "recorded", a.recording)
    api = create_app(rt)
    if a.start:
        api.router.on_startup.append(lambda: rt.start() and None)
    uvicorn.run(api, host=a.host, port=a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
