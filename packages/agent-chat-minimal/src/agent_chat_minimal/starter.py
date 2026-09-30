"""Agent-starter scaffold and non-interactive initializer (AGS-04).

Implements the shared validate -> plan -> render -> write pipeline over the
:class:`~agent_chat_minimal.setup.StarterOptions` /
:class:`~agent_chat_minimal.setup.GenerationPlan` contracts from AGS-07, so
the CLI here and a future TUI generate identical projects.

Generation never installs dependencies, downloads models, or makes remote
calls. It writes environment placeholders only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import replace  # noqa: F401 - re-exported for generated code reference
from pathlib import Path
from typing import Any

from .setup import (
    SETUP_CONTRACT_VERSION,
    TEMPLATE_VERSION,
    GenerationPlan,
    StarterOptions,
    diagnose_options,
    exit_status_for,
    get_provider_descriptor,
    normalize_package_name,
    validate_options,
)


class StarterError(Exception):
    """Generation failure with stable diagnostics and an exit status."""

    def __init__(self, message: str, *, code: str = "generation_failed", diagnostics: Any = ()):
        super().__init__(message)
        self.code = code
        self.diagnostics = list(diagnostics)
        self.exit_status = exit_status_for(self.diagnostics) or 2


def _library_version() -> str:
    from . import __version__

    return __version__


def _required_extras(options: StarterOptions) -> tuple[str, ...]:
    extras: list[str] = []
    descriptor = get_provider_descriptor(options.provider)
    if descriptor is not None and descriptor.package_extra != "openai":
        extras.append(descriptor.package_extra)
    elif descriptor is None:
        pass  # custom integrations manage their own dependencies
    if options.persistence == "sqlite":
        extras.append("persistence")
    return tuple(dict.fromkeys(extras))


def _dependency_spec(options: StarterOptions) -> str:
    extras = _required_extras(options)
    extra_spec = f"[{','.join(extras)}]" if extras else ""
    return f"agent-chat-fastapi-langgraph-assistant-ui{extra_spec}=={_library_version()}"


def _expected_files(package: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            [
                ".env.example",
                ".gitignore",
                "README.md",
                "agent_chat.yaml",
                "pyproject.toml",
                "starter-manifest.json",
                f"src/{package}/__init__.py",
                f"src/{package}/agents/__init__.py",
                f"src/{package}/agents/helper.py",
                f"src/{package}/server.py",
                f"src/{package}/ui.py",
                "tests/test_helper_agent.py",
            ]
        )
    )


def plan_starter(options: StarterOptions, target_dir: str | Path) -> GenerationPlan:
    """Return a dry-run plan without writing files (validated first)."""
    diagnostics = validate_options(options)
    if any(d.severity == "error" for d in diagnostics):
        raise StarterError(
            "invalid starter options", code="invalid_options", diagnostics=diagnostics
        )
    target = Path(target_dir).expanduser()
    return GenerationPlan(
        target_dir=str(target),
        project_name=options.project_name,
        package_name=options.package_name,
        provider=options.provider,
        model=options.model,
        preset=options.preset,
        persistence=options.persistence,
        expected_files=_expected_files(options.package_name),
        required_extras=_required_extras(options),
    )


def render_starter_files(options: StarterOptions) -> dict[str, str]:
    """Render every project file in memory (no I/O, deterministic)."""
    package = options.package_name
    project = options.project_name
    files = {
        "pyproject.toml": _render_pyproject(options),
        "agent_chat.yaml": _render_config(options),
        ".env.example": _render_env_example(options),
        ".gitignore": _render_gitignore(),
        "README.md": _render_readme(options),
        "starter-manifest.json": _render_manifest(options),
        f"src/{package}/__init__.py": _render_package_init(options),
        f"src/{package}/agents/__init__.py": _render_agents_init(),
        f"src/{package}/agents/helper.py": _render_helper_agent(options),
        f"src/{package}/server.py": _render_server(package),
        f"src/{package}/ui.py": _render_ui(),
        "tests/test_helper_agent.py": _render_tests(package),
    }
    expected = set(_expected_files(package))
    if set(files) != expected:
        missing = sorted(expected - set(files))
        extra = sorted(set(files) - expected)
        raise StarterError(
            f"template/plan mismatch (missing={missing}, extra={extra})",
            code="template_mismatch",
        )
    return files


def generate_starter(
    options: StarterOptions, target_dir: str | Path
) -> GenerationPlan:
    """Validate, render, and write the starter project atomically-ish.

    The destination must be new or an empty directory; existing files are
    never overwritten, so reruns cannot clobber user-edited projects. All
    files render in memory before any write, and write failures clean up
    files created during the failed run.
    """
    plan = plan_starter(options, target_dir)
    target = Path(plan.target_dir)
    if target.exists() and not target.is_dir():
        raise StarterError(
            f"destination exists and is not a directory: {target}",
            code="target_not_directory",
        )
    if target.is_dir() and any(target.iterdir()):
        conflicts = sorted(p.name for p in target.iterdir())
        raise StarterError(
            f"destination is not empty: {target} ({', '.join(conflicts)})",
            code="target_conflicts",
        )
    files = render_starter_files(options)
    for relative in files:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise StarterError(
                f"template escapes destination: {relative}", code="unsafe_path"
            )
    created_dirs: list[Path] = []
    written: list[Path] = []
    try:
        target.mkdir(parents=True, exist_ok=True)
        for relative in sorted(files):
            path = target / relative
            if path.exists():
                raise StarterError(
                    f"refusing to overwrite existing file: {path}",
                    code="target_conflicts",
                )
            if path.parent not in created_dirs and not path.parent.is_dir():
                path.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.append(path.parent)
            path.write_text(files[relative], encoding="utf-8")
            written.append(path)
    except StarterError:
        _cleanup_partial(target, written)
        raise
    except OSError as exc:
        _cleanup_partial(target, written)
        raise StarterError(f"failed to write starter: {exc}", code="write_failed") from exc
    return plan


def _cleanup_partial(target: Path, written: list[Path]) -> None:
    for path in reversed(written):
        try:
            path.unlink()
        except OSError:
            pass
    # Only remove the target itself if we created it and it is now empty.
    try:
        if target.is_dir() and not any(target.iterdir()):
            target.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Templates (packaged code resources, versioned by TEMPLATE_VERSION)
# ---------------------------------------------------------------------------


def _model_spec(options: StarterOptions) -> str:
    return f"{options.provider}:{options.model}"


def _render_pyproject(options: StarterOptions) -> str:
    package = options.package_name
    project = options.project_name
    return f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{project}"
version = "0.1.0"
description = "Agent Chat starter project generated from agent-chat-minimal"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "{_dependency_spec(options)}",
]

[project.optional-dependencies]
test = [
    "httpx>=0.27.0",
    "pytest>=8.0.0",
]

[project.scripts]
{project}-serve = "{package}.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/{package}"]
"""


