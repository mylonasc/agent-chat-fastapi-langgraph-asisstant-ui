"""Bundled static UI mounting."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings


logger = logging.getLogger(__name__)
DEFAULT_WEB_DIR = Path(__file__).parent / "web"
DEFAULT_WEB_FULL_DIR = Path(__file__).parent / "web_full"


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        reserved_paths = (
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
    resolved_full_dir = Path(settings.web_full_dir or DEFAULT_WEB_FULL_DIR).resolve()
    if resolved_full_dir.is_dir() and (resolved_full_dir / "index.html").is_file():

        @app.get("/full", include_in_schema=False)
        async def full_root():
            return RedirectResponse(url="/full/", status_code=307)

        app.mount(
            "/full",
            SPAStaticFiles(directory=resolved_full_dir, html=True),
            name="web-full",
        )
    else:
        logger.warning(
            "Full UI build not found at %s; /full is disabled. "
            "Set FULL_WEB_DIR to a frontend-full/out directory.",
            resolved_full_dir,
        )

    resolved_web_dir = Path(settings.web_dir or DEFAULT_WEB_DIR).resolve()
    if resolved_web_dir.is_dir() and (resolved_web_dir / "index.html").is_file():
        app.mount(
            "/",
            SPAStaticFiles(directory=resolved_web_dir, html=True),
            name="web",
        )
    else:
        logger.warning(
            "Minimal UI build not found at %s; starting in API-only mode. "
            "Set MINIMAL_WEB_DIR to a frontend-minimal/out directory.",
            resolved_web_dir,
        )
