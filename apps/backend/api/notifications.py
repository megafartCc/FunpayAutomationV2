from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.auth import get_current_user
from db.notifications_repo import MySQLNotificationsRepo

router = APIRouter()
notifications_repo = MySQLNotificationsRepo()


class NotificationItem(BaseModel):
    id: int
    event_type: str
    status: Literal["ok", "failed", "warning", "info"] | str
    title: str
    message: str | None = None
    owner: str | None = None
    account_name: str | None = None
    account_id: int | None = None
    order_id: str | None = None
    workspace_id: int | None = None
    workspace_name: str | None = None
    created_at: str | None = None


class NotificationsResponse(BaseModel):
    items: list[NotificationItem]


@router.get("/notifications", response_model=NotificationsResponse)
def list_notifications(
    workspace_id: int | None = None,
    limit: int = Query(200, ge=1, le=500),
    user=Depends(get_current_user),
) -> NotificationsResponse:
    items = notifications_repo.list_notifications(int(user.id), workspace_id, limit=limit)
    return NotificationsResponse(items=[NotificationItem(**item.__dict__) for item in items])
