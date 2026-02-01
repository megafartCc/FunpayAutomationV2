from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.bonus_repo import MySQLBonusRepo, BonusBalanceItem, BonusHistoryItem
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
bonus_repo = MySQLBonusRepo()
workspace_repo = MySQLWorkspaceRepo()


class BonusBalanceResponseItem(BaseModel):
    id: int
    owner: str
    balance_minutes: int
    workspace_id: int | None = None
    workspace_name: str | None = None
    updated_at: str | None = None


class BonusBalanceResponse(BaseModel):
    items: list[BonusBalanceResponseItem]


class BonusHistoryResponseItem(BaseModel):
    id: int
    owner: str
    delta_minutes: int
    balance_minutes: int
    reason: str
    order_id: str | None = None
    account_id: int | None = None
    workspace_id: int | None = None
    workspace_name: str | None = None
    created_at: str | None = None


class BonusHistoryResponse(BaseModel):
    items: list[BonusHistoryResponseItem]


class BonusAdjustRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=255)
    delta_minutes: int
    workspace_id: int | None = None
    reason: str | None = None
    order_id: str | None = None
    account_id: int | None = None


class BonusAdjustResponse(BaseModel):
    balance_minutes: int
    applied_delta: int


def _to_balance_item(record: BonusBalanceItem) -> BonusBalanceResponseItem:
    return BonusBalanceResponseItem(
        id=record.id,
        owner=record.owner,
        balance_minutes=record.balance_minutes,
        workspace_id=record.workspace_id,
        workspace_name=record.workspace_name,
        updated_at=record.updated_at,
    )


def _to_history_item(record: BonusHistoryItem) -> BonusHistoryResponseItem:
    return BonusHistoryResponseItem(
        id=record.id,
        owner=record.owner,
        delta_minutes=record.delta_minutes,
        balance_minutes=record.balance_minutes,
        reason=record.reason,
        order_id=record.order_id,
        account_id=record.account_id,
        workspace_id=record.workspace_id,
        workspace_name=record.workspace_name,
        created_at=record.created_at,
    )


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        return
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace.")


@router.get("/bonus/balances", response_model=BonusBalanceResponse)
def list_bonus_balances(
    query: str = "",
    limit: int = 200,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> BonusBalanceResponse:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    items = bonus_repo.list_balances(user_id, workspace_id, query=query or None, limit=limit)
    return BonusBalanceResponse(items=[_to_balance_item(item) for item in items])


@router.get("/bonus/history", response_model=BonusHistoryResponse)
def list_bonus_history(
    owner: str,
    limit: int = 200,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> BonusHistoryResponse:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    items = bonus_repo.list_history(user_id, owner, workspace_id, limit=limit)
    return BonusHistoryResponse(items=[_to_history_item(item) for item in items])


@router.post("/bonus/adjust", response_model=BonusAdjustResponse)
def adjust_bonus_balance(payload: BonusAdjustRequest, user=Depends(get_current_user)) -> BonusAdjustResponse:
    user_id = int(user.id)
    if payload.delta_minutes == 0:
        raise HTTPException(status_code=400, detail="Delta must be non-zero.")
    _ensure_workspace(payload.workspace_id, user_id)
    balance, applied = bonus_repo.adjust_balance(
        user_id,
        payload.owner,
        int(payload.delta_minutes),
        workspace_id=payload.workspace_id,
        reason=payload.reason or "manual",
        order_id=payload.order_id,
        account_id=payload.account_id,
    )
    return BonusAdjustResponse(balance_minutes=balance, applied_delta=applied)

