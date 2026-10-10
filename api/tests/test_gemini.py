"""Exercise the supported SDK over a fake HTTP transport, with no paid calls."""
import json
from datetime import date

import httpx
import pytest
from google import genai

from llm.gemini import generate_text
from llm.parse import _parse_with_gemini


@pytest.fixture
def sdk_transport(monkeypatch):
    real_client = genai.Client
    requests = []
    options = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    def install(text="Hello", status=200):
        def handler(request):
            requests.append(request)
            if status != 200:
                return httpx.Response(status, json={"error": {
                    "code": status, "message": "Test failure", "status": "UNAVAILABLE"}})
            return httpx.Response(200, json={"candidates": [{"content": {
                "role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}]})
        def client(**kwargs):
            options.append(kwargs["http_options"])
            kwargs["http_options"] = kwargs["http_options"].model_copy(update={
                "client_args": {"transport": httpx.MockTransport(handler)}})
            return real_client(**kwargs)
        monkeypatch.setattr(genai, "Client", client)
    return install, requests, options


def test_supported_sdk_sends_bounded_authenticated_request(sdk_transport):
    install, requests, options = sdk_transport
    install("Readable response")
    assert generate_text("Rewrite claims", max_output_tokens=384) == "Readable response"
    assert len(requests) == 1
    request = requests[0]
    assert request.headers["x-goog-api-key"] == "test-key"
    assert request.url.path.endswith("models/gemini-3.5-flash-lite:generateContent")
    assert json.loads(request.content)["generationConfig"]["maxOutputTokens"] == 384
    assert options[0].timeout == 10_000 and options[0].retry_options.attempts == 1


def test_transient_sdk_error_is_not_retried(sdk_transport):
    install, requests, _ = sdk_transport
    install(status=503)
    with pytest.raises(Exception, match="503"):
        generate_text("Rewrite claims", max_output_tokens=384)
    assert len(requests) == 1


def test_json_parser_applies_guards_before_frozen_delta_construction(sdk_transport):
    install, requests, _ = sdk_transport
    install(json.dumps({"kind": "recurring", "amount": 65, "start_day": 999,
                        "cadence_days": None, "label": "Gym", "confidence": .95}))
    result = _parse_with_gemini("$65/mo gym", date(2026, 10, 10))
    assert result.amount == 65 and result.start_day == 730
    assert result.cadence_days == 30 and result.confidence == .7
    config = json.loads(requests[0].content)["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["maxOutputTokens"] == 256
