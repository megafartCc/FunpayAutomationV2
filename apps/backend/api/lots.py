from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.lot_repo import MySQLLotRepo, LotRecord, LotCreateError
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
lots_repo = MySQLLotRepo()
workspace_repo = MySQLWorkspaceRepo()


class LotCreate(BaseModel):
    workspace_id: int = Field(..., ge=1, description="Workspace that owns this lot")
    lot_number: int = Field(..., ge=1)
    account_id: int = Field(..., ge=1)
    lot_url: str = Field(..., min_length=5)


class LotItem(BaseModel):
    lot_number: int
    account_id: int
    account_name: str
    lot_url: str | None = None
    workspace_id: int


class LotListResponse(BaseModel):
    items: list[LotItem]


def _to_item(record: LotRecord) -> LotItem:
    return LotItem(
        lot_number=record.lot_number,
        account_id=record.account_id,
        account_name=record.account_name,
        lot_url=record.lot_url,
        workspace_id=record.workspace_id,
    )


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for this lot.")


@router.get("/lots", response_model=LotListResponse)
def list_lots(workspace_id: int | None = None, user=Depends(get_current_user)) -> LotListResponse:
    _ensure_workspace(workspace_id, int(user.id))
    items = lots_repo.list_by_user(int(user.id), int(workspace_id))
    return LotListResponse(items=[_to_item(item) for item in items])


@router.post("/lots", response_model=LotItem, status_code=status.HTTP_201_CREATED)
def create_lot(payload: LotCreate, user=Depends(get_current_user)) -> LotItem:
    if not payload.lot_url.strip():
        raise HTTPException(status_code=400, detail="Lot URL is required")
    _ensure_workspace(payload.workspace_id, int(user.id))
    try:
        created = lots_repo.create(
            user_id=int(user.id),
            workspace_id=int(payload.workspace_id),
            lot_number=payload.lot_number,
            account_id=payload.account_id,
            lot_url=payload.lot_url.strip(),
        )
    except LotCreateError as exc:
        if exc.code == "account_not_found":
            detail = "Account not found"
        elif exc.code == "duplicate_lot_number":
            detail = "Lot number already exists in this workspace"
        elif exc.code == "account_already_mapped":
            detail = "This account already has a lot in this workspace"
        elif exc.code == "duplicate":
            detail = "Database schema mismatch: conflicting UNIQUE index on lots table."
        else:
            detail = "Failed to create lot"
        raise HTTPException(status_code=400, detail=detail)
    return _to_item(created)


@router.delete("/lots/{lot_number}", status_code=status.HTTP_200_OK)
def delete_lot(lot_number: int, workspace_id: int | None = None, user=Depends(get_current_user)) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    ok = lots_repo.delete(int(user.id), int(lot_number), int(workspace_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Lot not found")
    return {"ok": True}
