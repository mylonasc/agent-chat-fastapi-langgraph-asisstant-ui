"""Deployment-prefix contracts independent of the frontend build."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_chat_minimal import Settings, create_app
from agent_chat_minimal.static_ui import UI_BASE_PATH_MARKER, materialize_ui


@pytest.mark.parametrize("prefix", ["", "/chat", "/platform/apps/chat", "/chat-v2/a_b~c.d"])
def test_base_path_settings(prefix, monkeypatch, tmp_path):
    monkeypatch.setenv("BASE_PATH", prefix)
    assert Settings.from_env().base_path == prefix
    config = tmp_path / "chat.yaml"
    config.write_text("version: 1\nbase_path: /yaml\n")
    assert Settings.from_yaml(config, environ={}).base_path == "/yaml"
    assert Settings.from_yaml(config, environ={"BASE_PATH": prefix}).base_path == prefix
    assert Settings.from_yaml(config, environ={}, overrides={"base_path": prefix}).base_path == prefix


@pytest.mark.parametrize("prefix", [
    "/", "chat", "//host", "/chat/", "/chat//x", "/.", "/chat/..", "/a?x", "/a#x",
    "/a%2fb", "/a b", '/a"b', "/a\\b", "/é", "/__agent_chat_base_path__", None, 123,
])
def test_unsafe_base_paths_rejected(prefix):
    with pytest.raises(ValueError, match="base_path"):
        Settings(base_path=prefix)


@pytest.mark.parametrize("prefix", ["", "/chat", "/platform/apps/chat"])
def test_materialize_whole_export_without_mutating_package(prefix, tmp_path):
    source = tmp_path / "web"
    source.mkdir()
    marker = UI_BASE_PATH_MARKER
    assets = {
        "index.html": f'<script src="{marker}/_next/static/app.js"></script>',
        "_next/static/app.js": f'const basePath="{marker}";const css="{marker}/_next/static/app.css";',
        "index.txt": json.dumps({"href": f"{marker}/admin/"}),
        "_next/static/app.css": f'url("{marker}/_next/static/font.woff2")',
    }
    for name, content in assets.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    binary = b"\x00\xff" + marker.encode()
    (source / "font.woff2").write_bytes(binary)
    app = FastAPI()
    relocated = materialize_ui(app, source, prefix)
    assert relocated != source
    for name, original in assets.items():
        assert (source / name).read_text() == original
        assert (relocated / name).read_text() == original.replace(marker, prefix)
    assert (relocated / "font.woff2").read_bytes() == binary
    other_app = FastAPI()
    other = materialize_ui(other_app, source, "/other")
    assert other != relocated
    assert '/other/_next/' in (other / "index.html").read_text()
    for owner in (app, other_app):
        for temporary in owner.state.relocated_ui:
            temporary.cleanup()


def test_custom_export_not_rewritten(tmp_path, caplog):
    (tmp_path / "index.html").write_text('<script src="/custom/app.js"></script>')
    assert materialize_ui(FastAPI(), tmp_path, "/custom") == tmp_path
    assert "must be built for base_path=/custom" in caplog.text


@pytest.mark.parametrize("prefix", ["", "/chat", "/platform/apps/chat"])
@pytest.mark.parametrize("strip_prefix", [False, True])
def test_prefixed_static_api_and_redirects(prefix, strip_prefix, tmp_path):
    marker = UI_BASE_PATH_MARKER
    (tmp_path / "index.html").write_text(f'<script src="{marker}/app.js"></script>')
    (tmp_path / "app.js").write_text(f'const basePath="{marker}";')
    (tmp_path / "admin").mkdir()
    (tmp_path / "admin" / "index.html").write_text("Admin")
    app = create_app(graph=object(), settings=Settings(
        base_path=prefix, web_dir=str(tmp_path), web_full_dir=str(tmp_path),
    ))
    request_prefix = "" if strip_prefix else prefix
    with TestClient(app) as client:
        response = client.get(f"{request_prefix}/")
        assert f'src="{prefix}/app.js"' in response.text
        assert client.get(f"{request_prefix}/app.js").text == f'const basePath="{prefix}";'
        assert client.get(f"{request_prefix}/api/config").json()["api_base"] == prefix
        assert client.get(f"{request_prefix}/agents").status_code == 200
        assert client.get(f"{request_prefix}/api/missing").status_code == 404
        redirect = client.get(f"{request_prefix}/full", follow_redirects=False)
        assert redirect.headers["location"] == f"{prefix}/full/"
        redirect = client.get(f"{request_prefix}/admin?filter=test", follow_redirects=False)
        assert redirect.headers["location"].endswith(f"{prefix}/admin/?filter=test")
        assert client.get(f"{request_prefix}/openapi.json").json().get("servers", []) == (
            [{"url": prefix}] if prefix else []
        )
    for temporary in app.state.relocated_ui:
        temporary.cleanup()


def test_external_api_base_preserved():
    app = create_app(graph=object(), settings=Settings(
        base_path="/chat", api_base="https://api.example.test/backend",
    ))
    with TestClient(app) as client:
        assert client.get("/chat/api/config").json()["api_base"] == "https://api.example.test/backend"


def test_path_api_base():
    assert Settings(api_base="/backend/chat").api_base == "/backend/chat"
    for value in ("//evil.test", "/backend/", "/backend?query"):
        with pytest.raises(ValueError, match="api_base"):
            Settings(api_base=value)


def test_cli_base_path_override(monkeypatch):
    from agent_chat_minimal import composition

    monkeypatch.setenv("BASE_PATH", "/environment")
    monkeypatch.setattr(composition, "create_configured_app", lambda settings: settings)
    calls = []
    monkeypatch.setattr(composition.uvicorn, "run", lambda app, **kwargs: calls.append(app))
    composition.main(["--base-path", "/cli"])
    assert calls[0].base_path == "/cli"


@pytest.mark.parametrize("kind", ["http", "websocket"])
@pytest.mark.parametrize("path", ["/admin", "/chat/admin", "/chatting/admin"])
def test_path_normalization_preserves_scope(kind, path):
    import asyncio

    from agent_chat_minimal.base_path import BasePathMiddleware

    scopes = []

    async def downstream(scope, receive, send):
        scopes.append(scope)

    original = {"type": kind, "path": path, "raw_path": path.encode(), "query_string": b"x=1"}
    asyncio.run(BasePathMiddleware(downstream, "/chat")(original, None, None))
    expected = path if path.startswith("/chat/") else "/chat" + path
    assert scopes[0]["path"] == expected
    assert scopes[0]["raw_path"] == expected.encode()
    assert scopes[0]["query_string"] == b"x=1"
    assert original["path"] == path
