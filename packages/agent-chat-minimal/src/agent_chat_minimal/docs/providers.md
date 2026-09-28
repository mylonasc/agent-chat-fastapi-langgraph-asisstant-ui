# Model providers

Factories take either a `provider:name` spec (resolved via LangChain's
`init_chat_model`) or an already-built chat model instance.

## Specs

| Spec prefix | Example                     | Credential env      | Install extra        |
| ----------- | --------------------------- | ------------------- | -------------------- |
| `openai:`   | `openai:gpt-4o-mini`        | `OPENAI_API_KEY`    | `openai` ✓ |
| `anthropic:`| `anthropic:claude-sonnet-4-5` | `ANTHROPIC_API_KEY` | `anthropic`|
| `ollama:`   | `ollama:llama3.1`           | none (local daemon) | `ollama`   |
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
