"""Multi-thread conversation support, ported from the full backend (#threads).

``application/backend/full/fastlang/server/thread_manager.py`` manages thread
metadata (create/get/rename/archive/delete) while thread *content* lives in
two places, mirroring the full stack:

- assistant-ui message objects persisted verbatim per thread (so tool UI parts
  rehydrate), via :class:`ThreadMessageStore`;
- LangGraph checkpointer state keyed by ``thread_id`` (see ``checkpointer``
  support in :func:`create_app <agent_chat_minimal.server.create_app>`).

The REST surface in ``server.py`` intentionally uses the same paths as the
full backend (``/threads``, ``/threads/{id}/messages``, scoped ``/assistant``)
so ``frontend-full`` works against either server.
"""

from datetime import datetime
from threading import RLock
from typing import Any, Optional

from pydantic import BaseModel


class ThreadMetadata(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    is_archived: bool = False
    is_public: bool = False


class ThreadManager:
    """Thread-safe in-memory thread metadata registry."""

    def __init__(self) -> None:
        self._threads: dict[str, ThreadMetadata] = {}
        self._lock = RLock()

    def create_thread(
        self, user_id: str, title: str = "New Chat", thread_id: Optional[str] = None
    ) -> ThreadMetadata:
        import uuid

        thread_id = thread_id or str(uuid.uuid4())
        metadata = ThreadMetadata(
            id=thread_id,
            user_id=user_id,
            title=title,
            created_at=datetime.now(),
        )
        with self._lock:
            self._threads[thread_id] = metadata
        return metadata

    def get(self, thread_id: str) -> Optional[ThreadMetadata]:
        with self._lock:
            return self._threads.get(thread_id)

    def list_user_threads(
        self, user_id: str, include_archived: bool = False
    ) -> list[ThreadMetadata]:
        with self._lock:
            return [
                t
                for t in self._threads.values()
                if t.user_id == user_id and (include_archived or not t.is_archived)
            ]

    def archive(self, thread_id: str) -> None:
        with self._lock:
            if thread_id in self._threads:
                self._threads[thread_id].is_archived = True

    def unarchive(self, thread_id: str) -> None:
        with self._lock:
            if thread_id in self._threads:
                self._threads[thread_id].is_archived = False

    def update_title(self, thread_id: str, new_title: str) -> None:
        with self._lock:
            if thread_id in self._threads:
                self._threads[thread_id].title = new_title

    def delete(self, thread_id: str) -> None:
        with self._lock:
            self._threads.pop(thread_id, None)


class ThreadMessageStore:
    """Thread-safe verbatim store for assistant-ui message objects."""

    def __init__(self, cap: int = 500) -> None:
        self._messages: dict[str, list[dict[str, Any]]] = {}
        self._lock = RLock()
        self._cap = cap

    def append(self, thread_id: str, message: dict[str, Any]) -> int:
        with self._lock:
            items = self._messages.setdefault(thread_id, [])
            items.append(message)
            del items[: max(0, len(items) - self._cap)]
            return len(items)

    def list(self, thread_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._messages.get(thread_id, []))

    def drop(self, thread_id: str) -> None:
        with self._lock:
            self._messages.pop(thread_id, None)
