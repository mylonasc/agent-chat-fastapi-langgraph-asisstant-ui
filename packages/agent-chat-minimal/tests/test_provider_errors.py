"""DEV-01/DEV-02: provider errors surface as structured stream errors (#68)."""

import asyncio
import json

from fastapi.testclient import TestClient

from agent_chat_minimal import create_app
from agent_chat_minimal.config import Settings
from agent_chat_minimal.provider_errors import (
    classify_provider_error,
    format_stream_error,
)
from agent_chat_minimal.transport import create_response, create_run


class FailingGraph:
    def __init__(self, exc):
        self._exc = exc

    async def astream(self, *args, **kwargs):
        raise self._exc
        if False:  # pragma: no cover - keep async-generator shape
            yield ()


def _client(exc, **kwargs):
    kwargs.setdefault("graph", FailingGraph(exc))
    mode = kwargs.pop("server_mode", "prod")
    kwargs.setdefault("settings", Settings(server_mode=mode))
    # The stream protocol emits the error chunk, then re-raises to fail the
    # run: the default client propagates that structured failure.
    return TestClient(create_app(**kwargs))


def test_classify_missing_key():
    out = classify_provider_error(RuntimeError("OPENAI_API_KEY is missing: set it"))
    assert out["error"] == "auth_missing_key"
    assert "restart" in out["hint"]


def test_classify_invalid_key():
    out = classify_provider_error(Exception("Error 401: incorrect api key provided"))
    assert out["error"] == "auth_invalid_key"


def test_classify_quota_exhausted():
    out = classify_provider_error(
        Exception("You exceeded your current quota, check billing")
    )
    assert out["error"] == "quota_exhausted"


def test_classify_rate_limited():
    out = classify_provider_error(Exception("429 too many requests, slow down"))
    assert out["error"] == "rate_limited"


def test_classify_generic_provider_error():
    out = classify_provider_error(ValueError("weird provider boom"))
    assert out["error"] == "provider_error"
    assert "weird provider boom" in out["message"]


def _post_assistant(client):
    response = client.post("/assistant", json={"state": {"messages": []}, "commands": []})
    assert response.status_code == 200
    return response.text


def test_debug_stream_carries_structured_error():
    # The failed run ends cleanly (raising would abort the connection and
    # browsers would report only "network error"): the structured JSON
    # travels as a `3:` error chunk in the 200 stream.
    client = _client(
        RuntimeError("OPENAI_API_KEY is missing"),
        server_mode="debug",
    )
    text = _post_assistant(client)
    assert "auth_missing_key" in text
    assert "Model API key is missing" in text


def test_prod_stream_redacts_provider_detail():
    secret = "OPENAI_API_KEY is missing: sk-secret-abc123"
    client = _client(RuntimeError(secret), server_mode="prod")
    text = _post_assistant(client)
    assert "auth_missing_key" in text
    assert "sk-secret-abc123" not in text


def test_structured_error_reaches_wire_as_error_chunk():
    # A structured error emitted into the run arrives on the wire as a `3:`
    # error chunk before clean completion — that chunk is what the UI's
    # onError turns into the red error box.
    payload = format_stream_error(
        RuntimeError("You exceeded your current quota"), debug=True
    )

    async def failing_callback(controller):
        controller.add_error(payload)

    async def collect():
        body = []
        try:
            async for chunk in create_response(
                create_run(failing_callback)
            ).body_iterator:
                body.append(chunk)
        except RuntimeError:
            pass
        return "".join(body)

    wire = asyncio.run(collect())
    assert "quota_exhausted" in wire
    assert wire.splitlines()[-1].startswith("3:")


def test_format_stream_error_modes():
    debug = json.loads(format_stream_error(RuntimeError("no key: api key missing"), debug=True))
    assert debug["error"] == "auth_missing_key"
    assert "hint" in debug
    prod = json.loads(format_stream_error(RuntimeError("no key: api key missing"), debug=False))
    assert prod["error"] == "auth_missing_key"
    assert "hint" not in prod
    assert prod["message"] == "The assistant failed while generating a response."
