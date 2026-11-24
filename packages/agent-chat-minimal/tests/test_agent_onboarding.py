"""Offline agent discovery, guide search, and non-interactive scaffolding."""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from agent_chat_minimal import StarterOptions, docs
from agent_chat_minimal.docs_cli import main as docs_main
from agent_chat_minimal.onboarding import describe, doctor, main as setup_main
from agent_chat_minimal.starter import main as init_main, starter_next_steps


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Onboarding must not contact the network")

    monkeypatch.setattr(socket, "create_connection", fail)


def test_catalog_matches_complete_bundled_index_and_readme():
    catalog = docs.catalog()
    assert [item["name"] for item in catalog] == docs.list()
    index = docs.get("index")
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    for item in catalog:
        assert item["title"] and item["summary"]
        assert f"({item['name']}.md)" in index
        assert f"`{item['name']}`" in readme


def test_search_is_literal_case_insensitive_bounded_and_has_context():
    matches = docs.search("PERSISTENCE", limit=3)
    assert len(matches) == 3
    assert matches == docs.search("persistence", limit=3)
    for match in matches:
        assert match["heading"]
        assert "persistence" in match["excerpt"].casefold()
        line = docs.get(match["guide"]).splitlines()[match["line"] - 1]
        assert line.strip() == match["excerpt"]
    assert docs.search("no-such-guide-phrase-948102") == []
    assert docs.search(".*") == []  # no regex expansion


@pytest.mark.parametrize("query,limit", [("", 10), ("  ", 10), ("a", 0), ("a", -1), ("a", True)])
def test_search_rejects_invalid_inputs(query, limit):
    with pytest.raises(ValueError):
        docs.search(query, limit=limit)


def test_search_preserves_markdown_heading_inside_code(monkeypatch):
    monkeypatch.setattr(docs, "GUIDES", ("fixture",))
    monkeypatch.setattr(docs, "get", lambda name: "# Guide\n\n## Real heading\n```bash\n# a shell comment\nneedle\n```\n")
    assert docs.search("needle")[0]["heading"] == "Real heading"


@pytest.mark.parametrize("argv", [["list", "--json"], ["--json", "list"]])
def test_docs_cli_json_flag_on_either_side(argv, capsys):
    assert docs_main(argv) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["contract_version"] == 1 and payload["ok"]
    assert {guide["name"] for guide in payload["guides"]} >= {"agent-onboarding", "setup", "starter"}
    assert output.err == ""


