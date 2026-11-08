"""/live/: one shared Holo game for every viewer.

A single broadcaster (a headless Chromium started by this module, or any page opened with
/jury/live/broadcaster.html on the stage laptop) plays Doom with Holo and POSTs every step
(small JPEG frame + move) to /api/live/push. Viewers get the steps over the WebSocket
/api/live/ws; N viewers cost one Holo call per step, not N. When nobody broadcasts, the viewer
page falls back to its own in-browser game after a few seconds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

log = logging.getLogger("p2.live")
ROOT = Path(__file__).resolve().parent.parent
HISTORY = 24
IDLE_STOP_S = 180.0


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.history: deque[dict[str, Any]] = deque(maxlen=HISTORY)
        self.last_push = 0.0
        self.pushes = 0
        self.last_viewer = 0.0
        self.proc: subprocess.Popen[bytes] | None = None
        self.started_at = 0.0

    def push(self, step: dict[str, Any]) -> int:
        self.last_push = time.time()
        self.pushes += 1
        step["t"] = self.last_push
        self.history.append(step)
        return len(self.clients)

    async def fanout(self, step: dict[str, Any]) -> None:
        data = json.dumps(step)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    @property
    def live(self) -> bool:
        return time.time() - self.last_push < 15

    def status(self) -> dict[str, Any]:
        return {
            "live": self.live,
            "viewers": len(self.clients),
            "pushes": self.pushes,
            "age_s": round(time.time() - self.last_push, 1) if self.last_push else None,
            "broadcaster": "running" if self.proc and self.proc.poll() is None else "off",
        }

    # ---------------------------------------------------------------- headless broadcaster
    def want_broadcaster(self) -> bool:
        return os.environ.get("P2_LIVE_BROADCAST", "1") not in ("0", "false", "")

    def ensure_broadcaster(self, base: str) -> None:
        if not self.want_broadcaster() or self.live:
            return
        if self.proc and self.proc.poll() is None:
            if time.time() - self.started_at < 60:
                return
            self.proc.kill()
        cmd = [sys.executable, str(ROOT / "scripts" / "live_broadcaster.py"), "--url", base]
        try:
            self.proc = subprocess.Popen(cmd, cwd=ROOT)
            self.started_at = time.time()
            log.info("live broadcaster started: %s", " ".join(cmd))
        except Exception as e:  # noqa: BLE001
            log.warning("live broadcaster failed to start: %s", e)

    def maybe_stop(self) -> None:
        if (
            self.proc
            and self.proc.poll() is None
            and not self.clients
            and time.time() - self.last_viewer > IDLE_STOP_S
        ):
            self.proc.terminate()
            log.info("live broadcaster stopped: no viewers")


def create_router(hub: Hub | None = None) -> APIRouter:
    hub = hub or Hub()
    router = APIRouter(prefix="/api/live", tags=["live"])
    router.hub = hub  # type: ignore[attr-defined]

    def local(req: Request) -> bool:
        host = req.client.host if req.client else ""
        token = os.environ.get("P2_HOLO_PRIORITY_TOKEN", "")
        if token and req.headers.get("x-p2-priority") == token:
            return True
        return host in ("127.0.0.1", "::1", "testclient") and not req.headers.get(
            "cf-connecting-ip"
        )

    @router.get("/status")
    def status() -> dict[str, Any]:
        return hub.status()

    @router.post("/push")
    async def push(req: Request) -> dict[str, Any]:
        if not local(req):
            raise HTTPException(403, "only the broadcaster may push")
        body = await req.body()
        if len(body) > 400_000:
            raise HTTPException(413, "step too large")
        try:
            step = json.loads(body)
        except ValueError as e:
            raise HTTPException(400, "bad json") from e
        if not isinstance(step, dict):
            raise HTTPException(400, "bad step")
        n = hub.push(step)
        await hub.fanout(step)
        hub.maybe_stop()
        return {
            "viewers": n,
            "keep": bool(hub.clients) or time.time() - hub.last_viewer < IDLE_STOP_S,
        }

    @router.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        await sock.accept()
        hub.clients.add(sock)
        hub.last_viewer = time.time()
        base = f"http://127.0.0.1:{sock.url.port or 8000}"
        hub.ensure_broadcaster(base)
        try:
            await sock.send_text(
                json.dumps({"type": "hello", **hub.status(), "history": list(hub.history)})
            )
            while True:
                try:
                    await asyncio.wait_for(sock.receive_text(), timeout=20)
                except TimeoutError:
                    await sock.send_text(json.dumps({"type": "ping", **hub.status()}))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.clients.discard(sock)
            hub.last_viewer = time.time()

    return router
