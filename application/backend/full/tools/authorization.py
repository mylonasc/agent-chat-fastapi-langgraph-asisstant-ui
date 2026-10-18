"""Fail-closed authorization for the full demo's HTTP administration APIs.

This boundary does not authenticate chat routes or agent-invoked tools.
"""

import inspect
import os
from dataclasses import dataclass
from hmac import compare_digest

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class AdminPrincipal:
    subject: str
    is_admin: bool = False


_bearer = HTTPBearer(auto_error=False)


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AdminPrincipal:
    """Authorize an injected principal or a backend-only local admin token.

    Deployments may set ``app.state.admin_principal_resolver`` to a sync/async
    callable accepting Request and returning AdminPrincipal or None. It must
    validate credentials itself; client subject/role headers are not trusted.
    A configured resolver is authoritative: bearer-token fallback is disabled.
    """
    resolver = getattr(request.app.state, "admin_principal_resolver", None)
    if resolver is not None:
        principal = resolver(request)
        if inspect.isawaitable(principal):
            principal = await principal
    else:
        token = os.getenv("FULL_ADMIN_TOKEN", "")
        if not token.strip():
            raise HTTPException(
                status_code=503, detail="HTTP tool administration is disabled"
            )
        principal = None
        if credentials and compare_digest(
            credentials.credentials.encode(), token.encode()
        ):
            principal = AdminPrincipal(subject="local-admin", is_admin=True)

    if principal is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if (
        not isinstance(principal, AdminPrincipal)
        or not principal.subject.strip()
        or not principal.is_admin
    ):
        raise HTTPException(status_code=403, detail="Administrator access required")
    return principal
