"""Minimal Linkup /search client shared by the debrief and the placement scout."""

from __future__ import annotations

import html
import os
from collections.abc import Callable

import httpx

from app.contracts import Citation

URL = "https://api.linkup.so/v1/search"

Search = Callable[[str], list[Citation]]


def search(query: str, depth: str = "standard", timeout: float = 60.0) -> list[Citation]:
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True))
    except ImportError:
        pass
    key = os.environ.get("LINKUP_API_KEY")
    if not key:
        raise RuntimeError("LINKUP_API_KEY is not set")
    r = httpx.post(
        URL,
        json={"q": query, "depth": depth, "outputType": "searchResults"},
        headers={"Authorization": f"Bearer {key}"},
        timeout=timeout,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get("results", []):
        if not str(item.get("url") or "").startswith(("https://", "http://")):
            continue  # the dashboard renders it as a link: no javascript:/data: URLs
        snippet = (item.get("content") or "").strip().replace("\n", " ")
        out.append(
            Citation(
                title=html.unescape(item.get("name") or item["url"]),
                url=item["url"],
                snippet=html.unescape(snippet[:300]) or None,
            )
        )
    return out
