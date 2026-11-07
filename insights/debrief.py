"""Design debrief for one tester run: where the player died or restarted, what the agent noted,
what to change for each finding, and one or two cited design references from Linkup.

    python -m insights.debrief <run_dir> [--out debrief.json] [--no-linkup]

The run dir is what `python -m agents.tester` writes: `events.jsonl` (the game's QA log) and
`tester_run.json` (findings and notes). Verifier results (`verdicts.json`, written by
`python -m agents.verifier`) replace the tester's findings when present.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.contracts import (
    AgentNote,
    Citation,
    DebriefReport,
    Finding,
    FindingSuggestion,
    GameEvent,
    HeatCell,
)
from insights import linkup

GAME = "Chocolate Doom + Freedoom"
CELL = 128.0
TOPICS = {
    "too_hard": "difficulty spikes and fair challenge in first-person shooter level design",
    "confusing": "player navigation, landmarks and wayfinding in first-person shooter levels",
    "bug": "visual feedback and readability of power-up effects in games",
}


def load_events(path: Path) -> list[GameEvent]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(GameEvent.model_validate_json(line))
            except ValueError:
                continue
    return out


def heatmap(
    events: list[GameEvent], cell: float = CELL
) -> tuple[tuple[float, float, float, float] | None, list[HeatCell]]:
    """Deaths at the player's position; a retry is every level (re)start after the first one."""
    pts = [(e.player.x, e.player.y) for e in events if e.player]
    if not pts:
        return None, []
    xs, ys = zip(*pts, strict=True)
    # snapped to the cell grid: every cell centre is inside and the box is never zero-width
    bounds = (
        (min(xs) // cell) * cell,
        (min(ys) // cell) * cell,
        (max(xs) // cell + 1) * cell,
        (max(ys) // cell + 1) * cell,
    )
    cells: dict[tuple[int, int], HeatCell] = {}

    def at(e: GameEvent) -> HeatCell:
        k = (int(e.player.x // cell), int(e.player.y // cell))
        if k not in cells:
            cells[k] = HeatCell(x=(k[0] + 0.5) * cell, y=(k[1] + 0.5) * cell)
        return cells[k]

    seen: Counter[str] = Counter()
    for e in events:
        if not e.player:
            continue
        if e.type == "death":
            at(e).deaths += 1
        elif e.type == "level":
            seen[e.map or ""] += 1
            if seen[e.map or ""] > 1:
                at(e).retries += 1
    return bounds, sorted(cells.values(), key=lambda c: (-(c.deaths + c.retries), c.x, c.y))


def suggest(f: Finding) -> FindingSuggestion:
    if f.suggested_change:
        text = f.suggested_change
    else:
        text = f"{f.location}: {f.actual.rstrip('.')}. Change it so that {_lower(f.expected)}"
    return FindingSuggestion(finding_id=f.id, suggestion=text.rstrip(".") + ".")


def _lower(s: str) -> str:
    s = s.strip().rstrip(".")
    return s[:1].lower() + s[1:] if s else s


def topic(notes: list[AgentNote], findings: list[Finding], cells: list[HeatCell]) -> str:
    tags = Counter(t for n in notes for t in n.tags)
    if sum(c.deaths + c.retries for c in cells) >= 2:
        tags["too_hard"] += 2
    if findings:
        tags["bug"] += 1
    for tag, _ in tags.most_common():
        if tag in TOPICS:
            return TOPICS[tag]
    return TOPICS["confusing"]


def references(query: str, search: linkup.Search = linkup.search, n: int = 2) -> list[Citation]:
    try:
        hits = search(query)
    except Exception as e:  # noqa: BLE001 - the debrief is still useful without references
        print(f"linkup: {e}")
        return []
    out, hosts = [], set()
    for c in hits:
        host = c.url.split("/")[2] if "//" in c.url else c.url
        if host not in hosts:
            hosts.add(host)
            out.append(c)
        if len(out) == n:
            break
    return out


def build(
    run_dir: Path,
    search: linkup.Search | None = linkup.search,
    findings: list[Finding] | None = None,
) -> DebriefReport:
    run_dir = Path(run_dir)
    summary = _json(run_dir / "tester_run.json")
    events = load_events(run_dir / "events.jsonl")
    notes = [AgentNote.model_validate(n) for n in summary.get("notes", [])]
    if findings is None:
        findings = [Finding.model_validate(f) for f in summary.get("findings", [])]
        verified = {
            v["finding"]: Finding.model_validate(v["finding_full"])
            for v in _json(run_dir / "verdicts.json", [])
            if v.get("finding_full")
        }
        findings = [verified.get(f.id, f) for f in findings]
    bounds, cells = heatmap(events)
    times = [e.t for e in events if e.t is not None]
    maps = list(dict.fromkeys(e.map for e in events if e.map))
    return DebriefReport(
        session_id=summary.get("session_id") or run_dir.name,
        game=GAME,
        maps=maps,
        duration_s=max(times, default=0.0),
        map_bounds=bounds,
        heatmap=cells,
        notes=notes,
        suggestions=[suggest(f) for f in findings],
        references=references(topic(notes, findings, cells), search) if search else [],
        generated_at=datetime.now(UTC),
    )


def _json(path: Path, default: dict | list | None = None) -> dict | list:
    return json.loads(path.read_text()) if path.exists() else ({} if default is None else default)


def friction(report: DebriefReport) -> dict[str, int]:
    """Short counts for the dashboard header."""
    tags: defaultdict[str, int] = defaultdict(int)
    for n in report.notes:
        for t in n.tags:
            tags[t] += 1
    return {
        "deaths": sum(c.deaths for c in report.heatmap),
        "retries": sum(c.retries for c in report.heatmap),
        **tags,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m insights.debrief")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--out", type=Path, help="default: <run_dir>/debrief.json")
    p.add_argument("--no-linkup", action="store_true")
    a = p.parse_args(argv)
    report = build(a.run_dir, search=None if a.no_linkup else linkup.search)
    out = a.out or a.run_dir / "debrief.json"
    out.write_text(report.model_dump_json(indent=2))
    print(report.model_dump_json(indent=2))
    print(f"friction: {friction(report)}  ->  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
