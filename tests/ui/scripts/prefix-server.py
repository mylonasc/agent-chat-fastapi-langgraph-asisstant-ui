"""Credential-free fixture; UI_PYTHON must select the installed artifact."""

import os
import uuid

import uvicorn
from langchain_core.messages import AIMessageChunk

from agent_chat_minimal import Settings, create_app


class Graph:
    async def astream(self, *args, **kwargs):
        yield (), "messages", (AIMessageChunk(content="Prefix test reply.", id=str(uuid.uuid4())), {})


app = create_app(graph=Graph(), settings=Settings(
    base_path=os.environ["BASE_PATH"], ui_preset=os.environ["UI_PRESET"],
))
uvicorn.run(app, host="127.0.0.1", port=0)
