import json
import time

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.contracts import PlanId
from app.routes_billing import Billing, get_billing, router
from business.stripe_plans import (
    STRIPE_API,
    PlanStore,
    SignatureError,
    StripeClient,
    StripeError,
    apply_event,
    lookup_key,
    plans,
    sign,
    verify_signature,
)

KEY = "sk_test_" + "x" * 20
WHSEC = "whsec_test_secret"


def event(
    etype="checkout.session.completed",
    plan="parent",
    paid="paid",
    eid="evt_1",
    sub=None,
    oid="cs_1",
):
    obj = {"id": oid, "object": "checkout.session", "metadata": {"plan": plan}}
    if sub:
        obj["subscription"] = sub
    if paid is not None:
        obj["payment_status"] = paid
    return {"id": eid, "type": etype, "data": {"object": obj}}


# ---------------------------------------------------------------- signature


def test_signature_valid():
    body = json.dumps(event()).encode()
    assert verify_signature(body, sign(body, WHSEC), WHSEC)["id"] == "evt_1"


def test_signature_accepts_any_v1():
    body = b'{"id": "evt_2"}'
    good = sign(body, WHSEC)
    t, v1 = good.split(",")
    assert verify_signature(body, f"{t},v1=deadbeef,{v1}", WHSEC)["id"] == "evt_2"


@pytest.mark.parametrize(
    "header",
    [None, "", "garbage", "t=abc,v1=00", "v1=00", "t=123"],
)
def test_signature_malformed(header):
    with pytest.raises(SignatureError):
        verify_signature(b"{}", header, WHSEC)


def test_signature_tampered_body():
    body = json.dumps(event(plan="kid")).encode()
    header = sign(body, WHSEC)
    with pytest.raises(SignatureError, match="mismatch"):
        verify_signature(body.replace(b"kid", b"pro"), header, WHSEC)


def test_signature_wrong_secret():
    body = b"{}"
    with pytest.raises(SignatureError, match="mismatch"):
        verify_signature(body, sign(body, "whsec_other"), WHSEC)


def test_signature_too_old():
    body = b"{}"
    old = int(time.time()) - 3600
    with pytest.raises(SignatureError, match="tolerance"):
        verify_signature(body, sign(body, WHSEC, ts=old), WHSEC)


# ---------------------------------------------------------------- plan flag


def test_store_roundtrip(tmp_path):
    s = PlanStore(tmp_path / "b.json")
    assert s.active is None
    s.set(PlanId.kid)
    assert PlanStore(tmp_path / "b.json").active == PlanId.kid


def test_apply_paid_checkout_sets_plan(tmp_path):
    s = PlanStore(tmp_path / "b.json")
    assert apply_event(event(plan="parent"), s) == PlanId.parent
    assert s.active == PlanId.parent


@pytest.mark.parametrize("paid", ["unpaid", None])
def test_apply_unpaid_checkout_ignored(tmp_path, paid):
    s = PlanStore(tmp_path / "b.json")
    assert apply_event(event(paid=paid), s) is None
    assert s.active is None


def test_apply_unknown_plan_or_type_ignored(tmp_path):
    s = PlanStore(tmp_path / "b.json")
    assert apply_event(event(plan="gold"), s) is None
    assert apply_event(event(etype="invoice.paid"), s) is None
    assert s.active is None


def test_apply_subscription_deleted_clears_matching_plan(tmp_path):
    s = PlanStore(tmp_path / "b.json")
    s.set(PlanId.pro)
    apply_event(event(etype="customer.subscription.deleted", plan="kid", paid=None), s)
    assert s.active == PlanId.pro
    apply_event(event(etype="customer.subscription.deleted", plan="pro", paid=None), s)
    assert s.active is None


def test_old_subscription_deleted_keeps_newer(tmp_path):
    s = PlanStore(tmp_path / "b.json")
    apply_event(event(plan="pro", sub="sub_old"), s)
    apply_event(event(plan="pro", sub="sub_new", eid="evt_2"), s)
    gone = event(etype="customer.subscription.deleted", plan="pro", paid=None, oid="sub_old")
    apply_event(gone, s)
    assert s.active == PlanId.pro and s.load()["subscription"] == "sub_new"
    apply_event({**gone, "data": {"object": {**gone["data"]["object"], "id": "sub_new"}}}, s)
    assert s.active is None


def test_late_checkout_for_canceled_subscription_ignored(tmp_path):
    s = PlanStore(tmp_path / "b.json")
    apply_event(event(plan="kid", sub="sub_1"), s)
    apply_event(event(etype="customer.subscription.deleted", plan="kid", paid=None, oid="sub_1"), s)
    assert s.active is None
    assert apply_event(event(plan="kid", sub="sub_1", eid="evt_retry"), s) is None
    assert s.active is None


def test_set_without_subscription_drops_old_one(tmp_path):
    s = PlanStore(tmp_path / "b.json")
    apply_event(event(plan="pro", sub="sub_1"), s)
    s.set(PlanId.kid)
    apply_event(event(etype="customer.subscription.deleted", plan="kid", paid=None, oid="sub_9"), s)
    assert s.active is None


def test_plans_catalog_flags():
    out = plans(PlanId.kid, {PlanId.kid: "price_k"})
    assert [p.id for p in out] == ["pro", "parent", "kid"]
    assert [p.active for p in out] == [False, False, True]
    assert out[2].stripe_price_id == "price_k" and out[0].stripe_price_id is None


