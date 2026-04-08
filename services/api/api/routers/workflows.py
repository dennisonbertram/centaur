"""Workflow routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.deps import require_scope, verify_api_key
from api.runtime_control import ControlPlaneError
from api.workflow_engine import cancel_workflow_run, create_workflow_run, get_workflow_run, list_workflow_runs, get_workflow_checkpoints

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    dependencies=[Depends(verify_api_key)],
)


class WorkflowRunCreateRequest(BaseModel):
    workflow_name: str
    trigger_key: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    eager_start: bool = False


@router.post("/runs", dependencies=[Depends(require_scope("agent:execute"))])
async def create_run(request: Request, body: WorkflowRunCreateRequest):
    try:
        return await create_workflow_run(
            request.app.state.db_pool,
            workflow_name=body.workflow_name,
            run_input=body.input,
            trigger_key=body.trigger_key,
            eager_start=body.eager_start,
        )
    except ControlPlaneError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/runs", dependencies=[Depends(require_scope("agent:execute"))])
async def list_runs(
    request: Request,
    workflow_name: str | None = None,
    thread_key: str | None = None,
    status: str | None = None,
    parent_run_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_workflow_runs(
        request.app.state.db_pool,
        workflow_name=workflow_name,
        thread_key=thread_key,
        status=status,
        parent_run_id=parent_run_id,
        limit=limit,
    )


@router.get("/runs/{run_id}", dependencies=[Depends(require_scope("agent:execute"))])
async def get_run(run_id: str, request: Request):
    run = await get_workflow_run(request.app.state.db_pool, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return run


@router.get("/runs/{run_id}/children", dependencies=[Depends(require_scope("agent:execute"))])
async def get_run_children(
    run_id: str,
    request: Request,
    limit: int = Query(default=200, ge=1, le=200),
):
    run = await get_workflow_run(request.app.state.db_pool, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return await list_workflow_runs(
        request.app.state.db_pool,
        parent_run_id=run_id,
        limit=limit,
    )


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(require_scope("agent:execute"))])
async def cancel_run(run_id: str, request: Request):
    result = await cancel_workflow_run(request.app.state.db_pool, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return result


@router.get("/runs/{run_id}/checkpoints", dependencies=[Depends(require_scope("agent:execute"))])
async def get_checkpoints(run_id: str, request: Request):
    checkpoints = await get_workflow_checkpoints(request.app.state.db_pool, run_id)
    if checkpoints is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return checkpoints


class SendEventRequest(BaseModel):
    event_type: str
    correlation_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/events", dependencies=[Depends(require_scope("agent:execute"))])
async def send_event(request: Request, body: SendEventRequest):
    from api.workflow_engine import send_workflow_event
    return await send_workflow_event(
        request.app.state.db_pool,
        event_type=body.event_type,
        correlation_id=body.correlation_id,
        payload=body.payload,
    )
