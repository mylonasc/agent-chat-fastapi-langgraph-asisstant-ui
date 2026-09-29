"""Wizard-ready setup contracts, validation, and diagnostics (AGS-07).

This module is the shared setup engine used by scripts, the non-interactive
initializer (AGS-04), and a future optional TUI. It performs offline
validation only: it never installs dependencies, downloads models, makes
network calls, or resolves credential values. Connectivity is always reported
as ``not_tested`` here; explicit opt-in live probes live outside this module
(for example ``minimal-chat-serve --check`` with real credentials).

Template-backed plan/render/write implementation belongs to AGS-04, which
builds on the :class:`StarterOptions` and :class:`GenerationPlan` contracts
published here.
"""

from __future__ import annotations

import json
import keyword
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

SETUP_CONTRACT_VERSION = 1
TEMPLATE_VERSION = 1

EXIT_OK = 0
EXIT_INVALID = 2

Preset = Literal["minimal", "full"]
PersistenceMode = Literal["memory", "sqlite"]

_PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_ENV_VAR_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True)
class ProviderDescriptor:
    """Machine-readable metadata for one model provider."""

    name: str
    title: str
    package_extra: str
    default_model: str
    credential_env: str | None
    default_base_url: str | None
    description: str
    custom_endpoint_supported: bool = True


def _builtin_providers() -> dict[str, ProviderDescriptor]:
    return {
        "openai": ProviderDescriptor(
            name="openai",
            title="OpenAI",
            package_extra="openai",
            default_model="gpt-4o-mini",
            credential_env="OPENAI_API_KEY",
            default_base_url=None,
            description="Hosted OpenAI models via langchain-openai (default install).",
        ),
        "ollama": ProviderDescriptor(
            name="ollama",
            title="Ollama (local)",
            package_extra="ollama",
            default_model="llama3.1:8b",
            credential_env=None,
            default_base_url="http://localhost:11434",
            description="Local Ollama daemon via langchain-ollama; models install separately.",
        ),
        "litellm": ProviderDescriptor(
            name="litellm",
            title="LiteLLM",
            package_extra="litellm",
            default_model="anthropic/claude-sonnet-4-5",
            credential_env=None,
            default_base_url=None,
            description=(
                "Direct LiteLLM routing via langchain-litellm ChatLiteLLM. "
                "Credential requirements depend on the upstream provider; an "
                "OpenAI-compatible LiteLLM proxy uses provider 'openai' instead."
            ),
        ),
    }


_PROVIDER_REGISTRY: dict[str, ProviderDescriptor] = _builtin_providers()


def list_providers() -> list[ProviderDescriptor]:
    """Return provider descriptors suitable for wizard selection forms."""
    return [ _PROVIDER_REGISTRY[name] for name in sorted(_PROVIDER_REGISTRY) ]


def get_provider_descriptor(name: str) -> ProviderDescriptor | None:
    """Return the descriptor for a provider, or None for custom integrations."""
    return _PROVIDER_REGISTRY.get(name)


def register_provider_descriptor(descriptor: ProviderDescriptor) -> None:
    """Register a custom LangChain integration descriptor (wizard extension)."""
    if not descriptor.name.strip():
        raise ValueError("provider name must not be empty")
    _PROVIDER_REGISTRY[descriptor.name] = descriptor


@dataclass(frozen=True)
class StarterOptions:
    """Versioned, serializable inputs for starter generation."""

    contract_version: int = SETUP_CONTRACT_VERSION
    project_name: str = "my-agent"
    package_name: str = "my_agent"
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    preset: Preset = "minimal"
    persistence: PersistenceMode = "memory"
    base_url: str | None = None
    credential_env: str | None = None
    model_kwargs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StarterOptions":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(
                f"unknown starter option(s): {', '.join(sorted(unknown))}"
            )
        return cls(**{k: v for k, v in data.items() if k in known})


def normalize_package_name(project_name: str) -> str:
    """Derive a Python package name from a project/distribution name."""
    return re.sub(r"[-.]+", "_", project_name).lower()


