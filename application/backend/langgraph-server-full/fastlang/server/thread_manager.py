from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
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

    def create_thread(self, user_id: str, title: str = "New Chat", thread_id: Optional[str] = None) -> ThreadMetadata:
        thread_id = thread_id or str(uuid.uuid4())
        metadata = ThreadMetadata(
            id=thread_id,
            user_id=user_id,
            title=title,
            created_at=datetime.now(),
        )
        self._threads[thread_id] = metadata
        return metadata

    def get(self, thread_id: str) -> Optional[ThreadMetadata]:
        return self._threads.get(thread_id)

    def list_user_threads(self, user_id: str) -> List[ThreadMetadata]:
        return [t for t in self._threads.values() if t.user_id == user_id and not t.is_archived]

    def archive(self, thread_id: str):
        if thread_id in self._threads:
            self._threads[thread_id].is_archived = True

    def update_title(self, thread_id: str, new_title: str):
        if thread_id in self._threads:
            self._threads[thread_id].title = new_title

    def set_public(self, thread_id: str, is_public: bool = True):
        if thread_id in self._threads:
            self._threads[thread_id].is_public = is_public