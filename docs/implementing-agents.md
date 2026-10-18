# Implementing Agents

New non-RAG agents belong in or on top of `packages/agent-chat-minimal`. The
server accepts a compiled LangGraph graph over a state containing `messages`.
It calls `graph.astream(input, config=..., stream_mode=[...], subgraphs=True)`
and streams LangGraph event triples to Assistant UI.

Use the package's calculator example as the reference implementation:
`packages/agent-chat-minimal/src/agent_chat_minimal/demo_agent/calculator.py`.

## 1. Write A Graph Factory

Factories should accept an optional `checkpointer` keyword so the server can
share in-memory or durable LangGraph state. A `model` argument is conventional
and makes the agent configurable and testable.

```python
# my_agent.py
from langchain_core.tools import tool
from agent_chat_minimal.demo_agent.agent_factory import make_tool_agent


@tool
def shout(text: str) -> str:
    """Return the supplied text in uppercase."""
    return text.upper()


def make_shout_agent(
    model: str = "openai:gpt-4o-mini", checkpointer=None
):
    return make_tool_agent(
        model, [shout], "Reply using the shout tool.", checkpointer
    )
```

Tool docstrings are model-facing instructions. Test the factory with a fake or
local model before relying on provider credentials.

## 2. Serve It In An Application

Embed one graph directly when the application owns its agent:

```python
# serve.py
from agent_chat_minimal import create_app
from my_agent import make_shout_agent

app = create_app(graph_factory=make_shout_agent)
```

Run it with `python -m uvicorn serve:app --port 8011`. A prebuilt graph also
works: `create_app(graph=make_shout_agent(...))`.

To expose several named agents, pass a mapping and explicitly choose the
unscoped `/assistant` alias:

```python
app = create_app(
    agents={"shout": make_shout_agent, "weather": make_weather_agent},
    default_agent="shout",
)
```

This serves `POST /assistant/shout` and `POST /assistant/weather`; `POST
/assistant` invokes `shout`. A supplied `agents` mapping **replaces** the
built-in/discovered registry, so include every agent your application should
expose.

## 3. Publish A Plugin Agent

To make an agent available to `minimal-chat-serve` without forking this
repository, publish a Python package with an entry point:

```toml
[project.entry-points."agent_chat.agents"]
shout = "my_package.my_agent:make_shout_agent"
```

Install both distributions in the same environment, then select the plugin:

```bash
python -m pip install agent-chat-fastapi-langgraph-assistant-ui my-agent-package
DEFAULT_AGENT=shout minimal-chat-serve --port 8011
minimal-chat-serve --agent shout --check
```

`GET /agents` shows built-ins (`weather`, `calculator`) plus successfully
loaded plugins. Plugin names cannot replace built-ins; choose a unique name.

## Full RAG Backend

`application/backend/full` has no plugin registry. Its agents and tools are
assembled in source, primarily under `fastlang/server/` and `tools/`. Change it
only when extending the separate RAG demo; do not expect those tools to ship in
the portable package.

## 4. Render A2UI Surfaces From Tools

The chat UI renders [A2UI v0.9](https://a2ui.org/specification/v0.9-a2ui/)
surfaces from tool results via `@a2ui-sdk/react/0.9`. No graph changes are
needed: any `@tool` returning the envelope below gets a rich card instead of
the generic tool fallback. Reference: `demo_agent/tools/a2ui.py`,
`tests/test_a2ui_envelope.py`, `tests/test_a2ui_graph.py`.

```python
@tool("render_a2ui_demo")
def render_a2ui_demo(title: str, body: str) -> dict:
    return {
        "a2ui_version": "v0.9",
        "surfaceId": "demo-card",
        "catalogId": "https://a2ui.org/specification/v0_9/basic_catalog.json",
        "messages": [
            {"version": "v0.9",
             "createSurface": {"surfaceId": "demo-card",
                               "catalogId": ".../basic_catalog.json"}},
            {"version": "v0.9",
             "updateComponents": {"surfaceId": "demo-card", "components": [...]}},
            {"version": "v0.9",
             "updateDataModel": {"surfaceId": "demo-card",
                                 "path": "/booking", "value": {...}}},
        ],
    }
```

Contract rules:

1. Every message carries `"version": "v0.9"`. Keep components a flat list
   with `id` refs (`Column.children: [...]`).
2. **SDK dialect, not protocol-docs dialect.** `@a2ui-sdk/react` 0.9 Button
   props are `{child, primary?, action: {name, context?}}` — flat `name`,
   not `{event: {name}}`, and `primary: true`, not `variant: "primary"`.
   (The docs-shaped action renders but silently drops the action name;
   `test_a2ui_envelope.py` pins the SDK shape.)
3. Prefer `{"path": "/..."}` bindings plus `dataModel` over literals, so
   updates re-render without regenerating layout. Custom components
   (e.g. `NetworkGraph`, see `render_network_a2ui`) take literal props.
4. One self-contained envelope per call: `createSurface` +
   `updateComponents` (+ `dataModel` snapshot) every time, with a per-call
   `surfaceId`. The transcript stores results verbatim and replays them on
   reload, so shared mutable surfaces across turns break determinism.
5. Actions round-trip as ordinary chat text: a `confirm_booking` click
   arrives as a `[a2ui-action confirm_booking] {...}` user message on the
   next turn. Document stable action names in the tool docstring — the
   model only sees that.
6. Sanitize server-side (ids, weights) and keep payloads small and
   JSON-serializable; reuse the `_clamp_0_100` precedent in `graph_tool.py`.

The package's in-wheel version of this guide is
[`agents.md`](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/agents.md).
