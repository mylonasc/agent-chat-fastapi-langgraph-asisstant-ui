import ast
from pathlib import Path


PACKAGE = Path(__file__).parents[1] / "src" / "agent_chat_minimal"
BOUNDARY = [
    PACKAGE / "domain.py",
    PACKAGE / "ports.py",
    PACKAGE / "services.py",
    *(PACKAGE / "adapters").glob("*.py"),
]
FORBIDDEN = ("fastapi", "langgraph", "assistant_stream_ce", "sqlalchemy")


def test_domain_service_ports_and_adapters_are_framework_independent():
    violations = []
    for path in BOUNDARY:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            if any(
                name == dependency or name.startswith(f"{dependency}.")
                for name in names
                for dependency in FORBIDDEN
            ):
                violations.append(path.relative_to(PACKAGE).as_posix())
                break

    assert violations == []
