# Implementing an agent

Any compiled LangGraph graph over `{"messages": [...]}` is servable. The only
contract (see `ChatGraph` in `server.py`) is:

```python
graph.astream(input, config=..., stream_mode=[...], subgraphs=True)
# yields (namespace, event_type, chunk) triples
```

## Minimal custom agent (5 minutes)

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

## Multi-agent serving

```python
app = create_app(agents={"shout": make_shout_agent})
# POST /assistant/shout, GET /agents -> ["shout"]
```

Passing `agents` replaces the discovered registry. In a custom mapping,
`POST /assistant` aliases the first entry unless `default_agent` is provided.
Without `agents`, the discovered registry includes the built-ins and defaults
to `"weather"`.

## Reference: calculator agent

`demo_agent/calculator.py` (`add`/`subtract`/`multiply`/`divide` +
`make_calculator_agent`) is the canonical example: tools, system prompt,
provider-agnostic model arg, optional `checkpointer` passthrough.

## Sharing via pip (no fork)

Register the `agent_chat.agents` entry-points group:

```toml
[project.entry-points."agent_chat.agents"]
shout = "my_package.my_agent:make_shout_agent"
```

`discover_agents()` picks it up automatically alongside the built-ins.

## Checklist

- [ ] Factory signature `(model=..., checkpointer=None)` so the server can
      inject the shared checkpointer.
- [ ] Tools have clear docstrings — the model only sees those.
- [ ] Offline test with a fake model (see `tests/test_provider_agnostic.py`).
- [ ] `minimal-chat-serve --agent shout --check` builds without network creds
      only if the model is fake/local; otherwise expect a credential error.
