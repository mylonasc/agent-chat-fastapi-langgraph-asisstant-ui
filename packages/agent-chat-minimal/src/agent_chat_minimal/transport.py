"""Repository-owned boundary for the Assistant Stream wire protocol."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from assistant_stream_ce import create_run as _create_run
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.modules.langgraph import (
    append_langgraph_event as _append_langgraph_event,
)
from assistant_stream_ce.serialization import DataStreamResponse
from starlette.responses import StreamingResponse


class RunController(Protocol):
    """Controller surface used by canonical package run callbacks."""

    @property
    def state(self) -> Any: ...

    @state.setter
    def state(self, value: Any) -> None: ...


def create_run(
    callback: Callable[[RunController], Awaitable[None]], *, state: Any | None = None
) -> AsyncIterator[Any]:
    """Create a protocol run while keeping its implementation private."""
    return _create_run(callback, state=state)


def append_graph_event(
    state: Any, namespace: tuple[str, ...], event_type: str, payload: Any
) -> None:
    """Merge one LangGraph stream event into observable protocol state."""
    _append_langgraph_event(state, namespace, event_type, payload)


def create_response(stream: AsyncIterator[Any]) -> StreamingResponse:
    """Encode a run as the supported Assistant Stream HTTP response."""
    return DataStreamResponse(stream)
