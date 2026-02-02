from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_current_user
from db.order_history_repo import MySQLOrderHistoryRepo
from db.workspace_repo import MySQLWorkspaceRepo
from services.funpay_refund import refund_order


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


class OrderRefundRequest(BaseModel):
    order_id: str
    workspace_id: int | None = None


class OrderRefundResponse(BaseModel):
    order_id: str
    ok: bool
    message: str | None = None


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


@router.post("/orders/refund", response_model=OrderRefundResponse)
def refund_order_request(
    payload: OrderRefundRequest,
    user=Depends(get_current_user),
) -> OrderRefundResponse:
    user_id = int(user.id)
    resolved = orders_repo.resolve_order(payload.order_id, user_id, payload.workspace_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Order not found in history yet.")
    resolved_workspace_id = payload.workspace_id or resolved.workspace_id
    if resolved_workspace_id is None:
        raise HTTPException(status_code=400, detail="Order workspace is required for refund.")
    workspace = workspace_repo.get_by_id(int(resolved_workspace_id), user_id)
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for refund.")
    if (workspace.platform or "funpay").lower() != "funpay":
        raise HTTPException(status_code=400, detail="Refund is supported only for FunPay workspaces.")
    if not workspace.golden_key:
        raise HTTPException(status_code=400, detail="Workspace golden_key is missing.")
    result = refund_order(
        golden_key=workspace.golden_key,
        order_id=resolved.order_id,
        proxy_url=workspace.proxy_url,
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message or "Refund failed.")
    return OrderRefundResponse(order_id=result.order_id, ok=True, message=result.message)
