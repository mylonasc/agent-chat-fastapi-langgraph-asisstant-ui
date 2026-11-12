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


SYNTAX_SAMPLES = {
    "bash": 'echo "$HOME"',
    "c": "#include <stdio.h>\nint main(void) { return 0; }",
    "clojure": '(defn greet [name] (str "Hello " name))',
    "cpp": '#include <iostream>\nint main() { std::cout << "hi"; }',
    "csharp": "public class App { public static void Main() {} }",
    "css": ".app { color: red; }",
    "dart": "void main() { print('hi'); }",
    "diff": "- old line\n+ new line",
    "docker": "FROM python:3.12\nRUN pip install fastapi",
    "elixir": "defmodule App do\n  def hello, do: :world\nend",
    "go": "package main\nfunc main() {}",
    "graphql": "query User { user(id: 1) { name } }",
    "haskell": 'main :: IO ()\nmain = putStrLn "hi"',
    "ini": "[server]\nport = 8011",
    "java": "class App { public static void main(String[] args) {} }",
    "javascript": "const answer = 42;\nconsole.log(answer);",
    "json": '{"enabled": true, "port": 8011}',
    "jsx": "const App = () => <div>Hello</div>;",
    "kotlin": 'fun main() { println("hi") }',
    "less": "@color: red;\n.app { color: @color; }",
    "lua": "local function greet(name) return name end",
    "makefile": "build:\n\tpython -m build",
    "markdown": "# Heading\n\n**bold** and `code`",
    "markup": '<main class="app">Hello</main>',
    "objectivec": "int main(void) { return 0; }",
    "perl": 'my $name = "world";',
    "php": '<?php echo "hello"; ?>',
    "powershell": "Get-ChildItem | Select-Object Name",
    "python": 'def greet(name: str) -> str:\n    return f"Hello, {name}!"',
    "r": 'greet <- function(name) { paste("Hello", name) }',
    "ruby": "def greet(name)\n  puts name\nend",
    "rust": 'fn main() { println!("hello"); }',
    "sass": "$color: red\n.app\n  color: $color",
    "scala": 'object App { def main(args: Array[String]) = println("hi") }',
    "scss": "$color: red;\n.app { color: $color; }",
    "sql": "SELECT id, name FROM users;",
    "swift": "func greet(_ name: String) -> String { name }",
    "toml": "[server]\nport = 8011",
    "tsx": "const App = () => <div>Hello</div>;",
    "typescript": "const answer: number = 42;",
    "yaml": "name: local-chat\nenabled: true",
    # Aliases users commonly write in Markdown fences.
    "py": "print('python alias')",
    "sh": "echo shell-alias",
    "yml": "alias: yaml",
    "html": "<p>html alias</p>",
    "c++": "int main() { return 0; }",
    "c#": "class App {}",
}
SYNTAX_DEMO = "\n\n".join(
    f"```{language}\n{code}\n```" for language, code in SYNTAX_SAMPLES.items()
)


def make_echo_graph(checkpointer=None):
    """Deterministic model inside a real checkpointed graph.

    Count the model-facing messages *after* checkpoint loading/reduction,
    not just the HTTP request. A stateless fake missed stale branch context
    in #72. Unique assistant IDs also avoid cross-thread transcript collisions.
    """

    async def answer(state):
        import uuid

        humans = sum(1 for m in state["messages"] if _is_human(m))
        request = _message_text(state["messages"][-1]) if state["messages"] else ""
        text = (
            SYNTAX_DEMO
            if "[[syntax-highlight-demo]]" in request
            else f"reply-{humans}"
        )
        return {
            "messages": [
                AIMessage(content=text, id=f"ai-{uuid.uuid4().hex[:8]}")
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


def _message_text(message) -> str:
    content = (
        message.get("content", "")
        if isinstance(message, dict)
        else getattr(message, "content", "")
    )
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _bomb_factory():
    """Factory that always fails, like a misconfigured provider backend."""
    raise RuntimeError(
        "E2E bomb: agent factory failed: "
        "Initializing ChatOllama requires the langchain-ollama package. "
        "Please install it with `pip install langchain-ollama`"
    )


class StreamBombFake:
    """Graph that fails mid-stream, like an exhausted-credits provider call."""

    async def astream(self, *args, **kwargs):
        raise RuntimeError(
            "E2E stream bomb: You exceeded your current quota, "
            "please check your plan and billing details"
        )
        if False:  # pragma: no cover - keep async-generator shape
            yield ()


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
    elif os.environ.get("E2E_STREAM_BOMB") == "1":
        app = create_app(graph=StreamBombFake(), settings=settings, web_dir=web_dir)
    else:
        app = create_app(
            graph_factory=make_echo_graph, settings=settings, web_dir=web_dir
        )
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
