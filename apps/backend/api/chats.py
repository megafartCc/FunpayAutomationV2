from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.chat_repo import MySQLChatRepo
from db.workspace_repo import MySQLWorkspaceRepo
from services.chat_cache import ChatCache


router = APIRouter()
chat_repo = MySQLChatRepo()
workspace_repo = MySQLWorkspaceRepo()
chat_cache = ChatCache()


class ChatItem(BaseModel):
    id: int
    chat_id: int
    name: str | None = None
    last_message_text: str | None = None
    last_message_time: str | None = None
    unread: int = 0
    admin_unread_count: int = 0
    admin_requested: int = 0
    workspace_id: int | None = None


class ChatMessageItem(BaseModel):
    id: int
    message_id: int
    chat_id: int
    author: str | None = None
    text: str | None = None
    sent_time: str | None = None
    by_bot: int = 0
    message_type: str | None = None
    workspace_id: int | None = None


class ChatListResponse(BaseModel):
    items: list[ChatItem]


class ChatHistoryResponse(BaseModel):
    items: list[ChatMessageItem]


class ChatSendRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class ChatBadgesResponse(BaseModel):
    unread: int = 0
    admin_unread_count: int = 0


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="Select a workspace for chats.")
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for chats.")


def _parse_since(raw: str | None) -> datetime | None:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        pass
    try:
        ts = float(value)
    except Exception:
        return None
    if ts > 1_000_000_000_000:
        ts = ts / 1000.0
    return datetime.utcfromtimestamp(ts)




@router.get("/chats/badges", response_model=ChatBadgesResponse)
def chat_badges(
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> ChatBadgesResponse:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    badges = chat_repo.get_badges(user_id, int(workspace_id))
    return ChatBadgesResponse(unread=badges.unread, admin_unread_count=badges.admin_unread_count)

@router.get("/chats", response_model=ChatListResponse)
def list_chats(
    workspace_id: int | None = None,
    query: str = "",
    since: str | None = None,
    limit: int = 200,
    user=Depends(get_current_user),
) -> ChatListResponse:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    since_dt = _parse_since(since)
    cached_items = None
    if since_dt is None:
        cached_items = chat_cache.get_list(user_id, workspace_id, query or None, limit)
    if cached_items is not None:
        return ChatListResponse(items=[ChatItem(**item) for item in cached_items])

    items = chat_repo.list_chats(
        user_id,
        int(workspace_id),
        query=query or None,
        since=since_dt,
        limit=limit,
    )
    response_items = [
        ChatItem(
            id=item.id,
            chat_id=item.chat_id,
            name=item.name,
            last_message_text=item.last_message_text,
            last_message_time=item.last_message_time,
            unread=item.unread,
            admin_unread_count=item.admin_unread_count,
            admin_requested=item.admin_requested,
            workspace_id=item.workspace_id,
        )
        for item in items
    ]
    if since_dt is None:
        chat_cache.set_list(
            user_id,
            workspace_id,
            query or None,
            limit,
            [item.model_dump() for item in response_items],
        )
    return ChatListResponse(
        items=response_items
    )


@router.get("/chats/{chat_id}/history", response_model=ChatHistoryResponse)
def chat_history(
    chat_id: int,
    workspace_id: int | None = None,
    limit: int = 200,
    after_id: int | None = None,
    user=Depends(get_current_user),
) -> ChatHistoryResponse:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    after_value = int(after_id) if after_id is not None and int(after_id) > 0 else None
    cached_items = chat_cache.get_history(user_id, workspace_id, int(chat_id), limit, after_value)
    if cached_items is not None:
        chat_repo.mark_chat_read(user_id, int(workspace_id), int(chat_id))
        chat_cache.clear_list(user_id, workspace_id)
        return ChatHistoryResponse(items=[ChatMessageItem(**item) for item in cached_items])

    items = chat_repo.list_messages(
        user_id,
        int(workspace_id),
        int(chat_id),
        limit=limit,
        after_id=after_value,
    )
    chat_repo.mark_chat_read(user_id, int(workspace_id), int(chat_id))
    response_items = [
        ChatMessageItem(
            id=item.id,
            message_id=item.message_id,
            chat_id=item.chat_id,
            author=item.author,
            text=item.text,
            sent_time=item.sent_time,
            by_bot=item.by_bot,
            message_type=item.message_type,
            workspace_id=item.workspace_id,
        )
        for item in items
    ]
    chat_cache.set_history(
        user_id,
        workspace_id,
        int(chat_id),
        limit,
        after_value,
        [item.model_dump() for item in response_items],
    )
    if after_value is None:
        chat_cache.clear_list(user_id, workspace_id)
    return ChatHistoryResponse(
        items=response_items
    )


@router.post("/chats/{chat_id}/send")
def chat_send(
    chat_id: int,
    payload: ChatSendRequest,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    message_id = chat_repo.enqueue_outbox(
        user_id=user_id,
        workspace_id=int(workspace_id),
        chat_id=int(chat_id),
        text=payload.text.strip(),
    )
    chat_cache.clear_history(user_id, workspace_id, int(chat_id))
    chat_cache.clear_list(user_id, workspace_id)
    return {"ok": True, "queued_id": message_id}
