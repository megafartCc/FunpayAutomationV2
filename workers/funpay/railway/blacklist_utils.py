from __future__ import annotations

import mysql.connector

from .db_utils import column_exists, resolve_workspace_mysql_cfg, table_exists
from .text_utils import normalize_owner_name


def is_blacklisted(
    mysql_cfg: dict,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
) -> bool:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist"):
            return False
        has_status = column_exists(cursor, "blacklist", "status")
        if has_status:
            cursor.execute(
                """
                SELECT 1 FROM blacklist
                WHERE owner = %s AND user_id = %s AND workspace_id <=> %s AND status = 'confirmed'
                LIMIT 1
                """,
                (owner_key, int(user_id), int(workspace_id) if workspace_id is not None else None),
            )
        else:
            cursor.execute(
                """
                SELECT 1 FROM blacklist
                WHERE owner = %s AND user_id = %s AND workspace_id <=> %s
                LIMIT 1
                """,
                (owner_key, int(user_id), int(workspace_id) if workspace_id is not None else None),
            )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def log_blacklist_event(
    mysql_cfg: dict,
    *,
    owner: str,
    action: str,
    reason: str | None = None,
    details: str | None = None,
    amount: int | None = None,
    user_id: int,
    workspace_id: int | None = None,
) -> None:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist_logs"):
            return
        cursor.execute(
            """
            INSERT INTO blacklist_logs (owner, action, reason, details, amount, user_id, workspace_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_key,
                action,
                reason,
                details,
                int(amount) if amount is not None else None,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_blacklist_suggestion(
    mysql_cfg: dict,
    *,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
    reason: str | None = None,
    details: str | None = None,
) -> bool:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist"):
            return False
        if not column_exists(cursor, "blacklist", "status"):
            return False
        has_details = column_exists(cursor, "blacklist", "details")
        reason_value = reason.strip() if isinstance(reason, str) and reason.strip() else None
        details_value = details.strip() if isinstance(details, str) and details.strip() else None
        cursor.execute(
            """
            SELECT id, status FROM blacklist
            WHERE owner = %s AND user_id = %s AND workspace_id <=> %s
            LIMIT 1
            """,
            (owner_key, int(user_id), int(workspace_id) if workspace_id is not None else None),
        )
        row = cursor.fetchone()
        if row:
            current_status = row[1] if len(row) > 1 else None
            if current_status == "confirmed":
                return False
            if has_details:
                cursor.execute(
                    """
                    UPDATE blacklist
                    SET reason = %s, details = %s, status = 'pending', updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (reason_value, details_value, int(row[0])),
                )
            else:
                cursor.execute(
                    """
                    UPDATE blacklist
                    SET reason = %s, status = 'pending', updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (reason_value, int(row[0])),
                )
        else:
            if has_details:
                cursor.execute(
                    """
                    INSERT INTO blacklist (owner, reason, details, status, user_id, workspace_id)
                    VALUES (%s, %s, %s, 'pending', %s, %s)
                    """,
                    (
                        owner_key,
                        reason_value,
                        details_value,
                        int(user_id),
                        int(workspace_id) if workspace_id is not None else None,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO blacklist (owner, reason, status, user_id, workspace_id)
                    VALUES (%s, %s, 'pending', %s, %s)
                    """,
                    (
                        owner_key,
                        reason_value,
                        int(user_id),
                        int(workspace_id) if workspace_id is not None else None,
                    ),
                )
        conn.commit()
        return True
    finally:
        conn.close()


def get_blacklist_compensation_total(
    mysql_cfg: dict,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
) -> int:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return 0
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist_logs"):
            return 0
        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM blacklist_logs
            WHERE owner = %s AND user_id = %s AND action = 'blacklist_comp'
            """,
            (owner_key, int(user_id)),
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()


def remove_blacklist_entry(
    mysql_cfg: dict,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
) -> bool:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist"):
            return False
        cursor.execute(
            "DELETE FROM blacklist WHERE owner = %s AND user_id = %s",
            (owner_key, int(user_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
