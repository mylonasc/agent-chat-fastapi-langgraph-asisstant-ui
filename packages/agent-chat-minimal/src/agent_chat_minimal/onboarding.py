"""Agent-facing discovery and offline prerequisite checks (no installations)."""

import argparse
import json
import os
from importlib.metadata import PackageNotFoundError, version

from . import docs
from .setup import (
    Diagnostic,
    StarterOptions,
    describe_setup,
    diagnose_options,
    get_config_schema,
    get_provider_descriptor,
)
from .starter import StarterError, options_from_args
from .static_ui import bundled_ui_dir, is_ui_bundle


def describe() -> dict:
    """Return one offline entry point for docs, setup, and starter automation."""
    from . import __version__

    return {
        **describe_setup(),
        "library_version": __version__,
        "documentation": docs.catalog(),
        "commands": {
            "docs": ["minimal-chat-docs", "list", "--json"],
            "read_onboarding": ["minimal-chat-docs", "show", "agent-onboarding"],
            "local_ollama": ["minimal-chat-docs", "show", "ollama-quickstart"],
            "schema": ["minimal-chat-setup", "schema", "--json"],
            "doctor": ["minimal-chat-setup", "doctor", "--json"],
            "preview": ["minimal-chat-init", "./my-site", "--preset", "full", "--dry-run", "--json"],
            "generate": ["minimal-chat-init", "./my-site", "--preset", "full", "--json"],
        },
        "safety": {
            "network": False,
            "installs_dependencies": False,
            "overwrites_projects": False,
            "resolves_credential_values_in_output": False,
        },
    }


def doctor(options: StarterOptions) -> dict:
    """Check selected starter prerequisites, without importing optional providers.

    Readiness is local only, not a claim of credential validity, model availability,
    connectivity, or tool-call support. Report credential names/presence, not values.
    """
    report = diagnose_options(options)
    findings = list(report.diagnostics)
    checks = []
    dependencies = ["fastapi", "uvicorn", "langgraph", "assistant-stream-ce"]
    providers = {"openai": "langchain-openai", "ollama": "langchain-ollama", "litellm": "langchain-litellm"}
    if options.provider in providers:
        dependencies.append(providers[options.provider])
    if options.persistence == "sqlite":
        dependencies.extend(["SQLAlchemy", "aiosqlite", "alembic", "langgraph-checkpoint-sqlite"])
    for dependency in dependencies:
        try:
            installed = version(dependency)
        except PackageNotFoundError:
            installed = None
            findings.append(Diagnostic(
                code="missing_dependency", field_path="dependencies",
                message=f"{dependency} is not installed",
                remedy=f"Install {dependency}, or install the generated project's declared dependencies.",
            ))
        checks.append({"kind": "dependency", "name": dependency, "present": installed is not None, "version": installed})
    descriptor = get_provider_descriptor(options.provider)
    credential_env = options.credential_env or (descriptor.credential_env if descriptor else None)
    if credential_env:
        present = bool(os.environ.get(credential_env, "").strip())
        checks.append({"kind": "credential", "name": credential_env, "present": present})
        if not present:
            findings.append(Diagnostic(
                code="missing_credential", field_path="credential_env",
                message=f"{credential_env} is not set",
                remedy=f"Export {credential_env} in the server environment; .env files are not loaded automatically.",
            ))
    present = is_ui_bundle(bundled_ui_dir())
    checks.append({"kind": "bundled_ui", "present": present})
    if not present:
        findings.append(Diagnostic(
            code="missing_bundled_ui", field_path="ui",
            message="The installed static UI bundle is missing",
            remedy="Install a published wheel/sdist, or stage the frontend when developing from a checkout.",
        ))
    return {
        "contract_version": report.contract_version,
        "valid": report.valid,
        "ready": not any(item.severity == "error" for item in findings),
        "connectivity": "not_tested",
        "provider": options.provider,
        "preset": options.preset,
        "persistence": options.persistence,
        "checks": checks,
        "diagnostics": [item.to_dict() for item in findings],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Discover agent onboarding or check local setup prerequisites (offline)")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("describe", help="Discover docs, commands, providers, and setup contracts")
    commands.add_parser("schema", help="Read the bundled application configuration JSON schema")
    check = commands.add_parser("doctor", help="Check selected starter prerequisites; no network/model probes")
    check.add_argument("--provider", default="openai")
    check.add_argument("--model", default=None)
    check.add_argument("--preset", default="full", choices=["minimal", "full"])
    check.add_argument("--persistence", default="memory", choices=["memory", "sqlite"])
    check.add_argument("--credential-env", default=None)
    check.add_argument("--base-url", default=None)
    check.set_defaults(directory="my-site", project_name=None, package_name=None)
    for command in commands.choices.values():
        command.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.command == "schema":
            # Emit the schema itself, so it is directly consumable by validators.
            result = get_config_schema()
        elif args.command == "doctor":
            result = doctor(options_from_args(args))
        else:
            result = describe()
    except StarterError as exc:
        print(json.dumps({"contract_version": 1, "ok": False, "code": exc.code, "error": str(exc)}))
        return 2
    # Discovery/schema are inherently structured; --json is accepted for a
    # consistent interface. Doctor also has concise, human-readable output.
    if args.command != "doctor" or args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Local prerequisites: {'ready' if result['ready'] else 'not ready'} (connectivity not tested)")
        for diagnostic in result["diagnostics"]:
            print(f"{diagnostic['severity']}: {diagnostic['message']} — {diagnostic['remedy']}")
    return 0 if result.get("ready", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