def test_docs_cli_default_show_search_and_errors(capsys):
    assert docs_main([]) == 0
    assert "Coding-agent onboarding" in capsys.readouterr().out
    assert docs_main(["show", "STARTER.md", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["guide"] == "starter"
    assert docs_main(["search", "persistence", "--limit", "1", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["matches"]) == 1
    assert docs_main(["search", "no-such-phrase-394829", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["matches"] == []
    for argv in (["show", "../secrets", "--json"], ["search", "x", "--limit", "0", "--json"]):
        assert docs_main(argv) == 2
        output = capsys.readouterr()
        assert json.loads(output.out)["ok"] is False
        assert output.err == ""
    assert docs_main(["show", "unknown-guide"]) == 2
    assert "available" in capsys.readouterr().err


def test_setup_description_and_schema_are_self_contained(capsys):
    result = describe()
    assert result["library_version"]
    assert result["safety"]["network"] is False
    assert result["commands"]["generate"][-1] == "--json"
    assert {guide["name"] for guide in result["documentation"]} == set(docs.list())
    assert setup_main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out) == result
    assert setup_main(["schema", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "Agent Chat configuration"


def test_ollama_route_is_discoverable_from_every_onboarding_entry(capsys):
    command = describe()["commands"]["local_ollama"]
    assert command == ["minimal-chat-docs", "show", "ollama-quickstart"]
    assert docs_main([*command[1:], "--json"]) == 0
    guide = json.loads(capsys.readouterr().out)["markdown"]
    assert "python3.12 -m venv" in guide
    assert "ollama pull llama3.1:8b" in guide
    assert "mkdir -p data" in guide
    assert "--agent chat" in guide and "not implemented" in guide
    assert "does not forward" in guide
    assert "Live smoke test" in guide
    for name in ("index", "quickstart", "starter", "providers", "agent-onboarding"):
        assert "ollama-quickstart" in docs.get(name), name
    for path in ("README.md", "docs/README.md", "docs/packaged-app.md"):
        root = Path(__file__).resolve().parents[3]
        assert "ollama-quickstart" in (root / path).read_text(), path
    matches = docs.search("Local Ollama")
    assert any(match["guide"] == "ollama-quickstart" for match in matches)


def test_documented_ollama_initializer_and_history_configuration(tmp_path, capsys):
    from agent_chat_minimal import Settings

    target = tmp_path / "my-local-chat"
    assert init_main([
        str(target), "--provider", "ollama", "--model", "llama3.1:8b",
        "--preset", "full", "--persistence", "sqlite", "--json",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result["plan"]["required_extras"]) == {"ollama", "persistence"}
    settings = Settings.from_yaml(target / "agent_chat.yaml", environ={})
    assert settings.model == "ollama:llama3.1:8b"
    assert settings.ui_preset == "full"
    assert settings.persistence_enabled
    # The guide explicitly creates the parent directory; generation does not.
    assert not (target / "data").exists()
    (target / "data").mkdir()
    assert Path(settings.database_path).parent == target / "data"
    assert Path(settings.checkpoint_database_path).parent == target / "data"
    assert result["next_steps"][-1]["credential_env"] is None


def test_doctor_reports_missing_prerequisites_and_never_outputs_secrets(monkeypatch):
    import agent_chat_minimal.onboarding as onboarding

    def package_version(name):
        if name == "langchain-ollama":
            raise onboarding.PackageNotFoundError(name)
        return "1.0"

    monkeypatch.setattr(onboarding, "version", package_version)
    monkeypatch.setattr(onboarding, "is_ui_bundle", lambda path: False)
    monkeypatch.setenv("PRIVATE_MODEL_KEY", "do-not-print-this-value")
    result = doctor(StarterOptions(credential_env="PRIVATE_MODEL_KEY"))
    assert result["valid"] and not result["ready"]
    assert result["connectivity"] == "not_tested"
    assert "do-not-print-this-value" not in json.dumps(result)
    assert any(check.get("name") == "PRIVATE_MODEL_KEY" and check["present"] for check in result["checks"])
    result = doctor(StarterOptions(provider="ollama"))
    assert {item["code"] for item in result["diagnostics"]} >= {"missing_dependency", "missing_bundled_ui"}


def test_doctor_cli_checks_credential_names_and_exit_status(monkeypatch, capsys):
    import agent_chat_minimal.onboarding as onboarding

    monkeypatch.setattr(onboarding, "version", lambda name: "1.0")
    monkeypatch.setattr(onboarding, "is_ui_bundle", lambda path: True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert setup_main(["doctor", "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["diagnostics"][0]["code"] == "missing_credential"
    monkeypatch.setenv("OPENAI_API_KEY", "never-echo-me")
    assert setup_main(["--json", "doctor", "--persistence", "sqlite"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["ready"] and payload["valid"]
    assert "never-echo-me" not in output.out
    assert {check.get("name") for check in payload["checks"]} >= {"SQLAlchemy", "aiosqlite"}
    assert setup_main(["doctor"]) == 0
    assert "connectivity not tested" in capsys.readouterr().out
    assert setup_main(["doctor", "--provider", "unknown", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "model_required"


def test_initializer_json_preview_generation_and_conflicts(tmp_path, capsys):
    target = tmp_path / "my-site"
    assert init_main([str(target), "--preset", "full", "--dry-run", "--json"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["dry_run"] is True
    assert not target.exists()
    assert "AGENTS.md" in preview["plan"]["expected_files"]
    assert preview["next_steps_cwd"] == str(target)
    assert preview["next_steps"][0]["argv"] == ["python", "-m", "pip", "install", "-e", ".[test]"]
    assert init_main([str(target), "--preset", "full", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["plan"] == preview["plan"]
    assert result["next_steps"] == preview["next_steps"]
    instructions = (target / "AGENTS.md").read_text()
    assert "minimal-chat-docs" in instructions
    assert "my-site-serve" in instructions
    manifest = json.loads((target / "starter-manifest.json").read_text())
    assert manifest["next_steps"] == result["next_steps"]
    assert init_main([str(target), "--json"]) == 2
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["code"] == "target_conflicts"
    assert (target / "AGENTS.md").read_text() == instructions


def test_initializer_json_validation_error_includes_remedies(tmp_path, capsys):
    assert init_main([str(tmp_path / "bad name"), "--json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["diagnostics"][0]["remedy"]


def test_python_generation_next_steps_resolve_default_credential_name():
    assert starter_next_steps(StarterOptions())[-1]["credential_env"] == "OPENAI_API_KEY"


@pytest.mark.parametrize("module,args,key", [
    ("docs_cli", ["list", "--json"], "guides"),
    ("onboarding", ["describe", "--json"], "documentation"),
])
def test_module_entry_points_work_outside_checkout(tmp_path, module, args, key):
    result = subprocess.run(
        [sys.executable, "-m", f"agent_chat_minimal.{module}", *args],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    assert key in json.loads(result.stdout)
    assert result.stderr == ""
