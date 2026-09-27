"""Agent registry: name -> zero-arg graph factory (#13).

Third-party packages can register agents without forking via the
``agent_chat.agents`` entry-points group::

    [project.entry-points."agent_chat.agents"]
    my_agent = "my_package.my_module:make_my_agent"
"""

import logging
import os
from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Any

logger = logging.getLogger(__name__)

ENTRY_POINTS_GROUP = "agent_chat.agents"


def _weather_factory() -> Any:
    from .demo_agent.get_graph import make_agent_with_weather_tool

    return make_agent_with_weather_tool(os.getenv("MODEL", "openai:gpt-4o-mini"))


def _calculator_factory() -> Any:
    from .demo_agent.calculator import make_calculator_agent

    return make_calculator_agent(os.getenv("MODEL", "openai:gpt-4o-mini"))


AGENT_REGISTRY: dict[str, Callable[[], Any]] = {
    "weather": _weather_factory,
    "calculator": _calculator_factory,
}


def discover_agents() -> dict[str, Callable[[], Any]]:
    """Merge the built-in registry with ``agent_chat.agents`` entry points."""
    agents = dict(AGENT_REGISTRY)
    try:
        eps = entry_points(group=ENTRY_POINTS_GROUP)
    except Exception as exc:  # pragma: no cover - metadata backend variance
        logger.debug("entry_points discovery failed: %s", exc)
        return agents
    for ep in eps:
        if ep.name in agents:
            logger.warning(
                "entry point agent %r shadows built-in; skipping", ep.name
            )
            continue
        try:
            agents[ep.name] = ep.load()
        except Exception as exc:
            logger.warning("failed to load agent entry point %r: %s", ep.name, exc)
    return agents
