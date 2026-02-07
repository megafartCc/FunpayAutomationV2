from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from db.notifications_repo import MySQLNotificationsRepo
from services.funpay_refund import refund_order

from api.deps import get_current_user
from db.order_history_repo import MySQLOrderHistoryRepo
from db.workspace_repo import MySQLWorkspaceRepo
from db.account_repo import MySQLAccountRepo
from services.steam_service import deauthorize_sessions, SteamWorkerError


router = APIRouter()
orders_repo = MySQLOrderHistoryRepo()
workspace_repo = MySQLWorkspaceRepo()
notifications_repo = MySQLNotificationsRepo()
accounts_repo = MySQLAccountRepo()


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


class HeatmapCell(BaseModel):
    day: int
    hour: int
    count: int


class RentalsHeatmapResponse(BaseModel):
    items: list[HeatmapCell]
    max: int
    total: int
    days: int | None = None
    actions: list[str]


class OrderRefundRequest(BaseModel):
    order_id: str | None = None
    owner: str | None = None
    account_id: int | None = None
    workspace_id: int | None = None


class OrderRefundResponse(BaseModel):
    ok: bool
    order_id: str
    owner: str
    workspace_id: int | None = None
    message: str | None = None


def _resolve_workspace_for_refund(user_id: int, workspace_id: int | None):
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), user_id)
        if not workspace:
            raise HTTPException(status_code=400, detail="Select a workspace for refund.")
        return workspace
    workspaces = workspace_repo.list_by_user(user_id)
    if not workspaces:
        raise HTTPException(status_code=400, detail="No workspaces available for refund.")
    default_ws = next((ws for ws in workspaces if int(ws.is_default) == 1), None)
    return default_ws or workspaces[0]


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


@router.get("/orders/heatmap", response_model=RentalsHeatmapResponse)
def rentals_heatmap(
    days: int | None = 30,
    actions: str | None = "assign,replace_assign,extend",
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> RentalsHeatmapResponse:
    user_id = int(user.id)
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), user_id)
        if not workspace:
            raise HTTPException(status_code=400, detail="Select a workspace for heatmap.")
    action_list = [a.strip() for a in (actions or "").split(",") if a.strip()]
    rows = orders_repo.rentals_heatmap(
        user_id=user_id,
        workspace_id=workspace_id,
        days=int(days) if days is not None else None,
        actions=action_list,
    )
    items: list[HeatmapCell] = []
    total = 0
    max_count = 0
    for row in rows:
        try:
            dow = int(row.get("dow") or 0)
            hour = int(row.get("hour") or 0)
            count = int(row.get("count") or 0)
        except Exception:
            continue
        # MySQL DAYOFWEEK: 1=Sunday..7=Saturday. Convert to Monday=0..Sunday=6.
        day_index = (dow + 5) % 7
        items.append(HeatmapCell(day=day_index, hour=hour, count=count))
        total += count
        if count > max_count:
            max_count = count
    return RentalsHeatmapResponse(
        items=items,
        max=max_count,
        total=total,
        days=int(days) if days is not None else None,
        actions=action_list,
    )


@router.post("/orders/refund", response_model=OrderRefundResponse)
def refund_order_api(
    payload: OrderRefundRequest,
    user=Depends(get_current_user),
) -> OrderRefundResponse:
    user_id = int(user.id)
    order_record = None
    workspace_hint = payload.workspace_id

    if payload.order_id:
        order_record = orders_repo.resolve_order(payload.order_id, user_id, payload.workspace_id)
    if not order_record and (payload.owner or payload.account_id):
        order_record = orders_repo.latest_for_owner(
            owner=payload.owner,
            user_id=user_id,
            workspace_id=payload.workspace_id,
            account_id=payload.account_id,
        )
    if not order_record:
        raise HTTPException(status_code=404, detail="Order not found in history yet.")

    if order_record.action and str(order_record.action).lower().startswith("refund"):
        raise HTTPException(status_code=400, detail="Order already marked as refunded.")

    workspace_id = (
        payload.workspace_id
        if payload.workspace_id is not None
        else order_record.workspace_id
        if order_record.workspace_id is not None
        else None
    )
    workspace = _resolve_workspace_for_refund(user_id, workspace_id)
    if workspace.platform != "funpay":
        raise HTTPException(status_code=400, detail="Refunds are only available for FunPay workspaces.")
    if not workspace.golden_key:
        raise HTTPException(status_code=400, detail="Workspace credentials missing for refund.")

    try:
        refund_order(
            golden_key=workspace.golden_key,
            proxy_url=workspace.proxy_url,
            order_id=order_record.order_id,
        )
    except Exception as exc:
        notifications_repo.log_notification(
            event_type="refund_manual",
            status="failed",
            title="Refund failed",
            message=str(exc),
            owner=order_record.owner,
            account_name=order_record.account_name,
            account_id=order_record.account_id,
            order_id=order_record.order_id,
            user_id=user_id,
            workspace_id=workspace.id,
        )
        raise HTTPException(status_code=502, detail=f"Refund failed: {exc}") from exc

    if order_record.account_id:
        account_row = accounts_repo.get_by_id(int(order_record.account_id), user_id, workspace.id)
        mafile_json = account_row.get("mafile_json") if account_row else None
        if mafile_json:
            try:
                deauthorize_sessions(
                    steam_login=account_row.get("login") or account_row.get("account_name") or "",
                    steam_password=account_row.get("password") or "",
                    mafile_json=mafile_json,
                )
                notifications_repo.log_notification(
                    event_type="deauthorize",
                    status="ok",
                    title="Steam deauthorize on refund",
                    message="Steam sessions deauthorized after refund.",
                    owner=order_record.owner,
                    account_name=order_record.account_name,
                    account_id=order_record.account_id,
                    order_id=order_record.order_id,
                    user_id=user_id,
                    workspace_id=workspace.id,
                )
            except SteamWorkerError as exc:
                notifications_repo.log_notification(
                    event_type="deauthorize",
                    status="failed",
                    title="Steam deauthorize on refund",
                    message=f"Steam deauthorize after refund failed: {exc}",
                    owner=order_record.owner,
                    account_name=order_record.account_name,
                    account_id=order_record.account_id,
                    order_id=order_record.order_id,
                    user_id=user_id,
                    workspace_id=workspace.id,
                )

    orders_repo.insert_action(
        order_id=order_record.order_id,
        owner=order_record.owner,
        user_id=user_id,
        action="refund",
        workspace_id=workspace.id,
        account_id=order_record.account_id,
        account_name=order_record.account_name,
        steam_id=order_record.steam_id,
        rental_minutes=order_record.rental_minutes,
        lot_number=order_record.lot_number,
        amount=order_record.amount,
        price=order_record.price,
    )
    notifications_repo.log_notification(
        event_type="refund_manual",
        status="ok",
        title="Refund completed",
        message="Refund issued from admin panel.",
        owner=order_record.owner,
        account_name=order_record.account_name,
        account_id=order_record.account_id,
        order_id=order_record.order_id,
        user_id=user_id,
        workspace_id=workspace.id,
    )
    return OrderRefundResponse(
        ok=True,
        order_id=order_record.order_id,
        owner=order_record.owner,
        workspace_id=workspace.id,
        message="Refund requested.",
    )
