"""Record a RECORDED fallback run for the jury site: Holo plays Doom in a headless Chromium for N
steps; the frames and moves land in web/jury/recorded/ (run.json + fNNN.jpg), labelled RECORDED.

    .venv/bin/python scripts/record_holo_run.py --steps 120 --url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "jury" / "recorded"


async def record(url: str, steps: int, out: Path, headless: bool) -> dict:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=headless, args=["--autoplay-policy=no-user-gesture-required"])
        pg = await b.new_page(viewport={"width": 1100, "height": 800})
        await pg.goto(f"{url}/jury/dev.html?record=1&mode=live")
        t0 = time.time()
        while time.time() - t0 < steps * 4 + 60:
            n = await pg.evaluate("window.hd ? hd.tape.length : 0")
            if n >= steps:
                break
            await asyncio.sleep(2)
        tape = await pg.evaluate("hd.tape")
        await b.close()
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*.jpg"):
        f.unlink()
    rows = []
    for i, s in enumerate(tape):
        name = f"f{i:03d}.jpg"
        (out / name).write_bytes(base64.b64decode(s["image"].split(",", 1)[1]))
        rows.append({k: s[k] for k in ("step", "thought", "keys", "hold_ms", "aim", "status", "latency_ms")} | {"frame": name})
    run = {
        "label": "RECORDED",
        "note": "Holo (holo4-35b-a3b) playing Freedoom E1M1 in the browser build, recorded by scripts/record_holo_run.py",
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "steps": rows,
    }
    (out / "run.json").write_text(json.dumps(run, indent=1))
    return run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--steps", type=int, default=120)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()
    run = asyncio.run(record(a.url, a.steps, a.out, not a.headed))
    lat = sorted(s["latency_ms"] for s in run["steps"]) or [0]
    print(f"{len(run['steps'])} steps -> {a.out}, latency median {lat[len(lat) // 2]} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
