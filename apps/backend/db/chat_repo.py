from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[ChatSummary]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            join_params: list = [int(user_id), int(workspace_id)]
            params: list = [int(user_id), int(workspace_id)]
            time_expr = "c.last_message_time"
            join_sql = """
                LEFT JOIN (
                    SELECT chat_id, MAX(sent_time) AS last_sent_time
                    FROM chat_messages
                    WHERE user_id = %s AND workspace_id = %s
                    GROUP BY chat_id
                ) m ON m.chat_id = c.chat_id
            """
            time_expr = "COALESCE(m.last_sent_time, c.last_message_time)"
            where = "WHERE c.user_id = %s AND c.workspace_id = %s"
            if query:
                q = f"%{query.strip().lower()}%"
                where += " AND (LOWER(c.name) LIKE %s OR LOWER(c.last_message_text) LIKE %s)"
                params.extend([q, q])
            elif since is not None:
                where += f" AND {time_expr} >= %s"
                params.append(since)
            cursor.execute(
                f"""
                SELECT c.id, c.chat_id, c.name, c.last_message_text, {time_expr} AS last_message_time,
                       c.unread, c.user_id, c.workspace_id
                FROM chats c
                {join_sql}
                {where}
                ORDER BY (c.unread IS NULL), c.unread DESC, {time_expr} DESC, c.id DESC
                LIMIT %s
                """,
                tuple(join_params + params + [int(max(1, min(limit, 500)))]),
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
        after_id: int | None = None,
    ) -> list[ChatMessage]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            where = "WHERE user_id = %s AND workspace_id = %s AND chat_id = %s"
            params: list = [int(user_id), int(workspace_id), int(chat_id)]
            after_value = int(after_id) if after_id is not None and int(after_id) > 0 else None
            order_clause = "ORDER BY id DESC"
            if after_value is not None:
                where += " AND id > %s"
                params.append(after_value)
                order_clause = "ORDER BY id ASC"
            cursor.execute(
                f"""
                SELECT id, message_id, chat_id, author, text, sent_time, by_bot, message_type, user_id, workspace_id
                FROM chat_messages
                {where}
                {order_clause}
                LIMIT %s
                """,
                tuple(params + [int(max(1, min(limit, 500)))]),
            )
            rows = cursor.fetchall() or []
            if after_value is None:
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
