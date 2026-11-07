"""Hostile-tester agent: one H desktop session (pixels only) on the running QA build.

Usage (game window must be on this machine's screen; the SDK serves it as a `user_device` desktop):
    python -m agents.tester --map 3 1 --steps 60 --minutes 15
The tester never receives the known-bug list or the event log. The launcher records the screen and
keeps the hidden event log for the verifier (T08).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from agents.tools import TesterTools
from app.contracts import ActionKind, AgentAction

PROMPT = Path(__file__).parent / "prompts" / "tester.md"
AGENT_NAME = "player-two-tester"
MODEL = "holo4-27b"
DEFAULT_TASK = (
    "Test this level like a hostile QA tester. Explore, provoke the game, and report every bug "
    "you find with report_finding. Finish with a short summary."
)


class TesterAnswer(BaseModel):
    summary: str
    finding_titles: list[str]


def base_url() -> str:
    return os.environ.get("HAI_BASE_URL", "https://agp.hcompany.ai").rstrip("/")


def quota(api_key: str | None = None) -> dict[str, Any]:
    key = api_key or os.environ["HAI_API_KEY"]
    r = httpx.get(
        f"{base_url()}/api/v2/sessions/quota",
        headers={"Authorization": f"Bearer {key}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def agent_spec(tools: TesterTools, instructions: str | None = None) -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": "Hostile QA tester for a Doom QA build; sees pixels only.",
        "model": MODEL,
        "instructions": instructions or PROMPT.read_text(encoding="utf-8"),
        "environments": [{"id": "desktop", "kind": "desktop", "host": "user_device"}],
    }


_KEY_TOOLS = {"key", "press", "press_key", "hotkey", "key_press"}


def to_action(session_id: str, step: int, started: float, event: Any) -> list[AgentAction]:
    """One `AgentAction` per tool request in a policy step (timestamped for clip cuts)."""
    data = getattr(event, "data", None)
    data = data.model_dump() if hasattr(data, "model_dump") else data
    if not isinstance(data, dict) or not data.get("tool_reqs"):
        return []
    ts = getattr(event, "timestamp", None) or datetime.now(UTC)
    out = []
    for req in data["tool_reqs"]:
        name, args = req.get("tool_name", ""), req.get("args") or {}
        keys = args.get("keys") or args.get("key") or []
        keys = [keys] if isinstance(keys, str) else list(keys)
        if name in {"report_finding", "note", "ask_developer"}:
            kind = ActionKind.tool_call
        elif "hold" in name or args.get("duration") or args.get("duration_ms"):
            kind = ActionKind.key_hold
        elif name in _KEY_TOOLS or keys:
            kind = ActionKind.key_press
        elif "click" in name:
            kind = ActionKind.click
        elif "type" in name or "write" in name:
            kind = ActionKind.type_text
        elif "wait" in name:
            kind = ActionKind.wait
        else:
            kind = ActionKind.other
        out.append(
            AgentAction(
                session_id=session_id,
                step=step,
                ts=ts,
                t_session_s=max(0.0, ts.timestamp() - started),
                kind=kind,
                keys=[str(k) for k in keys],
                description=f"{name} {json.dumps(args, default=str)[:200]}",
            )
        )
    return out


@dataclass
class TesterRun:
    session_id: str
    share_url: str | None
    status: str
    answer: Any
    tools: TesterTools
    actions: list[AgentAction] = field(default_factory=list)
    events: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "share_url": self.share_url,
            "status": self.status,
            "answer": self.answer.model_dump()
            if hasattr(self.answer, "model_dump")
            else self.answer,
            "findings": [f.model_dump(mode="json") for f in self.tools.findings],
            "notes": [n.model_dump(mode="json") for n in self.tools.notes],
            "questions": self.tools.questions,
            "actions": len(self.actions),
            "events": self.events,
        }


class Tester:
    """Runs and steers one long H session; send follow-ups instead of new sessions."""

    def __init__(self, client: Any = None, tools: TesterTools | None = None):
        if client is None:
            from hai_agents import Client

            client = Client(api_key=os.environ["HAI_API_KEY"], base_url=base_url())
        self.client = client
        self.tools = tools or TesterTools()
        self.handle: Any = None
        self.run: TesterRun | None = None

    def start(
        self,
        task: str = DEFAULT_TASK,
        max_steps: int = 60,
        max_time_s: float = 900,
        idle_timeout_s: int = 600,
        min_slots: int = 2,
    ) -> TesterRun:
        q = quota()
        if q.get("available", 0) < min_slots:
            raise RuntimeError(f"H quota too low for a desktop session: {q}")
        self.tools.started_at = time.time()
        self.handle = self.client.start_session(
            agent=agent_spec(self.tools),
            messages=task,
            max_steps=max_steps,
            max_time_s=max_time_s,
            idle_timeout_s=idle_timeout_s,
            queue=False,
            tools=self.tools.tools(),
            answer_schema=TesterAnswer,
        )
        self.tools.session_id = self.handle.id
        share = None
        try:
            share = self.client.sessions.share_session(self.handle.id).share_url
            share = f"{base_url()}{share}" if share.startswith("/") else share
        except Exception:  # noqa: BLE001 - the share link is a nice-to-have
            pass
        self.run = TesterRun(self.handle.id, share, "running", None, self.tools)
        return self.run

    def follow(self, log_path: Path | None = None, from_index: int = 0) -> TesterRun:
        """Stream events until the session settles; tool calls run here. Returns the run."""
        assert self.handle and self.run
        f = log_path.open("a", encoding="utf-8") if log_path else None
        try:
            for ev in self.handle.stream(from_index=from_index):
                self.run.events += 1
                for a in to_action(
                    self.handle.id, len(self.run.actions), self.tools.started_at, ev
                ):
                    self.run.actions.append(a)
                    if f:
                        f.write(a.model_dump_json() + "\n")
                        f.flush()
        finally:
            if f:
                f.close()
        result = self.handle.wait_for_completion()
        self.run.status, self.run.answer = str(result.status), result.answer
        return self.run

    def send(self, message: str) -> None:
        assert self.handle
        self.handle.send_message(message)

    def stop(self) -> None:
        if self.handle:
            self.handle.cancel()


def main(argv: list[str] | None = None) -> int:
    from launcher.config import LauncherConfig, Speed
    from launcher.game import Game

    if sys.platform.startswith("linux") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("XDG_SESSION_TYPE", "x11")  # pyscreeze: use scrot on bare X11
    p = argparse.ArgumentParser(prog="python -m agents.tester")
    p.add_argument("--map", nargs=2, type=int, default=[3, 1], metavar=("EPISODE", "MAP"))
    p.add_argument("--speed", default="step:35")
    p.add_argument("--steps", type=int, default=60)
    p.add_argument("--minutes", type=float, default=15)
    p.add_argument("--task", default=DEFAULT_TASK)
    a = p.parse_args(argv)
    cfg = LauncherConfig.from_env()
    run_dir = (cfg.runs_dir / f"{datetime.now():%Y%m%d-%H%M%S}-tester").resolve()
    game = Game(cfg, run_dir)
    win = game.start(a.map[0], a.map[1], Speed.parse(a.speed))
    if win is None:
        game.stop()
        raise SystemExit("game window did not appear")
    from launcher import capture

    rec = capture.record(win, run_dir / "recording.mp4", cfg.fps)
    tester = Tester()
    try:
        run = tester.start(a.task, a.steps, a.minutes * 60, idle_timeout_s=60)
        print(json.dumps({"session_id": run.session_id, "share_url": run.share_url}), flush=True)
        run = tester.follow(run_dir / "actions.jsonl")
    finally:
        rec.stop()
        game.stop()
    out = run.summary() | {"run_dir": str(run_dir), "recording": str(rec.path)}
    (run_dir / "tester_run.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
