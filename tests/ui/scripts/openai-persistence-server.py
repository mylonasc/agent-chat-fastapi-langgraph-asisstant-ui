"""OpenAI-backed durable server fixture for the Playwright persistence suite."""

from __future__ import annotations

import os
from functools import partial

import uvicorn

from agent_chat_minimal import ProposedQuestion, Settings, create_configured_app
from agent_chat_minimal.demo_agent.get_graph import make_agent_with_weather_tool


def main() -> None:
    model = os.getenv("OPENAI_E2E_MODEL", "openai:gpt-4o-mini")
    settings = Settings(
        host="127.0.0.1",
        port=8011,
        model=model,
        default_agent="weather",
        ui_preset="full",
        persistence_enabled=True,
        database_path=os.environ["DATABASE_PATH"],
        checkpoint_database_path=os.environ["CHECKPOINT_DATABASE_PATH"],
        app_title="OpenAI persistence E2E",
        welcome_heading="How can I help?",
        welcome_description="OpenAI-backed persistence test fixture.",
        composer_placeholder="Message the test agent...",
        proposed_questions=(
            ProposedQuestion(
                id="hello",
                label="Say hello",
                prompt="Reply with a short greeting.",
                agents=("weather",),
            ),
        ),
    )
    agents = {
        "weather": partial(make_agent_with_weather_tool, model=model),
    }
    app = create_configured_app(settings, agents=agents)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
