from __future__ import annotations

import mysql.connector

from .db_utils import resolve_workspace_mysql_cfg, table_exists
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
