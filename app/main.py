"""T14 FastAPI app: REST snapshot + SSE stream for the dashboard (docs/CONTRACTS.md).

uvicorn app.main:app --port 8000      # P2_MODE=live | recorded (default recorded)
P2_RECORDING=eval/runs/<run>/events.jsonl for RECORDED mode
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.contracts import VoiceIntent
from app.orchestrator import Orchestrator, Recorded, sse_format
from app.routes_billing import router as billing_router

ROOT = Path(__file__).resolve().parent.parent
MOCK = ROOT / "docs" / "api-mock.json"


class StartRequest(BaseModel):
    mode: str | None = None  # "live" | "recorded"


class Runtime:
    """Holds the current session (live orchestrator or RECORDED replay)."""

    def __init__(self, runs_dir: Path, mode: str = "recorded", recording: Path | None = None):
        self.runs_dir, self.mode, self.recording = runs_dir, mode, recording
        self.current: Orchestrator | Recorded | None = None
        self.factory = None  # tests inject a factory returning an Orchestrator

    def new(self, mode: str | None = None) -> Orchestrator | Recorded:
        mode = mode or self.mode
        out = self.runs_dir / datetime.now().strftime("%Y%m%d-%H%M%S-session")
        if self.factory:
            return self.factory(out)
        if mode == "recorded":
            if not self.recording or not self.recording.exists():
                raise HTTPException(409, "no recording configured (P2_RECORDING)")
            return Recorded(self.recording, out)
        from app.orchestrator import build_live

        return build_live(out)

    def start(self, mode: str | None = None) -> Orchestrator | Recorded:
        if self.current and self.current.running:
            raise HTTPException(409, "a session is already running")
        try:
            self.current = self.new(mode)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - e.g. H busy, missing keys
            raise HTTPException(503, f"cannot start a live session: {e}") from e
        self.current.start()
        return self.current


def _mock(key: str) -> Any:
    return json.loads(MOCK.read_text())[key]


def create_app(rt: Runtime | None = None) -> FastAPI:
    rt = rt or Runtime(
        Path(os.environ.get("P2_RUNS_DIR", "recordings")).resolve(),
        os.environ.get("P2_MODE", "recorded"),
        Path(os.environ["P2_RECORDING"]) if os.environ.get("P2_RECORDING") else None,
    )
    app = FastAPI(title="PLAYER TWO")
    app.state.rt = rt
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                       allow_headers=["*"])  # fmt: skip
    app.include_router(billing_router)

    def store():
        return rt.current.store if rt.current else None

    def dump(xs: Any) -> Any:
        return [x.model_dump(mode="json") for x in xs]

    @app.get("/api/session")
    def session() -> Any:
        s = store()
        return s.session.model_dump(mode="json") if s and s.session else None

    @app.post("/api/session/start")
    def start(req: StartRequest | None = None) -> Any:
        o = rt.start(req.mode if req else None)
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

    @app.post("/api/intent")
    def intent(i: VoiceIntent) -> Any:
        if not rt.current:
            raise HTTPException(409, "no session")
        rt.current.intent(i)
        return {"ok": True}

    @app.post("/api/stop")
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
            bus = None
            while not await request.is_disconnected():
                if rt.current and rt.current.bus is not bus:
                    bus, last = rt.current.bus, (last if bus is None else -1)
                for ev in bus.since(last) if bus else []:
                    last = ev.id
                    yield sse_format(ev)
                await asyncio.sleep(0.25)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})  # fmt: skip

    @app.get("/media/{path:path}")
    def media(path: str) -> FileResponse:
        p = Path("/" + path).resolve()
        roots = [rt.runs_dir.resolve(), ROOT.resolve()]
        if not any(p.is_relative_to(r) for r in roots) or not p.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(p)

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
