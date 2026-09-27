"""Serving tests for the bundled full UI at /full (thread sidebar)."""

from fastapi.testclient import TestClient

from agent_chat_minimal import create_app


def _layout(root, name, title):
    web = root / name
    asset = web / "_next" / "static" / "app.js"
    asset.parent.mkdir(parents=True)
    (web / "index.html").write_text(f"<html>{title}</html>")
    asset.write_text(f"{name} asset")
    return web


def test_minimal_and_full_ui_served_side_by_side(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    web = _layout(tmp_path, "web", "minimal fixture")
    web_full = _layout(tmp_path, "web_full", "full fixture")

    client = TestClient(create_app(web_dir=web, web_full_dir=web_full))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").text == "<html>minimal fixture</html>"
    assert client.get("/full").text == "<html>full fixture</html>"
    assert client.get("/full/_next/static/app.js").text == "web_full asset"
    # SPA fallback is scoped: unknown /full/* paths get the full index
    assert client.get("/full/unknown/spa/path").text == "<html>full fixture</html>"
    # ...while unknown root paths still get the minimal index
    assert client.get("/unknown/spa/path").text == "<html>minimal fixture</html>"
    # API routes are untouched by either UI mount
    assert client.get("/agents").json()["default"] == "weather"
    response = client.post(
        "/assistant", json={"state": {"messages": []}, "commands": []}
    )
    assert response.status_code == 503


def test_missing_full_build_disables_only_full(tmp_path):
    web = _layout(tmp_path, "web", "minimal fixture")
    client = TestClient(create_app(web_dir=web, web_full_dir=tmp_path / "absent"))

    assert client.get("/").text == "<html>minimal fixture</html>"
    assert client.get("/full").status_code == 404
