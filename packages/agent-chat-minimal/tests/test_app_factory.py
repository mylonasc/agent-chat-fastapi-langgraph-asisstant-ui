import importlib

import pytest

from agent_chat_minimal import CapabilityProvider, Settings, create_app


def test_settings_precedence(monkeypatch, tmp_path):
    env_web = tmp_path / "env"
    configured_web = tmp_path / "configured"
    override_web = tmp_path / "override"
    monkeypatch.setenv("DEFAULT_AGENT", "from-env")
    monkeypatch.setenv("MINIMAL_WEB_DIR", str(env_web))

    settings = Settings(default_agent="configured", web_dir=str(configured_web))
    app = create_app(
        agents={"override": lambda: object()},
        settings=settings,
        default_agent="override",
        web_dir=override_web,
    )

    assert app.state.settings.default_agent == "override"
    assert app.state.settings.web_dir == str(override_web)


def test_settings_defaults_and_invalid_values(monkeypatch):
    for name in (
        "HOST",
        "PORT",
        "MODEL",
        "DEFAULT_AGENT",
        "MINIMAL_WEB_DIR",
        "FULL_WEB_DIR",
        "UI_PRESET",
        "DATABASE_URL",
        "DATABASE_PATH",
        "CHECKPOINT_DATABASE_URL",
        "CHECKPOINT_DATABASE_PATH",
        "AUTO_MIGRATE",
    ):
        monkeypatch.delenv(name, raising=False)

    assert Settings.from_env() == Settings()
    with pytest.raises(ValueError, match="PORT must be an integer"):
        monkeypatch.setenv("PORT", "not-a-number")
        Settings.from_env()
    with pytest.raises(ValueError, match="port must be between"):
        Settings(port=0)
    with pytest.raises(ValueError, match="ui_preset"):
        Settings(ui_preset="unknown")


@pytest.mark.parametrize("preset", ["minimal", "full"])
def test_presets_use_same_composition_root(preset):
    capabilities = CapabilityProvider.for_preset(preset)
    app = create_app(
        agents={"chosen": lambda: object()},
        settings=Settings(default_agent="chosen", ui_preset=preset),
        capability_provider=capabilities,
    )

    assert app.state.capabilities is capabilities
    assert app.state.capabilities.as_dict() == {
        "preset": preset,
        "enabled": ["agents", "assistant", "threads", "transcripts"],
    }


def test_reusable_server_module_has_factory_but_no_constructed_app(monkeypatch):
    import agent_chat_minimal.server as server

    server = importlib.reload(server)
    assert not hasattr(server, "app")

    monkeypatch.setattr(
        "agent_chat_minimal.registry.discover_agents",
        lambda **kwargs: {"weather": lambda: object()},
    )
    app = server.create_default_app()
    assert app.state.settings == Settings.from_env()
