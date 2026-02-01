from __future__ import annotations

from dataclasses import dataclass

import mysql.connector

from db.mysql import get_base_connection


def _normalize_owner(owner: str) -> str:
    return str(owner or "").strip().lower()


@dataclass
class BonusBalanceItem:
    id: int
    owner: str
    balance_minutes: int
    user_id: int
    workspace_id: int | None
    workspace_name: str | None
    updated_at: str | None


@dataclass
class BonusHistoryItem:
    id: int
    owner: str
    delta_minutes: int
    balance_minutes: int
    reason: str
    order_id: str | None
    account_id: int | None
    user_id: int
    workspace_id: int | None
    workspace_name: str | None
    created_at: str | None


class MySQLBonusRepo:
    def list_balances(
        self,
        user_id: int,
        workspace_id: int | None = None,
        *,
        query: str | None = None,
        limit: int = 200,
    ) -> list[BonusBalanceItem]:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list[object] = [int(user_id)]
            where = "WHERE bw.user_id = %s"
            if workspace_id is not None:
                where += " AND (bw.workspace_id = %s OR bw.workspace_id IS NULL)"
                params.append(int(workspace_id))
            if query:
                like = f"%{query.strip().lower()}%"
                where += " AND LOWER(bw.owner) LIKE %s"
                params.append(like)
            cursor.execute(
                f"""
                SELECT bw.id, bw.owner, bw.balance_minutes, bw.user_id, bw.workspace_id,
                       w.name AS workspace_name, bw.updated_at
                FROM bonus_wallet bw
                LEFT JOIN workspaces w ON w.id = bw.workspace_id AND w.user_id = bw.user_id
                {where}
                ORDER BY bw.balance_minutes DESC, bw.updated_at DESC
                LIMIT %s
                """,
                tuple(params + [int(max(1, min(limit, 500)))]),
            )
            rows = cursor.fetchall() or []
            return [
                BonusBalanceItem(
                    id=int(row["id"]),
                    owner=row.get("owner") or "",
                    balance_minutes=int(row.get("balance_minutes") or 0),
                    user_id=int(row.get("user_id") or user_id),
                    workspace_id=row.get("workspace_id"),
                    workspace_name=row.get("workspace_name"),
                    updated_at=str(row.get("updated_at")) if row.get("updated_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def list_history(
        self,
        user_id: int,
        owner: str,
        workspace_id: int | None = None,
        *,
        limit: int = 200,
    ) -> list[BonusHistoryItem]:
        owner_key = _normalize_owner(owner)
        if not owner_key:
            return []
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list[object] = [int(user_id), owner_key]
            where = "WHERE bh.user_id = %s AND bh.owner = %s"
            if workspace_id is not None:
                where += " AND (bh.workspace_id = %s OR bh.workspace_id IS NULL)"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT bh.id, bh.owner, bh.delta_minutes, bh.balance_minutes, bh.reason,
                       bh.order_id, bh.account_id, bh.user_id, bh.workspace_id,
                       w.name AS workspace_name, bh.created_at
                FROM bonus_history bh
                LEFT JOIN workspaces w ON w.id = bh.workspace_id AND w.user_id = bh.user_id
                {where}
                ORDER BY bh.id DESC
                LIMIT %s
                """,
                tuple(params + [int(max(1, min(limit, 500)))]),
            )
            rows = cursor.fetchall() or []
            return [
                BonusHistoryItem(
                    id=int(row["id"]),
                    owner=row.get("owner") or "",
                    delta_minutes=int(row.get("delta_minutes") or 0),
                    balance_minutes=int(row.get("balance_minutes") or 0),
                    reason=row.get("reason") or "",
                    order_id=row.get("order_id"),
                    account_id=row.get("account_id"),
                    user_id=int(row.get("user_id") or user_id),
                    workspace_id=row.get("workspace_id"),
                    workspace_name=row.get("workspace_name"),
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def adjust_balance(
        self,
        user_id: int,
        owner: str,
        delta_minutes: int,
        *,
        workspace_id: int | None,
        reason: str,
        order_id: str | None = None,
        account_id: int | None = None,
    ) -> tuple[int, int]:
        owner_key = _normalize_owner(owner)
        if not owner_key:
            return 0, 0
        conn = get_base_connection()
        try:
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
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
            current = int(row.get("balance_minutes") or 0) if row else 0
            new_balance = max(0, current + int(delta_minutes))
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
            applied_delta = int(new_balance - current)
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
                    int(applied_delta),
                    int(new_balance),
                    str(reason or "manual")[:64],
                    order_id.strip() if isinstance(order_id, str) and order_id.strip() else None,
                    int(account_id) if account_id is not None else None,
                ),
            )
            conn.commit()
            return int(new_balance), int(applied_delta)
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

