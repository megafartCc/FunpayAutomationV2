from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from db.raise_category_repo import MySQLRaiseCategoryRepo, RaiseCategoryRecord
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
raise_repo = MySQLRaiseCategoryRepo()
workspace_repo = MySQLWorkspaceRepo()


class RaiseCategoryItem(BaseModel):
    category_id: int
    category_name: str
    workspace_id: int | None = None
    updated_at: str | None = None


class RaiseCategoryResponse(BaseModel):
    items: list[RaiseCategoryItem]


def _to_item(record: RaiseCategoryRecord) -> RaiseCategoryItem:
    return RaiseCategoryItem(
        category_id=record.category_id,
        category_name=record.category_name,
        workspace_id=record.workspace_id,
        updated_at=record.updated_at,
    )


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        return
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace.")


@router.get("/raise-categories", response_model=RaiseCategoryResponse)
def list_raise_categories(workspace_id: int | None = None, user=Depends(get_current_user)) -> RaiseCategoryResponse:
    _ensure_workspace(workspace_id, int(user.id))
    items = raise_repo.list_by_user(int(user.id), workspace_id)
    return RaiseCategoryResponse(items=[_to_item(item) for item in items])
