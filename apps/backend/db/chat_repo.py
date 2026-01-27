from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import mysql.connector

from db.mysql import get_base_connection


@dataclass
class ChatSummary:
    id: int
    chat_id: int
    name: Optional[str]
    last_message_text: Optional[str]
    last_message_time: Optional[str]
    unread: int
    user_id: int
    workspace_id: Optional[int]


@dataclass
class ChatMessage:
    id: int
    message_id: int
    chat_id: int
    author: Optional[str]
    text: Optional[str]
    sent_time: Optional[str]
    by_bot: int
    message_type: Optional[str]
    user_id: int
    workspace_id: Optional[int]


class MySQLChatRepo:
    def _get_conn(self) -> mysql.connector.MySQLConnection:
        return get_base_connection()

    def list_chats(
        self,
        user_id: int,
        workspace_id: int,
        *,
        query: str | None = None,
        limit: int = 200,
    ) -> list[ChatSummary]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list = [int(user_id), int(workspace_id)]
            where = "WHERE user_id = %s AND workspace_id = %s"
            if query:
                q = f"%{query.strip().lower()}%"
                where += " AND (LOWER(name) LIKE %s OR LOWER(last_message_text) LIKE %s)"
                params.extend([q, q])
            cursor.execute(
                f"""
                SELECT id, chat_id, name, last_message_text, last_message_time, unread, user_id, workspace_id
                FROM chats
                {where}
                ORDER BY (unread IS NULL), unread DESC, last_message_time DESC, id DESC
                LIMIT %s
                """,
                tuple(params + [int(max(1, min(limit, 500)))]),
            )
            rows = cursor.fetchall() or []
            return [
                ChatSummary(
                    id=int(row["id"]),
                    chat_id=int(row["chat_id"]),
                    name=row.get("name"),
                    last_message_text=row.get("last_message_text"),
                    last_message_time=str(row.get("last_message_time")) if row.get("last_message_time") else None,
                    unread=int(row.get("unread") or 0),
                    user_id=int(row.get("user_id") or user_id),
                    workspace_id=row.get("workspace_id"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def list_messages(
        self,
        user_id: int,
        workspace_id: int,
        chat_id: int,
        *,
        limit: int = 200,
    ) -> list[ChatMessage]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, message_id, chat_id, author, text, sent_time, by_bot, message_type, user_id, workspace_id
                FROM chat_messages
                WHERE user_id = %s AND workspace_id = %s AND chat_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (int(user_id), int(workspace_id), int(chat_id), int(max(1, min(limit, 500)))),
            )
            rows = cursor.fetchall() or []
            rows.reverse()
            return [
                ChatMessage(
                    id=int(row["id"]),
                    message_id=int(row.get("message_id") or 0),
                    chat_id=int(row.get("chat_id") or chat_id),
                    author=row.get("author"),
                    text=row.get("text"),
                    sent_time=str(row.get("sent_time")) if row.get("sent_time") else None,
                    by_bot=int(row.get("by_bot") or 0),
                    message_type=row.get("message_type"),
                    user_id=int(row.get("user_id") or user_id),
                    workspace_id=row.get("workspace_id"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def enqueue_outbox(
        self,
        *,
        user_id: int,
        workspace_id: int,
        chat_id: int,
        text: str,
    ) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_outbox (chat_id, text, user_id, workspace_id)
                VALUES (%s, %s, %s, %s)
                """,
                (int(chat_id), text, int(user_id), int(workspace_id)),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def mark_chat_read(self, user_id: int, workspace_id: int, chat_id: int) -> None:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE chats
                SET unread = 0
                WHERE user_id = %s AND workspace_id = %s AND chat_id = %s
                """,
                (int(user_id), int(workspace_id), int(chat_id)),
            )
            conn.commit()
        finally:
            conn.close()
