from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.account_repo import MySQLAccountRepo
from db.lot_repo import MySQLLotRepo, LotRecord, LotCreateError
from db.workspace_repo import MySQLWorkspaceRepo
from services.funpay_lot_title import maybe_update_funpay_lot_title
from services.funpay_lot_price import get_funpay_lot_snapshot, edit_funpay_lot, update_funpay_lot_price


router = APIRouter()
lots_repo = MySQLLotRepo()
workspace_repo = MySQLWorkspaceRepo()
accounts_repo = MySQLAccountRepo()
logger = logging.getLogger("backend.lots")


class LotCreate(BaseModel):
    workspace_id: int = Field(..., ge=1, description="Workspace that owns this lot")
    lot_number: int = Field(..., ge=1)
    account_id: int = Field(..., ge=1)
    lot_url: str = Field(..., min_length=5)


class LotItem(BaseModel):
    lot_number: int
    account_id: int
    account_name: str
    display_name: str | None = None
    lot_url: str | None = None
    workspace_id: int


class LotListResponse(BaseModel):
    items: list[LotItem]


class LotSyncResponse(BaseModel):
    ok: bool
    updated: bool


class LotBulkSyncResponse(BaseModel):
    ok: bool
    total: int
    updated: int
    skipped: int
    failed: int


class FunPayLotDetails(BaseModel):
    lot_number: int
    title: str
    description: str
    price: float | None
    active: bool


