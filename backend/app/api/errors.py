"""Map domain errors to JSON responses. Bodies never include tracebacks or paths."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.errors import BeaiError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BeaiError)
    async def handle_beai(request: Request, exc: BeaiError) -> JSONResponse:
        logger.info("domain error %s", exc.code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        messages: list[str] = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            text = str(error.get("msg", "Invalid request"))
            messages.append(f"{location}: {text}" if location else text)
        message = "; ".join(messages) or "Request validation failed."
        return JSONResponse(
            status_code=422,
            content={"code": "invalid_input", "message": message},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            message = "Not found."
            code = "not_found"
        else:
            message = exc.detail if isinstance(exc.detail, str) else "Request failed."
            code = "http_error"
        return JSONResponse(status_code=exc.status_code, content={"code": code, "message": message})

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "The server could not complete this request.",
            },
        )
