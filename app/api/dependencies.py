"""FastAPI dependencies: authenticated tenant context, database sessions, rate limiting."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.auth.jwt import AuthError, decode_token
from app.auth.tenant_context import TenantContext, resolve_tenant
from app.db.session import analytics_engine, app_engine
from app.orchestration.workflow import ChatWorkflow, WorkflowDeps

logger = logging.getLogger("auth")
_bearer = HTTPBearer(auto_error=False)

GENERIC_AUTH_ERROR = "Authentication required."


def get_workflow(request: Request) -> ChatWorkflow:
    workflow: ChatWorkflow = request.app.state.workflow
    return workflow


def get_deps(request: Request) -> WorkflowDeps:
    deps: WorkflowDeps = request.app.state.deps
    return deps


def get_app_session() -> Iterator[Session]:
    with sessionmaker(bind=app_engine(), expire_on_commit=False)() as session:
        yield session


def get_analytics_session() -> Iterator[Session]:
    with sessionmaker(bind=analytics_engine(), expire_on_commit=False)() as session:
        yield session


def get_tenant(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
    app_session: Session = Depends(get_app_session),  # noqa: B008
) -> TenantContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR)
    settings = request.app.state.settings
    try:
        claims = decode_token(credentials.credentials, settings)
        return resolve_tenant(app_session, claims)
    except AuthError:
        logger.warning("authentication rejected")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR) from None


def enforce_rate_limit(
    request: Request,
    tenant: TenantContext = Depends(get_tenant),  # noqa: B008
) -> TenantContext:
    limiter = request.app.state.limiter
    if not limiter.allow(tenant.user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a minute and try again.",
        )
    return tenant
