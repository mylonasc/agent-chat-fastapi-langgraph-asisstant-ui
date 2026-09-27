# Agent Chat Minimal

This Python distribution bundles a LangGraph agent, a FastAPI server, and a
prebuilt static minimal chat UI. Node is needed only to build the web
payload, not to install or run the resulting wheel. The default agent runs
fully offline: **no `OPENAI_API_KEY` or any other API key is required**.

From the repository root, build the UI and wheel with:

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
```

The script runs the frozen pnpm install and static export, stages `out/` as
package data, and writes the wheel under `packages/agent-chat-minimal/dist/`.
Generated `web/` content and `dist/` are intentionally gitignored.

Install from PyPI (Python 3.11+, no Node required) and serve with:

```bash
pip install agent-chat-fastapi-langgraph-assistant-ui
minimal-chat-serve --port 8011
```

Or install and serve the locally built wheel with:

```bash
python -m pip install packages/agent-chat-minimal/dist/*.whl
minimal-chat-serve --port 8011
```

Open <http://localhost:8011/>. The same process serves the static UI,
`/health`, and `/assistant`, all working with zero configuration.
`MINIMAL_WEB_DIR` may override the bundled web directory.

## Creating a compatible agent

The server is a thin bridge between the chat UI and a LangGraph graph. Any
graph that keeps the contract below renders in the bundled UI, streams
token-by-token when the model supports it, and keeps conversation state
across turns.

### How a turn works

1. The UI sends `POST /assistant` with a JSON body of the form
   `{"state": {"messages": [...]}, "commands": [...]}`. Each command is
   either `add-message` (a new user message with `parts: [{type: "text",
   text: "..."}]`) or `add-tool-result` (a frontend tool result).
2. The server appends new user messages to `state["messages"]` as LangChain
   `HumanMessage` dicts and calls your graph as
   `graph.astream({"messages": [...]}, stream_mode=["messages"],
   subgraphs=True)`.
3. Every streamed message event is folded back into the state with
   `assistant_stream_ce.modules.langgraph.append_langgraph_event`, and the
   updated state streams back to the UI as the run progresses. The UI
   converts the LangChain messages (`human` / `ai` / `tool`, including AI
   tool calls) into chat bubbles.
4. The next request carries the accumulated `state`, so multi-turn
   conversation works without any server-side session storage.

### Compatibility contract

Your agent is compatible if it satisfies all of these:

1. **Built with LangGraph** and compiled (e.g. `workflow.compile()`), or
   any object exposing `astream(input, stream_mode=["messages"],
   subgraphs=True)` yielding `(namespace, "messages", (message, metadata))`
   tuples like LangGraph does.
2. **State has a `messages` channel** reduced with
   `langgraph.graph.message.add_messages`, e.g.
   `class State(TypedDict): messages: Annotated[list, add_messages]`. The
   server passes message *dicts* (LangChain `model_dump` form); LangGraph
   converts them back to message objects automatically.
3. **Emits LangChain messages**: `AIMessage` for replies (plain text, or
   with `tool_calls` to invoke tools), `ToolMessage` for tool results.
   Everything must survive `message.model_dump()` (plain JSON types only).
4. **Tools are LangChain `@tool` functions** whose arguments and return
   values are JSON-serializable. The argument schema is derived from the
   function signature and type hints.
5. **Tool rendering**: an AI message with `tool_calls` renders a tool
   bubble. Only `render_graph` (see below) has a custom visualization; any
   other tool falls back to a generic tool-result view. To add a custom
   visualization for your own tool, register a matching `makeAssistantToolUI`
   with the same `toolName` in the frontend.

### Wiring a custom agent

Pass a zero-argument factory to `create_app`:

```python
from agent_chat_minimal import create_app
from my_package.my_agent import make_my_agent

app = create_app(graph_factory=make_my_agent)
```

or point the server at it without code changes:

```bash
export MINIMAL_AGENT_FACTORY="my_package.my_agent:make_my_agent"
minimal-chat-serve --port 8011
```

`MINIMAL_AGENT_FACTORY` accepts `package.module:factory` (or
`package.module.factory`). The module must be importable where the server
runs, i.e. the package providing it must be installed in the same
environment. A bad value fails fast at startup with an explicit error.

### Minimal example: echo agent

```python
from typing import Annotated, TypedDict
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]


def reply(state: State):
    last_user_text = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )
    return {"messages": [AIMessage(content=f"You said: {last_user_text}")]}


def make_my_agent():
    workflow = StateGraph(State)
    workflow.add_node("reply", reply)
    workflow.set_entry_point("reply")
    workflow.add_edge("reply", END)
    return workflow.compile()
```

Serve it with `create_app(graph_factory=make_my_agent)` and every message is
echoed back in the UI. The repo's own default agent,
`agent_chat_minimal.demo_agent.local_agent.make_local_agent`, is a slightly
larger version of this pattern: a rule-based router node plus a `ToolNode`,
and a good template to copy.

### Example: agent with a custom tool

```python
import uuid
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition

@tool
def shout(text: str) -> str:
    """Return the input text in upper case."""
    return text.upper()

def _last_text(state: State) -> str:
    return next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

def make_my_agent():
    workflow = StateGraph(State)
    workflow.add_node("agent", lambda state: {
        "messages": [AIMessage(content="", tool_calls=[{
            "name": "shout",
            "args": {"text": _last_text(state)},
            "id": f"call-{uuid.uuid4().hex[:8]}",
            "type": "tool_call",
        }])]
    })
    workflow.add_node("tools", ToolNode([shout]))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", END)
    return workflow.compile()
```

Notes that save debugging time:

- Every tool call needs a unique `id`; the matching `ToolMessage` carries it
  back as `tool_call_id` so the UI can pair call and result.
- Tool arguments must match the `@tool` function signature; the result must
  be JSON-serializable (return a `str` or `dict`, not an arbitrary object).
- Always end the turn with a plain-text `AIMessage` after tool execution so
  the user gets a readable reply, not just a tool bubble.

### The `render_graph` tool

`agent_chat_minimal.demo_agent.tools.graph_tool.render_graph` renders an
interactive D3 graph in the UI (the frontend registers a `render_graph`
tool UI with that exact name). Call it with:

```python
{
    "nodes": [{"id": "a", "label": "A", "weight": 70}],
    "edges": [{"source": "a", "target": "b", "label": "", "weight": 50}],
    "directed": True,
}
```

`id`/`source`/`target` are required strings; `label` is optional;
`weight` is clamped to 0–100 for node sizing. Duplicate or id-less nodes
and edges pointing at missing ids are dropped. The tool returns the cleaned
payload, which is what the UI renders.

### Example: opting back into an OpenAI agent

The default agent needs no key. If you prefer a real LLM, install a package
providing one (this distribution already depends on `langchain-openai` for
the bundled example) and point the server at the OpenAI demo factory:

```bash
export OPENAI_API_KEY=sk-...
export MINIMAL_AGENT_FACTORY="agent_chat_minimal.demo_agent.get_graph:make_agent_with_weather_tool"
minimal-chat-serve --port 8011
```

`make_agent_with_weather_tool` builds the same `messages`-state graph shape
as the local agent — a chat model node plus a `ToolNode` with `get_weather`
and `render_graph` — so it satisfies the contract above and is another
reference for wiring model-based agents.

### Testing your agent

The fastest loop is the offline serving test (no key, no network). With the
package installed with the `test` extra:

```python
from fastapi.testclient import TestClient
from agent_chat_minimal import create_app

client = TestClient(create_app(graph_factory=make_my_agent))
response = client.post("/assistant", json={
    "state": {"messages": []},
    "commands": [{
        "type": "add-message",
        "message": {"id": "t1", "parts": [{"type": "text", "text": "hi"}]},
    }],
})
assert response.status_code == 200
assert "hi" in response.text
```

Or exercise a running server with curl:

```bash
curl -X POST http://localhost:8011/assistant \
  -H 'content-type: application/json' \
  -d '{"state":{"messages":[]},"commands":[{"type":"add-message","message":{"id":"t1","parts":[{"type":"text","text":"hi"}]}}]}'
```

Run the offline serving tests and clean-venv smoke check from the repository
root:

```bash
python3 -m venv /tmp/agent-chat-minimal-tests
/tmp/agent-chat-minimal-tests/bin/pip install \
  "packages/agent-chat-minimal[test]"
/tmp/agent-chat-minimal-tests/bin/pytest packages/agent-chat-minimal
packages/agent-chat-minimal/scripts/smoke_test_wheel.sh
```

Build the Python-only runtime image after building the wheel:

```bash
docker build -t agent-chat-minimal packages/agent-chat-minimal
docker run --rm -p 8011:8011 agent-chat-minimal
```

No `--env` / `--env-file` flags are needed: chat works without API keys.
