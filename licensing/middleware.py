from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os

from licensing.storage import LicenseStorage

EXEMPT_PATHS = {
    "/activate",
    "/login",
    "/static",
    "/favicon.ico",
    "/license",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


def _env_enabled(name: str, fallback: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return fallback
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class LicenseMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, storage: LicenseStorage | None = None):
        super().__init__(app)
        self.storage = storage or LicenseStorage()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXEMPT_PATHS or path.startswith("/static") or path.startswith("/activate"):
            return await call_next(request)

        status = self.storage.get_status()
        request.state.license_status = status

        if not _env_enabled("AIPET_REQUIRE_LICENSE", False):
            return await call_next(request)

        if status["mode"] == "inactive":
            return RedirectResponse("/activate", status_code=303)
        if status["mode"] == "downgraded":
            return RedirectResponse("/activate?reason=expired", status_code=303)

        return await call_next(request)
