import sys
from types import ModuleType

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent_chat_minimal import ToolsNotSupportedError
from agent_chat_minimal.demo_agent.agent_factory import make_tool_agent, resolve_llm
from agent_chat_minimal.demo_agent.get_graph import (
    get_weather,
    make_agent_with_weather_tool,
)
from agent_chat_minimal.models import ModelConfig


class BindableFake(GenericFakeChatModel):
    def bind_tools(self, *args, **kwargs):
        return self


def test_fake_model_instance_compiles_and_invokes():
    fake = BindableFake(messages=iter([AIMessage(content="fake hi")]))
    graph = make_agent_with_weather_tool(fake)
    result = graph.invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert result["messages"]


def test_resolve_llm_passes_instance_through():
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="x")]))
    assert resolve_llm(fake) is fake


def test_legacy_bare_name_maps_to_openai_spec(monkeypatch):
    seen = {}

    def fake_make_tool_agent(model, tools, checkpointer=None):
        seen["model"] = model
        return object()

    import agent_chat_minimal.demo_agent.get_graph as get_graph

    monkeypatch.setattr(get_graph, "make_tool_agent", fake_make_tool_agent)
    get_graph.make_agent_with_weather_tool("gpt-4o-mini")
    assert seen["model"] == "openai:gpt-4o-mini"


def test_string_spec_forwarded_to_init_chat_model(monkeypatch):
    seen = {}

    def fake_init(spec, **kwargs):
        seen["spec"] = spec
        return GenericFakeChatModel(messages=iter([AIMessage(content="x")]))

    import langchain.chat_models as chat_models

    monkeypatch.setattr(chat_models, "init_chat_model", fake_init)
    resolve_llm("anthropic:claude-sonnet-4-5")
    assert seen["spec"] == "anthropic:claude-sonnet-4-5"


def test_structured_config_forwards_endpoint_credential_and_kwargs(monkeypatch):
    seen = {}

    def fake_init(spec, **kwargs):
        seen["spec"] = spec
        seen["kwargs"] = kwargs
        return GenericFakeChatModel(messages=iter([AIMessage(content="x")]))

    import langchain.chat_models as chat_models

    monkeypatch.setattr(chat_models, "init_chat_model", fake_init)
    monkeypatch.setenv("CUSTOM_OPENAI_KEY", "secret")
    resolve_llm(
        ModelConfig(
            provider="openai",
            model="gpt-4o-mini",
            base_url="https://example.test/v1",
            credential_env="CUSTOM_OPENAI_KEY",
            kwargs={"temperature": 0.2},
        )
    )

    assert seen == {
        "spec": "openai:gpt-4o-mini",
        "kwargs": {
            "streaming": True,
            "base_url": "https://example.test/v1",
            "api_key": "secret",
            "temperature": 0.2,
        },
    }


def test_structured_config_keeps_namespaced_model_identifier_opaque():
    config = ModelConfig(provider="ollama", model="llama3.1:8b")
    assert config.spec == "ollama:llama3.1:8b"


def test_litellm_uses_optional_langchain_integration(monkeypatch):
    seen = {}

    class FakeChatLiteLLM:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    module = ModuleType("langchain_litellm")
    module.ChatLiteLLM = FakeChatLiteLLM
    monkeypatch.setitem(sys.modules, "langchain_litellm", module)
    monkeypatch.setenv("UPSTREAM_KEY", "secret")

    model = resolve_llm(
        ModelConfig(
            provider="litellm",
            model="anthropic/claude-sonnet-4-5",
            base_url="https://proxy.example.test",
            credential_env="UPSTREAM_KEY",
        )
    )

    assert isinstance(model, FakeChatLiteLLM)
    assert seen == {
        "model": "anthropic/claude-sonnet-4-5",
        "streaming": True,
        "api_base": "https://proxy.example.test",
        "api_key": "secret",
    }


class _NoToolsError(Exception):
    """Mimics e.g. ollama.ResponseError for a model without tool support."""


class _ToolRejectingModel:
    """Stand-in chat model whose provider rejects tools at invoke time."""

    def bind_tools(self, *args, **kwargs):
        return self

    def invoke(self, messages):
        raise _NoToolsError(
            "registry.ollama.ai/library/llama3:latest does not support tools"
        )


class _FlakyModel(_ToolRejectingModel):
    def invoke(self, messages):
        raise RuntimeError("connection reset by peer")


def test_tool_rejection_becomes_actionable_error_naming_the_model():
    from agent_chat_minimal.demo_agent import agent_factory

    original = agent_factory.resolve_llm
    agent_factory.resolve_llm = lambda model: _ToolRejectingModel()
    try:
        graph = make_tool_agent("ollama:llama3", [get_weather])
    finally:
        agent_factory.resolve_llm = original

    try:
        graph.invoke({"messages": [{"role": "user", "content": "hi"}]})
    except ToolsNotSupportedError as exc:
        assert "'ollama:llama3'" in str(exc)
        assert "does not support tools" in str(exc)
        assert "tool-capable model" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("tool rejection was not converted")


def test_unrelated_invoke_errors_pass_through_unchanged():
    from agent_chat_minimal.demo_agent import agent_factory

    original = agent_factory.resolve_llm
    agent_factory.resolve_llm = lambda model: _FlakyModel()
    try:
        graph = make_tool_agent("ollama:llama3", [get_weather])
    finally:
        agent_factory.resolve_llm = original

    try:
        graph.invoke({"messages": [{"role": "user", "content": "hi"}]})
    except RuntimeError as exc:
        assert str(exc) == "connection reset by peer"
        assert not isinstance(exc, ToolsNotSupportedError)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("unrelated error was swallowed")


def test_tool_rejection_names_structured_model_configs():
    from agent_chat_minimal.demo_agent import agent_factory

    original = agent_factory.resolve_llm
    agent_factory.resolve_llm = lambda model: _ToolRejectingModel()
    try:
        graph = make_tool_agent(
            ModelConfig(provider="ollama", model="llama3.1:8b"), [get_weather]
        )
    finally:
        agent_factory.resolve_llm = original

    try:
        graph.invoke({"messages": [{"role": "user", "content": "hi"}]})
    except ToolsNotSupportedError as exc:
        # The namespaced model id stays opaque in the message.
        assert "ollama:llama3.1:8b" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("tool rejection was not converted")
