from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.auto_raise_repo import MySQLAutoRaiseRepo, AutoRaiseLogRecord
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
auto_raise_repo = MySQLAutoRaiseRepo()
workspace_repo = MySQLWorkspaceRepo()


class AutoRaiseLogItem(BaseModel):
    id: int
    level: str
    source: str | None = None
    line: int | None = None
    message: str
    workspace_id: int | None = None
    created_at: str | None = None


class AutoRaiseLogsResponse(BaseModel):
    items: list[AutoRaiseLogItem]


class AutoRaiseRequest(BaseModel):
    workspace_id: int | None = Field(None, ge=1)


class AutoRaiseRequestResponse(BaseModel):
    created: int


def _to_log_item(record: AutoRaiseLogRecord) -> AutoRaiseLogItem:
    return AutoRaiseLogItem(
        id=record.id,
        level=record.level,
        source=record.source,
        line=record.line,
        message=record.message,
        workspace_id=record.workspace_id,
        created_at=record.created_at,
    )


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        return
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace.")


@router.get("/auto-raise/logs", response_model=AutoRaiseLogsResponse)
def list_auto_raise_logs(
    workspace_id: int | None = None,
    limit: int = 200,
    user=Depends(get_current_user),
) -> AutoRaiseLogsResponse:
    _ensure_workspace(workspace_id, int(user.id))
    items = auto_raise_repo.list_logs(int(user.id), workspace_id=workspace_id, limit=limit)
    return AutoRaiseLogsResponse(items=[_to_log_item(item) for item in items])


@router.post("/auto-raise/manual", response_model=AutoRaiseRequestResponse)
def request_auto_raise(payload: AutoRaiseRequest, user=Depends(get_current_user)) -> AutoRaiseRequestResponse:
    user_id = int(user.id)
    if payload.workspace_id is not None:
        _ensure_workspace(payload.workspace_id, user_id)
        created = auto_raise_repo.create_requests(user_id, [int(payload.workspace_id)], message="manual")
        return AutoRaiseRequestResponse(created=created)

    workspaces = workspace_repo.list_by_user(user_id)
    workspace_ids = [int(ws.id) for ws in workspaces]
    created = auto_raise_repo.create_requests(user_id, workspace_ids, message="manual")
    return AutoRaiseRequestResponse(created=created)
