from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.chat_repo import MySQLChatRepo
from db.workspace_repo import MySQLWorkspaceRepo


router = APIRouter()
chat_repo = MySQLChatRepo()
workspace_repo = MySQLWorkspaceRepo()


class ChatItem(BaseModel):
    id: int
    chat_id: int
    name: str | None = None
    last_message_text: str | None = None
    last_message_time: str | None = None
    unread: int = 0
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


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="Select a workspace for chats.")
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for chats.")


@router.get("/chats", response_model=ChatListResponse)
def list_chats(
    workspace_id: int | None = None,
    query: str = "",
    limit: int = 200,
    user=Depends(get_current_user),
) -> ChatListResponse:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    items = chat_repo.list_chats(user_id, int(workspace_id), query=query or None, limit=limit)
    return ChatListResponse(
        items=[
            ChatItem(
                id=item.id,
                chat_id=item.chat_id,
                name=item.name,
                last_message_text=item.last_message_text,
                last_message_time=item.last_message_time,
                unread=item.unread,
                workspace_id=item.workspace_id,
            )
            for item in items
        ]
    )


@router.get("/chats/{chat_id}/history", response_model=ChatHistoryResponse)
def chat_history(
    chat_id: int,
    workspace_id: int | None = None,
    limit: int = 200,
    user=Depends(get_current_user),
) -> ChatHistoryResponse:
    user_id = int(user.id)
    _ensure_workspace(workspace_id, user_id)
    items = chat_repo.list_messages(user_id, int(workspace_id), int(chat_id), limit=limit)
    chat_repo.mark_chat_read(user_id, int(workspace_id), int(chat_id))
    return ChatHistoryResponse(
        items=[
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
    return {"ok": True, "queued_id": message_id}
