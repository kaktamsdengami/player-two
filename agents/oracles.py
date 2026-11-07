"""Log oracles: which known bugs the hidden QA event log proves, and which one a finding is about.

Only the verifier and the eval harness use this module; the tester never sees it. A known bug is
proven when its `LogSignature` fires on a finished log. A finding is matched to a proven bug when
its own words (title, expected, actual) are about the same thing: one replay often proves several
bugs at once (any long wall fires KB4), so the log alone cannot say which one the tester saw.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.contracts import Finding, GameEvent, KnownBug
from launcher.log import signature_hits

KNOWN_BUGS = Path(__file__).resolve().parents[1] / "eval" / "known_bugs.yaml"
MIN_SCORE = 0.08

_STOP = set(
    "the and for with that this when while from into than then are was were has have its not "
    "but you your all any one two after before only also just more less like does dont didnt "
    "should would could will being been game player screen shows show stays keep keeps".split()
)


def load_known_bugs(path: Path = KNOWN_BUGS) -> list[KnownBug]:
    return [KnownBug.model_validate(b) for b in yaml.safe_load(path.read_text(encoding="utf-8"))]


@dataclass(frozen=True)
class Proof:
    bug: KnownBug
    hits: list[GameEvent]

    @property
    def first(self) -> GameEvent:
        return min(self.hits, key=lambda e: e.tic)


def proven(events: list[GameEvent], bugs: list[KnownBug]) -> list[Proof]:
    """Known bugs whose signature fires on this (finished) log, in list order."""
    out = []
    for b in bugs:
        hits = signature_hits(b.log_signature, events)
        if hits:
            out.append(Proof(b, hits))
    return out


def _stems(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w[:5] for w in words if len(w) >= 3 and w not in _STOP}


def relevance(finding: Finding, bug: KnownBug) -> float:
    """Word-stem overlap between what the tester wrote and the bug (0..1)."""
    f = _stems(" ".join([finding.title, finding.expected, finding.actual]))
    b = _stems(" ".join([bug.title, bug.expected, bug.actual]))
    return len(f & b) / len(f | b) if f and b else 0.0


def match(finding: Finding, proofs: list[Proof]) -> Proof | None:
    """The proven bug this finding is about, or None (the finding is new or not proven)."""
    scored = sorted(((relevance(finding, p.bug), i, p) for i, p in enumerate(proofs)), reverse=True)
    if scored and scored[0][0] >= MIN_SCORE:
        return scored[0][2]
    return None
