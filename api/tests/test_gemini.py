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
    # google-genai's SyncHttpxClient is a plain httpx.Client subclass with no
    # custom transport override, so (unlike client_args on HttpOptions, which
    # doesn't exist as a field in this SDK version - HttpOptions only has
    # base_url/api_version/headers/timeout, extra="forbid") the same global
    # transport patch api/tests/test_api.py already uses for the FastAPI
    # TestClient works here too: intercept at httpx.HTTPTransport itself.
    real_client = genai.Client
    requests = []
    options = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    def install(text="Hello", status=200):
        def handle_request(self, request):
            requests.append(request)
            if status != 200:
                return httpx.Response(status, json={"error": {
                    "code": status, "message": "Test failure", "status": "UNAVAILABLE"}})
            return httpx.Response(200, json={"candidates": [{"content": {
                "role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}]})
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle_request)

        def client(**kwargs):
            options.append(kwargs["http_options"])
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
    assert options[0].timeout == 10_000


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
