"""Authenticated management routes. Public capability data never contains secrets."""

import asyncio
import logging
import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..domain import Principal
from .store import RevisionConflict

logger = logging.getLogger(__name__)


class ToolSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    global_revision: int = Field(ge=0, strict=True)
    toolsets: list[str]
    tools: dict[str, dict] = Field(default_factory=dict)


def mount_toolkit_api(app, manager, sessions, resolver, service_error):
    router = APIRouter()

    async def principal(request: Request):
        return await resolver.resolve(request)

    PrincipalDep = Annotated[Principal, Depends(principal)]

    async def administrator(request: Request, actor: PrincipalDep):
        # Claims are accepted only from the injected trusted resolver, never
        # from a client-supplied subject/role header.
        if actor.claims.get("role") == "admin":
            return actor
        token = os.getenv("AGENT_CHAT_ADMIN_TOKEN", "")
        authorization = request.headers.get("authorization", "")
        if (
            token
            and authorization.startswith("Bearer ")
            and secrets.compare_digest(authorization[7:].encode(), token.encode())
        ):
            return actor
        raise HTTPException(
            status_code=403, detail="Administrator authorization required"
        )

    AdminDep = Annotated[Principal, Depends(administrator)]

    async def owned(thread_id, actor):
        from ..services import ConflictError, ForbiddenError, NotFoundError

        try:
            await sessions.get(actor, thread_id)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise service_error(exc) from exc

    async def update(body, actor, thread_id=None):
        try:
            scope = (
                manager.thread_scope(thread_id, actor.subject) if thread_id else None
            )
            snapshot = await asyncio.to_thread(manager.update, body, scope)
        except RevisionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        logger.info(
            "tool settings changed actor=%s scope=%s revision=%s",
            actor.subject,
            thread_id or "global",
            snapshot["revision"],
        )
        return snapshot

    @router.get("/tooling")
    async def catalog(actor: PrincipalDep):
        return await asyncio.to_thread(manager.snapshot)

    @router.get("/tooling/admin")
    async def admin_catalog(actor: AdminDep):
        return await asyncio.to_thread(manager.snapshot)

    @router.put("/tooling/admin")
    async def admin_update(body: ToolSettingsUpdate, actor: AdminDep):
        return await update(body, actor)

    @router.get("/threads/{thread_id}/tools")
    async def thread_catalog(thread_id: str, actor: PrincipalDep):
        await owned(thread_id, actor)
        return await asyncio.to_thread(
            manager.snapshot, manager.thread_scope(thread_id, actor.subject)
        )

    @router.put("/threads/{thread_id}/tools")
    async def thread_update(
        thread_id: str, body: ToolSettingsUpdate, actor: PrincipalDep
    ):
        await owned(thread_id, actor)
        return await update(body, actor, thread_id)

    app.include_router(router)