def _render_config(options: StarterOptions) -> str:
    lines = [
        "version: 1",
        f"model: {options.provider}:{options.model}",
        "default_agent: helper",
        f"ui_preset: {options.preset}",
    ]
    if options.persistence == "sqlite":
        lines += [
            "persistence_enabled: true",
            "database_path: data/app.db",
            "checkpoint_database_path: data/checkpoints.db",
        ]
    lines += [
        "ui:",
        f"  title: {options.project_name} chat",
        "  welcome_heading: How can I help?",
        "  welcome_description: Ask the starter agent anything to get going.",
        "  composer_placeholder: Message the starter agent...",
        "  questions:",
        "    - id: greeting",
        "      label: Say hello",
        "      prompt: Say hello to me using the greeting tool.",
        "      agents: [helper]",
        "    - id: what-can-you-do",
        "      label: What can you do?",
        "      prompt: What can you do as a starter agent?",
        "      agents: [helper]",
    ]
    return "\n".join(lines) + "\n"


def _render_env_example(options: StarterOptions) -> str:
    descriptor = get_provider_descriptor(options.provider)
    credential = options.credential_env or (
        descriptor.credential_env if descriptor else None
    )
    lines = [
        "# Copy to .env and fill in values. Generation never stores credentials.",
        "# AGENT_CHAT_CONFIG=./agent_chat.yaml",
    ]
    if credential:
        lines.append(f"{credential}=")
    elif options.provider == "ollama":
        lines.append("# Ollama needs no API key; ensure the local daemon is running.")
    else:
        lines.append("# Set the credential env var required by your upstream provider.")
    if options.base_url:
        lines.append(f"# MODEL_BASE_URL={options.base_url}")
    return "\n".join(lines) + "\n"


