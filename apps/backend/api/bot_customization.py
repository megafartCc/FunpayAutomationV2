from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from db.bot_customization_repo import MySQLBotCustomizationRepo, normalize_bot_settings
from db.workspace_repo import MySQLWorkspaceRepo

router = APIRouter()
bot_repo = MySQLBotCustomizationRepo()
workspace_repo = MySQLWorkspaceRepo()


class BotCustomizationResponse(BaseModel):
    workspace_id: int | None
    source: Literal["workspace", "global", "default"]
    settings: dict[str, Any]


@router.get("/bot-customization", response_model=BotCustomizationResponse)
def get_bot_customization(
    workspace_id: int | None = None, user=Depends(get_current_user)
) -> BotCustomizationResponse:
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
    settings, source = bot_repo.get_settings(int(user.id), workspace_id)
    return BotCustomizationResponse(workspace_id=workspace_id, source=source, settings=settings)


@router.put("/bot-customization", response_model=BotCustomizationResponse)
def save_bot_customization(
    payload: dict[str, Any],
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> BotCustomizationResponse:
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
    normalized = normalize_bot_settings(payload)
    saved = bot_repo.save_settings(int(user.id), workspace_id, normalized)
    source = "workspace" if workspace_id is not None else "global"
    return BotCustomizationResponse(workspace_id=workspace_id, source=source, settings=saved)


@router.delete("/bot-customization")
def delete_bot_customization(
    workspace_id: int | None = None, user=Depends(get_current_user)
) -> dict[str, Any]:
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
    removed = bot_repo.delete_settings(int(user.id), workspace_id)
    return {"ok": True, "removed": removed}
