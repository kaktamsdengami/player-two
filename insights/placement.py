"""T17 product-placement scout: in-game surfaces that suit native placement + sourced brands.

python -m insights.placement <run_dir> [--every 5] [--spots 5] [--out placement.json] [--no-linkup]

Frames are sampled from the run's recording every few seconds and a vision model lists the
surfaces it sees; the same surface across frames is merged, scored by screen time x visibility,
and each top spot gets 2-3 brand candidates from Linkup, every one with a source link.
Agent notes tagged `placement` become spots too. Suggestions only: no brand deal is implied.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.contracts import AgentNote, BrandCandidate, Citation, PlacementSpot
from insights import linkup

MODELS_URL = "https://api.hcompany.ai/v1/chat/completions"
VISION_MODEL = "holo4-27b"
EVERY_S = 5.0
AUDIENCE = "players of retro first-person shooters, aged 18-34"
SURFACES = {"screen", "poster", "wall", "item", "other"}
STOP = {"the", "a", "an", "of", "on", "in", "large", "small", "big"}

DETECT_PROMPT = (
    "You scout native product-placement spots in a video game frame (in-game ads, like a poster "
    "or screen in a real street). List up to 4 in-game surfaces or objects where a brand could "
    "appear naturally: wall panels, screens, posters, signs, crates, pickups. Ignore the HUD and "
    "the player's weapon. visibility is how prominent the spot is in this frame (0 to 1). "
    'Answer JSON only: {"spots": [{"name": "short noun phrase", "surface": '
    '"screen|poster|wall|item|other", "location": "where in the level", "visibility": 0.5}]}'
)

BRAND_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "real brand name"},
                    "rationale": {"type": "string", "description": "one sentence: why it fits"},
                    "source_url": {
                        "type": "string",
                        "description": "URL of a page about this brand's gaming marketing",
                    },
                },
            },
        }
    },
}

Detect = Callable[[Path], list[dict[str, Any]]]
Ask = Callable[[str, dict], dict]


@dataclass
class Sighting:
    name: str
    surface: str
    location: str
    visibility: float
    t: float
    screenshot: str | None


def frames(recording: Path, out_dir: Path, every_s: float = EVERY_S) -> list[tuple[float, Path]]:
    """One PNG every `every_s` seconds of the recording: [(t, path)]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("frame_*.png"):
        old.unlink()
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(recording),
         "-vf", f"fps=1/{every_s},scale=640:-2", str(out_dir / "frame_%04d.png")],
        check=True,
    )  # fmt: skip
    paths = sorted(out_dir.glob("frame_*.png"))
    return [(i * every_s, p) for i, p in enumerate(paths)]


def _json(text: str) -> Any:
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m[0]) if m else {}


def detect(frame: Path, model: str | None = None, timeout: float = 90.0) -> list[dict[str, Any]]:
    """Ask the H vision model which placement surfaces this frame shows."""
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True))
    except ImportError:
        pass
    img = base64.b64encode(frame.read_bytes()).decode()
    r = httpx.post(
        MODELS_URL,
        headers={"Authorization": f"Bearer {os.environ['HAI_API_KEY']}"},
        json={
            "model": model or os.environ.get("P2_VISION_MODEL", VISION_MODEL),
            "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                {"type": "text", "text": DETECT_PROMPT},
            ]}],
        },
        timeout=timeout,
    )  # fmt: skip
    r.raise_for_status()
    spots = _json(r.json()["choices"][0]["message"]["content"]).get("spots", [])
    return [s for s in spots if isinstance(s, dict) and s.get("name")]


def norm(name: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in STOP]
    return " ".join(words) or name.lower().strip()


def sightings(shots: list[tuple[float, Path]], detect_: Detect = detect) -> list[Sighting]:
    out = []
    for t, p in shots:
        try:
            spots = detect_(p)
        except Exception as e:  # noqa: BLE001 - one bad frame must not lose the run
            print(f"detect failed on {p.name}: {e}", file=sys.stderr)
            continue
        for s in spots:
            if not isinstance(s, dict) or not s.get("name"):
                continue
            surface = str(s.get("surface", "other")).lower()
            try:
                vis = min(max(float(s.get("visibility") or 0.5), 0.0), 1.0)
            except (TypeError, ValueError):
                vis = 0.5
            out.append(Sighting(str(s["name"]), surface if surface in SURFACES else "other",
                                str(s.get("location") or "unknown"), vis, t, str(p)))  # fmt: skip
    return out


