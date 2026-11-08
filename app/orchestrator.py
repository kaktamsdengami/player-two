"""T14 orchestrator: one process drives a whole PLAYER TWO session.

explore (one long H session) -> finding -> verify -> present (voice + clip) -> wait for the
developer -> fix (Devin) -> re-verify -> next finding -> follow-up message to the same H session.

Every state change goes through `Orchestrator.publish`: the in-memory `Store` (REST snapshot) and
the `Bus` (SSE stream, persisted as events.jsonl so a run can be replayed later as RECORDED).
The core is pure; `build_live()` wires the real tester, verifier, narration and fix loop.
"""

from __future__ import annotations

import itertools
import json
import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.contracts import (
    AgentAction,
    AgentNote,
    Finding,
    FindingStatus,
    FixAttempt,
    FixResult,
    Intent,
    Narration,
    SessionInfo,
    SessionState,
    SseEvent,
    SseType,
    VoiceIntent,
)

FOLLOW_UP = (
    "Keep testing the same level. Try what you have not tried yet: other power-ups, other walls, "
    "other doors. Report every new bug with report_finding."
)


def follow_up(fixed: list[Finding]) -> str:
    """The next round's message: re-test what was just fixed (in the tester's own words) first."""
    if not fixed:
        return FOLLOW_UP
    bugs = "; ".join(f'"{f.title}" (you saw it by: {" / ".join(f.steps)})' for f in fixed)
    return (
        f"The developer installed a new build that should fix: {bugs}. The level restarted from "
        "the beginning. Check the fix first: go straight back there the same way (turn to face "
        "where you saw it and walk straight to it; shoot only if a monster is already in the "
        "centre of the screen, never turn away to chase one), do the same again and look closely. "
        "If it still happens, report it with report_finding; if it is fixed, say so with "
        "note. " + FOLLOW_UP
    )


DECIDE = {Intent.fix, Intent.yes, Intent.skip, Intent.no, Intent.stop}


def _now() -> datetime:
    return datetime.now(UTC)


class Bus:
    """Append-only SSE event list; thread-safe, optionally persisted as JSONL."""

    _ids = itertools.count()  # process-wide, so ids keep growing across sessions (Last-Event-ID)

    def __init__(self, path: Path | None = None):
        self.events: list[SseEvent] = []
        self.path = path
        self._lock = threading.Lock()

    def publish(self, type_: SseType, data: dict[str, Any], session_id: str | None) -> SseEvent:
        with self._lock:
            ev = SseEvent(id=next(Bus._ids), type=type_, ts=_now(), session_id=session_id,
                          data=data)  # fmt: skip
            self.events.append(ev)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(ev.model_dump_json() + "\n")
        return ev

    def since(self, last_id: int = -1) -> list[SseEvent]:
        with self._lock:
            return [e for e in self.events if e.id > last_id]


def sse_format(ev: SseEvent) -> str:
    kind = getattr(ev.type, "value", ev.type)
    return f"id: {ev.id}\nevent: {kind}\ndata: {ev.model_dump_json()}\n\n"


@dataclass
class Store:
    """What the REST endpoints return; rebuilt from the event stream (live or recorded)."""

    session: SessionInfo | None = None
    actions: list[AgentAction] = field(default_factory=list)
    notes: list[AgentNote] = field(default_factory=list)
    findings: dict[str, Finding] = field(default_factory=dict)
    fixes: dict[str, FixAttempt] = field(default_factory=dict)
    narrations: list[Narration] = field(default_factory=list)
    debrief: dict[str, Any] | None = None
    placement: list[dict[str, Any]] = field(default_factory=list)

    def apply(self, ev: SseEvent) -> None:
        d, t = ev.data, ev.type
        if t == SseType.session_state:
            self.session = SessionInfo.model_validate(d)
        elif t == SseType.agent_action:
            self.actions.append(AgentAction.model_validate(d))
        elif t == SseType.agent_note:
            self.notes.append(AgentNote.model_validate(d))
        elif t in (SseType.finding_new, SseType.finding_updated):
            f = Finding.model_validate(d)
            self.findings[f.id] = f
        elif t == SseType.fix_updated:
            a = FixAttempt.model_validate(d)
            self.fixes[a.id] = a
        elif t == SseType.narration:
            self.narrations.append(Narration.model_validate(d))
        elif t == SseType.debrief_ready:
            self.debrief = d
        elif t == SseType.placement_ready:
            self.placement.append(d)


