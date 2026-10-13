"""FastAPI application. Binds to loopback by default and does not auto-migrate."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.app.api.errors import register_exception_handlers
from backend.app.api.routes.analyses import router as analyses_router
from backend.app.api.routes.compounds import router as compounds_router
from backend.app.api.routes.docking import router as docking_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.models import router as models_router
from backend.app.api.routes.safety import router as safety_router
from backend.app.api.routes.sequences import router as sequences_router
from backend.app.api.routes.simulation import router as simulation_router
from backend.app.api.routes.structures import router as structures_router
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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from backend.app.jobs.runner import JobRunner
        from backend.app.services.docking.job import run_docking_job
        from backend.app.services.structure.compare import run_comparison_job
        from backend.app.services.structure.pocket_job import run_pocket_job

        runner = JobRunner(app.state.session_factory, app.state.engine, app.state.settings)
        runner.register("structure_comparison", run_comparison_job)
        runner.register("pocket_detection", run_pocket_job)
        runner.register("docking", run_docking_job)
        app.state.jobs = runner
        runner.start()
        from backend.app.services.properties.job import run_solubility_job
        from backend.app.services.simulation.job import run_simulation_job

        runner.register("solubility_training", run_solubility_job)
        runner.register("simulation", run_simulation_job)
        if app.state.settings.register_builtins:
            from backend.app.services.embeddings.builtins import sync_builtin_models
            from backend.app.services.properties.builtin import sync_solubility_model

            session = app.state.session_factory()
            try:
                sync_builtin_models(session)
                sync_solubility_model(session)
            finally:
                session.close()
        try:
            yield
        finally:
            runner.shutdown()
            http = getattr(app.state, "http", None)
            if http is not None:
                http.close()

    storage = active.resolved_storage_dir()
    storage.mkdir(parents=True, exist_ok=True)
    database_url = active.resolved_database_url()
    if database_url.startswith("sqlite:///"):
        db_path = database_url[len("sqlite:///") :]
        if db_path and db_path != ":memory:":
            from pathlib import Path

            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="BEAI", version=active.app_version, lifespan=lifespan)
    app.state.settings = active
    app.state.engine = make_engine(database_url)
    app.state.session_factory = session_factory(app.state.engine)
    from backend.app.data_access.http import ExternalHttp

    cache_dir = active.resolved_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    app.state.http = ExternalHttp(cache_dir)
    from backend.app.services.models_registry.runtime import ModelRuntime

    app.state.model_runtime = ModelRuntime()
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
    app.include_router(structures_router)
    app.include_router(analyses_router)
    app.include_router(jobs_router)
    app.include_router(sequences_router)
    app.include_router(compounds_router)
    app.include_router(docking_router)
    app.include_router(safety_router)
    app.include_router(models_router)
    app.include_router(simulation_router)
    return app


app = create_app()
