from fastapi.testclient import TestClient
from langchain_core.messages.ai import AIMessageChunk

from agent_chat_minimal import create_app


class ToyGraph:
    async def astream(self, *args, **kwargs):
        yield (), "messages", (AIMessageChunk(content="hi from toy"), {})


def test_injected_graph_serves_without_openai_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html>toy</html>")

    client = TestClient(create_app(graph=ToyGraph(), web_dir=web_dir))
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post(
        "/assistant", json={"state": {"messages": []}, "commands": []}
    )
    assert response.status_code == 200


def test_graph_factory_failure_gives_generic_503(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def boom():
        raise RuntimeError("no creds for test provider")

    client = TestClient(create_app(graph_factory=boom))
    response = client.post(
        "/assistant", json={"state": {"messages": []}, "commands": []}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "agent_not_ready"
