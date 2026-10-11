"""FastAPI application. Binds to loopback by default and does not auto-migrate."""

import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.app.api.errors import register_exception_handlers
from backend.app.api.routes.health import router as health_router
from backend.app.core.config import Settings
from backend.app.core.logging import configure_logging, request_id_var
from backend.app.db.session import make_engine, session_factory


class RequestIdMiddleware:
    """Attach ``X-Request-ID`` and a logging context value. Does not read the body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = _header(scope, b"x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(request_id)

        async def send_with_id(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass a ``Settings`` instance pointed at a temporary directory."""

    active = settings or Settings()
    configure_logging(active.log_level)
    storage = active.resolved_storage_dir()
    storage.mkdir(parents=True, exist_ok=True)
    database_url = active.resolved_database_url()
    if database_url.startswith("sqlite:///"):
        db_path = database_url[len("sqlite:///") :]
        if db_path and db_path != ":memory:":
            from pathlib import Path

            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="BEAI", version=active.app_version)
    app.state.settings = active
    app.state.engine = make_engine(database_url)
    app.state.session_factory = session_factory(app.state.engine)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active.cors_origin_list(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
