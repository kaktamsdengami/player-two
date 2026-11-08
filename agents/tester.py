"""Hostile-tester agent: one H desktop session (pixels only) on the running QA build.

Usage (game window must be on this machine's screen; the SDK serves it as a `user_device` desktop):
    python -m agents.tester --map 3 1 --steps 120 --minutes 20
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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from agents.tools import TesterTools
from app.contracts import ActionKind, AgentAction

PROMPT = Path(__file__).parent / "prompts" / "tester.md"
SHELL_REFUSED = "Shell access is disabled for the tester: test the game from pixels only."


def forbid_shell() -> None:
    """Pixels only: refuse run_command_desktop on the local desktop driver (it can read logs)."""
    try:
        from hai_drivers.desktop.local.driver import LocalDesktopDriver
        from hai_drivers.desktop.models import RunCommandResponse
    except ImportError:
        return

    def refuse(self: Any, *a: Any, **kw: Any) -> RunCommandResponse:
        return RunCommandResponse(returncode=126, stdout="", stderr=SHELL_REFUSED)

    LocalDesktopDriver.run_command = refuse  # type: ignore[method-assign]


AGENT_NAME = "player-two-tester"
MODEL = "holo4-35b-a3b"  # H's fastest; override with P2_TESTER_MODEL
DEFAULT_TASK = (
    "Test this level like a hostile QA tester. Explore, provoke the game, and report every bug "
    "you find with report_finding. Finish with a short summary."
)


def with_plan(task: str, plan: str | None) -> str:
    """A developer's focus area (a test plan names an area, never a bug); none: free exploration."""
    return f"{task}\n\nThe developer asks you to focus on: {plan.strip()}" if plan else task


class TesterAnswer(BaseModel):
    summary: str
    finding_titles: list[str]


REGIONS = ("https://agp.hcompany.ai", "https://agp.eu.hcompany.ai")
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class HBusyError(RuntimeError):
    """No region has enough free H slots; retry later (a desktop slot leaks ~15 min)."""


LIVE = ("queued", "pending", "running", "paused", "idle", "awaiting_tool_results")
STREAM_RETRIES = 5


def base_url() -> str:
    return os.environ.get("HAI_BASE_URL", REGIONS[0]).rstrip("/")


def with_retry(fn: Any, tries: int = 4, base_s: float = 2.0, sleep: Any = time.sleep) -> Any:
    """Call `fn()`, retrying 429/5xx and timeouts with exponential backoff."""
    for i in range(tries):
        try:
            return fn()
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if isinstance(e, httpx.HTTPStatusError) and code not in RETRY_STATUS:
                raise
            if i == tries - 1:
                raise
            sleep(base_s * 2**i)
    raise AssertionError("unreachable")


