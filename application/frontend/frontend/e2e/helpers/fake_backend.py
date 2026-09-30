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


def main() -> None:
    port = int(os.environ.get("E2E_PORT", "18099"))
    web_dir = FRONTEND_DIR / "out"
    settings = Settings(ui_preset="full")
    app = create_app(graph=EchoFake(), settings=settings, web_dir=web_dir)
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
