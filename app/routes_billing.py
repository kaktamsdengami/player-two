"""Billing routes (T18): plans, Stripe Checkout, webhook -> active plan flag.

Mount with `app.include_router(router)`. Env: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
DASHBOARD_URL (where Checkout returns, default http://localhost:5173).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.contracts import Plan, PlanId
from business.stripe_plans import (
    PlanStore,
    SignatureError,
    StripeClient,
    StripeError,
    apply_event,
    plans,
    verify_signature,
)

router = APIRouter(prefix="/api")


class CheckoutRequest(BaseModel):
    plan: PlanId
    return_path: str | None = None  # a path on this server to come back to; default: dashboard


class CheckoutResponse(BaseModel):
    url: str


class Billing:
    def __init__(
        self,
        stripe: StripeClient | None,
        store: PlanStore,
        webhook_secret: str | None,
        dashboard_url: str = "http://localhost:5173",
    ):
        self.stripe = stripe
        self.store = store
        self.webhook_secret = webhook_secret
        self.dashboard_url = dashboard_url.rstrip("/")
        self._prices: dict[PlanId, str] | None = None

    def prices(self) -> dict[PlanId, str]:
        if self._prices is None:
            if not self.stripe:
                raise HTTPException(503, "STRIPE_SECRET_KEY is not set")
            self._prices = self.stripe.ensure_prices()
        return self._prices


@lru_cache
def get_billing() -> Billing:
    load_dotenv()
    key = os.environ.get("STRIPE_SECRET_KEY")
    return Billing(
        stripe=StripeClient(key) if key else None,
        store=PlanStore(),
        webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET") or None,
        dashboard_url=os.environ.get("DASHBOARD_URL", "http://localhost:5173"),
    )


BillingDep = Annotated[Billing, Depends(get_billing)]


@router.get("/plans", response_model=list[Plan])
def list_plans(b: BillingDep) -> list[Plan]:
    prices = None
    if b.stripe:
        try:
            prices = b.prices()
        except StripeError:
            prices = None
    return plans(b.store.active, prices)


@router.post("/billing/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest, b: BillingDep, request: Request) -> CheckoutResponse:
    plan = PlanId(req.plan)
    try:
        price = b.prices()[plan]
        if req.return_path:
            path = req.return_path
            if not path.startswith("/") or path.startswith("//") or any(c in path for c in "?#\\"):
                raise HTTPException(400, "return_path must be a plain path on this site")
            base = str(request.base_url).rstrip("/") + path  # our own origin, never a third party
            success = f"{base}?checkout=success&plan={plan.value}"
            cancel = f"{base}?checkout=cancel"
        else:
            success = f"{b.dashboard_url}/?checkout=success#plans"
            cancel = f"{b.dashboard_url}/?checkout=cancel#plans"
        url = b.stripe.create_checkout(plan, price, success_url=success, cancel_url=cancel)
    except StripeError as e:
        raise HTTPException(502, str(e)) from e
    return CheckoutResponse(url=url)


@router.post("/billing/webhook")
async def webhook(request: Request, b: BillingDep) -> dict:
    if not b.webhook_secret:
        raise HTTPException(503, "STRIPE_WEBHOOK_SECRET is not set")
    payload = await request.body()
    try:
        event = verify_signature(payload, request.headers.get("stripe-signature"), b.webhook_secret)
    except (SignatureError, ValueError) as e:
        raise HTTPException(400, f"invalid webhook: {e}") from e
    set_plan = apply_event(event, b.store)
    active = b.store.active
    return {
        "received": True,
        "type": event.get("type"),
        "set": set_plan.value if set_plan else None,
        "active": active.value if active else None,
    }
