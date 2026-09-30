"""Agent-starter scaffold and initializer (AGS-04)."""

import json
import sys

import pytest
from fastapi.testclient import TestClient

from agent_chat_minimal import Settings, StarterOptions
from agent_chat_minimal.starter import (
    StarterError,
    generate_starter,
    main as init_main,
    plan_starter,
    render_starter_files,
)


def _options(**kwargs):
    kwargs.setdefault("project_name", "my-agent")
    kwargs.setdefault("package_name", "my_agent")
    return StarterOptions(**kwargs)


def test_plan_is_deterministic_and_selects_extras():
    options = _options(provider="ollama", model="llama3.1:8b", persistence="sqlite")
    first = plan_starter(options, "/tmp/my-agent")
    second = plan_starter(options, "/tmp/my-agent")
    assert first == second
    assert "src/my_agent/server.py" in first.expected_files
    assert "agent_chat.yaml" in first.expected_files
    assert set(first.required_extras) == {"ollama", "persistence"}

    base = plan_starter(_options(), "/tmp/my-agent")
    assert base.required_extras == ()


def test_dry_run_writes_nothing(tmp_path, capsys):
    target = tmp_path / "my-agent"
    code = init_main([str(target), "--provider", "openai", "--dry-run"])
    assert code == 0
    assert not target.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert "src/my_agent/server.py" in payload["plan"]["expected_files"]


def test_generate_refuses_conflicts_and_never_overwrites(tmp_path):
    target = tmp_path / "my-agent"
    generate_starter(_options(), target)
    with pytest.raises(StarterError, match="not empty"):
        generate_starter(_options(), target)
    # The original generated server is untouched.
    server = (target / "src/my_agent/server.py").read_text()
    assert "create_agent_app" in server


def test_generated_project_runs_outside_checkout(tmp_path, monkeypatch):
    target = tmp_path / "my-agent"
    generate_starter(_options(preset="full"), target)

    # No machine-specific absolute paths captured at generation time.
    server_text = (target / "src/my_agent/server.py").read_text()
    ui_text = (target / "src/my_agent/ui.py").read_text()
    assert str(target) not in server_text
    assert "site-packages" not in server_text
    assert "bundled_ui_dir" in ui_text

    # Config loads with an unrelated working directory (config-relative).
    monkeypatch.chdir(tmp_path)
    settings = Settings.from_yaml(target / "agent_chat.yaml", environ={})
    assert settings.default_agent == "helper"
    assert settings.ui_preset == "full"

    # Bare factory discovers ./agent_chat.yaml from the project directory,
    # which is also how the installed console script runs (no absolute paths).
    monkeypatch.syspath_prepend(str(target / "src"))
    monkeypatch.chdir(target)
    for module in [m for m in list(sys.modules) if m.startswith("my_agent")]:
        del sys.modules[module]
    from my_agent.server import create_agent_app as bare_factory

    assert TestClient(bare_factory()).get("/agents").json() == {
        "agents": ["helper"],
        "default": "helper",
    }

    # Generated code executes: fake-model agent invoke + app routes.
    for module in [m for m in list(sys.modules) if m.startswith("my_agent")]:
        del sys.modules[module]
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    from my_agent.agents.helper import make_helper_agent

    class BindableFake(GenericFakeChatModel):
        def bind_tools(self, *args, **kwargs):
            return self

    fake = BindableFake(messages=iter([AIMessage(content="hi")]))
    result = make_helper_agent(fake).invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert result["messages"]

    from my_agent.server import create_agent_app, main as project_main

    client = TestClient(create_agent_app(str(target / "agent_chat.yaml")))
    assert client.get("/agents").json() == {"agents": ["helper"], "default": "helper"}
    assert client.get("/api/config").status_code == 200
    # --check constructs the real configured model, so it needs a credential
    # present; a dummy key keeps it offline (newer langchain-openai versions
    # require a key at construction time, not just at invoke time).
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert project_main(["--config", str(target / "agent_chat.yaml"), "--check"]) == 0


def test_generated_sqlite_project_uses_relative_paths(tmp_path):
    target = tmp_path / "sqlite-agent"
    generate_starter(
        _options(
            project_name="sqlite-agent",
            package_name="sqlite_agent",
            persistence="sqlite",
        ),
        target,
    )
    settings = Settings.from_yaml(target / "agent_chat.yaml", environ={})
    assert settings.persistence_enabled is True
    assert str(settings.database_path).startswith(str(target))

    manifest = json.loads((target / "starter-manifest.json").read_text())
    assert manifest["persistence"] == "sqlite"
    assert "persistence" in manifest["required_extras"]
    assert sorted(manifest["expected_files"]) == sorted(
        render_starter_files(
            _options(
                project_name="sqlite-agent",
                package_name="sqlite_agent",
                persistence="sqlite",
            )
        ).keys()
    )
