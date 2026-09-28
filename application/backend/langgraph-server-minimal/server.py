"""Compatibility development entry point for the packaged minimal server.

The portable package owns routes, transport, presets, persistence, and static
UI behavior. Keep this module only so existing contributor commands using
``uvicorn server:app`` continue to work without maintaining a second server.
"""

from agent_chat_minimal import create_default_app

app = create_default_app()