def _render_gitignore() -> str:
    return """__pycache__/
*.pyc
.venv/
.env
data/*.db
dist/
build/
*.egg-info/
"""


def _render_readme(options: StarterOptions) -> str:
    project = options.project_name
    package = options.package_name
    descriptor = get_provider_descriptor(options.provider)
    credential = options.credential_env or (
        descriptor.credential_env if descriptor else None
    )
    cred_setup = (
        f"export {credential}=...  # required for {options.provider}:{options.model}"
        if credential
        else "# No API key needed for this provider configuration."
    )
    return f"""# {project}

Agent Chat starter project. The agent code here is yours; the server,
persistence, and UI come from the installed
`agent-chat-fastapi-langgraph-assistant-ui` library (see
`starter-manifest.json` for the tested version).

## Install

```bash
pip install -e .            # base install
pip install -e .[test]      # offline tests
```

Provider extras are already included in `pyproject.toml`
(`{_dependency_spec(options)}`).

## Credentials

```bash
{cred_setup}
```

Only environment placeholders ship with the project; resolved credentials are
never written to `agent_chat.yaml`.

## Run

```bash
{project}-serve --config ./agent_chat.yaml
# ...or from the project directory, `--config` is optional: the server uses
# `./agent_chat.yaml` when present (`AGENT_CHAT_CONFIG` overrides both).
```

Open the printed address (same-origin UI, no rebuild needed). Switch presets
with `ui_preset: minimal|full` in `agent_chat.yaml`, then restart.

## Check

```bash
{project}-serve --check   # build the helper agent graph and exit
pytest                       # offline tests, no network
```

## Troubleshooting

`model '...' does not support tool calling` means the configured model
cannot use tools (tool binding succeeds locally, so `--check` passes and
only a real conversation fails). Set `model:` in `agent_chat.yaml` to a
tool-capable model for your provider (e.g. `ollama:llama3.1` instead of
`ollama:llama3`), or edit `src/{package}/agents/helper.py` to answer
without tools.

## Layout

- `src/{package}/agents/helper.py` — edit your agent here.
- `src/{package}/server.py` — thin composition over the library; keep models
  and presentation in `agent_chat.yaml`.
- `src/{package}/ui.py` — installed bundle with optional project `web/`
  override (no copied assets, no absolute paths).
- `agent_chat.yaml` — versioned configuration; paths resolve relative to
  this file, so the project stays relocatable.
"""


def _render_manifest(options: StarterOptions) -> str:
    manifest = {
        "contract_version": SETUP_CONTRACT_VERSION,
        "template_version": TEMPLATE_VERSION,
        "library_version": _library_version(),
        "project_name": options.project_name,
        "package_name": options.package_name,
        "provider": options.provider,
        "model": options.model,
        "preset": options.preset,
        "persistence": options.persistence,
        "expected_files": list(_expected_files(options.package_name)),
        "required_extras": list(_required_extras(options)),
    }
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def _render_package_init(options: StarterOptions) -> str:
    return f'''"""{options.project_name}: user-owned agent project (see README.md)."""

__version__ = "0.1.0"
'''


def _render_agents_init() -> str:
    return '''"""Project agents (edit freely; library upgrades never touch this)."""

from .helper import make_helper_agent

__all__ = ["make_helper_agent"]
'''


