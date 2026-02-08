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
    account_login: Optional[str]
    account_id: Optional[int]
    steam_id: Optional[str]
    rental_minutes: Optional[int]
    lot_number: Optional[int]
    amount: Optional[int]
    price: Optional[float]
    refund_amount: Optional[float]
    action: Optional[str]
    user_id: int
    workspace_id: Optional[int]
    workspace_name: Optional[str]
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

    @staticmethod
    def _normalize_owner(owner: str | None) -> str:
        return (owner or "").strip().lower()

    @staticmethod
    def _column_exists(cursor: mysql.connector.cursor.MySQLCursor, column: str) -> bool:
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'order_history' AND column_name = %s
            LIMIT 1
            """,
            (column,),
        )
        return cursor.fetchone() is not None

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
            has_refund_amount = self._column_exists(cursor, "refund_amount")
            params: list = [int(user_id), order_key]
            refund_select = "oh.refund_amount" if has_refund_amount else "NULL AS refund_amount"
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND (workspace_id = %s OR workspace_id IS NULL)"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT oh.id, oh.order_id, oh.owner, oh.account_name, a.login AS account_login, oh.account_id, oh.steam_id,
                       oh.rental_minutes, oh.lot_number, oh.amount, oh.price, {refund_select}, oh.action,
                       oh.user_id, oh.workspace_id, w.name AS workspace_name, oh.created_at
                FROM order_history oh
                LEFT JOIN workspaces w ON w.id = oh.workspace_id AND w.user_id = oh.user_id
                LEFT JOIN accounts a ON a.id = oh.account_id AND a.user_id = oh.user_id
                WHERE oh.user_id = %s AND oh.order_id = %s{workspace_clause}
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
                    SELECT oh.id, oh.order_id, oh.owner, oh.account_name, a.login AS account_login, oh.account_id, oh.steam_id,
                           oh.rental_minutes, oh.lot_number, oh.amount, oh.price, {refund_select}, oh.action,
                           oh.user_id, oh.workspace_id, w.name AS workspace_name, oh.created_at
                    FROM order_history oh
                    LEFT JOIN workspaces w ON w.id = oh.workspace_id AND w.user_id = oh.user_id
                    LEFT JOIN accounts a ON a.id = oh.account_id AND a.user_id = oh.user_id
                    WHERE oh.user_id = %s AND oh.order_id LIKE %s{workspace_clause}
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
                account_login=row.get("account_login"),
                account_id=row.get("account_id"),
                steam_id=row.get("steam_id"),
                rental_minutes=row.get("rental_minutes"),
                lot_number=row.get("lot_number"),
                amount=row.get("amount"),
                price=row.get("price"),
                refund_amount=row.get("refund_amount"),
                action=row.get("action"),
                user_id=int(row.get("user_id") or user_id),
                workspace_id=row.get("workspace_id"),
                workspace_name=row.get("workspace_name"),
                created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
            )
        finally:
            conn.close()

    def rentals_heatmap(
        self,
        *,
        user_id: int,
        workspace_id: int | None = None,
        days: int | None = None,
        actions: list[str] | None = None,
    ) -> list[dict]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            has_refund_amount = self._column_exists(cursor, "refund_amount")
            refund_select = "oh.refund_amount" if has_refund_amount else "NULL AS refund_amount"
            params: list = [int(user_id)]
            where = ["user_id = %s"]
            if workspace_id is not None:
                where.append("(workspace_id = %s OR workspace_id IS NULL)")
                params.append(int(workspace_id))
            if days and int(days) > 0:
                where.append("created_at >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s DAY)")
                params.append(int(days))
            action_list = [str(a).strip() for a in (actions or []) if str(a).strip()]
            if action_list:
                placeholders = ", ".join(["%s"] * len(action_list))
                where.append(f"action IN ({placeholders})")
                params.extend(action_list)
            cursor.execute(
                f"""
                SELECT DAYOFWEEK(created_at) AS dow,
                       HOUR(created_at) AS hour,
                       COUNT(*) AS count
                FROM order_history
                WHERE {' AND '.join(where)}
                GROUP BY dow, hour
                """,
                tuple(params),
            )
            return list(cursor.fetchall() or [])
        finally:
            conn.close()

    def list_history(
        self,
        user_id: int,
        workspace_id: int | None = None,
        *,
        query: str | None = None,
        limit: int = 200,
    ) -> list[OrderHistoryItem]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            has_refund_amount = self._column_exists(cursor, "refund_amount")
            refund_select = "oh.refund_amount" if has_refund_amount else "NULL AS refund_amount"
            params: list = [int(user_id)]
            where = "WHERE oh.user_id = %s"
            if workspace_id is not None:
                where += " AND (oh.workspace_id = %s OR oh.workspace_id IS NULL)"
                params.append(int(workspace_id))
            if query:
                q = query.strip().lower()
                like = f"%{q}%"
                where += (
                    " AND (LOWER(oh.order_id) LIKE %s OR LOWER(oh.owner) LIKE %s OR "
                    "LOWER(oh.account_name) LIKE %s OR LOWER(a.login) LIKE %s OR LOWER(oh.steam_id) LIKE %s OR "
                    "CAST(oh.account_id AS CHAR) LIKE %s OR CAST(oh.lot_number AS CHAR) LIKE %s)"
                )
                params.extend([like, like, like, like, like, like, like])
            cursor.execute(
                f"""
                SELECT oh.id, oh.order_id, oh.owner, oh.account_name, a.login AS account_login, oh.account_id, oh.steam_id,
                       oh.rental_minutes, oh.lot_number, oh.amount, oh.price, {refund_select}, oh.action,
                       oh.user_id, oh.workspace_id, w.name AS workspace_name, oh.created_at
                FROM order_history oh
                LEFT JOIN workspaces w ON w.id = oh.workspace_id AND w.user_id = oh.user_id
                LEFT JOIN accounts a ON a.id = oh.account_id AND a.user_id = oh.user_id
                {where}
                ORDER BY oh.id DESC
                LIMIT %s
                """,
                tuple(params + [int(max(1, min(limit, 500)))]),
            )
            rows = cursor.fetchall() or []
            return [
                OrderHistoryItem(
                    id=int(row["id"]),
                    order_id=str(row.get("order_id") or ""),
                    owner=row.get("owner") or "",
                    account_name=row.get("account_name"),
                    account_login=row.get("account_login"),
                    account_id=row.get("account_id"),
                    steam_id=row.get("steam_id"),
                    rental_minutes=row.get("rental_minutes"),
                    lot_number=row.get("lot_number"),
                    amount=row.get("amount"),
                    price=row.get("price"),
                    refund_amount=row.get("refund_amount"),
                    action=row.get("action"),
                    user_id=int(row.get("user_id") or user_id),
                    workspace_id=row.get("workspace_id"),
                    workspace_name=row.get("workspace_name"),
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def latest_for_owner(
        self,
        *,
        owner: str | None,
        user_id: int,
        workspace_id: int | None = None,
        account_id: int | None = None,
    ) -> OrderHistoryItem | None:
        owner_key = self._normalize_owner(owner)
        if not owner_key:
            return None
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            has_refund_amount = self._column_exists(cursor, "refund_amount")
            refund_select = "oh.refund_amount" if has_refund_amount else "NULL AS refund_amount"
            params: list = [int(user_id), owner_key]
            where = "WHERE oh.user_id = %s AND LOWER(oh.owner) = %s"
            if workspace_id is not None:
                where += " AND (oh.workspace_id = %s OR oh.workspace_id IS NULL)"
                params.append(int(workspace_id))
            if account_id is not None:
                where += " AND oh.account_id = %s"
                params.append(int(account_id))
            cursor.execute(
                f"""
                SELECT oh.id, oh.order_id, oh.owner, oh.account_name, a.login AS account_login, oh.account_id, oh.steam_id,
                       oh.rental_minutes, oh.lot_number, oh.amount, oh.price, {refund_select}, oh.action,
                       oh.user_id, oh.workspace_id, w.name AS workspace_name, oh.created_at
                FROM order_history oh
                LEFT JOIN workspaces w ON w.id = oh.workspace_id AND w.user_id = oh.user_id
                LEFT JOIN accounts a ON a.id = oh.account_id AND a.user_id = oh.user_id
                {where}
                ORDER BY oh.id DESC
                LIMIT 1
                """,
                tuple(params),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return OrderHistoryItem(
                id=int(row["id"]),
                order_id=str(row.get("order_id") or ""),
                owner=row.get("owner") or "",
                account_name=row.get("account_name"),
                account_login=row.get("account_login"),
                account_id=row.get("account_id"),
                steam_id=row.get("steam_id"),
                rental_minutes=row.get("rental_minutes"),
                lot_number=row.get("lot_number"),
                amount=row.get("amount"),
                price=row.get("price"),
                refund_amount=row.get("refund_amount"),
                action=row.get("action"),
                user_id=int(row.get("user_id") or user_id),
                workspace_id=row.get("workspace_id"),
                workspace_name=row.get("workspace_name"),
                created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
            )
        finally:
            conn.close()

    def insert_action(
        self,
        *,
        order_id: str,
        owner: str,
        user_id: int,
        action: str,
        workspace_id: int | None = None,
        account_id: int | None = None,
        account_name: str | None = None,
        steam_id: str | None = None,
        rental_minutes: int | None = None,
        lot_number: int | None = None,
        amount: int | None = None,
        price: float | None = None,
        refund_amount: float | None = None,
    ) -> None:
        order_key = self._normalize_order_id(order_id)
        owner_key = self._normalize_owner(owner)
        if not order_key or not owner_key:
            return
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            has_steam = self._column_exists(cursor, "steam_id")
            has_refund_amount = self._column_exists(cursor, "refund_amount")
            if has_steam:
                if has_refund_amount:
                    cursor.execute(
                        """
                        INSERT INTO order_history (
                            order_id, owner, account_name, account_id, steam_id, rental_minutes,
                            lot_number, amount, price, refund_amount, action, user_id, workspace_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            order_key,
                            owner_key,
                            account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                            int(account_id) if account_id is not None else None,
                            steam_id.strip() if isinstance(steam_id, str) and steam_id.strip() else None,
                            int(rental_minutes) if rental_minutes is not None else None,
                            int(lot_number) if lot_number is not None else None,
                            int(amount) if amount is not None else None,
                            float(price) if price is not None else None,
                            float(refund_amount) if refund_amount is not None else None,
                            action,
                            int(user_id),
                            int(workspace_id) if workspace_id is not None else None,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO order_history (
                            order_id, owner, account_name, account_id, steam_id, rental_minutes,
                            lot_number, amount, price, action, user_id, workspace_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            order_key,
                            owner_key,
                            account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                            int(account_id) if account_id is not None else None,
                            steam_id.strip() if isinstance(steam_id, str) and steam_id.strip() else None,
                            int(rental_minutes) if rental_minutes is not None else None,
                            int(lot_number) if lot_number is not None else None,
                            int(amount) if amount is not None else None,
                            float(price) if price is not None else None,
                            action,
                            int(user_id),
                            int(workspace_id) if workspace_id is not None else None,
                        ),
                    )
            else:
                if has_refund_amount:
                    cursor.execute(
                        """
                        INSERT INTO order_history (
                            order_id, owner, account_name, account_id, rental_minutes,
                            lot_number, amount, price, refund_amount, action, user_id, workspace_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            order_key,
                            owner_key,
                            account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                            int(account_id) if account_id is not None else None,
                            int(rental_minutes) if rental_minutes is not None else None,
                            int(lot_number) if lot_number is not None else None,
                            int(amount) if amount is not None else None,
                            float(price) if price is not None else None,
                            float(refund_amount) if refund_amount is not None else None,
                            action,
                            int(user_id),
                            int(workspace_id) if workspace_id is not None else None,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO order_history (
                            order_id, owner, account_name, account_id, rental_minutes,
                            lot_number, amount, price, action, user_id, workspace_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            order_key,
                            owner_key,
                            account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                            int(account_id) if account_id is not None else None,
                            int(rental_minutes) if rental_minutes is not None else None,
                            int(lot_number) if lot_number is not None else None,
                            int(amount) if amount is not None else None,
                            float(price) if price is not None else None,
                            action,
                            int(user_id),
                            int(workspace_id) if workspace_id is not None else None,
                        ),
                    )
            conn.commit()
        finally:
            conn.close()