@dataclass(frozen=True)
class Diagnostic:
    """One stable, serializable setup finding (never carries secrets)."""

    code: str
    field_path: str
    message: str
    remedy: str
    severity: Literal["error", "warning"] = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SetupReport:
    """Redacted validation result for options or generated plans."""

    contract_version: int = SETUP_CONTRACT_VERSION
    valid: bool = False
    connectivity: Literal["not_tested"] = "not_tested"
    effective_config: dict[str, Any] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "valid": self.valid,
            "connectivity": self.connectivity,
            "effective_config": self.effective_config,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def redacted_options(options: StarterOptions) -> dict[str, Any]:
    """Return effective options with only env var names (never values)."""
    data = options.to_dict()
    # Defensive: StarterOptions stores env var references, never resolved
    # credentials, so redaction is structural rather than value-scanning.
    return data


def validate_options(options: StarterOptions) -> list[Diagnostic]:
    """Offline validation of starter options (no I/O, no network)."""
    findings: list[Diagnostic] = []
    if options.contract_version != SETUP_CONTRACT_VERSION:
        findings.append(
            Diagnostic(
                code="unsupported_contract",
                field_path="contract_version",
                message=f"unsupported setup contract: {options.contract_version!r}",
                remedy=f"Use contract_version {SETUP_CONTRACT_VERSION}.",
            )
        )
    if not options.project_name.strip() or len(options.project_name) > 100:
        findings.append(
            Diagnostic(
                code="bad_project_name",
                field_path="project_name",
                message="project_name must contain 1 to 100 characters",
                remedy="Choose a directory-safe name such as 'my-agent'.",
            )
        )
    elif not _PROJECT_NAME_RE.match(options.project_name):
        findings.append(
            Diagnostic(
                code="bad_project_name",
                field_path="project_name",
                message="project_name may only contain letters, digits, '-' and '_'",
                remedy="Rename to match ^[A-Za-z0-9][A-Za-z0-9_-]*$, e.g. 'my-agent'.",
            )
        )
    expected_package = normalize_package_name(options.project_name)
    if options.package_name != expected_package:
        findings.append(
            Diagnostic(
                code="bad_package_name",
                field_path="package_name",
                message=(
                    f"package_name {options.package_name!r} does not match "
                    f"project_name {options.project_name!r}"
                ),
                remedy=f"Use package_name {expected_package!r}.",
            )
        )
    elif (
        not options.package_name.isidentifier()
        or keyword.iskeyword(options.package_name)
    ):
        findings.append(
            Diagnostic(
                code="bad_package_name",
                field_path="package_name",
                message="package_name must be a valid Python identifier",
                remedy="Use lowercase letters, digits, and underscores only.",
            )
        )
    if not options.provider.strip():
        findings.append(
            Diagnostic(
                code="empty_provider",
                field_path="provider",
                message="provider must not be empty",
                remedy="Select a known provider or register a custom descriptor.",
            )
        )
    elif get_provider_descriptor(options.provider) is None:
        findings.append(
            Diagnostic(
                code="unknown_provider",
                field_path="provider",
                message=(
                    f"provider {options.provider!r} has no registered descriptor; "
                    "treating it as a custom LangChain integration"
                ),
                remedy=(
                    "Register a ProviderDescriptor for wizard metadata, or "
                    "continue with a generic integration/model-builder."
                ),
                severity="warning",
            )
        )
    if not options.model.strip():
        findings.append(
            Diagnostic(
                code="empty_model",
                field_path="model",
                message="model must not be empty",
                remedy="Set an opaque model id such as 'gpt-4o-mini' or 'llama3.1:8b'.",
            )
        )
    if options.preset not in ("minimal", "full"):
        findings.append(
            Diagnostic(
                code="bad_preset",
                field_path="preset",
                message="preset must be 'minimal' or 'full'",
                remedy="Select the packaged minimal or full UI preset.",
            )
        )
    if options.persistence not in ("memory", "sqlite"):
        findings.append(
            Diagnostic(
                code="bad_persistence",
                field_path="persistence",
                message="persistence must be 'memory' or 'sqlite'",
                remedy="Select 'memory' for zero-file defaults or 'sqlite' for durable storage.",
            )
        )
    if options.base_url is not None and not options.base_url.strip():
        findings.append(
            Diagnostic(
                code="bad_base_url",
                field_path="base_url",
                message="base_url must not be blank",
                remedy="Set an explicit endpoint URL or leave base_url unset.",
            )
        )
    if options.credential_env is not None:
        if not _ENV_VAR_RE.match(options.credential_env):
            findings.append(
                Diagnostic(
                    code="bad_credential_env",
                    field_path="credential_env",
                    message="credential_env must look like an env var name",
                    remedy="Use uppercase letters, digits, and underscores, e.g. 'OPENAI_API_KEY'.",
                )
            )
    if not isinstance(options.model_kwargs, dict):
        findings.append(
            Diagnostic(
                code="bad_model_kwargs",
                field_path="model_kwargs",
                message="model_kwargs must be a mapping",
                remedy="Pass model parameters as a JSON object.",
            )
        )
    return findings


