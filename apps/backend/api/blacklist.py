from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.blacklist_repo import MySQLBlacklistRepo
from db.order_history_repo import MySQLOrderHistoryRepo
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
blacklist_repo = MySQLBlacklistRepo()
workspace_repo = MySQLWorkspaceRepo()
orders_repo = MySQLOrderHistoryRepo()


class BlacklistEntryItem(BaseModel):
    id: int
    owner: str
    reason: str | None = None
    workspace_id: int | None = None
    created_at: str | None = None


class BlacklistLogItem(BaseModel):
    id: int
    owner: str
    action: str
    reason: str | None = None
    details: str | None = None
    amount: int | None = None
    workspace_id: int | None = None
    created_at: str | None = None


class BlacklistListResponse(BaseModel):
    items: list[BlacklistEntryItem]


class BlacklistLogsResponse(BaseModel):
    items: list[BlacklistLogItem]


class BlacklistCreate(BaseModel):
    owner: str | None = Field(None, min_length=1, max_length=255)
    reason: str | None = Field(None, max_length=500)
    order_id: str | None = Field(None, max_length=128)


class BlacklistUpdate(BaseModel):
    owner: str = Field(..., min_length=1, max_length=255)
    reason: str | None = Field(None, max_length=500)


class BlacklistRemove(BaseModel):
    owners: list[str] = Field(default_factory=list)


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        return
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for blacklist.")


@router.get("/blacklist", response_model=BlacklistListResponse)
def list_blacklist(
    query: str = "",
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> BlacklistListResponse:
    user_id = int(user.id)
    if workspace_id is not None:
        _ensure_workspace(workspace_id, user_id)
    items = blacklist_repo.list_blacklist(user_id, workspace_id, query=query or None)
    return BlacklistListResponse(
        items=[
            BlacklistEntryItem(
                id=entry.id,
                owner=entry.owner,
                reason=entry.reason,
                workspace_id=entry.workspace_id,
                created_at=entry.created_at,
            )
            for entry in items
        ]
    )


@router.get("/blacklist/logs", response_model=BlacklistLogsResponse)
def list_blacklist_logs(
    limit: int = 100,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> BlacklistLogsResponse:
    user_id = int(user.id)
    if workspace_id is not None:
        _ensure_workspace(workspace_id, user_id)
    items = blacklist_repo.list_blacklist_logs(user_id, workspace_id, limit=limit)
    return BlacklistLogsResponse(
        items=[
            BlacklistLogItem(
                id=item.id,
                owner=item.owner,
                action=item.action,
                reason=item.reason,
                details=item.details,
                amount=item.amount,
                workspace_id=item.workspace_id,
                created_at=item.created_at,
            )
            for item in items
        ]
    )


@router.post("/blacklist", response_model=BlacklistEntryItem)
def add_blacklist(
    payload: BlacklistCreate,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> BlacklistEntryItem:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    owner = (payload.owner or "").strip()
    resolved_workspace_id = None
    resolved_workspace_name = None
    if not owner and payload.order_id:
        resolved = orders_repo.resolve_order(payload.order_id, user_id, workspace_id)
        if resolved:
            owner = resolved.owner
            resolved_workspace_id = resolved.workspace_id
            resolved_workspace_name = resolved.workspace_name
    if not owner:
        raise HTTPException(status_code=400, detail="Owner is required.")
    ok = blacklist_repo.add_blacklist_entry(owner, payload.reason, user_id, workspace_id)
    if not ok:
        raise HTTPException(status_code=400, detail="User already blacklisted.")
    details_parts = []
    if payload.order_id:
        details_parts.append(f"order_id={payload.order_id}")
    if resolved_workspace_id is not None:
        details_parts.append(f"workspace_id={resolved_workspace_id}")
        if resolved_workspace_name:
            details_parts.append(f"workspace={resolved_workspace_name}")
    details_value = "; ".join(details_parts) if details_parts else None
    blacklist_repo.log_blacklist_event(
        owner,
        "add",
        reason=payload.reason,
        details=details_value,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    items = blacklist_repo.list_blacklist(user_id, workspace_id, query=owner)
    entry = items[0] if items else None
    if not entry:
        raise HTTPException(status_code=500, detail="Blacklist entry not found after creation.")
    return BlacklistEntryItem(
        id=entry.id,
        owner=entry.owner,
        reason=entry.reason,
        workspace_id=entry.workspace_id,
        created_at=entry.created_at,
    )


@router.patch("/blacklist/{entry_id}", response_model=BlacklistEntryItem)
def update_blacklist(
    entry_id: int,
    payload: BlacklistUpdate,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> BlacklistEntryItem:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    updated = blacklist_repo.update_blacklist_entry(entry_id, payload.owner, payload.reason, user_id, workspace_id)
    if not updated:
        raise HTTPException(status_code=400, detail="Failed to update blacklist entry.")
    blacklist_repo.log_blacklist_event(
        payload.owner,
        "update",
        reason=payload.reason,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    items = blacklist_repo.list_blacklist(user_id, workspace_id, query=payload.owner)
    entry = next((item for item in items if item.id == entry_id), items[0] if items else None)
    if not entry:
        raise HTTPException(status_code=404, detail="Blacklist entry not found.")
    return BlacklistEntryItem(
        id=entry.id,
        owner=entry.owner,
        reason=entry.reason,
        workspace_id=entry.workspace_id,
        created_at=entry.created_at,
    )


@router.post("/blacklist/remove")
def remove_blacklist(
    payload: BlacklistRemove,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    removed = blacklist_repo.remove_blacklist_entries(payload.owners or [], user_id, workspace_id)
    for owner in payload.owners or []:
        blacklist_repo.log_blacklist_event(owner, "remove", user_id=user_id, workspace_id=workspace_id)
    return {"removed": removed}


@router.post("/blacklist/clear")
def clear_blacklist(
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    removed = blacklist_repo.clear_blacklist(user_id, workspace_id)
    blacklist_repo.log_blacklist_event(
        "all",
        "clear_all",
        details=f"removed={removed}",
        user_id=user_id,
        workspace_id=workspace_id,
    )
    return {"removed": removed}
