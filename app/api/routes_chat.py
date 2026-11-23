"""POST /chat and GET /capabilities."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    enforce_rate_limit,
    get_analytics_session,
    get_app_session,
    get_deps,
    get_workflow,
)
from app.auth.tenant_context import TenantContext
from app.orchestration.schemas import (
    CapabilitiesResponse,
    CapabilityItem,
    ChatRequest,
    ChatResponse,
)
from app.orchestration.workflow import ChatWorkflow, WorkflowDeps

router = APIRouter()


@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=False)
def chat(
    request: Request,
    body: ChatRequest,
    tenant: TenantContext = Depends(enforce_rate_limit),  # noqa: B008
    workflow: ChatWorkflow = Depends(get_workflow),  # noqa: B008
    app_session: Session = Depends(get_app_session),  # noqa: B008
    analytics_session: Session = Depends(get_analytics_session),  # noqa: B008
) -> ChatResponse:
    settings = request.app.state.settings
    if len(body.message) > settings.max_message_chars:
        raise HTTPException(status_code=413, detail="Message is too long.")
    return workflow.handle(
        context=tenant,
        message=body.message,
        request_id=uuid.uuid4(),
        app_session=app_session,
        analytics_session=analytics_session,
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(
    tenant: TenantContext = Depends(enforce_rate_limit),  # noqa: B008
    deps: WorkflowDeps = Depends(get_deps),  # noqa: B008
) -> CapabilitiesResponse:
    items = [
        CapabilityItem(name=spec.name, description=spec.description, min_role=spec.min_role)
        for spec in deps.registry.enabled_for_role(tenant.role)
    ]
    return CapabilitiesResponse(role=tenant.role, capabilities=items, request_id=str(uuid.uuid4()))
