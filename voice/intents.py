"""Spoken text -> VoiceIntent. Keyword rules in English and French; anything else is `steer`."""

from __future__ import annotations

import re
import unicodedata

from app.contracts import Intent, VoiceIntent

_FIX_EN = r"(fix|patch|repair|correct)\b"
_ADV_EN = r"((ever|even|really|just|bother|try|need|have) (to )?)?"
_FIX_FR = r"(corrige|repare|fixe|patche|touche)\w*"

# Order matters: the first rule that matches wins ("don't fix it" must be `no`, not `fix`).
RULES: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.stop, (r"\bstop\b", r"\barrete\w*", r"\bhalt\b", r"\bpause\b", r"\bstoppe\w*")),
    (
        Intent.no,
        (
            rf"\b(don'?t|do not|never|no need to) {_ADV_EN}{_FIX_EN}",
            rf"\bne (le |la |les |l'|pas )?{_FIX_FR}",
            rf"\b(pas|jamais) (besoin de )?{_FIX_FR}",
            r"^no\b",
            r"^nope\b",
            r"^non\b",
            r"\bnot now\b",
            r"\bpas maintenant\b",
        ),
    ),
    (
        Intent.fix,
        (
            r"\bfix\b",
            r"\bpatch\b",
            r"\brepair\b",
            r"\bcorrige\w*",
            r"\brepare\w*",
            r"\bfixe\w*",
        ),
    ),
    (Intent.skip, (r"\bskip\b", r"\bnext\b", r"\bignore\b", r"\bpasse\w*", r"\bsuivant\w*")),
    (
        Intent.explain,
        (
            r"\bexplain\b",
            r"\bwhy\b",
            r"\bwhat happened\b",
            r"\bshow me\b",
            r"\bexplique\w*",
            r"\bpourquoi\b",
            r"\bmontre\w*",
        ),
    ),
    (
        Intent.yes,
        (
            r"^yes\b",
            r"^yeah\b",
            r"^yep\b",
            r"^sure\b",
            r"^ok(ay)?\b",
            r"^oui\b",
            r"^ouais\b",
            r"^d'?accord\b",
            r"^vas[- ]y\b",
            r"^go( ahead)?\b",
        ),
    ),
]
_COMPILED = [(i, [re.compile(p) for p in ps]) for i, ps in RULES]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'")
    t = re.sub(r"[^a-z0-9' -]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_intent(
    text: str,
    *,
    language: str | None = None,
    confidence: float | None = None,
    finding_id: str | None = None,
) -> VoiceIntent | None:
    """Return the intent for a final transcript, or None for silence/noise."""
    norm = normalize(text)
    if not norm:
        return None
    intent = Intent.steer
    for candidate, patterns in _COMPILED:
        if any(p.search(norm) for p in patterns):
            intent = candidate
            break
    if intent is Intent.steer and len(norm.split()) < 2:
        return None  # a lone unknown word is more likely noise than a steering instruction
    return VoiceIntent(
        intent=intent,
        text=text.strip(),
        language=language,
        source="voice",
        confidence=confidence,
        finding_id=finding_id,
    )


def button_intent(intent: Intent | str, finding_id: str | None = None) -> VoiceIntent:
    """The dashboard fallback: every intent is also a button (`source: "button"`)."""
    return VoiceIntent(intent=Intent(intent), source="button", finding_id=finding_id)
