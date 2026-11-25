"""Credential-free checks for the optional full-agent monitoring example."""

import asyncio
import json
import os
from unittest.mock import Mock

import pytest

pytest.importorskip("phoenix.otel")
pytest.importorskip("openinference.instrumentation.langchain")

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from examples.phoenix_monitoring import serve


class ToolCallingModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def spans():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    instrumentor = LangChainInstrumentor()
    instrumentor.instrument(tracer_provider=provider)
    try:
        yield exporter
    finally:
        instrumentor.uninstrument()
        provider.shutdown()


def test_real_full_agent_stream_has_nested_model_and_tool_spans(spans, monkeypatch):
    from fastlang.server.get_graph import make_web_rag_search_agent
    from tools.web_rag import status_tool

    # Keep the repository's tool, graph, and async streaming path. Only replace
    # the paid model and status storage reads with deterministic test doubles.
    monkeypatch.setattr(status_tool, "get_index_status", lambda *a: {"ready": False})
    monkeypatch.setattr(status_tool.INDEXING_MANAGER, "list_jobs", lambda **kw: [])
    model = ToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "web_rag_status", "args": {}, "id": "status-1"}],
            ),
            AIMessage(content="Your local index is not ready."),
        ]
    )
    graph = make_web_rag_search_agent(model_name=model, mode="react")

    async def stream():
        return [
            event
            async for event in graph.astream(
                {"messages": [HumanMessage(content="Check the index status.")]},
                {"configurable": {"thread_id": "phoenix-test"}},
                stream_mode=["messages", "updates", "custom"],
                subgraphs=True,
            )
        ]

    assert asyncio.run(stream())
    finished = spans.get_finished_spans()
    kinds = [s.attributes.get("openinference.span.kind") for s in finished]
    assert "CHAIN" in kinds
    assert kinds.count("LLM") == 2
    tool_span = next(
        s for s in finished if s.attributes.get("openinference.span.kind") == "TOOL"
    )
    assert tool_span.name == "web_rag_status"
    output = json.loads(tool_span.attributes["output.value"])
    assert json.loads(output["data"]["content"])["index"]["ready"] is False
    assert len({s.context.trace_id for s in finished}) == 1
    assert tool_span.parent is not None
    assert any(s.attributes.get("session.id") == "phoenix-test" for s in finished)


def test_http_stream_keeps_tracing_context(spans, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from fastlang.server import get_graph

    graph = get_graph.make_web_rag_search_agent(
        model_name=ToolCallingModel(responses=[AIMessage(content="Monitoring works.")]),
        mode="react",
    )
    # The import constructs a model but makes no requests. Replace the graph
    # before invoking HTTP; a placeholder suffices for credential validation.
    monkeypatch.setenv("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY") or "test-placeholder")
    monkeypatch.setenv("AGENT_MODE", "react")
    from fastlang.server import server

    monkeypatch.setattr(server, "graph", graph)
    monkeypatch.setattr(server, "OPENAI_API_KEY", "test-not-a-real-key")
    thread_id = "phoenix-http-test"

    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            return await client.post(
                "/assistant",
                json={
                    "thread_id": thread_id,
                    "state": {"messages": []},
                    "commands": [{
                        "type": "add-message",
                        "message": {
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        },
                    }],
                },
            )

    try:
        response = asyncio.run(request())
        assert response.status_code == 200
        assert "Monitoring works." in response.text
        assert any(
            s.attributes.get("session.id") == thread_id
            for s in spans.get_finished_spans()
        )
    finally:
        server.thread_manager._threads.pop(thread_id, None)


def test_configure_tracing_uses_http_batching_without_double_instrumentation(monkeypatch):
    import phoenix.otel

    provider = Mock()
    register = Mock(return_value=provider)
    instrument = Mock()
    monkeypatch.setattr(phoenix.otel, "register", register)
    monkeypatch.setattr(LangChainInstrumentor, "instrument", instrument)
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "test-project")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://collector:6006/v1/traces")

    assert serve.configure_tracing() is provider
    register.assert_called_once_with(
        project_name="test-project",
        endpoint="http://collector:6006/v1/traces",
        protocol="http/protobuf",
        batch=True,
        auto_instrument=False,
    )
    instrument.assert_called_once_with(tracer_provider=provider)


@pytest.mark.parametrize("fail", [False, True])
def test_launcher_initializes_before_server_and_flushes_on_exit(monkeypatch, fail):
    import uvicorn

    provider = Mock()
    configured = []

    def configure():
        configured.append(True)
        return provider

    def run(app, **kwargs):
        assert configured
        assert app == "fastlang.server.server:app"
        if fail:
            raise RuntimeError("server failed")

    monkeypatch.setattr(serve, "configure_tracing", configure)
    monkeypatch.setattr(uvicorn, "run", run)
    if fail:
        with pytest.raises(RuntimeError, match="server failed"):
            serve.main()
    else:
        serve.main()
    provider.force_flush.assert_called_once_with()
    provider.shutdown.assert_called_once_with()
