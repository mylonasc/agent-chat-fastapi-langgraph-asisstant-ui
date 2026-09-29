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

The package's in-wheel version of this guide is
[`agents.md`](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/agents.md).
