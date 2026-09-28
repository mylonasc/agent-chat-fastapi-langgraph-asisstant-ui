"""Separate async lifecycle for LangGraph's SQLite checkpoint saver."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import TracebackType

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


_SQLITE_URL_PREFIXES = ("sqlite+aiosqlite:///", "sqlite:///")


def _connection_string(database: str | Path) -> str:
    if isinstance(database, Path):
        return str(database.expanduser().resolve())
    if database == ":memory:":
        return database
    for prefix in _SQLITE_URL_PREFIXES:
        if database.startswith(prefix):
            path = database.removeprefix(prefix)
            if not path:
                raise ValueError("checkpoint database URL must include a path")
            if path == ":memory:":
                return path
            return str(Path(path).expanduser().resolve())
    if "://" in database:
        raise ValueError("checkpoint database must be a SQLite path or URL")
    if not database.strip():
        raise ValueError("checkpoint database path must not be empty")
    return str(Path(database).expanduser().resolve())


def _require_session_id(session_id: str) -> None:
    if not session_id or not session_id.strip():
        raise ValueError("session id must not be empty")


class LangGraphSQLiteCheckpoints:
    """Own an ``AsyncSqliteSaver`` connection and implement CheckpointDeleter.

    Callers authorize a session before handing its validated ID to this adapter.
    The same ID is used as LangGraph's ``configurable.thread_id``.
    """

    def __init__(
        self,
        context: AbstractAsyncContextManager[AsyncSqliteSaver],
        saver: AsyncSqliteSaver,
    ) -> None:
        self._context = context
        self._saver = saver
        self._disposed = False

    @classmethod
    async def open(cls, database: str | Path) -> LangGraphSQLiteCheckpoints:
        """Open the connection and eagerly create the official saver schema."""
        context = AsyncSqliteSaver.from_conn_string(_connection_string(database))
        saver = await context.__aenter__()
        try:
            await saver.setup()
        except BaseException as exc:
            await context.__aexit__(type(exc), exc, exc.__traceback__)
            raise
        return cls(context, saver)

    @property
    def checkpointer(self) -> AsyncSqliteSaver:
        """Return the saver accepted by LangGraph graph factories."""
        if self._disposed:
            raise RuntimeError("checkpoint adapter is disposed")
        return self._saver

    async def delete_session(self, session_id: str) -> None:
        _require_session_id(session_id)
        if self._disposed:
            raise RuntimeError("checkpoint adapter is disposed")
        await self._saver.adelete_thread(session_id)

    async def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        await self._context.__aexit__(None, None, None)

    async def __aenter__(self) -> LangGraphSQLiteCheckpoints:
        if self._disposed:
            raise RuntimeError("checkpoint adapter is disposed")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.dispose()


__all__ = ["LangGraphSQLiteCheckpoints"]