# ---------------------------------------------------------------- Stripe client


def test_live_key_refused():
    with pytest.raises(StripeError, match="test-mode"):
        StripeClient("sk_live_abc")


@respx.mock
def test_ensure_prices_creates_only_missing():
    respx.get(f"{STRIPE_API}/prices").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "price_pro", "lookup_key": lookup_key("pro")}]}
        )
    )
    created = respx.post(f"{STRIPE_API}/prices").mock(
        side_effect=lambda req: httpx.Response(200, json={"id": f"price_new{len(created.calls)}"})
    )
    out = StripeClient(KEY).ensure_prices()
    assert out[PlanId.pro] == "price_pro"
    assert set(out) == {PlanId.pro, PlanId.parent, PlanId.kid}
    assert len(created.calls) == 2
    sent = [dict(httpx.QueryParams(c.request.content.decode())) for c in created.calls]
    assert {s["lookup_key"] for s in sent} == {lookup_key("parent"), lookup_key("kid")}
    parent = next(s for s in sent if s["lookup_key"] == lookup_key("parent"))
    assert parent["unit_amount"] == "900"
    assert parent["currency"] == "eur" and parent["recurring[interval]"] == "month"
    q = respx.calls[0].request.url.params
    assert q.get_list("lookup_keys[]") == [lookup_key(p) for p in PlanId]


@respx.mock
def test_create_checkout_form():
    route = respx.post(f"{STRIPE_API}/checkout/sessions").mock(
        return_value=httpx.Response(
            200, json={"id": "cs_1", "url": "https://checkout.stripe.com/c/x"}
        )
    )
    url = StripeClient(KEY).create_checkout("kid", "price_k", "http://ok", "http://no")
    assert url == "https://checkout.stripe.com/c/x"
    form = dict(httpx.QueryParams(route.calls[0].request.content.decode()))
    assert form["mode"] == "subscription"
    assert form["line_items[0][price]"] == "price_k"
    assert form["metadata[plan]"] == "kid" and form["subscription_data[metadata][plan]"] == "kid"
    assert route.calls[0].request.headers["authorization"].startswith("Basic ")


@respx.mock
def test_stripe_error_surfaces_message():
    respx.post(f"{STRIPE_API}/checkout/sessions").mock(
        return_value=httpx.Response(400, json={"error": {"message": "No such price"}})
    )
    with pytest.raises(StripeError, match="No such price"):
        StripeClient(KEY).create_checkout("pro", "price_x", "a", "b")


# ---------------------------------------------------------------- routes


class FakeStripe:
    def __init__(self):
        self.calls = []

    def ensure_prices(self):
        return {p: f"price_{p.value}" for p in PlanId}

    def create_checkout(self, plan, price_id, success_url, cancel_url):
        self.calls.append((plan, price_id, success_url, cancel_url))
        return "https://checkout.stripe.com/c/test"


def client(tmp_path, stripe=None, secret=WHSEC):
    b = Billing(stripe, PlanStore(tmp_path / "b.json"), secret, "http://dash:5173/")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_billing] = lambda: b
    return TestClient(app), b


def test_route_plans_without_stripe(tmp_path):
    c, _ = client(tmp_path)
    r = c.get("/api/plans")
    assert r.status_code == 200
    assert [p["active"] for p in r.json()] == [False, False, False]


def test_route_checkout(tmp_path):
    fake = FakeStripe()
    c, _ = client(tmp_path, stripe=fake)
    r = c.post("/api/billing/checkout", json={"plan": "parent"})
    assert r.status_code == 200 and r.json() == {"url": "https://checkout.stripe.com/c/test"}
    plan, price, ok, cancel = fake.calls[0]
    assert (plan, price) == (PlanId.parent, "price_parent")
    assert ok == "http://dash:5173/?checkout=success#plans"
    assert c.get("/api/plans").json()[1]["stripe_price_id"] == "price_parent"


def test_route_checkout_bad_plan_and_no_key(tmp_path):
    c, _ = client(tmp_path)
    assert c.post("/api/billing/checkout", json={"plan": "gold"}).status_code == 422
    assert c.post("/api/billing/checkout", json={"plan": "pro"}).status_code == 503


def test_route_webhook_switches_plan(tmp_path):
    c, b = client(tmp_path)
    body = json.dumps(event(plan="kid")).encode()
    r = c.post(
        "/api/billing/webhook", content=body, headers={"Stripe-Signature": sign(body, WHSEC)}
    )
    assert r.status_code == 200
    assert r.json()["active"] == "kid"
    assert [p["active"] for p in c.get("/api/plans").json()] == [False, False, True]


def test_route_webhook_rejects_bad_signature(tmp_path):
    c, b = client(tmp_path)
    body = json.dumps(event(plan="pro")).encode()
    bad = sign(body, "whsec_attacker")
    assert (
        c.post("/api/billing/webhook", content=body, headers={"Stripe-Signature": bad}).status_code
        == 400
    )
    assert c.post("/api/billing/webhook", content=body).status_code == 400
    assert b.store.active is None


def test_route_webhook_needs_secret(tmp_path):
    c, _ = client(tmp_path, secret=None)
    assert c.post("/api/billing/webhook", content=b"{}").status_code == 503
