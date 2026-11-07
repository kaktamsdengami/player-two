import json

import httpx
import pytest

from app.contracts import Intent, VoiceIntent
from voice.intents import button_intent, normalize, parse_intent
from voice.listen import Listener, handle_message, init_config, start_session


@pytest.mark.parametrize(
    "text,intent",
    [
        ("Fix it!", "fix"),
        ("fix it please", "fix"),
        ("Can you patch that?", "fix"),
        ("Corrige-le", "fix"),
        ("répare ça", "fix"),
        ("Fixe-le", "fix"),
        ("Stop!", "stop"),
        ("stop the game", "stop"),
        ("Arrête", "stop"),
        ("arrête tout", "stop"),
        ("don't fix it", "no"),
        ("Don’t fix it", "no"),
        ("ne le corrige pas", "no"),
        ("don't patch it", "no"),
        ("do not repair that", "no"),
        ("ne le fixe pas", "no"),
        ("ne répare pas", "no"),
        ("pas besoin de corriger", "no"),
        ("No", "no"),
        ("non merci", "no"),
        ("not now", "no"),
        ("skip", "skip"),
        ("next bug", "skip"),
        ("passe au suivant", "skip"),
        ("explain", "explain"),
        ("why did that happen", "explain"),
        ("pourquoi ?", "explain"),
        ("explique-moi", "explain"),
        ("yes", "yes"),
        ("Oui", "yes"),
        ("ok go ahead", "yes"),
        ("d'accord", "yes"),
        ("try the door again", "steer"),
        ("essaie la porte encore", "steer"),
    ],
)
def test_parse_intent(text, intent):
    result = parse_intent(text, language="en")
    assert result is not None
    assert result.intent == intent
    assert result.source == "voice"
    assert result.text == text.strip()


@pytest.mark.parametrize("text", ["", "   ", "...", "uh", "hmm"])
def test_noise_is_ignored(text):
    assert parse_intent(text) is None


def test_normalize_strips_accents_and_punctuation():
    assert normalize("  Arrête!!  Répare ÇA ") == "arrete repare ca"


def test_finding_and_confidence_carried():
    r = parse_intent("fix it", language="en", confidence=0.9, finding_id="F-1")
    assert (r.finding_id, r.confidence, r.language) == ("F-1", 0.9, "en")


@pytest.mark.parametrize("intent", list(Intent))
def test_every_intent_has_a_button(intent):
    b = button_intent(intent.value, finding_id="F-1")
    assert b.intent == intent and b.source == "button"
    VoiceIntent.model_validate(b.model_dump())


def _transcript(text, final=True, lang="fr", conf=0.9):
    return json.dumps(
        {
            "type": "transcript",
            "session_id": "s",
            "created_at": "2026-11-07T12:00:00Z",
            "data": {
                "id": "u1",
                "is_final": final,
                "utterance": {"text": text, "language": lang, "confidence": conf},
            },
        }
    )


def test_handle_message():
    assert handle_message(_transcript(" Stop ")) == ("Stop", True, "fr", 0.9)
    assert handle_message(json.dumps({"type": "speech_start", "data": {}})) is None
    assert handle_message(_transcript("", final=True)) is None


def test_listener_dispatch_final_only():
    intents, transcripts = [], []
    li = Listener(
        "k",
        intents.append,
        lambda text, final, lang: transcripts.append((text, final)),
        finding_id=lambda: "F-2",
    )
    assert li.dispatch(_transcript("fix", final=False)) is None
    li.dispatch(_transcript("corrige-le", final=True))
    li.dispatch(json.dumps({"type": "end_session", "data": {}}))
    assert transcripts == [("fix", False), ("corrige-le", True)]
    assert [(i.intent, i.finding_id, i.language) for i in intents] == [("fix", "F-2", "fr")]


def test_reader_survives_callback_errors():
    seen = []

    def on_intent(intent):
        seen.append(intent.intent)
        if len(seen) == 1:
            raise ConnectionError("orchestrator down")

    li = Listener("k", on_intent)
    li._read([_transcript("fix it"), _transcript("stop")])
    assert seen == ["fix", "stop"]


def test_start_session_posts_config():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-gladia-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"id": "abc", "url": "wss://api.gladia.io/v2/live?token=abc"}
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert start_session("secret", http=http)["id"] == "abc"
    assert seen["url"] == "https://api.gladia.io/v2/live"
    assert seen["key"] == "secret"
    assert seen["body"] == init_config()
    assert seen["body"]["language_config"]["languages"] == ["en", "fr"]


def test_start_session_error():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad")))
    with pytest.raises(RuntimeError, match="401"):
        start_session("x", http=http)
