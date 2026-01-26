from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import mysql.connector

from db.mysql import get_base_connection


@dataclass
class OrderHistoryItem:
    id: int
    order_id: str
    owner: str
    account_name: Optional[str]
    account_id: Optional[int]
    rental_minutes: Optional[int]
    lot_number: Optional[int]
    amount: Optional[int]
    user_id: int
    workspace_id: Optional[int]
    created_at: Optional[str]


class MySQLOrderHistoryRepo:
    def _get_conn(self) -> mysql.connector.MySQLConnection:
        return get_base_connection()

    @staticmethod
    def _normalize_order_id(order_id: str) -> str:
        value = str(order_id or "").strip()
        if value.startswith("#"):
            value = value[1:]
        return value

    def resolve_order(
        self,
        order_id: str,
        user_id: int,
        workspace_id: int | None = None,
    ) -> OrderHistoryItem | None:
        order_key = self._normalize_order_id(order_id)
        if not order_key:
            return None
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list = [int(user_id), order_key]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND (workspace_id = %s OR workspace_id IS NULL)"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT id, order_id, owner, account_name, account_id, rental_minutes, lot_number,
                       amount, user_id, workspace_id, created_at
                FROM order_history
                WHERE user_id = %s AND order_id = %s{workspace_clause}
                ORDER BY id DESC
                LIMIT 1
                """,
                tuple(params),
            )
            row = cursor.fetchone()
            if not row:
                like_key = f"%{order_key}%"
                params = [int(user_id), like_key]
                workspace_clause = ""
                if workspace_id is not None:
                    workspace_clause = " AND (workspace_id = %s OR workspace_id IS NULL)"
                    params.append(int(workspace_id))
                cursor.execute(
                    f"""
                    SELECT id, order_id, owner, account_name, account_id, rental_minutes, lot_number,
                           amount, user_id, workspace_id, created_at
                    FROM order_history
                    WHERE user_id = %s AND order_id LIKE %s{workspace_clause}
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    tuple(params),
                )
                row = cursor.fetchone()
            if not row:
                return None
            return OrderHistoryItem(
                id=int(row["id"]),
                order_id=str(row.get("order_id") or order_key),
                owner=row.get("owner") or "",
                account_name=row.get("account_name"),
                account_id=row.get("account_id"),
                rental_minutes=row.get("rental_minutes"),
                lot_number=row.get("lot_number"),
                amount=row.get("amount"),
                user_id=int(row.get("user_id") or user_id),
                workspace_id=row.get("workspace_id"),
                created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
            )
        finally:
            conn.close()
