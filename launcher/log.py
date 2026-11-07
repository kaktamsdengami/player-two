"""Tail and query the QA build's JSONL event log (`-qa-log`). Never handed to the tester agent."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.contracts import EventMatch, GameEvent, LogSignature

_OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a is not None and a > b,
    "ge": lambda a, b: a is not None and a >= b,
    "lt": lambda a, b: a is not None and a < b,
    "le": lambda a, b: a is not None and a <= b,
    "in": lambda a, b: a in b,
    "exists": lambda a, b: (a is not None) == bool(b),
}


def _get(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def event_matches(m: EventMatch, ev: GameEvent) -> bool:
    if ev.type != m.type:
        return False
    d = ev.model_dump()
    for path, cond in m.where.items():
        value = _get(d, path)
        conds = cond if isinstance(cond, dict) else {"eq": cond}
        if not all(_OPS[op](value, want) for op, want in conds.items()):
            return False
    return True


def signature_hits(
    sig: LogSignature, events: list[GameEvent], until_tic: int | None = None
) -> list[GameEvent] | None:
    """The events that prove `sig` (one per `all_of` entry, in any order), or None.

    `until_tic` is how far a still-growing log is known to reach: a `none_of` window that is
    still open there proves nothing yet. Leave it None for a finished log."""
    hits = [[e for e in events if event_matches(m, e)] for m in sig.all_of]
    if not all(hits):
        return None

    def clean(lo: float, hi: float) -> bool:
        return not any(
            event_matches(n, e) and lo <= e.tic <= hi for n in sig.none_of for e in events
        )

    if sig.within_tics is None:
        if sig.none_of and until_tic is not None:
            return None  # absence over the whole run needs the finished log
        return [h[0] for h in hits] if clean(float("-inf"), float("inf")) else None
    for lo in sorted({e.tic for h in hits for e in h}):
        hi = lo + sig.within_tics
        picked = [next((e for e in h if lo <= e.tic <= hi), None) for h in hits]
        if any(e is None for e in picked):
            continue
        if sig.none_of and until_tic is not None and hi > until_tic:
            continue
        if clean(lo, hi):
            return picked  # type: ignore[return-value]
    return None


class EventLog:
    """Incremental reader: `poll()` returns lines written since the last call."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._pos = 0
        self._partial = ""
        self.events: list[GameEvent] = []

    def poll(self) -> list[GameEvent]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            f.seek(self._pos)
            chunk = f.read()
            self._pos = f.tell()
        lines = (self._partial + chunk).split("\n")
        self._partial = lines.pop()  # unfinished last line, completed by the next poll
        new = [GameEvent.model_validate(json.loads(line)) for line in lines if line.strip()]
        self.events += new
        return new

    def since(self, t: float | None = None, tic: int | None = None) -> list[GameEvent]:
        self.poll()
        return list(_since(self.events, t, tic))

    def tail(self, n: int = 20) -> list[GameEvent]:
        self.poll()
        return self.events[-n:]

    def find(self, match: EventMatch, t: float | None = None) -> list[GameEvent]:
        return [e for e in self.since(t) if event_matches(match, e)]

    def happened(self, sig: LogSignature, since_t: float | None = None) -> list[GameEvent] | None:
        """Has signature `sig` happened since game time `since_t`? Returns the proving events."""
        return signature_hits(sig, self.since(since_t))

    def wait_for(
        self, sig: LogSignature, timeout: float, since_t: float | None = None, every: float = 0.2
    ) -> list[GameEvent] | None:
        """Poll a live log. While polling, a `none_of` only counts once the log has passed its
        window. At the timeout the log is taken as final (quiet tics write no events)."""
        end = time.monotonic() + timeout
        while True:
            final = time.monotonic() >= end
            events = self.since(since_t)
            last = self.events[-1].tic if self.events else 0
            hits = signature_hits(sig, events, until_tic=None if final else last)
            if hits or final:
                return hits
            time.sleep(every)


def _since(events: Iterable[GameEvent], t: float | None, tic: int | None) -> Iterable[GameEvent]:
    for e in events:
        if t is not None and (e.t is None or e.t < t):
            continue
        if tic is not None and e.tic < tic:
            continue
        yield e
