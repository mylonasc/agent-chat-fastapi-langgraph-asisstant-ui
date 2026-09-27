"""Runtime access to the bundled guides (see ``docs/*.md``).

```python
from agent_chat_minimal import docs
docs.list()           # ['agents', 'configuration', 'index', ...]
print(docs.get("threads"))
docs.show("quickstart")
```
"""

GUIDES = ("index", "quickstart", "agents", "providers", "configuration", "threads")


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
