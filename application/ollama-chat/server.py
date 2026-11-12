"""Local Ollama chat using the repository's packaged API and chat UI."""

import argparse
from functools import partial
from pathlib import Path

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from agent_chat_minimal import Settings, create_configured_app
from agent_chat_minimal.demo_agent.agent_factory import AgentState
from agent_chat_minimal.models import resolve_model


def make_chat_agent(model, checkpointer=None):
    """No tools required: works with ordinary Ollama chat models too."""
    llm = resolve_model(model)

    async def answer(state: AgentState):
        response = await llm.ainvoke([
            SystemMessage(content="You are a helpful local assistant. Answer clearly and accurately."),
            *state["messages"],
        ])
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", answer)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph.compile(checkpointer=checkpointer)


def load_settings(config=None):
    path = Path(config) if config else Path(__file__).with_name("agent_chat.yaml")
    return Settings.from_yaml(path)


def create_app(settings=None):
    settings = settings or load_settings()
    if settings.persistence_enabled:
        for path, url in (
            (settings.database_path, settings.database_url),
            (settings.checkpoint_database_path, settings.checkpoint_database_url),
        ):
            if not url:
                Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return create_configured_app(
        settings,
        agents={"chat": partial(make_chat_agent, model=settings.model)},
        default_agent="chat",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Alternate YAML configuration file")
    args = parser.parse_args()
    settings = load_settings(args.config)

    import uvicorn

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
