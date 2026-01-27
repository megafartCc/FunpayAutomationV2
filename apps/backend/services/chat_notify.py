from __future__ import annotations

from db.chat_repo import MySQLChatRepo


def notify_owner(
    *,
    user_id: int,
    workspace_id: int,
    owner: str | None,
    text: str | None,
) -> bool:
    owner_key = (owner or "").strip()
    message = (text or "").strip()
    if not owner_key or not message:
        return False
    repo = MySQLChatRepo()
    chat_id = repo.find_chat_id_by_name(int(user_id), int(workspace_id), owner_key)
    if not chat_id:
        return False
    repo.enqueue_outbox(
        user_id=int(user_id),
        workspace_id=int(workspace_id),
        chat_id=int(chat_id),
        text=message,
    )
    return True