def quota(api_key: str | None = None, url: str | None = None) -> dict[str, Any]:
    key = api_key or os.environ["HAI_API_KEY"]

    def get() -> dict[str, Any]:
        r = httpx.get(
            f"{url or base_url()}/api/v2/sessions/quota",
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return with_retry(get)


def choose_region(min_slots: int = 2, quota_fn: Any = None) -> str:
    """First region (HAI_BASE_URL first) with `min_slots` free; sets HAI_BASE_URL to it."""
    quota_fn = quota_fn or (lambda url: quota(url=url))
    allowed = os.environ.get("HAI_REGIONS")  # e.g. only US when EU desktop sessions stall
    regions = [r.strip().rstrip("/") for r in (allowed or "").split(",") if r.strip()] or REGIONS
    order = [base_url()] + [r for r in regions if r != base_url()]
    order = [r for r in order if r in regions]
    seen = {}
    for url in order:
        try:
            seen[url] = quota_fn(url).get("available", 0)
        except httpx.HTTPError as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code and 400 <= code < 500 and code != 404 and code not in RETRY_STATUS:
                raise  # a bad key or request fails in every region; waiting won't help
            seen[url] = f"error: {type(e).__name__}"
            continue
        if seen[url] >= min_slots:
            os.environ["HAI_BASE_URL"] = url
            return url
    raise HBusyError(f"H busy (free slots per region: {seen}); retry in ~15 min")


def agent_spec(tools: TesterTools, instructions: str | None = None) -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": "Hostile QA tester for a Doom QA build; sees pixels only.",
        "model": os.environ.get("P2_TESTER_MODEL") or MODEL,
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
        dur = args.get("duration_ms")
        if dur is None and args.get("duration") is not None:
            dur = float(args["duration"]) * 1000
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
                duration_ms=int(dur) if dur is not None and kind == ActionKind.key_hold else None,
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
        if sys.platform.startswith("linux") and not os.environ.get("WAYLAND_DISPLAY"):
            os.environ.setdefault("XDG_SESSION_TYPE", "x11")  # pyscreeze: scrot on bare X11
        forbid_shell()
        if client is None:
            from hai_agents import Client

            client = Client(api_key=os.environ["HAI_API_KEY"], base_url=base_url(), timeout=120)
        self.client = client
        self.tools = tools or TesterTools()
        self.handle: Any = None
        self.run: TesterRun | None = None
        self.created_after: datetime | None = None

    def start(
        self,
        task: str = DEFAULT_TASK,
        max_steps: int = 120,
        max_time_s: float = 1200,
        idle_timeout_s: int = 600,
        min_slots: int = 2,
    ) -> TesterRun:
        q = quota()
        if q.get("available", 0) < min_slots:
            raise RuntimeError(f"H quota too low for a desktop session: {q}")
        self.tools.started_at = time.time()
        self.created_after = datetime.now(UTC) - timedelta(seconds=10)
        try:
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
        except Exception:
            self.sweep()  # the create call can fail after the server already started the session
            raise
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
        start = self.run.events
        try:
            for _ in range(STREAM_RETRIES):
                try:
                    for ev in self.handle.stream(from_index=from_index + self.run.events - start):
                        self.run.events += 1
                        for a in to_action(
                            self.handle.id, len(self.run.actions), self.tools.started_at, ev
                        ):
                            self.run.actions.append(a)
                            if f:
                                f.write(a.model_dump_json() + "\n")
                                f.flush()
                    break
                except httpx.TimeoutException:  # a slow first step: reconnect where we left off
                    continue
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
        elif self.created_after:
            self.sweep()

    def sweep(self) -> list[str]:
        """Cancel this tester's live H sessions that have no handle, so none drives the desktop."""
        try:
            page = self.client.sessions.list_sessions(
                agent=AGENT_NAME, created_after=self.created_after, status=list(LIVE)
            )
        except Exception:  # noqa: BLE001 - best effort; the caller reports its own error
            return []
        ids = []
        for s in page.items:
            if s.status not in LIVE:
                continue
            try:
                self.client.sessions.cancel_session(s.id)
                ids.append(s.id)
            except Exception:  # noqa: BLE001
                pass
        return ids


def main(argv: list[str] | None = None) -> int:
    from launcher.config import PRESETS, LauncherConfig, Speed
    from launcher.game import Game

    p = argparse.ArgumentParser(prog="python -m agents.tester")
    p.add_argument("--map", nargs=2, type=int, metavar=("EPISODE", "MAP"), help="default E3M1")
    p.add_argument("--speed", default="step")
    p.add_argument("--steps", type=int, default=120)  # ~6-7 s each: fits 20 min
    p.add_argument("--minutes", type=float, default=20)
    p.add_argument("--task", default=DEFAULT_TASK)
    p.add_argument("--plan", help="developer's focus area, appended to the task")
    p.add_argument("--preset", choices=sorted(PRESETS), help="QA start preset (map, spawns, plan)")
    a = p.parse_args(argv)
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True))
    try:
        print(f"H region: {choose_region()}", flush=True)
    except HBusyError as e:
        raise SystemExit(str(e)) from None
    cfg = LauncherConfig.from_env()
    cfg.preset = a.preset or cfg.preset
    preset = PRESETS.get(cfg.preset)
    if preset and a.map and tuple(a.map) != preset.map:
        raise SystemExit(
            f"preset {cfg.preset} runs on E{preset.map[0]}M{preset.map[1]}: drop --map"
        )
    a.map = a.map or (list(preset.map) if preset else [3, 1])
    plan = a.plan or (preset.plan if preset else None)
    run_dir = (cfg.runs_dir / f"{datetime.now():%Y%m%d-%H%M%S}-tester").resolve()
    game = Game(cfg, run_dir)
    speed = Speed.parse(a.speed)
    if not speed.tics:
        raise SystemExit("the tester prompt assumes frame-step: use --speed step[:N]")
    win = game.start(a.map[0], a.map[1], speed, record=run_dir / "agent")
    if win is None:
        game.stop()
        raise SystemExit("game window did not appear")
    from launcher import capture

    rec = capture.record(win, run_dir / "recording.mp4", cfg.fps)
    tester = Tester()
    try:
        task = with_plan(a.task, plan)
        run = tester.start(task, a.steps, a.minutes * 60, idle_timeout_s=60)
        print(json.dumps({"session_id": run.session_id, "share_url": run.share_url}), flush=True)
        run = tester.follow(run_dir / "actions.jsonl")
    except BaseException:
        tester.stop()
        raise
    finally:
        rec.stop()
        game.stop()
    out = run.summary() | {
        "run_dir": str(run_dir),
        "recording": str(rec.path),
        "speed": speed.spec(),
        "game_started_at": game.started_at,
        "start": cfg.start,
        "preset": cfg.preset,
        "plan": plan,
        "map": a.map,
    }
    (run_dir / "tester_run.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
