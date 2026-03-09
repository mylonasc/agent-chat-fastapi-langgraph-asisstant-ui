from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from threading import RLock
import uuid


class ThreadMetadata(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    is_archived: bool = False
    is_public: bool = False  # for sharing (optional)


class ThreadManager:
    def __init__(self):
        self._threads = {}
        self._lock = RLock()

    def create_thread(
        self, user_id: str, title: str = "New Chat", thread_id: Optional[str] = None
    ) -> ThreadMetadata:
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
    ) -> List[ThreadMetadata]:
        with self._lock:
            return [
                t
                for t in self._threads.values()
                if t.user_id == user_id and (include_archived or not t.is_archived)
            ]

    def archive(self, thread_id: str):
        with self._lock:
            if thread_id in self._threads:
                self._threads[thread_id].is_archived = True

    def unarchive(self, thread_id: str):
        with self._lock:
            if thread_id in self._threads:
                self._threads[thread_id].is_archived = False

    def update_title(self, thread_id: str, new_title: str):
        with self._lock:
            if thread_id in self._threads:
                self._threads[thread_id].title = new_title

    def set_public(self, thread_id: str, is_public: bool = True):
        with self._lock:
            if thread_id in self._threads:
                self._threads[thread_id].is_public = is_public

    def delete(self, thread_id: str):
        with self._lock:
            self._threads.pop(thread_id, None)