def diagnose_options(options: StarterOptions) -> SetupReport:
    """Build a serializable offline report for options (connectivity unknown)."""
    findings = validate_options(options)
    errors = [d for d in findings if d.severity == "error"]
    return SetupReport(
        valid=not errors,
        effective_config=redacted_options(options),
        diagnostics=tuple(findings),
    )


def exit_status_for(diagnostics: list[Diagnostic] | tuple[Diagnostic, ...]) -> int:
    """Map diagnostics to a stable CLI exit status."""
    return EXIT_INVALID if any(d.severity == "error" for d in diagnostics) else EXIT_OK


@dataclass(frozen=True)
class GenerationPlan:
    """Versioned contract for what the generator (AGS-04) will write.

    AGS-04 owns template-backed plan construction and file rendering; this
    dataclass is the serializable boundary shared with scripts and the future
    TUI so previews stay identical across presentation layers.
    """

    contract_version: int = SETUP_CONTRACT_VERSION
    template_version: int = TEMPLATE_VERSION
    target_dir: str = ""
    project_name: str = "my-agent"
    package_name: str = "my_agent"
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    preset: Preset = "minimal"
    persistence: PersistenceMode = "memory"
    expected_files: tuple[str, ...] = ()
    required_extras: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationPlan":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(
                f"unknown generation plan field(s): {', '.join(sorted(unknown))}"
            )
        data = dict(data)
        data["expected_files"] = tuple(data.get("expected_files", ()))
        data["required_extras"] = tuple(data.get("required_extras", ()))
        return cls(**{k: v for k, v in data.items() if k in known})


class StarterGenerator(Protocol):
    """Contract implemented by the AGS-04 template-backed generator."""

    def plan(self, options: StarterOptions, target_dir: str | Path) -> GenerationPlan:
        """Return a dry-run plan without writing files."""
        ...

    def generate(
        self, options: StarterOptions, target_dir: str | Path
    ) -> GenerationPlan:
        """Validate, render, and write the starter project."""
        ...


def get_config_schema() -> dict[str, Any]:
    """Return the machine-readable versioned application-config schema."""
    schema_path = Path(__file__).parent / "schemas" / "agent_chat.schema.json"
    return json.loads(schema_path.read_text())


def describe_setup() -> dict[str, Any]:
    """Return wizard-facing metadata: contract, providers, and flows."""
    return {
        "contract_version": SETUP_CONTRACT_VERSION,
        "template_version": TEMPLATE_VERSION,
        "providers": [asdict(p) for p in list_providers()],
        "presets": ["minimal", "full"],
        "persistence_modes": ["memory", "sqlite"],
        "config_schema_id": "https://agent-chat.dev/schemas/agent-chat/v1.json",
        "wizard_flow": [
            "project",
            "provider",
            "endpoint",
            "environment_references",
            "model",
            "preset",
            "questions",
            "storage",
            "preview",
            "generate",
            "diagnose",
        ],
        "notes": (
            "Base serving has no TUI dependency. A future TUI presents these "
            "options, previews the GenerationPlan, confirms, then generates. "
            "Cancellation performs no writes; generation never installs "
            "dependencies, downloads models, or calls remote models."
        ),
    }


__all__ = [
    "EXIT_INVALID",
    "EXIT_OK",
    "SETUP_CONTRACT_VERSION",
    "TEMPLATE_VERSION",
    "Diagnostic",
    "GenerationPlan",
    "PersistenceMode",
    "Preset",
    "ProviderDescriptor",
    "SetupReport",
    "StarterGenerator",
    "StarterOptions",
    "describe_setup",
    "diagnose_options",
    "exit_status_for",
    "get_config_schema",
    "get_provider_descriptor",
    "list_providers",
    "normalize_package_name",
    "redacted_options",
    "register_provider_descriptor",
    "validate_options",
]
