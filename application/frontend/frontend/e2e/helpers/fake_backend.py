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

from langchain_core.messages.ai import AIMessageChunk  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from agent_chat_minimal import Settings, create_app  # noqa: E402


class EchoFake:
    """Deterministic chat graph: reply-N per human message count.

    Assistant ids are unique per turn (like real LangChain run ids):
    repeating ids such as ``ai-1`` in every thread would collide across
    threads on transcript append (409) exactly like the legacy numeric
    human ids did.
    """

    async def astream(self, *args, **kwargs):
        import uuid

        state_input = args[0] if args else {}
        messages = state_input.get("messages", []) if isinstance(state_input, dict) else []
        humans = sum(1 for m in messages if _is_human(m))
        text = f"reply-{humans}"
        yield (), "messages", (AIMessageChunk(content=text, id=f"ai-{uuid.uuid4().hex[:8]}"), {})


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


def _a2ui_graph():
    """Deterministic a2ui agent: first turn calls render_a2ui_demo, then replies.

    Uses the real demo tool + real ToolNode + real transport so the e2e
    exercises the exact envelope bytes production agents emit. No network,
    no credentials.

    NOTE: GenericFakeChatModel cannot drive tools here: its _stream drops
    tool_calls (and empty content yields zero chunks, aborting server-side
    streaming). Hence the small scripted model below, which preserves
    tool_calls in both _generate and _stream.
    """
    import uuid
    from collections.abc import Iterator

    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessageChunk
    from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

    from agent_chat_minimal.demo_agent.get_graph import (
        make_agent_with_weather_tool,
    )

    def _script() -> Iterator[AIMessage]:
        # Ack stream only; card-vs-ack is decided per turn in _next().
        n = 0
        while True:
            n += 1
            yield AIMessage(content=f"a2ui-ack-{n}")

    def _is_fresh_thread(messages) -> bool:
        for m in messages or []:
            t = m.get("type") if isinstance(m, dict) else getattr(m, "type", "")
            if t in ("ai", "AIMessage", "AIMessageChunk", "tool", "ToolMessage"):
                return False
        return True

    def _tool_call_card() -> AIMessage:
        return AIMessage(
            content="rendering card",
            tool_calls=[
                {
                    "name": "render_a2ui_demo",
                    "args": {"title": "Book Your Table", "body": "E2E card body."},
                    "id": f"call-{uuid.uuid4().hex[:8]}",
                    "type": "tool_call",
                }
            ],
        )

    class ScriptedFake(BaseChatModel):
        script: object

        def _llm_type(self) -> str:
            return "e2e-scripted-fake"

        def bind_tools(self, *args, **kwargs):
            return self

        def _next(self, messages) -> AIMessage:
            # Stateless per thread: a fresh thread (no AI/tool messages yet)
            # gets the card; follow-ups get acks. Never depends on process
            # global position, so parallel/sequential tests are isolated.
            if _is_fresh_thread(messages):
                return _tool_call_card()
            return next(self.script)  # type: ignore[arg-type]

        def _generate(self, messages, stop=None, **kwargs) -> ChatResult:
            return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

        def _stream(self, messages, stop=None, **kwargs) -> Iterator[ChatGenerationChunk]:
            message = self._next(messages)
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=message.content,
                    tool_calls=list(message.tool_calls or []),
                )
            )

    return make_agent_with_weather_tool(ScriptedFake(script=_script()))


def main() -> None:
    port = int(os.environ.get("E2E_PORT", "18099"))
    web_dir = FRONTEND_DIR / "out"
    settings = Settings(
        ui_preset="full",
        server_mode=os.environ.get("E2E_SERVER_MODE", "prod"),
    )
    if os.environ.get("E2E_BOMB") == "1":
        app = create_app(graph_factory=_bomb_factory, settings=settings, web_dir=web_dir)
    elif os.environ.get("E2E_A2UI") == "1":
        app = create_app(graph=_a2ui_graph(), settings=settings, web_dir=web_dir)
    else:
        app = create_app(graph=EchoFake(), settings=settings, web_dir=web_dir)
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
