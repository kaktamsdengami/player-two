"""Read-only API key checks. Prints one line per service, never the key itself.

Usage: python -m scripts.check_keys [--only h,devin,...]
Exit code 0 only if every checked service answers HTTP 200.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass

import httpx

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


@dataclass
class Check:
    name: str
    env: tuple[str, ...]
    request: Callable[[dict[str, str]], httpx.Request]


def _h_base(env: dict[str, str]) -> str:
    return env.get("HAI_BASE_URL", "https://agp.hcompany.ai").rstrip("/")


CHECKS = [
    Check(
        "h-agents",
        ("HAI_API_KEY",),
        lambda e: httpx.Request(
            "GET",
            f"{_h_base(e)}/api/v2/sessions/quota",
            headers={"Authorization": f"Bearer {e['HAI_API_KEY']}"},
        ),
    ),
    Check(
        "h-models",
        ("HAI_API_KEY",),
        lambda e: httpx.Request(
            "GET",
            "https://api.hcompany.ai/v1/models",
            headers={"Authorization": f"Bearer {e['HAI_API_KEY']}"},
        ),
    ),
    Check(
        "devin",
        ("DEVIN_API_KEY", "DEVIN_ORG_ID"),
        lambda e: httpx.Request(
            "GET",
            f"https://api.devin.ai/v3/organizations/{e['DEVIN_ORG_ID']}/sessions",
            params={"limit": 1},
            headers={"Authorization": f"Bearer {e['DEVIN_API_KEY']}"},
        ),
    ),
    Check(
        "gladia",
        ("GLADIA_API_KEY",),
        lambda e: httpx.Request(
            "GET",
            "https://api.gladia.io/v2/live",
            params={"limit": 1},
            headers={"x-gladia-key": e["GLADIA_API_KEY"]},
        ),
    ),
    Check(
        "linkup",
        ("LINKUP_API_KEY",),
        lambda e: httpx.Request(
            "GET",
            "https://api.linkup.so/v1/credits/balance",
            headers={"Authorization": f"Bearer {e['LINKUP_API_KEY']}"},
        ),
    ),
    Check(
        "stripe",
        ("STRIPE_SECRET_KEY",),
        lambda e: httpx.Request(
            "GET",
            "https://api.stripe.com/v1/balance",
            headers={"Authorization": f"Bearer {e['STRIPE_SECRET_KEY']}"},
        ),
    ),
]


def run(
    only: set[str] | None = None,
    env: dict[str, str] | None = None,
    client: httpx.Client | None = None,
) -> list[tuple[str, str]]:
    env = dict(os.environ if env is None else env)
    client = client or httpx.Client(timeout=15)
    results = []
    for check in CHECKS:
        if only and check.name not in only:
            continue
        missing = [k for k in check.env if not env.get(k)]
        if missing:
            results.append((check.name, f"MISSING {','.join(missing)}"))
            continue
        try:
            status = client.send(check.request(env)).status_code
            results.append((check.name, f"HTTP {status}"))
        except httpx.HTTPError as exc:
            results.append((check.name, f"ERROR {type(exc).__name__}"))
    if env.get("STRIPE_SECRET_KEY", "").startswith("sk_live"):
        results.append(("stripe-mode", "LIVE KEY (expected test mode)"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="comma-separated names: " + ",".join(c.name for c in CHECKS))
    args = parser.parse_args(argv)
    if load_dotenv:
        load_dotenv()
    results = run(set(args.only.split(",")) if args.only else None)
    for name, status in results:
        print(f"{name:12} {status}")
    return 0 if all(s == "HTTP 200" for _, s in results) else 1


if __name__ == "__main__":
    sys.exit(main())
