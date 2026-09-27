from fastapi.testclient import TestClient

from agent_chat_minimal import create_app


def test_api_and_static_serving_without_network(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    web_dir = tmp_path / "web"
    asset = web_dir / "_next" / "static" / "test.js"
    asset.parent.mkdir(parents=True)
    (web_dir / "index.html").write_text("<html>minimal fixture</html>")
    asset.write_text("fixture asset")

    client = TestClient(create_app(web_dir=web_dir))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").text == "<html>minimal fixture</html>"
    assert client.get("/_next/static/test.js").text == "fixture asset"
    assert client.get("/unknown/spa/path").text == "<html>minimal fixture</html>"

    response = client.post(
        "/assistant",
        json={"state": {"messages": []}, "commands": []},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "OPENAI_API_KEY not configured"
