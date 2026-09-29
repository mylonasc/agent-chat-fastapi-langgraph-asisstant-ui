# Model providers

Factories take either a legacy `provider:name` spec, a structured `ModelConfig`,
or an already-built chat model instance. Most specs resolve through LangChain's
`init_chat_model`; direct LiteLLM uses its optional LangChain integration.

## Specs

| Spec prefix | Example                     | Credential env      | Install extra        |
| ----------- | --------------------------- | ------------------- | -------------------- |
| `openai:`   | `openai:gpt-4o-mini`        | `OPENAI_API_KEY`    | `openai` ✓ |
| `anthropic:`| `anthropic:claude-sonnet-4-5` | `ANTHROPIC_API_KEY` | `anthropic`|
| `ollama:`   | `ollama:llama3.1`           | none (local daemon) | `ollama`   |
| `litellm:` | `litellm:anthropic/claude-sonnet-4-5` | upstream-specific | `litellm` |
| `google_genai:` | `google_genai:gemini-2.5-flash` | `GOOGLE_API_KEY`| `google` |

`openai` remains installed by default for the packaged demo. Install another
provider with, for example, `pip install "agent-chat-fastapi-langgraph-assistant-ui[ollama]"`.
Provider imports remain lazy until selected.

Bare `gpt-4o-mini` still works (provider inferred as OpenAI) for backward
compatibility; prefer the explicit `openai:` prefix.

## Selecting the model

```bash
MODEL=anthropic:claude-sonnet-4-5 minimal-chat-serve
minimal-chat-serve --model ollama:llama3.1 --agent calculator
```

## Structured configuration

Use `ModelConfig` where an application needs a custom endpoint, credential
environment variable, or model parameters. The credential value is read only
when the model is constructed and is never stored in the configuration object.

```python
from agent_chat_minimal import ModelConfig
from agent_chat_minimal.demo_agent.get_graph import make_agent_with_weather_tool

model = ModelConfig(
    provider="ollama",
    model="llama3.1:8b",  # model ids are opaque; this colon is preserved
    base_url="http://localhost:11434",
    kwargs={"temperature": 0.2},
)
graph = make_agent_with_weather_tool(model)
```

`litellm:` directly constructs `langchain_litellm.ChatLiteLLM`; install it with
`pip install "agent-chat-fastapi-langgraph-assistant-ui[litellm]"`. Its model
name is passed through unchanged, for example `anthropic/claude-sonnet-4-5`.
If LiteLLM is running an OpenAI-compatible proxy instead, use `provider="openai"`
with that proxy's `base_url`. Credential requirements depend on the upstream
provider. Model construction and the package's offline checks do not prove that
an endpoint is reachable or supports tool calls.

## Instances and offline tests

Pass any `BaseChatModel` (streaming or fake) straight in:

```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

class Bindable(GenericFakeChatModel):
    def bind_tools(self, *a, **k):
        return self  # base class raises NotImplementedError

graph = make_calculator_agent(Bindable(messages=iter([...])))
```

This is how the bundled tests run the full agent loop with no network.
