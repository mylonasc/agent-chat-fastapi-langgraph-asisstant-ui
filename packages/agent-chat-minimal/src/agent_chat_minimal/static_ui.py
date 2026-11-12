"""Bundled static UI mounting."""

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings


logger = logging.getLogger(__name__)
DEFAULT_WEB_DIR = Path(__file__).parent / "web"
DEFAULT_WEB_FULL_DIR = Path(__file__).parent / "web_full"
UI_BASE_PATH_MARKER = "/__agent_chat_base_path__"
_TEXT_ASSET_SUFFIXES = {".html", ".js", ".css", ".json", ".txt", ".map", ".svg"}


def materialize_ui(app: FastAPI, directory: Path, base_path: str) -> Path:
    """Relocate a deliberately compiled basePath across the entire export.

    Never mutate installed package data or rewrite response bodies. Per-app
    temporary copies allow multiple prefixes in one process and preserve normal
    StaticFiles caching/range behavior. Keep the directory alive with the app.
    Legacy/custom exports without the marker are served unchanged; they must
    already have been built for their public prefix.
    """
    if UI_BASE_PATH_MARKER.encode() not in (directory / "index.html").read_bytes():
        if base_path:
            logger.warning(
                "UI at %s has no relocation marker; it must be built for base_path=%s. "
                "API_BASE and ASGI root_path cannot relocate a root-built UI.",
                directory, base_path,
            )
        return directory
    temporary = tempfile.TemporaryDirectory(prefix="agent-chat-ui-")
    try:
        target = Path(temporary.name) / "web"
        shutil.copytree(directory, target)
        marker = UI_BASE_PATH_MARKER.encode()
        for path in target.rglob("*"):
            if path.is_file() and path.suffix in _TEXT_ASSET_SUFFIXES:
                content = path.read_bytes()
                if marker in content:
                    path.write_bytes(content.replace(marker, base_path.encode()))
    except BaseException:
        temporary.cleanup()
        raise
    if not hasattr(app.state, "relocated_ui"):
        app.state.relocated_ui = []
    app.state.relocated_ui.append(temporary)
    return target


def bundled_ui_dir(preset: str = "minimal") -> Path:
    """Return the installed prebuilt UI directory for a preset.

    Generated projects should call this at startup instead of capturing a
    machine-specific absolute path at generation time.
    """
    if preset == "minimal":
        return DEFAULT_WEB_DIR
    if preset == "full":
        return DEFAULT_WEB_FULL_DIR
    raise ValueError("preset must be 'minimal' or 'full'")


def is_ui_bundle(path: Path) -> bool:
    """Return True when a directory contains a servable static UI bundle."""
    return path.is_dir() and (path / "index.html").is_file()


def resolve_ui_dir(override: str | None, preset: str = "minimal") -> Path:
    """Resolve an explicit UI override or fall back to the installed bundle.

    Empty overrides return the bundled resource path (which may itself be
    absent in a source checkout, yielding documented API-only mode). Explicit
    overrides must be non-empty strings; existence is checked by the caller
    so missing bundles degrade to API-only mode with a warning.
    """
    if not override:
        return bundled_ui_dir(preset)
    if not override.strip():
        raise ValueError("UI override path must not be blank")
    return Path(override).expanduser()


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        reserved_paths = (
            "api",
            "assistant",
            "agents",
            "threads",
            "tools",
            "full",
            "health",
            "docs",
            "openapi.json",
        )
        if path in reserved_paths or path.startswith(
            tuple(f"{prefix}/" for prefix in reserved_paths)
        ):
            raise StarletteHTTPException(status_code=404)

        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)

        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


def mount_static_ui(app: FastAPI, settings: Settings) -> None:
    """Mount full and minimal builds after API routes, preserving route order."""
    resolved_full_dir = resolve_ui_dir(settings.web_full_dir, "full").resolve()
    if is_ui_bundle(resolved_full_dir):

        @app.get("/full", include_in_schema=False)
        async def full_root():
            return RedirectResponse(url=f"{settings.base_path}/full/", status_code=307)

        app.mount(
            "/full",
            SPAStaticFiles(directory=materialize_ui(app, resolved_full_dir, settings.base_path), html=True),
            name="web-full",
        )
    else:
        # No full bundle ships anymore (/full was removed); the mount hook
        # stays for explicit FULL_WEB_DIR overrides. Only warn when one was
        # configured, to keep default startup logs clean.
        if settings.web_full_dir:
            logger.warning(
                "Full UI build not found at %s; /full is disabled. "
                "Set FULL_WEB_DIR to a static export directory.",
                resolved_full_dir,
            )
        else:
            logger.debug("No FULL_WEB_DIR override; /full is not served.")

    resolved_web_dir = resolve_ui_dir(settings.web_dir, "minimal").resolve()
    if is_ui_bundle(resolved_web_dir):
        app.mount(
            "/",
            SPAStaticFiles(directory=materialize_ui(app, resolved_web_dir, settings.base_path), html=True),
            name="web",
        )
    else:
        logger.warning(
            "Minimal UI build not found at %s; starting in API-only mode. "
            "Set MINIMAL_WEB_DIR to a static export directory, run "
            "packages/agent-chat-minimal/scripts/stage_ui.sh from a source "
            "checkout, or install a built wheel.",
            resolved_web_dir,
        )