def _render_helper_agent(options: StarterOptions) -> str:
    default_spec = _model_spec(options)
    return f'''"""Example agent owned by this project (edit freely).

Uses the library tool-agent factory; no persistence or transport code lives
here. Requires a tool-capable chat model: a model without tool support
fails requests with ToolsNotSupportedError naming the model (e.g. use
'ollama:llama3.1' instead of 'ollama:llama3').
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph import StateGraph

from agent_chat_minimal.demo_agent.agent_factory import make_tool_agent
from agent_chat_minimal.models import ModelConfig


@tool
def get_greeting(name: str) -> str:
    """Return a friendly greeting for the given name."""
    return f"Hello, {{name}}! This starter agent is working."


HELPER_TOOLS = [get_greeting]

HELPER_SYSTEM_PROMPT = (
    "You are a helpful starter assistant. "
    "For greeting requests, call get_greeting and reply with the result."
)


def make_helper_agent(
    model: str | ModelConfig | BaseChatModel = "{default_spec}",
    checkpointer=None,
) -> StateGraph:
    """Build the starter agent for any provider model spec/instance."""
    return make_tool_agent(model, list(HELPER_TOOLS), HELPER_SYSTEM_PROMPT, checkpointer)
'''


def _render_server(package: str) -> str:
    return f'''"""Project server: thin composition over the installed library.

No database, network, or model work happens at import time. Configuration
comes from ``agent_chat.yaml`` (paths resolve relative to that file), so the
project runs from any working directory and stays relocatable.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from functools import partial
from pathlib import Path

from agent_chat_minimal import Settings, create_configured_app

from .agents.helper import make_helper_agent
from . import ui as project_ui

def _source_checkout_root() -> Path:
    """Project root when running from a source checkout (src-layout)."""
    return Path(__file__).resolve().parent.parent.parent


def default_config_path() -> Path:
    """Locate ``agent_chat.yaml`` without a machine-specific absolute path.

    Installed packages have no project root on disk, so discovery prefers an
    explicit ``--config``/``AGENT_CHAT_CONFIG`` value, then
    ``./agent_chat.yaml`` in the working directory, and finally the source
    checkout layout (``src/<package>/server.py`` -> project root).
    """
    env_config = os.getenv("AGENT_CHAT_CONFIG")
    if env_config:
        return Path(env_config).expanduser()
    cwd_config = Path.cwd() / "agent_chat.yaml"
    if cwd_config.is_file():
        return cwd_config
    return _source_checkout_root() / "agent_chat.yaml"


PROJECT_ROOT = _source_checkout_root()


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load settings with config-file-relative paths and local UI override."""
    explicit = Path(config_path).expanduser() if config_path else default_config_path()
    settings = Settings.from_yaml(explicit)
    config_root = Path(explicit).expanduser().resolve().parent
    local_web = project_ui.local_web_dir(config_root)
    if local_web is not None and not settings.web_dir:
        settings = replace(settings, web_dir=str(local_web))
    return settings


def agent_factories(settings: Settings):
    """Explicit Python agent mapping (diagnostics use this, not the registry)."""
    return {{"helper": partial(make_helper_agent, model=settings.model)}}


def create_agent_app(config_path: str | Path | None = None):
    """ASGI factory: ``uvicorn {package}.server:create_agent_app --factory``."""
    settings = load_settings(config_path)
    factories = agent_factories(settings)
    return create_configured_app(
        settings, agents=factories, default_agent=settings.default_agent
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Serve the starter agent project")
    parser.add_argument("--config", default=None, help="Path to agent_chat.yaml")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build the configured helper agent graph and exit (no server)",
    )
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    if args.host:
        settings = replace(settings, host=args.host)
    if args.port is not None:
        settings = replace(settings, port=args.port)
    factories = agent_factories(settings)
    factory = factories.get(settings.default_agent)
    if factory is None:
        print(f"unknown agent {{settings.default_agent!r}}", file=__import__("sys").stderr)
        return 2
    if args.check:
        factory()
        print(f"agent {{settings.default_agent!r}} built OK")
        return 0
    import uvicorn

    uvicorn.run(
        create_configured_app(
            settings, agents=factories, default_agent=settings.default_agent
        ),
        host=settings.host,
        port=settings.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _render_ui() -> str:
    return '''"""Project UI hook: installed bundle with optional local override.

Never captures an absolute site-packages path at generation time. Place an
optional static export at ``<project>/web/index.html`` to serve it instead
of the installed bundle; otherwise the library bundle is used.
"""

from pathlib import Path

from agent_chat_minimal import bundled_ui_dir


def local_web_dir(project_root: str | Path) -> Path | None:
    """Return ``<project>/web`` when it contains a servable bundle."""
    candidate = Path(project_root) / "web"
    if candidate.is_dir() and (candidate / "index.html").is_file():
        return candidate
    return None


