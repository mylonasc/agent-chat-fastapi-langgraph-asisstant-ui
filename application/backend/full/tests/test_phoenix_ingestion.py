"""Real, isolated Phoenix ingestion; opt in with PHOENIX_DOCKER_TEST=1."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("PHOENIX_DOCKER_TEST") != "1", reason="requires Docker; opt in explicitly"
)


def test_authenticated_full_agent_ingestion():
    import httpx

    root = Path(__file__).resolve().parents[1]
    compose = (root / "examples/phoenix_monitoring/compose.yml").read_text()
    image = next(line.split("image:", 1)[1].strip() for line in compose.splitlines() if "image:" in line)
    name = "phoenix-test-" + uuid.uuid4().hex[:12]
    password = secrets.token_urlsafe(32) + "aA1!"
    subprocess.run(["docker", "pull", image], check=True, capture_output=True, timeout=180)
    try:
        subprocess.run(
            ["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::6006",
             "-e", "PHOENIX_ENABLE_AUTH=true",
             "-e", "PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD=" + password,
             "-e", "PHOENIX_WORKING_DIR=/tmp/phoenix-test", image],
            check=True, capture_output=True, timeout=30,
        )
        info = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
        port = info["NetworkSettings"]["Ports"]["6006/tcp"][0]["HostPort"]
        base = "http://127.0.0.1:" + port
        with httpx.Client(base_url=base, timeout=10) as client:
            deadline = time.monotonic() + 90
            while True:
                try:
                    if client.get("/").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if time.monotonic() >= deadline:
                    pytest.fail("isolated Phoenix did not become ready")
                time.sleep(1)
            # Prove anonymous trace export is rejected, rather than testing a
            # collector that accidentally has authentication disabled.
            assert client.post("/v1/traces", content=b"").status_code == 401
            login = client.post("/auth/login", json={"email": "admin@localhost", "password": password})
            assert login.status_code == 204, f"login status: {login.status_code}"
            response = client.post("/v1/system/api_keys", json={"data": {"name": "ingestion-test"}})
            assert response.status_code == 201, f"key creation status: {response.status_code}"
            key = response.json()["data"]["key"]

        env = os.environ.copy()
        # Never inherit developer collector credentials or endpoints.
        for k in list(env):
            if k.startswith(("PHOENIX_", "OTEL_", "OPENINFERENCE_")):
                env.pop(k)
        env.update(
            PHOENIX_API_KEY=key,
            PHOENIX_COLLECTOR_ENDPOINT=base + "/v1/traces",
            PHOENIX_PROJECT_NAME="full-agent-ingestion-test",
            PHOENIX_DISCOVER_CONFIG="false",
        )
        result = subprocess.run(
            [sys.executable, "-c", '''
import asyncio
from examples.phoenix_monitoring.serve import configure_tracing
provider = configure_tracing()
try:
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from fastlang.server.get_graph import make_web_rag_search_agent
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
    graph = make_web_rag_search_agent(
        model_name=Model(responses=[AIMessage(content="Synthetic ingestion check.")]),
        mode="react",
    )
    async def run():
        async for event in graph.astream(
            {"messages": [HumanMessage(content="Synthetic monitoring check.")]},
            {"configurable": {"thread_id": "ingestion-test"}},
            stream_mode=["messages", "updates", "custom"], subgraphs=True,
        ):
            pass
    asyncio.run(run())
    provider.force_flush()
finally:
    provider.shutdown()
'''], cwd=root, env=env, capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, "synthetic agent subprocess failed"
        assert "Failed to export" not in result.stderr, "exporter reported a failure"
        # Verify persistence, not merely force_flush(): it can return True even
        # when the collector rejects a batch. The isolated DB holds no user data.
        query = '''
import sqlite3
db = sqlite3.connect('file:/tmp/phoenix-test/phoenix.db?mode=ro', uri=True)
print(db.execute("SELECT COUNT(*) FROM spans JOIN traces ON spans.trace_rowid=traces.id JOIN projects ON traces.project_rowid=projects.id WHERE projects.name=?", ('full-agent-ingestion-test',)).fetchone()[0])
'''
        deadline = time.monotonic() + 30
        while True:
            count = int(subprocess.check_output(["docker", "exec", name, "python", "-c", query]))
            if count >= 3:
                break
            if time.monotonic() >= deadline:
                pytest.fail("Phoenix did not persist the synthetic agent spans")
            time.sleep(1)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
