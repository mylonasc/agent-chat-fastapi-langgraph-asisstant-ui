import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tools.authorization import AdminPrincipal
from tools.config import CONFIG_STORE
from tools.web_rag.tool import WebRAGTool
from tools.web_search.tool import WebSearchTool


ENDPOINTS = [
    ("GET", "/tools/web_rag/configuration"),
    ("POST", "/tools/web_rag/configuration"),
    ("GET", "/tools/web_rag/status"),
    ("GET", "/tools/web_rag/jobs/private-job"),
    ("GET", "/tools/web_rag/chunks"),
    ("GET", "/tools/web_rag/raw"),
    ("GET", "/tools/web_rag/download/chunks"),
    ("GET", "/tools/web_rag/download/raw"),
    ("POST", "/tools/web_rag/test-search"),
    ("POST", "/tools/web_rag/tools"),
    ("GET", "/tools/web_search/configuration"),
    ("POST", "/tools/web_search/configuration"),
    ("POST", "/tools/web_search/tools"),
]
ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FULL_ADMIN_TOKEN", "test-admin-token")
    app = FastAPI()
    app.include_router(WebRAGTool().get_router())
    app.include_router(WebSearchTool().get_router())
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("method,path", ENDPOINTS)
@pytest.mark.parametrize("access", ["disabled", "anonymous", "invalid", "non-admin"])
def test_tool_routes_fail_closed(client, monkeypatch, method, path, access):
    def forbidden_side_effect(*args, **kwargs):
        pytest.fail("unauthorized request reached tool data/configuration")

    monkeypatch.setattr(CONFIG_STORE, "get", forbidden_side_effect)
    monkeypatch.setattr(CONFIG_STORE, "set", forbidden_side_effect)
    headers = {
        "x-agent-chat-subject": "admin",
        "x-admin": "true",
        "x-role": "admin",
    }
    expected = 401
    if access == "disabled":
        monkeypatch.delenv("FULL_ADMIN_TOKEN")
        headers.update(ADMIN_HEADERS)
        expected = 503
    elif access == "invalid":
        headers["Authorization"] = "Bearer incorrect"
    elif access == "non-admin":
        client.app.state.admin_principal_resolver = lambda request: AdminPrincipal(
            "reader"
        )
        headers.update(ADMIN_HEADERS)
        expected = 403

    response = client.request(
        method,
        path,
        headers=headers,
        json={"action": "index", "url": "https://example.com", "query": "private"},
    )
    assert response.status_code == expected
    if expected == 401:
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_authorized_config_read_and_write(client, monkeypatch):
    values = {
        "web_rag": {"pdf_parser": "pypdf"},
        "web_search": {"max_results": 2},
    }
    monkeypatch.setattr(CONFIG_STORE, "get", lambda name: values[name])
    monkeypatch.setattr(
        CONFIG_STORE, "set", lambda name, value: values.update({name: value})
    )
    for name in values:
        path = f"/tools/{name}/configuration"
        response = client.get(path, headers=ADMIN_HEADERS)
        assert response.status_code == 200
        assert response.json() == values[name]
        response = client.post(path, headers=ADMIN_HEADERS, json={"updated": True})
        assert response.status_code == 200
        assert values[name] == {"updated": True}


@pytest.mark.parametrize(
    "kind,filename,key",
    [
        ("chunks", "documents.json", "documents"),
        ("raw", "raw_sources.jsonl", "sources"),
    ],
)
def test_authorized_downloads(client, monkeypatch, tmp_path, kind, filename, key):
    user_dir = tmp_path / "user_selected-user"
    user_dir.mkdir()
    item = {"content": "private document"}
    data = json.dumps([item]) if kind == "chunks" else json.dumps(item) + "\n"
    (user_dir / filename).write_text(data, encoding="utf-8")
    monkeypatch.setattr(
        CONFIG_STORE, "get", lambda name: {"base_path": str(tmp_path)}
    )
    response = client.get(
        f"/tools/web_rag/download/{kind}",
        params={"user_id": "selected-user"},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()[key] == [item]
    assert response.json()["user_id"] == "selected-user"
    assert response.headers["Content-Disposition"].startswith("attachment;")


@pytest.mark.parametrize("asynchronous", [False, True])
def test_injected_admin_resolver(client, monkeypatch, asynchronous):
    seen = []

    def resolve(request):
        seen.append(request.url.path)
        return AdminPrincipal("verified-admin", is_admin=True)

    async def resolve_async(request):
        return resolve(request)

    monkeypatch.delenv("FULL_ADMIN_TOKEN")
    monkeypatch.setattr(CONFIG_STORE, "get", lambda name: {"safe": True})
    client.app.state.admin_principal_resolver = (
        resolve_async if asynchronous else resolve
    )
    response = client.get("/tools/web_rag/configuration")
    assert response.status_code == 200
    assert seen == ["/tools/web_rag/configuration"]


def test_injected_resolver_cannot_fall_back_to_local_token(client):
    client.app.state.admin_principal_resolver = lambda request: None
    response = client.get("/tools/web_rag/configuration", headers=ADMIN_HEADERS)
    assert response.status_code == 401
