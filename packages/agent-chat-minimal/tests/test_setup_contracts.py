"""Wizard-ready setup contracts and diagnostics (AGS-07)."""

import json

from agent_chat_minimal import (
    SETUP_CONTRACT_VERSION,
    GenerationPlan,
    ProviderDescriptor,
    StarterOptions,
    describe_setup,
    diagnose_options,
    exit_status_for,
    get_config_schema,
    get_provider_descriptor,
    list_providers,
    register_provider_descriptor,
    validate_options,
)


def test_builtin_provider_descriptors_cover_first_class_providers():
    providers = {p.name: p for p in list_providers()}
    assert set(providers) >= {"openai", "ollama", "litellm"}
    assert providers["openai"].package_extra == "openai"
    assert providers["ollama"].package_extra == "ollama"
    assert providers["litellm"].package_extra == "litellm"
    assert get_provider_descriptor("custom-integration") is None


def test_unknown_provider_is_warning_not_error():
    options = StarterOptions(provider="my-langchain-integration", model="my-model")
    report = diagnose_options(options)
    assert report.valid is True
    assert report.connectivity == "not_tested"
    codes = {d.code: d.severity for d in report.diagnostics}
    assert codes["unknown_provider"] == "warning"
    assert exit_status_for(report.diagnostics) == 0


def test_invalid_options_produce_stable_error_codes():
    options = StarterOptions(
        project_name="bad name!",
        package_name="wrong",
        provider="",
        model="",
        preset="enormous",
        persistence="cloud",
        base_url="   ",
        credential_env="not an env var",
    )
    diagnostics = validate_options(options)
    codes = {d.code for d in diagnostics}
    assert {
        "bad_project_name",
        "bad_package_name",
        "empty_provider",
        "empty_model",
        "bad_preset",
        "bad_persistence",
        "bad_base_url",
        "bad_credential_env",
    } <= codes
    assert all(d.field_path for d in diagnostics)
    assert all(d.remedy for d in diagnostics)
    assert exit_status_for(diagnostics) == 2


def test_custom_provider_registration_extends_wizard_metadata():
    register_provider_descriptor(
        ProviderDescriptor(
            name="test-custom",
            title="Test Custom",
            package_extra="test-extra",
            default_model="test-model",
            credential_env="TEST_CUSTOM_KEY",
            default_base_url=None,
            description="Test-only custom integration.",
        )
    )
    try:
        options = StarterOptions(provider="test-custom", model="test-model")
        assert diagnose_options(options).valid is True
    finally:
        import agent_chat_minimal.setup as setup_module

        setup_module._PROVIDER_REGISTRY.pop("test-custom", None)


def test_plan_contract_serializes_and_rejects_unknown_fields():
    plan = GenerationPlan(
        target_dir="/tmp/my-agent",
        project_name="my-agent",
        package_name="my_agent",
        provider="ollama",
        model="llama3.1:8b",
        preset="full",
        persistence="sqlite",
        expected_files=("pyproject.toml", "agent_chat.yaml"),
        required_extras=("ollama", "persistence"),
    )
    data = plan.to_dict()
    assert data["contract_version"] == SETUP_CONTRACT_VERSION
    assert GenerationPlan.from_dict(json.loads(json.dumps(data))) == plan
    try:
        GenerationPlan.from_dict({**data, "future": True})
    except ValueError as exc:
        assert "unknown generation plan" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("unknown plan field was accepted")


def test_diagnostics_serialize_without_credential_values(monkeypatch):
    monkeypatch.setenv("SECRET_UPSTREAM_KEY", "super-secret-value")
    options = StarterOptions(
        provider="openai",
        model="gpt-4o-mini",
        credential_env="SECRET_UPSTREAM_KEY",
    )
    report = diagnose_options(options)
    payload = json.dumps(report.to_dict())
    assert report.valid is True
    assert "super-secret-value" not in payload
    assert "SECRET_UPSTREAM_KEY" in payload


def test_config_schema_and_setup_description_are_machine_readable():
    schema = get_config_schema()
    assert schema["title"] == "Agent Chat configuration"
    assert schema["properties"]["version"] == {"const": 1}
    assert "ui" in schema["properties"]

    description = describe_setup()
    assert description["contract_version"] == SETUP_CONTRACT_VERSION
    assert {p["name"] for p in description["providers"]} >= {
        "openai",
        "ollama",
        "litellm",
    }
    assert description["wizard_flow"][0] == "project"
    assert description["wizard_flow"][-1] == "diagnose"
