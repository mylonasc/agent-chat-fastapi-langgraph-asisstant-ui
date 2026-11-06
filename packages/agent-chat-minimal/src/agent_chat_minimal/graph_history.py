"""Reconcile client-selected message history with compiled LangGraph state."""

from typing import Any

from langgraph.channels.binop import BinaryOperatorAggregate
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite


def authoritative_graph_input(graph: Any, messages: list) -> dict[str, Any]:
    """Replace reducer-backed message history, without deleting checkpoints.

    The packaged transport sends the complete selected branch, not a delta.
    Applying it as an ordinary ``add_messages`` update would retain omitted
    messages from whichever branch last ran on this conversation's checkpoint.

    Normalize through the graph's own reducer with empty history first (for
    example, ``add_messages`` converts wire dicts into BaseMessages), then
    bypass the saved value for this one input update. Other state channels and
    historical checkpoints remain intact. Each later request supplies its own
    selected branch, so either alternative can be resumed independently.

    LastValue channels already replace their value. Non-LangGraph implementations
    retain the minimal ChatGraph protocol and receive an ordinary message list.
    """
    if isinstance(graph, CompiledStateGraph):
        channel = graph.channels.get("messages")
        if isinstance(channel, BinaryOperatorAggregate):
            return {"messages": Overwrite(channel.operator([], messages))}
    return {"messages": messages}