def from_notes(notes: list[AgentNote]) -> list[Sighting]:
    """The tester's `note(..., tags=["placement"])` calls: what it pointed out itself."""
    return [
        Sighting(n.text[:60], "other", n.location or "unknown", 0.5, n.t_session_s, n.screenshot)
        for n in notes
        if "placement" in n.tags
    ]


def spots(
    seen: list[Sighting], session_id: str, every_s: float = EVERY_S, top: int = 5,
    audience: str = AUDIENCE,
) -> list[PlacementSpot]:  # fmt: skip
    """Merge sightings of the same surface; screen time x mean visibility ranks them."""
    groups: dict[str, list[Sighting]] = defaultdict(list)
    for s in seen:
        groups[norm(s.name)].append(s)
    out = []
    for i, g in enumerate(groups.values()):
        best = max(g, key=lambda s: s.visibility)
        out.append(
            PlacementSpot(
                id=f"spot-{i + 1}",
                session_id=session_id,
                name=best.name,
                surface=Counter(
                    s.surface if s.surface in SURFACES else "other" for s in g
                ).most_common(1)[0][0],
                location=Counter(s.location for s in g).most_common(1)[0][0],
                screen_time_s=len({s.t for s in g}) * every_s,
                visibility=round(sum(s.visibility for s in g) / len(g), 3),
                screenshot=best.screenshot,
                audience=audience,
            )
        )
    out.sort(key=lambda p: -p.screen_time_s * p.visibility)
    return [p.model_copy(update={"id": f"spot-{i + 1}"}) for i, p in enumerate(out[:top])]


def _http(url: Any) -> bool:
    return isinstance(url, str) and url.startswith(("https://", "http://"))


def brands(spot: PlacementSpot, ask: Ask = linkup.structured, n: int = 3) -> list[BrandCandidate]:
    """2-3 real brands that market in games and fit this surface and audience, each sourced."""
    q = (
        f"Which {n} real brands that already advertise or sponsor in video games would fit a "
        f"native in-game placement on a {spot.surface} ({spot.name}, {spot.location}) in a retro "
        f"sci-fi first-person shooter played by {spot.audience}? For each, give a one-sentence "
        f"rationale and the URL of a page about that brand's gaming marketing."
    )
    res = ask(q, BRAND_SCHEMA)
    data = res.get("data", res)
    sources = [s for s in res.get("sources", []) if _http(s.get("url"))]
    out = []
    for c in (data.get("candidates") or [])[:n]:
        if not c.get("name"):
            continue
        url = c.get("source_url")
        src = next((s for s in sources if s["url"] == url), None)
        if _http(url):
            cites = [Citation(title=(src or {}).get("name") or url, url=url)]
        else:  # no own link: cite a source that names the brand
            named = [s for s in sources if c["name"].lower() in json.dumps(s).lower()]
            cites = [Citation(title=s.get("name") or s["url"], url=s["url"]) for s in named[:1]]
        if cites:
            out.append(
                BrandCandidate(name=c["name"], rationale=c.get("rationale") or "", sources=cites)
            )
    return out


def scout(
    run_dir: Path, every_s: float = EVERY_S, top: int = 5, detect_: Detect = detect,
    ask: Ask | None = linkup.structured, audience: str = AUDIENCE,
) -> list[PlacementSpot]:  # fmt: skip
    run = json.loads((run_dir / "tester_run.json").read_text())
    notes = [AgentNote.model_validate(n) for n in run.get("notes", [])]
    rec = Path(run.get("recording") or run_dir / "recording.mp4")
    shots = frames(rec, run_dir / "placement", every_s) if rec.exists() else []
    seen = sightings(shots, detect_) + from_notes(notes)
    found = spots(seen, run.get("session_id") or run_dir.name, every_s, top, audience)
    if ask is None:
        return found
    out = []
    for s in found:
        try:
            out.append(s.model_copy(update={"brand_candidates": brands(s, ask)}))
        except Exception as e:  # noqa: BLE001 - spots are still useful without brands
            print(f"linkup failed for {s.name}: {e}", file=sys.stderr)
            out.append(s)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("run_dir", type=Path)
    p.add_argument("--every", type=float, default=EVERY_S, help="seconds between sampled frames")
    p.add_argument("--spots", type=int, default=5)
    p.add_argument("--audience", default=AUDIENCE)
    p.add_argument("--out", type=Path)
    p.add_argument("--no-linkup", action="store_true")
    a = p.parse_args(argv)
    res = scout(a.run_dir, a.every, a.spots, ask=None if a.no_linkup else linkup.structured,
                audience=a.audience)  # fmt: skip
    text = json.dumps([s.model_dump(mode="json") for s in res], indent=2)
    (a.out or a.run_dir / "placement.json").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
