"""Custom tools of the H tester agent: `report_finding`, `note`, `ask_developer`.

The agent calls them by name; the SDK runs them in this process. Each call is validated into a
contract model (`Finding`, `AgentNote`). A bad call returns an error to the agent, so it can retry,
instead of crashing the session. The tester never sets `known_bug_ref`: that is the verifier's job.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from hai_agents.tools import Tool, tool
from pydantic import ValidationError

from app.contracts import AgentNote, Finding, FindingKind, Severity

NO_ANSWER = "No developer answer right now. Keep testing and decide yourself."


class TesterTools:
    __test__ = False
    def __init__(
        self,
        session_id: str = "pending",
        started_at: float | None = None,
        on_finding: Callable[[Finding], None] | None = None,
        on_note: Callable[[AgentNote], None] | None = None,
        answer: Callable[[str], str | None] | None = None,
    ):
        self.session_id = session_id
        self.started_at = time.time() if started_at is None else started_at
        self.on_finding, self.on_note, self.answer = on_finding, on_note, answer
        self.findings: list[Finding] = []
        self.notes: list[AgentNote] = []
        self.questions: list[dict[str, Any]] = []

    def _now(self) -> tuple[datetime, float]:
        now = time.time()
        return datetime.fromtimestamp(now, UTC), max(0.0, now - self.started_at)

    def report_finding(
        self,
        title: str,
        location: str,
        steps: list[str],
        expected: str,
        actual: str,
        severity: Severity = Severity.medium,
        kind: FindingKind = FindingKind.bug,
        suggested_change: str | None = None,
    ) -> dict[str, Any]:
        """Report one problem you saw on screen. `steps` must let someone else reproduce it from
        the start of the level (keys pressed, where you went, what you picked up). `expected` is
        what a correct game would show, `actual` is what you saw. kind: bug | design | placement."""
        ts, t = self._now()
        try:
            finding = Finding(
                id=f"F{len(self.findings) + 1}",
                session_id=self.session_id,
                kind=kind,
                title=title,
                location=location,
                steps=[s for s in steps if s.strip()],
                expected=expected,
                actual=actual,
                severity=severity,
                reported_at=ts,
                t_session_s=t,
                suggested_change=suggested_change,
            )
        except ValidationError as e:
            return {"ok": False, "error": _short(e)}
        self.findings.append(finding)
        if self.on_finding:
            self.on_finding(finding)
        return {"ok": True, "finding_id": finding.id}

    def note(self, text: str, tags: list[str] | None = None, location: str | None = None) -> dict:
        """Write down an observation that is not a bug: something confusing, too hard, too easy,
        or a spot where an in-game ad or poster would fit. tags e.g. confusing, too_hard,
        placement."""
        ts, t = self._now()
        try:
            n = AgentNote(
                session_id=self.session_id,
                ts=ts,
                t_session_s=t,
                text=text,
                tags=tags or [],
                location=location,
            )
        except ValidationError as e:
            return {"ok": False, "error": _short(e)}
        self.notes.append(n)
        if self.on_note:
            self.on_note(n)
        return {"ok": True}

    def ask_developer(self, question: str) -> dict[str, Any]:
        """Ask the game developer a short question (e.g. whether something is intended). You may
        get no answer; then keep testing and decide yourself."""
        ts, t = self._now()
        reply = (self.answer(question) if self.answer else None) or NO_ANSWER
        self.questions.append({"ts": ts.isoformat(), "t_session_s": t, "q": question, "a": reply})
        return {"answer": reply}

    def tools(self) -> list[Tool]:
        return [tool(self.report_finding), tool(self.note), tool(self.ask_developer)]


def _short(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
