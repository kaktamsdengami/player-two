"""Stripe test-mode plans (T18): catalog, idempotent prices, Checkout, webhook signature, plan flag.

Talks to the Stripe REST API with httpx (no SDK). Prices are found by `lookup_key`
(`player_two_<plan>`), so `ensure_prices()` can run on every start without duplicating them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.contracts import Plan, PlanId

STRIPE_API = "https://api.stripe.com/v1"
LOOKUP_PREFIX = "player_two_"
SIGNATURE_TOLERANCE_S = 300

CATALOG: dict[PlanId, dict] = {
    PlanId.pro: {
        "name": "Pro",
        "tagline": "A hostile QA tester for your game",
        "price_eur_month": 49,
        "features": [
            "Unlimited test sessions",
            "Devin fix loop",
            "Design debrief",
            "Placement scout",
        ],
    },
    PlanId.parent: {
        "name": "Parent",
        "tagline": "Know a game before your kid plays it",
        "price_eur_month": 9,
        "features": ["Overnight game checks", "Morning report"],
    },
    PlanId.kid: {
        "name": "Kid",
        "tagline": "A friend on the couch",
        "price_eur_month": 5,
        "features": ["Friendly commentator", "Hints, never spoilers"],
    },
}


class StripeError(RuntimeError):
    pass


class SignatureError(ValueError):
    pass


def lookup_key(plan: PlanId | str) -> str:
    return f"{LOOKUP_PREFIX}{PlanId(plan).value}"


class StripeClient:
    """Minimal Stripe REST client. Refuses live keys: this product only runs in test mode."""

    def __init__(self, secret_key: str, http: httpx.Client | None = None):
        if not secret_key.startswith(("sk_test_", "rk_test_")):
            raise StripeError("Stripe key is not a test-mode key; refusing to use it")
        self.http = http or httpx.Client(timeout=20)
        self.auth = (secret_key, "")

    def _req(self, method: str, path: str, data=None, params=None) -> dict:
        r = self.http.request(
            method, f"{STRIPE_API}{path}", auth=self.auth, data=data, params=params
        )
        body = r.json() if r.content else {}
        if r.status_code >= 400:
            msg = (body.get("error") or {}).get("message", r.text[:200])
            raise StripeError(f"Stripe {method} {path}: HTTP {r.status_code}: {msg}")
        return body

    def ensure_prices(self) -> dict[PlanId, str]:
        """Return {plan: price_id}, creating a monthly EUR price (and product) for missing plans."""
        params = [("active", "true"), ("limit", "10")]
        params += [("lookup_keys[]", lookup_key(p)) for p in CATALOG]
        found = {
            p["lookup_key"]: p["id"] for p in self._req("GET", "/prices", params=params)["data"]
        }
        out: dict[PlanId, str] = {}
        for plan, spec in CATALOG.items():
            key = lookup_key(plan)
            if key not in found:
                created = self._req(
                    "POST",
                    "/prices",
                    data={
                        "currency": "eur",
                        "unit_amount": int(round(spec["price_eur_month"] * 100)),
                        "recurring[interval]": "month",
                        "lookup_key": key,
                        "product_data[name]": f"PLAYER TWO {spec['name']}",
                        "product_data[metadata][plan]": plan.value,
                        "metadata[plan]": plan.value,
                    },
                )
                found[key] = created["id"]
            out[plan] = found[key]
        return out

    def create_checkout(
        self, plan: PlanId | str, price_id: str, success_url: str, cancel_url: str
    ) -> str:
        plan = PlanId(plan).value
        session = self._req(
            "POST",
            "/checkout/sessions",
            data={
                "mode": "subscription",
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "client_reference_id": plan,
                "metadata[plan]": plan,
                "subscription_data[metadata][plan]": plan,
            },
        )
        return session["url"]


def verify_signature(
    payload: bytes,
    header: str | None,
    secret: str,
    tolerance: int = SIGNATURE_TOLERANCE_S,
    now: float | None = None,
) -> dict:
    """Check a `Stripe-Signature` header (HMAC-SHA256 of `t.payload`) and return the event."""
    if not header:
        raise SignatureError("missing Stripe-Signature header")
    ts, sigs = None, []
    for part in header.split(","):
        k, _, v = part.strip().partition("=")
        if k == "t":
            ts = v
        elif k == "v1":
            sigs.append(v)
    if not ts or not ts.isdigit() or not sigs:
        raise SignatureError("malformed Stripe-Signature header")
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise SignatureError("signature mismatch")
    if abs((now if now is not None else time.time()) - int(ts)) > tolerance:
        raise SignatureError("timestamp outside tolerance")
    return json.loads(payload)


def sign(payload: bytes, secret: str, ts: int | None = None) -> str:
    """Build a `Stripe-Signature` header (tests and local replays)."""
    ts = int(time.time()) if ts is None else ts
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


class PlanStore:
    """Active plan flag, persisted as JSON under data/ (git-ignored)."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or Path(os.environ.get("PLAYER_TWO_DATA", "data")) / "billing.json")

    def load(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {"active": None}

    @property
    def active(self) -> PlanId | None:
        a = self.load().get("active")
        return PlanId(a) if a in PlanId._value2member_map_ else None

    _lock = threading.Lock()

    def update(self, **fields) -> None:
        with self._lock:
            self._write(fields)

    def _write(self, fields: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = {**self.load(), **fields, "updated": datetime.now(UTC).isoformat()}
        tmp = self.path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(state))
        os.replace(tmp, self.path)

    def set(self, plan: PlanId | None, **extra) -> None:
        self.update(active=plan.value if plan else None, **{"subscription": None, **extra})


def apply_event(event: dict, store: PlanStore) -> PlanId | None:
    """Update the plan flag from a verified webhook event; return the plan it set, if any."""
    obj = (event.get("data") or {}).get("object") or {}
    plan = (obj.get("metadata") or {}).get("plan") or obj.get("client_reference_id")
    if plan not in PlanId._value2member_map_:
        return None
    etype = event.get("type")
    state = store.load()
    canceled = state.get("canceled") or []
    if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        sub = obj.get("subscription")
        if obj.get("payment_status") not in ("paid", "no_payment_required") or sub in canceled:
            return None
        store.set(PlanId(plan), event_id=event.get("id"), checkout=obj.get("id"), subscription=sub)
        return PlanId(plan)
    if etype == "customer.subscription.deleted":
        sub = obj.get("id")
        canceled = [*canceled, sub][-50:]
        if state.get("active") == plan and state.get("subscription") in (None, sub):
            store.set(None, event_id=event.get("id"), subscription=None, canceled=canceled)
        else:
            store.update(canceled=canceled)
    return None


def plans(active: PlanId | None, price_ids: dict[PlanId, str] | None = None) -> list[Plan]:
    price_ids = price_ids or {}
    return [
        Plan(id=p, stripe_price_id=price_ids.get(p), active=(p == active), **spec)
        for p, spec in CATALOG.items()
    ]
