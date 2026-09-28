"""Bundled guides are present and readable (in-wheel documentation)."""

import pytest

from agent_chat_minimal import docs


def test_all_guides_readable():
    names = docs.list()
    assert set(names) >= {
        "index",
        "quickstart",
        "agents",
        "providers",
        "configuration",
        "threads",
        "persistence",
    }
    for name in names:
        text = docs.get(name)
        assert len(text) > 200, name


def test_unknown_guide_raises_helpful_error():
    with pytest.raises(KeyError, match="available"):
        docs.get("nope")
