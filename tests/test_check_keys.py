import httpx

from scripts import check_keys

ENV = {
    "HAI_API_KEY": "h",
    "DEVIN_API_KEY": "d",
    "DEVIN_ORG_ID": "org",
    "GLADIA_API_KEY": "g",
    "LINKUP_API_KEY": "l",
    "STRIPE_SECRET_KEY": "sk_test_x",
}


def _client(status=200, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_all_services_ok():
    seen = []
    results = check_keys.run(env=ENV, client=_client(200, seen))
    assert [s for _, s in results] == ["HTTP 200"] * len(check_keys.CHECKS)
    assert any("/api/v2/sessions/quota" in str(r.url) for r in seen)
    assert any("/v3/organizations/org/sessions" in str(r.url) for r in seen)


def test_missing_key_reported_without_request():
    seen = []
    results = dict(check_keys.run(only={"gladia"}, env={}, client=_client(200, seen)))
    assert results == {"gladia": "MISSING GLADIA_API_KEY"}
    assert seen == []


def test_region_override_and_failure():
    seen = []
    env = {**ENV, "HAI_BASE_URL": "https://agp.eu.hcompany.ai/"}
    results = dict(check_keys.run(only={"h-agents"}, env=env, client=_client(401, seen)))
    assert results == {"h-agents": "HTTP 401"}
    assert str(seen[0].url) == "https://agp.eu.hcompany.ai/api/v2/sessions/quota"


def test_live_stripe_key_flagged():
    env = {**ENV, "STRIPE_SECRET_KEY": "sk_live_x"}
    results = dict(check_keys.run(only={"stripe"}, env=env, client=_client()))
    assert "stripe-mode" in results
