"""Deterministic backend for thread-sync e2e tests (no network, no creds).

Serves the prebuilt static UI and the API from one origin (like a real
deployment) with an echo fake agent: turn N answers ``reply-N`` where N is
the number of human messages seen so far. Run via the Playwright webServer
entry in ``e2e/thread-sync.config.ts``.
"""

import os
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = FRONTEND_DIR.parent.parent.parent
PACKAGE_SRC = REPO_ROOT / "packages" / "agent-chat-minimal" / "src"
assert PACKAGE_SRC.is_dir(), f"package source not found at {PACKAGE_SRC}"
sys.path.insert(0, str(PACKAGE_SRC))

from langchain_core.messages import AIMessage  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402

from agent_chat_minimal import Settings, create_app  # noqa: E402
from agent_chat_minimal.demo_agent.agent_factory import AgentState  # noqa: E402


def make_echo_graph(checkpointer=None):
    """Deterministic model inside a real checkpointed graph.

    Count the model-facing messages *after* checkpoint loading/reduction,
    not just the HTTP request. A stateless fake missed stale branch context
    in #72. Unique assistant IDs also avoid cross-thread transcript collisions.
    """

    async def answer(state):
        import uuid

        humans = sum(1 for m in state["messages"] if _is_human(m))
        return {
            "messages": [
                AIMessage(content=f"reply-{humans}", id=f"ai-{uuid.uuid4().hex[:8]}")
            ]
        }

    builder = StateGraph(AgentState)
    builder.add_node("model", answer)
    builder.add_edge(START, "model")
    builder.add_edge("model", END)
    return builder.compile(checkpointer=checkpointer)


def _is_human(message) -> bool:
    if isinstance(message, dict):
        return message.get("type") == "human" or message.get("role") == "user"
    return getattr(message, "type", "") == "human"


def _bomb_factory():
    """Factory that always fails, like a misconfigured provider backend."""
    raise RuntimeError(
        "E2E bomb: agent factory failed: "
        "Initializing ChatOllama requires the langchain-ollama package. "
        "Please install it with `pip install langchain-ollama`"
    )


def main() -> None:
    port = int(os.environ.get("E2E_PORT", "18099"))
    web_dir = FRONTEND_DIR / "out"
    settings = Settings(
        ui_preset="full",
        server_mode=os.environ.get("E2E_SERVER_MODE", "prod"),
    )
    if os.environ.get("E2E_BOMB") == "1":
        app = create_app(
            graph_factory=_bomb_factory, settings=settings, web_dir=web_dir
        )
    else:
        app = create_app(
            graph_factory=make_echo_graph, settings=settings, web_dir=web_dir
        )
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
