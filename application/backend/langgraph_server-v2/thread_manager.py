from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import uuid
# --- Production Metadata Models ---
class ThreadMetadata(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime

# Simple Directory Manager (Replace with DB calls in Production)
class ThreadManager:
    def __init__(self):
        self._threads = {} # In production: self.db.query(Thread)

    def create_thread(self, user_id: str, title: str = "New Chat") -> ThreadMetadata:
        thread_id = str(uuid.uuid4())
        metadata = ThreadMetadata(
            id=thread_id,
            user_id=user_id,
            title=title,
            created_at=datetime.now()
        )
        self._threads[thread_id] = metadata
        return metadata

    def list_user_threads(self, user_id: str) -> List[ThreadMetadata]:
        return [t for t in self._threads.values() if t.user_id == user_id]

    def update_title(self, thread_id: str, new_title: str):
        if thread_id in self._threads:
            self._threads[thread_id].title = new_title