class Explorer(Protocol):
    """One long H session (agents.tester.Tester behind an adapter)."""

    def start(self, task: str | None) -> tuple[str, str | None]: ...
    def follow(self, on_action: Callable[[AgentAction], None]) -> None: ...
    def send(self, message: str) -> None: ...
    def stop(self) -> None: ...


@dataclass
class Deps:
    explorer: Explorer
    verify: Callable[[Finding, list[AgentAction]], Finding]
    narrate: Callable[[Finding, Path], Narration]
    fix: Callable[[Finding, Callable[[FixAttempt], None]], FixAttempt]
    game: str = "Chocolate Doom (QA build) + Freedoom"
    build: str = "player-two-qa"
    map: str | None = "E3M1"
    speed: str = "frame-step"
    run_dir: Path | None = None  # the game's QA log + recording; tester_run.json goes there
    replay: dict[str, str] = field(default_factory=dict)  # speed/start for later verifier runs
    debrief: Callable[[Path], Any] | None = None  # insights.debrief.build
    placement: Callable[[Path], list[Any]] | None = None  # insights.placement.scout


class Stopped(Exception):
    pass


class Orchestrator:
    def __init__(
        self,
        deps: Deps,
        out_dir: Path,
        rounds: int = 3,
        approval_timeout_s: float = 600,
        task: str | None = None,
    ):
        self.deps, self.out_dir, self.rounds, self.task = deps, out_dir, rounds, task
        self.approval_timeout_s = approval_timeout_s
        out_dir.mkdir(parents=True, exist_ok=True)
        self.bus = Bus(out_dir / "events.jsonl")
        self.store = Store()
        self.intents: queue.Queue[VoiceIntent] = queue.Queue()
        self.pending: queue.Queue[Finding] = queue.Queue()
        self.fixed: list[Finding] = []  # since the last round: the next round re-tests them
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.info = SessionInfo(
            id=f"s-{uuid.uuid4().hex[:8]}", game=deps.game, build=deps.build, map=deps.map,
            started_at=_now(), speed=deps.speed, live=True,
        )  # fmt: skip

    # ------------------------------------------------------------------ events
    def publish(self, type_: SseType, model: Any) -> SseEvent:
        data = model.model_dump(mode="json") if hasattr(model, "model_dump") else dict(model)
        ev = self.bus.publish(type_, data, self.info.id)
        self.store.apply(ev)
        return ev

    def set_state(self, state: SessionState, **update: Any) -> None:
        update |= {"state": state, "findings": len(self.store.findings),
                   "steps": len(self.store.actions)}  # fmt: skip
        self.info = self.info.model_copy(update=update)
        self.publish(SseType.session_state, self.info)

    def error(self, message: str, where: str) -> None:
        self.publish(SseType.error, {"message": message, "where": where})

    # ------------------------------------------------------------------ inputs
    def on_action(self, a: AgentAction) -> None:
        self.publish(SseType.agent_action, a)

    def on_note(self, n: AgentNote) -> None:
        self.publish(SseType.agent_note, n)

    def on_finding(self, f: Finding) -> None:
        self.publish(SseType.finding_new, f)
        self.pending.put(f)

    def intent(self, i: VoiceIntent) -> None:
        self.publish(SseType.intent, i)
        if i.intent == Intent.stop:
            self.stop()
        elif i.intent == Intent.steer and i.text:
            try:
                self.deps.explorer.send(i.text)
            except Exception as e:  # noqa: BLE001 - steering is best effort
                self.error(str(e), "steer")
        else:
            self.intents.put(i)

    # ------------------------------------------------------------------ lifecycle
    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            raise RuntimeError("a session is already running")
        self._thread = threading.Thread(target=self.run, name="orchestrator", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        """Cancel the H session (within 5 s) and end the run as `stopped`."""
        if self._stop.is_set():
            return
        self._stop.set()
        t = threading.Thread(target=self._cancel_h, daemon=True)
        t.start()
        t.join(timeout_s)
        if self.info.state not in (SessionState.done, SessionState.error):
            self.set_state(SessionState.stopped)

    def _cancel_h(self) -> None:
        try:
            self.deps.explorer.stop()
        except Exception as e:  # noqa: BLE001
            self.error(f"H cancel failed: {e}", "stop")

    def _check(self) -> None:
        if self._stop.is_set():
            raise Stopped

    def run(self) -> None:
        try:
            self.set_state(SessionState.exploring)
            h_id, share = self.deps.explorer.start(self.task)
            if self._stop.is_set():  # stop arrived while the H session was being created
                self._cancel_h()
                raise Stopped
            self.set_state(SessionState.exploring, h_session_id=h_id, share_url=share)
            for r in range(self.rounds):
                self._check()
                if r:
                    self.deps.explorer.send(follow_up(self.fixed))
                    self.fixed = []
                    self.set_state(SessionState.exploring)
                self.deps.explorer.follow(self.on_action)
                self._check()
                while not self.pending.empty():
                    self.handle(self.pending.get())
            self._cancel_h()  # release the H slots and close the game
            self.set_state(SessionState.debriefing)
            self.debrief()
            self.set_state(SessionState.done)
        except Stopped:
            pass
        except Exception as e:  # noqa: BLE001 - the dashboard shows it
            if self._stop.is_set():
                return
            self.error(str(e), "orchestrator")
            self.set_state(SessionState.error)
            self._cancel_h()

    def debrief(self) -> None:
        """Design debrief + placement scout on this run; each is best effort."""
        run_dir = self.deps.run_dir or self.out_dir / "run"
        rec = run_dir / "recording.mp4"
        summary = {
            "session_id": self.info.h_session_id or self.info.id,
            "findings": [f.model_dump(mode="json") for f in self.store.findings.values()],
            "notes": [n.model_dump(mode="json") for n in self.store.notes],
            "recording": str(rec) if rec.exists() else None,
        } | self.deps.replay
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "tester_run.json").write_text(json.dumps(summary, indent=2))
        except OSError as e:
            self.error(f"could not write tester_run.json: {e}", "debrief")
            return
        if self.deps.debrief:
            self._check()
            try:
                self.publish(SseType.debrief_ready, self.deps.debrief(run_dir))
            except Exception as e:  # noqa: BLE001
                self.error(f"debrief failed: {e}", "debrief")
        if self.deps.placement:
            self._check()
            try:
                for spot in self.deps.placement(run_dir):
                    self.publish(SseType.placement_ready, spot)
            except Exception as e:  # noqa: BLE001
                self.error(f"placement scout failed: {e}", "placement")

    def handle(self, f: Finding) -> None:
        self._check()
        self.set_state(SessionState.verifying)
        f = self.deps.verify(f, list(self.store.actions))
        self.publish(SseType.finding_updated, f)
        if f.status != FindingStatus.verified:
            return
        self._check()
        self._drain_intents()  # a "fix it" said before this finding must not approve it
        self.set_state(SessionState.presenting)
        try:
            self.publish(SseType.narration, self.deps.narrate(f, self.out_dir / "voice"))
        except Exception as e:  # noqa: BLE001 - the clip still plays without a voice
            self.error(f"narration failed: {e}", "narrate")
        # a voice "fix it" heard during the narration does not count; Skip and button presses do
        self._drain_intents(
            keep=lambda i: i.source == "button" or i.intent in (Intent.skip, Intent.no)
        )
        f = f.model_copy(update={"status": FindingStatus.presented})
        self.publish(SseType.finding_updated, f)
        self.set_state(SessionState.awaiting_approval)
        approved = self.wait_for_fix()
        self._drain_intents()  # repeated transcripts of the same "fix it" must not carry over
        if not approved:
            return
        f = f.model_copy(update={"status": FindingStatus.fixing})
        self.publish(SseType.finding_updated, f)
        self.set_state(SessionState.fixing)

        def update(a: FixAttempt) -> None:
            if a.result == FixResult.merged and self.info.state != SessionState.reverifying:
                self.set_state(SessionState.reverifying)
            self.publish(SseType.fix_updated, a)

        try:
            a = self.deps.fix(f, update)
        except Exception as e:  # noqa: BLE001 - one failed fix must not end the session
            self.error(f"fix failed: {e}", "fix")
            self.publish(
                SseType.finding_updated, f.model_copy(update={"status": FindingStatus.presented})
            )
            return
        self.publish(SseType.fix_updated, a)
        status = FindingStatus.fixed if a.result == FixResult.fixed else FindingStatus.presented
        self.publish(SseType.finding_updated, f.model_copy(update={"status": status}))
        if status == FindingStatus.fixed:
            self.fixed.append(f)
        self._check()

    def _drain_intents(self, keep: Callable[[VoiceIntent], bool] = lambda i: False) -> None:
        kept = []
        while True:
            try:
                i = self.intents.get_nowait()
            except queue.Empty:
                break
            if keep(i):
                kept.append(i)
        for i in kept:
            self.intents.put(i)

    def wait_for_fix(self) -> bool:
        end = time.monotonic() + self.approval_timeout_s
        while time.monotonic() < end:
            self._check()
            try:
                i = self.intents.get(timeout=0.2)
            except queue.Empty:
                continue
            if i.intent in (Intent.fix, Intent.yes):
                return True
            if i.intent in (Intent.skip, Intent.no):
                return False
        return False


