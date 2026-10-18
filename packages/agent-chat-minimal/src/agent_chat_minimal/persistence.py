"""Persistence bundle validation for composition roots (#65).

Sessions/transcripts/feedback and the LangGraph checkpointer are separate
stores with separate lifecycles by design, but silently mixing a durable
store with an ephemeral one loses data on restart. This module classifies
the injected pieces and fails fast on mismatched pairs. Unknown (custom)
adapter types are left alone: only positively classified pairs validate.
"""

from typing import Any


class _DeferredCheckpointer:
    """Expose the lifespan-owned saver to lazily constructed graph factories."""

    def __init__(self) -> None:
        self._adapter: Any | None = None

    def set_adapter(self, adapter: Any) -> None:
        self._adapter = adapter

    def clear_adapter(self) -> None:
        self._adapter = None

    @property
    def checkpointer(self) -> Any:
        if self._adapter is None:
            raise RuntimeError("checkpoint store is not available before application startup")
        return self._adapter.checkpointer

    async def delete_session(self, session_id: str) -> None:
        await self.checkpointer.adelete_thread(session_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.checkpointer, name)


def _is_memory_repositories(repositories: Any) -> bool:
    from .adapters.memory import InMemoryRepositories

    return isinstance(repositories, InMemoryRepositories)


def _is_durable_repositories(repositories: Any) -> bool:
    try:
        from .adapters.sqlite import SQLiteRepositories
    except ModuleNotFoundError:
        return False
    return isinstance(repositories, SQLiteRepositories)


def _is_memory_checkpointer(checkpointer: Any) -> bool:
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except ModuleNotFoundError:
        return type(checkpointer).__name__ == "MemorySaver"
    return isinstance(checkpointer, MemorySaver)


def _saver_of(checkpointer: Any) -> Any:
    """Resolve a possible saver proxy without triggering lazy errors.

    An unset deferred proxy raises ``RuntimeError`` on attribute access;
    treat it as unresolvable (its outer type already classifies it).
    """
    try:
        return checkpointer.checkpointer
    except (AttributeError, RuntimeError):
        return checkpointer


def _is_durable_checkpointer(checkpointer: Any) -> bool:
    if isinstance(checkpointer, _DeferredCheckpointer):
        return True
    try:
        from .adapters.langgraph_sqlite import LangGraphSQLiteCheckpoints
    except ModuleNotFoundError:
        return False
    return isinstance(checkpointer, LangGraphSQLiteCheckpoints)


def validate_persistence_bundle(
    repositories: Any,
    checkpointer: Any | None,
    checkpoint_deleter: Any | None = None,
) -> None:
    """Fail fast when durable and ephemeral persistence are mixed.

    ``checkpointer=None`` explicitly opts out of graph memory and is always
    allowed. A durable ``checkpoint_deleter`` paired with an ephemeral (or
    missing) checkpointer is rejected, since session deletion would claim
    checkpoint cleanup it cannot perform.
    """
    repos_memory = _is_memory_repositories(repositories)
    repos_durable = _is_durable_repositories(repositories)
    if not repos_memory and not repos_durable:
        return

    if checkpointer is None:
        if checkpoint_deleter is not None:
            raise ValueError(
                "checkpoint_deleter requires a durable checkpointer; "
                "pass a checkpointer or drop the deleter"
            )
        return

    saver = _saver_of(checkpointer)
    saver_memory = _is_memory_checkpointer(saver)
    saver_durable = _is_durable_checkpointer(checkpointer)
    if not saver_memory and not saver_durable:
        return

    if repos_durable and saver_memory:
        raise ValueError(
            "durable session repositories paired with an ephemeral LangGraph "
            "checkpointer would lose graph memory on restart; pair SQLite "
            "repositories with the durable checkpoint adapter"
        )
    if repos_memory and saver_durable:
        raise ValueError(
            "ephemeral session repositories paired with a durable LangGraph "
            "checkpointer would orphan checkpoints on restart; pair durable "
            "checkpoints with SQLite repositories"
        )
    if saver_durable and checkpoint_deleter is not None:
        deleter_saver = _saver_of(checkpoint_deleter)
        if _is_memory_checkpointer(deleter_saver) and not _is_durable_checkpointer(
            checkpoint_deleter
        ):
            raise ValueError(
                "durable checkpointer paired with an ephemeral "
                "checkpoint_deleter would leak checkpoints on session "
                "deletion; pair both from the same durable adapter"
            )


__all__ = ["validate_persistence_bundle"]
