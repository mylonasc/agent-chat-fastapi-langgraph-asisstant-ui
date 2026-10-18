"""Persistence bundle validation: durable and ephemeral stores must not mix (#65)."""

import asyncio

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent_chat_minimal import create_app, validate_persistence_bundle
from agent_chat_minimal.adapters import InMemoryRepositories
from agent_chat_minimal.adapters.sqlite import SQLiteRepositories, sqlite_url
from agent_chat_minimal.persistence import _DeferredCheckpointer

_OPEN_REPOS = []


def _sqlite_repos(tmp_path):
    path = tmp_path / "bundle.db"
    repos = asyncio.run(SQLiteRepositories.open(sqlite_url(path)))
    _OPEN_REPOS.append(repos)
    return repos


@pytest.fixture(autouse=True)
def _dispose_sqlite_repos():
    yield
    for repos in _OPEN_REPOS:
        asyncio.run(repos.dispose())
    _OPEN_REPOS.clear()


def test_memory_bundle_passes():
    validate_persistence_bundle(InMemoryRepositories(), MemorySaver())


def test_explicit_no_graph_memory_passes():
    validate_persistence_bundle(InMemoryRepositories(), None)


def test_unknown_custom_types_are_left_alone():
    validate_persistence_bundle(object(), object(), object())


def test_durable_repositories_reject_ephemeral_checkpointer(tmp_path):
    with pytest.raises(ValueError, match="durable session repositories"):
        validate_persistence_bundle(_sqlite_repos(tmp_path), MemorySaver())


def test_ephemeral_repositories_reject_durable_checkpointer():
    with pytest.raises(ValueError, match="ephemeral session repositories"):
        validate_persistence_bundle(
            InMemoryRepositories(), _DeferredCheckpointer()
        )


def test_durable_pair_passes(tmp_path):
    validate_persistence_bundle(
        _sqlite_repos(tmp_path), _DeferredCheckpointer(), _DeferredCheckpointer()
    )


def test_deleter_without_checkpointer_is_rejected():
    with pytest.raises(ValueError, match="checkpoint_deleter requires"):
        validate_persistence_bundle(
            InMemoryRepositories(), None, _DeferredCheckpointer()
        )


def test_durable_saver_rejects_ephemeral_deleter():
    class EphemeralDeleter:
        checkpointer = MemorySaver()

        async def delete_session(self, session_id):
            pass

    with pytest.raises(ValueError, match="ephemeral"):
        validate_persistence_bundle(
            InMemoryRepositories(), _DeferredCheckpointer(), EphemeralDeleter()
        )


def test_mismatched_bundle_fails_fast_in_create_app(tmp_path):
    with pytest.raises(ValueError, match="durable session repositories"):
        create_app(repositories=_sqlite_repos(tmp_path))


def test_memory_default_create_app_passes():
    assert create_app() is not None