class FunPayLotUpdatePayload(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    price: float | None = Field(None, ge=0)
    active: bool | None = None


class FunPayLotManualPricePayload(BaseModel):
    lot_number: int = Field(..., ge=1)
    price: float = Field(..., ge=0)


class FunPayLotManualPriceResponse(BaseModel):
    ok: bool
    changed: bool
    old_price: float | None = None


def _get_workspace_and_record(user_id: int, workspace_id: int | None, lot_number: int):
    _ensure_workspace(workspace_id, int(user_id))
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not workspace.golden_key:
        raise HTTPException(status_code=400, detail="Workspace golden_key is required")
    record = lots_repo.get_by_number(int(user_id), int(workspace_id), int(lot_number))
    if not record:
        raise HTTPException(status_code=404, detail="Lot not found")
    return workspace, record


def _to_item(record: LotRecord) -> LotItem:
    return LotItem(
        lot_number=record.lot_number,
        account_id=record.account_id,
        account_name=record.display_name or record.account_name,
        display_name=record.display_name,
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
    workspace = workspace_repo.get_by_id(int(payload.workspace_id), int(user.id))
    try:
        created = lots_repo.create(
            user_id=int(user.id),
            workspace_id=int(payload.workspace_id),
            lot_number=payload.lot_number,
            account_id=payload.account_id,
            lot_url=payload.lot_url.strip(),
            display_name=None,
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
    if workspace:
        try:
            account = accounts_repo.get_by_id(int(payload.account_id), int(user.id))
            maybe_update_funpay_lot_title(
                workspace=workspace,
                account=account,
                lot_url=created.lot_url,
            )
        except Exception as exc:
            logger.warning("Lot title update failed: %s", exc)
    return _to_item(created)


@router.delete("/lots/{lot_number}", status_code=status.HTTP_200_OK)
def delete_lot(lot_number: int, workspace_id: int | None = None, user=Depends(get_current_user)) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    ok = lots_repo.delete(int(user.id), int(lot_number), int(workspace_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Lot not found")
    return {"ok": True}


class LotUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    lot_url: str | None = Field(None, min_length=5)


@router.patch("/lots/{lot_number}", response_model=LotItem)
def update_lot(
    lot_number: int,
    payload: LotUpdate,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> LotItem:
    _ensure_workspace(workspace_id, int(user.id))
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
    updated = lots_repo.update(
        user_id=int(user.id),
        workspace_id=int(workspace_id),
        lot_number=int(lot_number),
        display_name=payload.display_name if payload.display_name is not None else None,
        lot_url=payload.lot_url if payload.lot_url is not None else None,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Lot not found")
    if payload.lot_url is not None and workspace:
        try:
            account = accounts_repo.get_by_id(int(updated.account_id), int(user.id))
            maybe_update_funpay_lot_title(
                workspace=workspace,
                account=account,
                lot_url=updated.lot_url,
            )
        except Exception as exc:
            logger.warning("Lot title update failed: %s", exc)
    return _to_item(updated)


@router.post("/lots/{lot_number}/sync-title", response_model=LotSyncResponse)
def sync_lot_title(
    lot_number: int,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> LotSyncResponse:
    _ensure_workspace(workspace_id, int(user.id))
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    record = lots_repo.get_by_number(int(user.id), int(workspace_id), int(lot_number))
    if not record:
        raise HTTPException(status_code=404, detail="Lot not found")
    account = accounts_repo.get_by_id(int(record.account_id), int(user.id))
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    try:
        updated = maybe_update_funpay_lot_title(
            workspace=workspace,
            account=account,
            lot_url=record.lot_url,
        )
    except Exception as exc:
        logger.warning("Lot title update failed: %s", exc)
        updated = False
    return LotSyncResponse(ok=True, updated=bool(updated))


@router.post("/lots/sync-titles", response_model=LotBulkSyncResponse)
def sync_lot_titles(
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> LotBulkSyncResponse:
    _ensure_workspace(workspace_id, int(user.id))
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    records = lots_repo.list_by_user(int(user.id), int(workspace_id))
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    for record in records:
        account = accounts_repo.get_by_id(int(record.account_id), int(user.id))
        if not account:
            failed_count += 1
            continue
        try:
            updated = maybe_update_funpay_lot_title(
                workspace=workspace,
                account=account,
                lot_url=record.lot_url,
            )
        except Exception:
            updated = False
            failed_count += 1
        if updated:
            updated_count += 1
        else:
            skipped_count += 1
    return LotBulkSyncResponse(
        ok=True,
        total=len(records),
        updated=updated_count,
        skipped=skipped_count,
        failed=failed_count,
    )


@router.get("/lots/{lot_number}/funpay", response_model=FunPayLotDetails)
def get_funpay_lot(
    lot_number: int,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> FunPayLotDetails:
    workspace, _record = _get_workspace_and_record(int(user.id), workspace_id, int(lot_number))
    snapshot = get_funpay_lot_snapshot(
        golden_key=workspace.golden_key,
        proxy_url=workspace.proxy_url,
        lot_id=int(lot_number),
        user_agent=os.getenv("FUNPAY_USER_AGENT"),
    )
    if not snapshot:
        raise HTTPException(status_code=500, detail="FunPay API is unavailable")
    return FunPayLotDetails(
        lot_number=int(lot_number),
        title=snapshot.title,
        description=snapshot.description,
        price=snapshot.price,
        active=snapshot.active,
    )


@router.patch("/lots/{lot_number}/funpay", response_model=FunPayLotDetails)
def patch_funpay_lot(
    lot_number: int,
    payload: FunPayLotUpdatePayload,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> FunPayLotDetails:
    workspace, _record = _get_workspace_and_record(int(user.id), workspace_id, int(lot_number))
    if payload.title is None and payload.description is None and payload.price is None and payload.active is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    snapshot = edit_funpay_lot(
        golden_key=workspace.golden_key,
        proxy_url=workspace.proxy_url,
        lot_id=int(lot_number),
        title=payload.title,
        description=payload.description,
        price=payload.price,
        active=payload.active,
        user_agent=os.getenv("FUNPAY_USER_AGENT"),
    )
    if not snapshot:
        raise HTTPException(status_code=500, detail="FunPay API is unavailable")
    return FunPayLotDetails(
        lot_number=int(lot_number),
        title=snapshot.title,
        description=snapshot.description,
        price=snapshot.price,
        active=snapshot.active,
    )


@router.post("/lots/manual-auto-price", response_model=FunPayLotManualPriceResponse)
def manual_auto_price_lot(
    payload: FunPayLotManualPricePayload,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> FunPayLotManualPriceResponse:
    workspace, _record = _get_workspace_and_record(int(user.id), workspace_id, int(payload.lot_number))
    changed, old_price = update_funpay_lot_price(
        golden_key=workspace.golden_key,
        proxy_url=workspace.proxy_url,
        lot_id=int(payload.lot_number),
        price=float(payload.price),
        user_agent=os.getenv("FUNPAY_USER_AGENT"),
    )
    return FunPayLotManualPriceResponse(ok=True, changed=bool(changed), old_price=old_price)
