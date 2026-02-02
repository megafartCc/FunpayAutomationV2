from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_current_user
from db.order_history_repo import MySQLOrderHistoryRepo
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
orders_repo = MySQLOrderHistoryRepo()
workspace_repo = MySQLWorkspaceRepo()


class OrderResolveResponse(BaseModel):
    order_id: str
    owner: str
    lot_number: int | None = None
    account_name: str | None = None
    account_id: int | None = None
    amount: int | None = None
    workspace_id: int | None = None
    workspace_name: str | None = None
    created_at: str | None = None


class OrderHistoryItem(BaseModel):
    id: int
    order_id: str
    buyer: str
    account_name: str | None = None
    account_login: str | None = None
    account_id: int | None = None
    steam_id: str | None = None
    rental_minutes: int | None = None
    lot_number: int | None = None
    amount: int | None = None
    price: float | None = None
    action: str | None = None
    workspace_id: int | None = None
    workspace_name: str | None = None
    created_at: str | None = None


class OrdersHistoryResponse(BaseModel):
    items: list[OrderHistoryItem]


@router.get("/orders/resolve", response_model=OrderResolveResponse)
def resolve_order(
    order_id: str = Query(..., min_length=1, max_length=64),
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> OrderResolveResponse:
    user_id = int(user.id)
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), user_id)
        if not workspace:
            raise HTTPException(status_code=400, detail="Select a workspace for order lookup.")
    item = orders_repo.resolve_order(order_id, user_id, workspace_id)
    if not item or not item.owner:
        raise HTTPException(status_code=404, detail="Order not found in history yet.")
    return OrderResolveResponse(
        order_id=item.order_id,
        owner=item.owner,
        lot_number=item.lot_number,
        account_name=item.account_name,
        account_id=item.account_id,
        amount=item.amount,
        workspace_id=item.workspace_id,
        workspace_name=item.workspace_name,
        created_at=item.created_at,
    )


@router.get("/orders/history", response_model=OrdersHistoryResponse)
def orders_history(
    query: str = "",
    limit: int = 200,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> OrdersHistoryResponse:
    user_id = int(user.id)
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), user_id)
        if not workspace:
            raise HTTPException(status_code=400, detail="Select a workspace for order history.")
    items = orders_repo.list_history(user_id, workspace_id, query=query or None, limit=limit)
    return OrdersHistoryResponse(
        items=[
            OrderHistoryItem(
                id=item.id,
                order_id=item.order_id,
                buyer=item.owner,
                account_name=item.account_name,
                account_login=item.account_login,
                account_id=item.account_id,
                steam_id=item.steam_id,
                rental_minutes=item.rental_minutes,
                lot_number=item.lot_number,
                amount=item.amount,
                price=item.price,
                action=item.action,
                workspace_id=item.workspace_id,
                workspace_name=item.workspace_name,
                created_at=item.created_at,
            )
            for item in items
        ]
    )
