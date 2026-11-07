import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.contracts import API_RESPONSES, SSE_PAYLOAD, SseEvent, SseType

MOCK = json.loads(
    (Path(__file__).parents[1] / "docs" / "api-mock.json").read_text(encoding="utf-8")
)


def test_mock_covers_every_endpoint():
    assert set(API_RESPONSES) <= set(MOCK)


@pytest.mark.parametrize("endpoint", sorted(API_RESPONSES))
def test_mock_payload_validates(endpoint):
    TypeAdapter(API_RESPONSES[endpoint]).validate_python(MOCK[endpoint])


def test_every_sse_type_has_a_payload_model_and_a_mock_sample():
    assert set(SSE_PAYLOAD) == set(SseType)
    seen = set()
    for raw in MOCK["GET /api/events"]:
        event = SseEvent.model_validate(raw)
        assert event.payload() is not None
        seen.add(event.type)
    assert seen == {t.value for t in SseType}


def test_mock_is_labelled_and_not_live():
    assert MOCK["GET /api/session"]["live"] is False
    assert "MOCK" in MOCK["_comment"]
