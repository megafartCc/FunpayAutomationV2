from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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
    created_at: str | None = None


@router.get("/orders/resolve", response_model=OrderResolveResponse)
def resolve_order(
    order_id: str = Field(..., min_length=1, max_length=64),
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> OrderResolveResponse:
    user_id = int(user.id)
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="workspace_id is required")
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
        created_at=item.created_at,
    )
