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
        if not item.get("url"):
            continue
        snippet = (item.get("content") or "").strip().replace("\n", " ")
        out.append(
            Citation(
                title=html.unescape(item.get("name") or item["url"]),
                url=item["url"],
                snippet=html.unescape(snippet[:300]) or None,
            )
        )
    return out