# ---------------------------------------------------------------------- RECORDED replay


def play_recording(
    events_file: Path, publish: Callable[[SseType, dict[str, Any]], Any], pace: float = 1.0,
    max_gap_s: float = 3.0, stop: threading.Event | None = None,
) -> None:  # fmt: skip
    """Re-publish a saved events.jsonl with its timing (gaps capped); marks every state RECORDED."""
    prev: datetime | None = None
    for line in events_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or (stop and stop.is_set()):
            continue
        ev = SseEvent.model_validate_json(line)
        if prev is not None and pace > 0:
            time.sleep(min((ev.ts - prev).total_seconds(), max_gap_s) / pace)
        prev = ev.ts
        data = dict(ev.data)
        if ev.type == SseType.session_state:
            data["live"] = False
        publish(ev.type, data)


class Recorded:
    """Orchestrator look-alike that replays a saved run (dashboard RECORDED mode)."""

    def __init__(self, events_file: Path, out_dir: Path, pace: float = 1.0):
        self.events_file, self.pace = events_file, pace
        self.bus, self.store = Bus(), Store()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.out_dir = out_dir

    def _publish(self, t: SseType, d: dict[str, Any]) -> None:
        ev = self.bus.publish(t, d, d.get("id") if t == SseType.session_state else None)
        self.store.apply(ev)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        self._thread = threading.Thread(
            target=play_recording, args=(self.events_file, self._publish, self.pace),
            kwargs={"stop": self._stop}, daemon=True,
        )  # fmt: skip
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()

    def intent(self, i: VoiceIntent) -> None:
        self._publish(SseType.intent, i.model_dump(mode="json"))