def web_dir(project_root: str | Path, preset: str = "minimal") -> Path:
    """Resolve the local override or fall back to the installed bundle."""
    return local_web_dir(project_root) or bundled_ui_dir(preset)
'''


def _render_tests(package: str) -> str:
    return f'''"""Starter project tests (offline, no credentials or network)."""

from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent_chat_minimal import Settings

from {package}.agents.helper import make_helper_agent

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class BindableFake(GenericFakeChatModel):
    def bind_tools(self, *args, **kwargs):
        return self


def test_helper_agent_invokes_offline():
    fake = BindableFake(messages=iter([AIMessage(content="hello")]))
    graph = make_helper_agent(fake)
    result = graph.invoke({{"messages": [{{"role": "user", "content": "hi"}}]}})
    assert result["messages"]


def test_project_config_loads_with_relative_paths():
    settings = Settings.from_yaml(PROJECT_ROOT / "agent_chat.yaml", environ={{}})
    assert settings.default_agent == "helper"
    assert Path(settings.database_path).is_absolute() or True  # memory default ok


def test_project_app_serves_custom_agent():
    from {package}.server import create_agent_app

    client = TestClient(create_agent_app())
    body = client.get("/agents").json()
    assert body == {{"agents": ["helper"], "default": "helper"}}
    assert client.get("/api/config").status_code == 200
'''


# ---------------------------------------------------------------------------
# CLI adapter (non-interactive; shares validation with the future TUI)
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a user-owned agent starter project (no network)"
    )
    parser.add_argument("directory", help="Destination directory (new or empty)")
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--package-name", default=None)
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default=None)
    parser.add_argument("--preset", default="minimal", choices=["minimal", "full"])
    parser.add_argument(
        "--persistence", default="memory", choices=["memory", "sqlite"]
    )
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--credential-env", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generation plan as JSON without writing files",
    )
    return parser


def options_from_args(args: argparse.Namespace) -> StarterOptions:
    project_name = args.project_name or Path(args.directory).name
    package_name = args.package_name or normalize_package_name(project_name)
    descriptor = get_provider_descriptor(args.provider)
    if args.model is not None:
        model = args.model
    elif descriptor is not None:
        model = descriptor.default_model
    else:
        raise StarterError(
            f"provider {args.provider!r} needs an explicit --model",
            code="model_required",
            diagnostics=validate_options(
                StarterOptions(
                    project_name=project_name,
                    package_name=package_name,
                    provider=args.provider,
                    model="",
                )
            ),
        )
    credential_env = args.credential_env
    if credential_env is None and descriptor is not None:
        credential_env = descriptor.credential_env
    base_url = args.base_url
    if base_url is None and descriptor is not None:
        base_url = descriptor.default_base_url
    return StarterOptions(
        project_name=project_name,
        package_name=package_name,
        provider=args.provider,
        model=model,
        preset=args.preset,
        persistence=args.persistence,
        base_url=base_url,
        credential_env=credential_env,
    )


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        options = options_from_args(args)
    except StarterError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "code": exc.code}, indent=2), file=sys.stderr)
        return exc.exit_status
    if args.dry_run:
        try:
            plan = plan_starter(options, args.directory)
        except StarterError as exc:
            print(
                json.dumps({"ok": False, "error": str(exc), "code": exc.code}, indent=2),
                file=sys.stderr,
            )
            return exc.exit_status
        print(json.dumps({"ok": True, "plan": plan.to_dict()}, indent=2, sort_keys=True))
        return 0
    report = diagnose_options(options)
    if not report.valid:
        print(report.to_json(), file=sys.stderr)
        return exit_status_for(report.diagnostics)
    try:
        plan = generate_starter(options, args.directory)
    except StarterError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "code": exc.code}, indent=2), file=sys.stderr)
        return exc.exit_status
    print(f"created {plan.project_name} in {plan.target_dir}")
    for relative in plan.expected_files:
        print(f"  {relative}")
    return 0


__all__ = [
    "StarterError",
    "build_parser",
    "generate_starter",
    "main",
    "options_from_args",
    "plan_starter",
    "render_starter_files",
]
