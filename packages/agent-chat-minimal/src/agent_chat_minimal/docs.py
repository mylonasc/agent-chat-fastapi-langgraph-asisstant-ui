"""Runtime access to the bundled guides (see ``docs/*.md``).

```python
from agent_chat_minimal import docs
docs.list()           # ['agents', 'configuration', 'index', ...]
print(docs.get("threads"))
docs.show("quickstart")
```
"""

from __future__ import annotations

GUIDES = (
    "index",
    "quickstart",
    "agents",
    "providers",
    "configuration",
    "threads",
    "transport",
    "persistence",
    "runtime-config",
    "setup",
    "starter",
    "editable-ui",
    "agent-onboarding",
    "ollama-quickstart",
)


def _read(name: str) -> str:
    from importlib.resources import files

    return (files(__package__) / "docs" / f"{name}.md").read_text(encoding="utf-8")


def list() -> list[str]:  # noqa: A001 - intentional `docs.list()` API
    """Return available guide names."""
    return [g for g in GUIDES]


def get(name: str) -> str:
    """Return a guide's markdown, e.g. ``docs.get("agents")``."""
    key = name.removesuffix(".md").lower()
    if key not in GUIDES:
        raise KeyError(f"unknown guide {name!r}; available: {', '.join(GUIDES)}")
    return _read(key)


def show(name: str) -> None:
    """Print a guide to stdout."""
    print(get(name))


def catalog() -> list[dict[str, str]]:
    """Return guide names, titles, and summaries for agent discovery."""
    entries = []
    for name in GUIDES:
        text = get(name)
        title, _, rest = text.partition("\n")
        summary = rest.strip().split("\n\n", 1)[0].replace("\n", " ")
        entries.append({"name": name, "title": title.lstrip("# "), "summary": summary})
    return entries


def search(query: str, *, limit: int = 10) -> list[dict[str, str | int]]:
    """Search literal text case-insensitively; return guide/line/heading context.

    Results follow guide order, then line order. No regex evaluation, network,
    external index, or optional dependency is needed.
    """
    if not query.strip():
        raise ValueError("search query must not be empty")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")
    needle = query.strip().casefold()
    matches = []
    for name in GUIDES:
        heading = ""
        in_code = False
        for number, line in enumerate(get(name).splitlines(), 1):
            if line.startswith("```"):
                in_code = not in_code
            if not in_code and line.startswith("#"):
                heading = line.lstrip("# ")
            if needle in line.casefold():
                matches.append({"guide": name, "line": number, "heading": heading, "excerpt": line.strip()})
                if len(matches) >= limit:
                    return matches
    return matches