def iter_sse(bus: Bus, last_id: int = -1, poll_s: float = 0.25) -> Iterator[list[SseEvent]]:
    while True:
        evs = bus.since(last_id)
        if evs:
            last_id = evs[-1].id
        yield evs
        time.sleep(poll_s)


# ---------------------------------------------------------------------- live wiring


def build_live(out_dir: Path, episode: int = 3, map_: int = 1, task: str | None = None,
               rounds: int = 3, plan: str | None = None,
               preset: str | None = None) -> Orchestrator:  # fmt: skip
    """The real thing: H tester, QA-log verifier, ElevenLabs narration, Devin fix loop."""

    from agents.fix_loop import FixLoop, ScriptReplay, add_comparison, attach_clip
    from agents.oracles import load_known_bugs
    from agents.tester import DEFAULT_TASK, Tester, choose_region, with_plan
    from agents.tools import TesterTools
    from agents.verifier import Verifier
    from devin.client import DevinClient
    from launcher import capture
    from launcher.build import create_branch, pull_and_rebuild, qa_script
    from launcher.config import IS_WINDOWS, PRESETS, LauncherConfig, Speed
    from launcher.game import Game
    from launcher.window import refocus
    from voice.narrate import narrate

    cfg = LauncherConfig.from_env()
    if preset and preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}: {', '.join(PRESETS)}")
    if preset is not None:  # "" = free exploration even when P2_PRESET is set
        cfg.preset = preset  # every launch (tester, verifier) starts the same way
    if cfg.preset:
        episode, map_ = PRESETS[cfg.preset].map
        plan = plan or PRESETS[cfg.preset].plan
    task = with_plan(task or DEFAULT_TASK, plan)
    speed = Speed.parse("step")
    game = Game(cfg, out_dir / "game")
    bugs = {b.id: b for b in load_known_bugs()}
    scripts = {"KB1": ("qa/kb1_kb2_medikit.txt", 1, 1), "KB2": ("qa/kb1_kb2_medikit.txt", 1, 1),
               "KB3": ("qa/kb3_sky_invul_e3m1.txt", 3, 1),
               "KB4": ("qa/kb4_e1m7.txt", 1, 7)}  # fmt: skip
    run_dir = out_dir / "run"  # session-wide QA log, recording, tester_run.json
    run_dir.mkdir(parents=True, exist_ok=True)
    orch: Orchestrator

    def archive() -> None:
        """Game.start wipes the QA log: keep every round's events for the debrief heatmap."""
        if not game.running and game.log_path.exists():
            first = game.run_dir / "agent_events.jsonl"  # round 1 = the agent.lmp demo
            if not first.exists():
                first.write_text(game.log_path.read_text())
            with (run_dir / "events.jsonl").open("a") as f:
                f.write(game.log_path.read_text())
            game.log_path.unlink()

    class TesterExplorer:
        def __init__(self) -> None:
            self.tools = TesterTools(on_finding=lambda f: orch.on_finding(f),
                                     on_note=lambda n: orch.on_note(n))  # fmt: skip
            self.tester: Tester | None = None
            self.rec: Any = None
            self.win: Any = None

        def start(self, task_: str | None) -> tuple[str, str | None]:
            choose_region()  # raises HBusyError("H busy ... retry in ~15 min"): shown as error
            self.tester = Tester(tools=self.tools)  # the H client binds HAI_BASE_URL here
            win = game.start(episode, map_, speed, record=game.run_dir / "agent")
            if win is None:
                raise RuntimeError("game window did not appear")
            self.win = win
            try:  # for the placement scout; the loop runs without it
                self.rec = capture.record(win, run_dir / "recording.mp4", cfg.fps)
            except Exception as e:  # noqa: BLE001
                orch.error(f"screen recording failed: {e}", "record")
            run = self.tester.start(task=task_ or DEFAULT_TASK, max_steps=120 * rounds,
                                    max_time_s=900 * rounds, idle_timeout_s=1800)  # fmt: skip
            return run.session_id, run.share_url

        def follow(self, on_action: Callable[[AgentAction], None]) -> None:
            seen = len(self.tester.run.actions) if self.tester.run else 0
            log = out_dir / "actions.jsonl"
            start = self.tester.run.events if self.tester.run else 0
            t = threading.Thread(target=self.tester.follow, args=(log, start), daemon=True)
            t.start()
            while t.is_alive() or (self.tester.run and seen < len(self.tester.run.actions)):
                if (
                    t.is_alive() and not orch._stop.is_set() and self.win and refocus(self.win)
                ):  # a click beside the game
                    orch.error("the game lost keyboard focus: gave it back", "focus")
                acts = self.tester.run.actions if self.tester.run else []
                for a in acts[seen:]:
                    on_action(a)
                seen = len(acts)
                time.sleep(0.3)

        def send(self, message: str) -> None:
            if not game.running:
                archive()
                self.win = game.start(episode, map_, speed)
            self.tester.send(message)

        def stop(self) -> None:
            if self.tester:
                self.tester.stop()
            if self.rec:
                self.rec.stop()
                self.rec = None
            game.stop()
            archive()

    def verify(f: Finding, actions: list[AgentAction]) -> Finding:
        game.stop()
        v = Verifier(Game(cfg, out_dir / "verify"), episode, map_, speed)
        # round 1 is the recorded demo; once a later round restarted the game it no longer matches
        demo = None if (game.run_dir / "agent_events.jsonl").exists() else game.run_dir
        verdict = v.verify(
            f,
            actions,
            out_dir=out_dir / "verify" / f.id,
            demo=demo,
            demo_started_at=game.started_at,
        )
        return verdict.finding

    def fix(f: Finding, update: Callable[[FixAttempt], None]) -> FixAttempt:
        if f.known_bug_ref not in bugs or f.known_bug_ref not in scripts:
            raise RuntimeError(f"no replay script for {f.known_bug_ref or 'an unmatched finding'}")
        bug = bugs[f.known_bug_ref]
        script, ep, mp = scripts[bug.id]
        branch = f"qa-run/{orch.info.id}"
        create_branch(branch)  # GitHub API: the stage laptop has no fork clone
        fix_dir = out_dir / "fix"
        # the fixed build goes to its own folder so the next demo still runs the buggy QA build
        fix_cfg = replace(cfg, exe=fix_dir / "build" / cfg.exe.name) if IS_WINDOWS else cfg

        def rebuild(ref: str) -> Path:
            fix_cfg.exe = pull_and_rebuild(fix_cfg, ref)
            return fix_cfg.exe

        approved: list[str | None] = []

        def approve_once(a: FixAttempt) -> bool:
            """The developer's "fix it" approves one merge; a feedback-round PR stays open."""
            if orch._stop.is_set() or approved:
                return False
            approved.append(a.pr_url)
            return True

        loop = FixLoop(
            devin=DevinClient.from_env(base_branch=branch),
            replay=ScriptReplay(
                Game(fix_cfg, fix_dir), bug, qa_script(cfg, script, fix_dir), ep, mp
            ),
            rebuild=rebuild,
            approve=approve_once,
            on_update=update,
        )
        a, replay = loop.run(f)
        attach_clip(f, replay)
        a = add_comparison(a, bug)
        if a.result == FixResult.fixed:
            cfg.exe = fix_cfg.exe  # the next round plays the fixed build: the agent re-tests it
        return a

    try:  # T16 / T17: optional until merged
        from insights.debrief import build as debrief
    except ImportError:
        debrief = None
    try:
        from insights.placement import scout as placement
    except ImportError:
        placement = None

    def narrate_verified(f: Finding, out: Path) -> Narration:
        """Say what the verifier proved, on the map that was played (the agent's own words can
        be off, e.g. a wrong map name or "walls" for the sky)."""
        bug = bugs.get(f.known_bug_ref or "")
        upd = {"location": f"E{episode}M{map_}"}
        if bug:
            upd |= {"actual": bug.title, "expected": bug.expected}
        return narrate(f.model_copy(update=upd), out)

    deps = Deps(TesterExplorer(), verify, narrate_verified, fix, map=f"E{episode}M{map_}",
                run_dir=run_dir, debrief=debrief, placement=placement,
                replay={"speed": speed.spec(), "start": cfg.start, "preset": cfg.preset,
                        "plan": plan})  # fmt: skip
    orch = Orchestrator(deps, out_dir, rounds=rounds, task=task)
    return orch
