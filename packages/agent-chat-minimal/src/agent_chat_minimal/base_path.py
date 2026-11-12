"""Normalize prefix-stripping proxies to the ASGI path/root_path contract."""

from starlette.types import ASGIApp, Receive, Scope, Send


class BasePathMiddleware:
    """Keep generated URLs/redirects public for stripped and preserved paths.

    ASGI path includes root_path. A stripping proxy without server-level
    root_path configuration sends only the internal path; restore its configured
    public prefix before routing. Never infer it from untrusted request headers.
    """

    def __init__(self, app: ASGIApp, base_path: str) -> None:
        self.app = app
        self.base_path = base_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"}:
            path = scope["path"]
            if path != self.base_path and not path.startswith(self.base_path + "/"):
                scope = dict(scope)
                scope["path"] = self.base_path + path
                if "raw_path" in scope:
                    scope["raw_path"] = self.base_path.encode() + scope["raw_path"]
        await self.app(scope, receive, send)
