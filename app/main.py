"""Application factory and ASGI entry point.

Run locally:   uvicorn app.main:app --reload
Tests inject fake Jev and LLM providers through create_app(jev=..., llm=...).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import routes_chat, routes_transactions
from app.config import Settings, get_settings
from app.db.session import app_engine
from app.jev.adapter import JevClassifier, TypeSafeJevAdapter
from app.jev.client import build_typesafe_client
from app.llm.provider import LLMProvider, build_llm_provider
from app.orchestration.rate_limit import SlidingWindowRateLimiter
from app.orchestration.tool_registry import build_registry
from app.orchestration.workflow import ChatWorkflow, WorkflowDeps

logger = logging.getLogger("api")


def _error(status_code: int, code: str, message: str, request_id: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error": {"code": code, "message": message},
            "request_id": request_id or str(uuid.uuid4()),
        },
    )


def create_app(
    settings: Settings | None = None,
    *,
    jev: JevClassifier | None = None,
    llm: LLMProvider | None = None,
    now_utc: Callable[[], datetime] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    is_prod = settings.app_env.lower() == "production"

    registry = build_registry(settings.disabled_capability_names)
    if jev is None and settings.jev_configured:
        jev = TypeSafeJevAdapter(build_typesafe_client(settings), model=None)
    if llm is None:
        llm = build_llm_provider(settings)

    deps = WorkflowDeps(
        settings=settings,
        registry=registry,
        jev=jev,
        llm=llm,
        now_utc=now_utc or (lambda: datetime.now(UTC)),
    )

    app = FastAPI(
        title="Merchant Payment Analytics Assistant",
        version="0.1.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/openapi.json",
    )
    app.state.settings = settings
    app.state.deps = deps
    app.state.workflow = ChatWorkflow(deps)
    app.state.limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Log the detail server-side; never echo schema internals to the client.
        logger.info("request validation failed: %d error(s)", len(exc.errors()))
        return _error(422, "invalid_request", "The request is invalid.")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            413: "request_too_large",
            429: "rate_limited",
        }.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else "Request failed."
        return _error(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error path=%s", request.url.path)
        return _error(500, "internal_error", "An internal error occurred.")

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, object]:
        database_ok = True
        try:
            with app_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            database_ok = False
            logger.warning("health: database check failed")
        body: dict[str, object] = {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "unavailable",
        }
        if not is_prod:
            # Booleans only. Never values, never key material.
            body["configured"] = {
                "auth": settings.auth_configured,
                "jev": settings.jev_configured,
                "llm": settings.llm_configured,
            }
        return body

    app.include_router(routes_chat.router)
    app.include_router(routes_transactions.router)
    return app


app = create_app()
