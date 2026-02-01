from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.auto_raise_repo import MySQLAutoRaiseRepo, AutoRaiseLogRecord, AutoRaiseSettings
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


class AutoRaiseSettingsPayload(BaseModel):
    enabled: bool
    all_workspaces: bool
    interval_minutes: int = Field(ge=15, le=720)
    workspaces: dict[int, bool] = Field(default_factory=dict)


class AutoRaiseSettingsResponse(BaseModel):
    enabled: bool
    all_workspaces: bool
    interval_minutes: int
    workspaces: dict[int, bool]


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


def _to_settings_response(settings: AutoRaiseSettings) -> AutoRaiseSettingsResponse:
    return AutoRaiseSettingsResponse(
        enabled=bool(settings.enabled),
        all_workspaces=bool(settings.all_workspaces),
        interval_minutes=int(settings.interval_minutes),
        workspaces={int(key): bool(value) for key, value in settings.workspaces.items()},
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


@router.get("/auto-raise/settings", response_model=AutoRaiseSettingsResponse)
def get_auto_raise_settings(user=Depends(get_current_user)) -> AutoRaiseSettingsResponse:
    settings = auto_raise_repo.get_settings(int(user.id))
    return _to_settings_response(settings)


@router.put("/auto-raise/settings", response_model=AutoRaiseSettingsResponse)
def save_auto_raise_settings(
    payload: AutoRaiseSettingsPayload, user=Depends(get_current_user)
) -> AutoRaiseSettingsResponse:
    user_id = int(user.id)
    workspaces = payload.workspaces or {}
    for workspace_id in workspaces.keys():
        _ensure_workspace(int(workspace_id), user_id)
    settings = AutoRaiseSettings(
        enabled=bool(payload.enabled),
        all_workspaces=bool(payload.all_workspaces),
        interval_minutes=int(payload.interval_minutes),
        workspaces={int(key): bool(value) for key, value in workspaces.items()},
    )
    auto_raise_repo.save_settings(user_id, settings)
    return _to_settings_response(settings)


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
