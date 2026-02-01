from __future__ import annotations

import mysql.connector

from .db_utils import resolve_workspace_mysql_cfg, table_exists
from .text_utils import normalize_owner_name


def _safe_owner(owner: str | None) -> str | None:
    owner_key = normalize_owner_name(owner)
    return owner_key or None


def get_bonus_balance(
    mysql_cfg: dict,
    *,
    user_id: int,
    owner: str,
    workspace_id: int | None,
) -> int:
    owner_key = _safe_owner(owner)
    if not owner_key:
        return 0
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "bonus_wallet"):
            return 0
        cursor.execute(
            """
            SELECT balance_minutes
            FROM bonus_wallet
            WHERE user_id = %s AND workspace_id <=> %s AND owner = %s
            LIMIT 1
            """,
            (int(user_id), int(workspace_id) if workspace_id is not None else None, owner_key),
        )
        row = cursor.fetchone()
        if not row:
            return 0
        return int(row[0] or 0)
    finally:
        conn.close()


def has_bonus_event(
    mysql_cfg: dict,
    *,
    user_id: int,
    owner: str,
    order_id: str,
    reason: str,
    workspace_id: int | None,
) -> bool:
    owner_key = _safe_owner(owner)
    if not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "bonus_history"):
            return False
        cursor.execute(
            """
            SELECT 1
            FROM bonus_history
            WHERE user_id = %s AND workspace_id <=> %s AND owner = %s AND order_id = %s AND reason = %s
            LIMIT 1
            """,
            (
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
                owner_key,
                order_id.strip(),
                str(reason or "")[:64],
            ),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def adjust_bonus_balance(
    mysql_cfg: dict,
    *,
    user_id: int,
    owner: str,
    workspace_id: int | None,
    delta_minutes: int,
    reason: str,
    order_id: str | None = None,
    account_id: int | None = None,
) -> tuple[int, int]:
    owner_key = _safe_owner(owner)
    if not owner_key:
        return 0, 0
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        conn.start_transaction()
        cursor = conn.cursor()
        if not table_exists(cursor, "bonus_wallet"):
            conn.rollback()
            return 0, 0
        cursor.execute(
            """
            SELECT balance_minutes
            FROM bonus_wallet
            WHERE user_id = %s AND workspace_id <=> %s AND owner = %s
            LIMIT 1
            FOR UPDATE
            """,
            (int(user_id), int(workspace_id) if workspace_id is not None else None, owner_key),
        )
        row = cursor.fetchone()
        current = int(row[0] or 0) if row else 0
        new_balance = max(0, int(current) + int(delta_minutes))
        if row:
            cursor.execute(
                """
                UPDATE bonus_wallet
                SET balance_minutes = %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND workspace_id <=> %s AND owner = %s
                """,
                (
                    int(new_balance),
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    owner_key,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO bonus_wallet (user_id, workspace_id, owner, balance_minutes)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    owner_key,
                    int(new_balance),
                ),
            )
        applied = int(new_balance - current)
        if table_exists(cursor, "bonus_history"):
            cursor.execute(
                """
                INSERT INTO bonus_history (
                    user_id, workspace_id, owner, delta_minutes, balance_minutes, reason, order_id, account_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    owner_key,
                    int(applied),
                    int(new_balance),
                    str(reason or "manual")[:64],
                    order_id.strip() if isinstance(order_id, str) and order_id.strip() else None,
                    int(account_id) if account_id is not None else None,
                ),
            )
        conn.commit()
        return int(new_balance), int(applied)
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
