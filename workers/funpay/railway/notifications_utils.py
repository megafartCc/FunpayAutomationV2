from __future__ import annotations

import mysql.connector

from .db_utils import resolve_workspace_mysql_cfg, table_exists
from .text_utils import normalize_owner_name


def log_notification_event(
    mysql_cfg: dict,
    *,
    event_type: str,
    status: str,
    title: str,
    user_id: int,
    workspace_id: int | None = None,
    message: str | None = None,
    owner: str | None = None,
    account_name: str | None = None,
    account_id: int | None = None,
    order_id: str | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "notification_logs"):
            return
        cursor.execute(
            """
            INSERT INTO notification_logs (
                event_type, status, title, message, owner, account_name,
                account_id, order_id, user_id, workspace_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_type,
                status,
                title,
                message,
                normalize_owner_name(owner) if owner else None,
                account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                int(account_id) if account_id is not None else None,
                order_id.strip() if isinstance(order_id, str) and order_id.strip() else None,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_workspace_status(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    platform: str,
    status: str,
    message: str | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "workspace_status"):
            return
        cursor.execute(
            """
            INSERT INTO workspace_status (user_id, workspace_id, platform, status, message)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                message = VALUES(message),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
                platform,
                status,
                message,
            ),
        )
        conn.commit()
    finally:
        conn.close()
