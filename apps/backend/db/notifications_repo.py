from __future__ import annotations

from dataclasses import dataclass

import mysql.connector

from db.mysql import get_base_connection


@dataclass
class NotificationLog:
    id: int
    event_type: str
    status: str
    title: str
    message: str | None
    owner: str | None
    account_name: str | None
    account_id: int | None
    order_id: str | None
    user_id: int
    workspace_id: int | None
    workspace_name: str | None
    created_at: str | None


class MySQLNotificationsRepo:
    def list_notifications(
        self,
        user_id: int,
        workspace_id: int | None,
        limit: int = 200,
    ) -> list[NotificationLog]:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list[object] = [user_id]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND n.workspace_id = %s"
                params.append(workspace_id)
            cursor.execute(
                f"""
                SELECT n.id, n.event_type, n.status, n.title, n.message, n.owner, n.account_name, n.account_id,
                       n.order_id, n.user_id, n.workspace_id, n.created_at,
                       w.name AS workspace_name
                FROM notification_logs n
                LEFT JOIN workspaces w ON w.id = n.workspace_id AND w.user_id = n.user_id
                WHERE n.user_id = %s{workspace_clause}
                ORDER BY n.created_at DESC
                LIMIT %s
                """,
                (*params, int(limit)),
            )
            rows = cursor.fetchall() or []
            return [
                NotificationLog(
                    id=int(row["id"]),
                    event_type=row["event_type"],
                    status=row["status"],
                    title=row["title"],
                    message=row.get("message"),
                    owner=row.get("owner"),
                    account_name=row.get("account_name"),
                    account_id=int(row["account_id"]) if row.get("account_id") is not None else None,
                    order_id=row.get("order_id"),
                    user_id=int(row["user_id"]),
                    workspace_id=int(row["workspace_id"]) if row.get("workspace_id") is not None else None,
                    workspace_name=row.get("workspace_name"),
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def log_notification(
        self,
        *,
        event_type: str,
        status: str,
        title: str,
        user_id: int,
        message: str | None = None,
        owner: str | None = None,
        account_name: str | None = None,
        account_id: int | None = None,
        order_id: str | None = None,
        workspace_id: int | None = None,
    ) -> None:
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO notification_logs (
                    event_type, status, title, message, owner, account_name, account_id,
                    order_id, user_id, workspace_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_type,
                    status,
                    title,
                    message,
                    owner,
                    account_name,
                    account_id,
                    order_id,
                    user_id,
                    workspace_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
