"""The shared /live/ game: a headless Chromium plays Doom with Holo and pushes every step to the
server (POST /api/live/push). Started by app/routes_live.py when the first viewer connects, or by
hand on the stage laptop:

    .venv/bin/python scripts/live_broadcaster.py --url http://127.0.0.1:8000 [--headed]

Stops itself when the server reports no viewers for a while (keep=false) or after --max-minutes.
"""

from __future__ import annotations

import argparse
import asyncio
import time


async def run(url: str, headed: bool, max_minutes: float) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        b = await p.chromium.launch(
            headless=not headed,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--mute-audio",
            ],
        )
        pg = await b.new_page(viewport={"width": 960, "height": 720})
        pg.on("pageerror", lambda e: print("pageerror", str(e)[:120], flush=True))
        await pg.goto(f"{url}/jury/live/broadcaster.html?api={url}")
        t0 = time.time()
        while time.time() - t0 < max_minutes * 60:
            await asyncio.sleep(10)
            keep = await pg.evaluate("window.keep !== false")
            if not keep:
                print("no viewers: stopping", flush=True)
                break
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=240)
    a = ap.parse_args()
    asyncio.run(run(a.url, a.headed, a.max_minutes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
