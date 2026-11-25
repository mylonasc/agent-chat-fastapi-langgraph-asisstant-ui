"""Serve the existing full agent with opt-in OpenInference/Phoenix tracing.

Run from backend/full: uv run --extra phoenix python -m examples.phoenix_monitoring.serve
"""

import os


def configure_tracing():
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    provider = register(
        project_name=os.getenv("PHOENIX_PROJECT_NAME", "full-agent"),
        endpoint=os.getenv(
            "PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces"
        ),
        protocol="http/protobuf",
        batch=True,
        auto_instrument=False,
    )
    # LangChain instrumentation covers LangGraph nodes, chat models, tools and
    # LangChain retrievers. Do not also instrument OpenAI: that duplicates LLM spans.
    LangChainInstrumentor().instrument(tracer_provider=provider)
    return provider


def main():
    import uvicorn

    # Must happen before importing server.py, which constructs the real graph.
    provider = configure_tracing()
    try:
        uvicorn.run("fastlang.server.server:app", host="127.0.0.1", port=8010)
    finally:
        provider.force_flush()
        provider.shutdown()


if __name__ == "__main__":
    main()
