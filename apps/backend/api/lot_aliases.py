from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.lot_alias_repo import MySQLLotAliasRepo, LotAliasRecord
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
alias_repo = MySQLLotAliasRepo()
workspace_repo = MySQLWorkspaceRepo()


class LotAliasCreate(BaseModel):
    workspace_id: int | None = Field(None, ge=1)
    lot_number: int = Field(..., ge=1)
    funpay_url: str = Field(..., min_length=5)


class LotAliasReplace(BaseModel):
    workspace_id: int | None = Field(None, ge=1)
    lot_number: int = Field(..., ge=1)
    urls: list[str] = Field(default_factory=list)


class LotAliasItem(BaseModel):
    id: int
    lot_number: int
    funpay_url: str
    workspace_id: int | None = None


class LotAliasListResponse(BaseModel):
    items: list[LotAliasItem]


def _to_item(record: LotAliasRecord) -> LotAliasItem:
    return LotAliasItem(
        id=record.id,
        lot_number=record.lot_number,
        funpay_url=record.funpay_url,
        workspace_id=record.workspace_id,
    )


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for aliases.")


@router.get("/lot-aliases", response_model=LotAliasListResponse)
def list_lot_aliases(workspace_id: int | None = None, user=Depends(get_current_user)) -> LotAliasListResponse:
    _ensure_workspace(workspace_id, int(user.id))
    records = alias_repo.list_by_user(int(user.id), int(workspace_id))
    return LotAliasListResponse(items=[_to_item(r) for r in records])


@router.post("/lot-aliases", response_model=LotAliasItem, status_code=status.HTTP_201_CREATED)
def create_lot_alias(payload: LotAliasCreate, user=Depends(get_current_user)) -> LotAliasItem:
    if not payload.funpay_url.strip():
        raise HTTPException(status_code=400, detail="FunPay URL is required")
    _ensure_workspace(payload.workspace_id, int(user.id))
    created = alias_repo.create(
        user_id=int(user.id),
        workspace_id=int(payload.workspace_id),
        lot_number=payload.lot_number,
        funpay_url=payload.funpay_url.strip(),
    )
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create alias (duplicate?)")
    return _to_item(created)


@router.delete("/lot-aliases/{alias_id}", status_code=status.HTTP_200_OK)
def delete_lot_alias(alias_id: int, workspace_id: int | None = None, user=Depends(get_current_user)) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    ok = alias_repo.delete_in_workspace(int(alias_id), int(user.id), int(workspace_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Alias not found")
    return {"ok": True}


@router.post("/lot-aliases/replace", response_model=LotAliasListResponse, status_code=status.HTTP_200_OK)
def replace_lot_aliases(payload: LotAliasReplace, user=Depends(get_current_user)) -> LotAliasListResponse:
    urls = [u.strip() for u in payload.urls if u and u.strip()]
    _ensure_workspace(payload.workspace_id, int(user.id))
    alias_repo.replace_for_lot(
        user_id=int(user.id),
        workspace_id=int(payload.workspace_id),
        lot_number=payload.lot_number,
        urls=urls,
    )
    records = alias_repo.list_by_user(int(user.id), int(payload.workspace_id))
    filtered = [r for r in records if r.lot_number == payload.lot_number]
    return LotAliasListResponse(items=[_to_item(r) for r in filtered])
