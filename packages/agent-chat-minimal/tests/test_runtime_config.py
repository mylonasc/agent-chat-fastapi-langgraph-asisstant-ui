"""PUIR-08 runtime configuration contract (Python consumer side)."""

from fastapi.testclient import TestClient

from agent_chat_minimal import (
    DEFAULT_RUNTIME_CONFIG,
    RUNTIME_CONFIG_VERSION,
    CapabilityProvider,
    Settings,
    build_runtime_config,
    create_app,
    parse_runtime_config,
)


def _client(**kwargs):
    kwargs.setdefault("agents", {"dummy": lambda: object()})
    return TestClient(create_app(**kwargs))


def test_config_endpoint_serves_versioned_schema_with_defaults():
    body = _client().get("/api/config").json()
    assert body["version"] == RUNTIME_CONFIG_VERSION
    assert body["api_base"] == ""
    assert body["ui_preset"] == "minimal"
    assert body["identity_mode"] == "anonymous"
    assert body["features"] == {
        "agents": True,
        "assistant": True,
        "threads": True,
        "transcripts": True,
    }
    assert body["tools"]["web_rag"] == {
        "enabled": False,
        "status_path": "/tools/web_rag/status",
    }
    for name in ("admin", "sharing", "attachments"):
        assert body["tools"][name]["enabled"] is False


def test_config_is_never_cached_and_reflects_deployment_settings():
    settings = Settings(
        ui_preset="full",
        api_base="http://localhost:8010",
        identity_mode="delegated",
    )
    response = _client(settings=settings, default_agent="dummy")
    raw = response.get("/api/config")
    assert raw.headers["cache-control"] == "no-store"
    body = raw.json()
    assert body["ui_preset"] == "full"
    assert body["api_base"] == "http://localhost:8010"
    assert body["identity_mode"] == "delegated"


def test_config_reflects_enabled_tool_capabilities():
    provider = CapabilityProvider(
        preset="full",
        enabled=frozenset({"agents", "assistant", "threads", "transcripts", "web_rag"}),
    )
    body = _client(capability_provider=provider).get("/api/config").json()
    assert body["tools"]["web_rag"]["enabled"] is True
    assert body["tools"]["admin"]["enabled"] is False


def test_config_is_json_even_with_static_ui_mounted(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>fixture</html>")
    client = _client(web_dir=web)
    response = client.get("/api/config")
    assert response.status_code == 200
    assert "<html>" not in response.text
    assert response.json()["version"] == RUNTIME_CONFIG_VERSION


def test_builder_matches_compiled_defaults():
    snapshot = build_runtime_config(
        Settings(), CapabilityProvider.for_preset("minimal")
    )
    assert snapshot.as_dict() == DEFAULT_RUNTIME_CONFIG


def test_parser_tolerates_missing_malformed_and_future_payloads():
    assert parse_runtime_config(None).as_dict() == DEFAULT_RUNTIME_CONFIG
    assert parse_runtime_config("garbage").as_dict() == DEFAULT_RUNTIME_CONFIG
    assert parse_runtime_config({}).as_dict() == DEFAULT_RUNTIME_CONFIG

    malformed = parse_runtime_config(
        {
            "version": "nine",
            "api_base": 42,
            "ui_preset": "enormous",
            "identity_mode": ["anonymous"],
            "features": {"threads": "yes", "bogus": True},
            "tools": {"web_rag": {"enabled": "maybe"}},
            "future_field": {"nested": True},
        }
    ).as_dict()
    assert malformed == DEFAULT_RUNTIME_CONFIG

    newer = parse_runtime_config(
        {"version": 99, "ui_preset": "full", "unknown_top_level": 1}
    )
    assert newer.version == 99
    assert newer.ui_preset == "full"
    assert newer.features["threads"] is True


def test_shared_v1_fixture_parses_identically():
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "runtime-config-v1.json").read_text()
    )
    parsed = parse_runtime_config(fixture).as_dict()
    assert parsed == fixture
    assert parsed["tools"]["web_rag"]["enabled"] is True


def test_settings_validate_api_base_and_identity_mode(monkeypatch):
    import pytest

    for name in ("API_BASE", "IDENTITY_MODE"):
        monkeypatch.delenv(name, raising=False)
    assert Settings.from_env().api_base == ""

    monkeypatch.setenv("API_BASE", "http://localhost:8010")
    monkeypatch.setenv("IDENTITY_MODE", "delegated")
    settings = Settings.from_env()
    assert settings.api_base == "http://localhost:8010"

    with pytest.raises(ValueError, match="api_base"):
        Settings(api_base="relative/path")
    with pytest.raises(ValueError, match="identity_mode"):
        Settings(identity_mode="sso")
