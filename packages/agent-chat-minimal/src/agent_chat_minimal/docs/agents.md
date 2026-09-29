# Implementing an agent

Any compiled LangGraph graph over `{"messages": [...]}` is servable. The server
calls this contract (see `ChatGraph` in `server.py`):

```python
graph.astream(input, config=..., stream_mode=[...], subgraphs=True)
# yields (namespace, event_type, chunk) triples
```

The reference implementation is `demo_agent/calculator.py`: a provider-aware
factory that passes the optional checkpointer to a LangGraph tool agent.

## 1. Write a factory

```python
# my_agent.py
from langchain_core.tools import tool
from agent_chat_minimal.demo_agent.agent_factory import make_tool_agent

@tool
def shout(text: str) -> str:
    """Uppercase the input."""
    return text.upper()

def make_shout_agent(model="openai:gpt-4o-mini", checkpointer=None):
    return make_tool_agent(model, [shout], "Reply ONLY with the tool result.")
```

Serve it — no server fork needed:

```python
# serve.py
from agent_chat_minimal import create_app
from my_agent import make_shout_agent

app = create_app(graph_factory=make_shout_agent)
# python -m uvicorn serve:app --port 8011
```

Prefer an instance? `create_app(graph=make_shout_agent(...))` works too;
the factory form defers credential errors to startup instead of import.

## 2. Serve it from an application

```python
app = create_app(
    agents={"shout": make_shout_agent},
    default_agent="shout",
)
# POST /assistant/shout; POST /assistant aliases "shout"
```

Passing `agents` replaces the discovered registry; it does not add to it.
Without `agents`, the discovered registry includes the built-ins and defaults to
`"weather"`. Specify `default_agent` whenever a mapping has more than one
entry.

## 3. Share through pip (no fork)

Register the `agent_chat.agents` entry-points group:

```toml
[project.entry-points."agent_chat.agents"]
shout = "my_package.my_agent:make_shout_agent"
```

`discover_agents()` picks it up automatically alongside the built-ins. Install
the plugin and package in the same environment, then choose it with
`DEFAULT_AGENT=shout minimal-chat-serve --port 8011` or
`minimal-chat-serve --agent shout --check`. Entry points cannot shadow the
`weather` or `calculator` built-ins.

## Checklist

- [ ] Factory accepts `checkpointer=None` so the server can inject shared graph
      state. A `model=...` argument is recommended for configurable providers.
- [ ] Tools have clear docstrings — the model only sees those.
- [ ] Offline test with a fake model (see `tests/test_provider_agnostic.py`).
- [ ] `minimal-chat-serve --agent shout --check` builds without network creds
      only if the model is fake/local; otherwise expect a credential error.
