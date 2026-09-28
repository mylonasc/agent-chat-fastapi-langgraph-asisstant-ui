import ast
import tomllib
from pathlib import Path


PACKAGE = Path(__file__).parents[1] / "src" / "agent_chat_minimal"


def test_only_transport_module_imports_assistant_stream_ce():
    importers = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            if any(
                name == "assistant_stream_ce"
                or name.startswith("assistant_stream_ce.")
                for name in names
            ):
                importers.append(path.relative_to(PACKAGE).as_posix())
                break

    assert importers == ["transport.py"]


def test_assistant_stream_dependency_is_intentionally_pinned():
    pyproject = tomllib.loads(
        (PACKAGE.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert "assistant-stream-ce==0.0.2" in pyproject["project"]["dependencies"]
