from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.workspace_repo import MySQLWorkspaceRepo, WorkspaceRecord


router = APIRouter()
workspace_repo = MySQLWorkspaceRepo()


def _mask_key(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 6:
        return "•" * len(raw)
    return f"{'•' * (len(raw) - 4)}{raw[-4:]}"


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    golden_key: str = Field(..., min_length=5)
    proxy_url: str = Field(..., min_length=3)
    is_default: bool = False


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    golden_key: str | None = Field(None, min_length=5)
    proxy_url: str | None = Field(None, min_length=3)
    is_default: bool | None = None


class WorkspaceItem(BaseModel):
    id: int
    name: str
    proxy_url: str
    is_default: bool
    created_at: str | None = None
    key_hint: str | None = None


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceItem]


def _to_item(record: WorkspaceRecord) -> WorkspaceItem:
    return WorkspaceItem(
        id=record.id,
        name=record.name,
        proxy_url=record.proxy_url,
        is_default=bool(record.is_default),
        created_at=record.created_at,
        key_hint=_mask_key(record.golden_key),
    )


@router.get("/workspaces", response_model=WorkspaceListResponse)
def list_workspaces(user=Depends(get_current_user)) -> WorkspaceListResponse:
    items = workspace_repo.list_by_user(int(user.id))
    return WorkspaceListResponse(items=[_to_item(item) for item in items])


@router.post("/workspaces", response_model=WorkspaceItem, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, user=Depends(get_current_user)) -> WorkspaceItem:
    name = payload.name.strip()
    golden_key = payload.golden_key.strip()
    proxy_url = payload.proxy_url.strip()
    if not proxy_url:
        raise HTTPException(status_code=400, detail="Proxy is required for this workspace.")

    created = workspace_repo.create(
        user_id=int(user.id),
        name=name,
        golden_key=golden_key,
        proxy_url=proxy_url,
        is_default=payload.is_default,
    )
    if not created:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace already exists.")
    return _to_item(created)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceItem)
def update_workspace(workspace_id: int, payload: WorkspaceUpdate, user=Depends(get_current_user)) -> WorkspaceItem:
    existing = workspace_repo.get_by_id(workspace_id, int(user.id))
    if not existing:
        raise HTTPException(status_code=404, detail="Workspace not found")

    fields: dict = {}
    if payload.name is not None:
        fields["name"] = payload.name.strip()
    if payload.golden_key is not None and payload.golden_key.strip():
        fields["golden_key"] = payload.golden_key.strip()
    if payload.proxy_url is not None:
        proxy_url = payload.proxy_url.strip()
        if not proxy_url:
            raise HTTPException(status_code=400, detail="Proxy is required for this workspace.")
        fields["proxy_url"] = proxy_url

    make_default = payload.is_default is True
    if not fields and not make_default:
        raise HTTPException(status_code=400, detail="No changes provided")

    ok = workspace_repo.update(
        workspace_id=workspace_id,
        user_id=int(user.id),
        fields=fields,
        make_default=make_default,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update workspace")
    updated = workspace_repo.get_by_id(workspace_id, int(user.id))
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_item(updated)


@router.post("/workspaces/{workspace_id}/default")
def set_default_workspace(workspace_id: int, user=Depends(get_current_user)) -> dict:
    ok = workspace_repo.set_default(workspace_id, int(user.id))
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"ok": True}


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, user=Depends(get_current_user)) -> dict:
    ok = workspace_repo.delete(workspace_id, int(user.id))
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"ok": True}
