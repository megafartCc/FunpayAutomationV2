from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import get_base_connection


@dataclass
class BlacklistEntry:
    id: int
    owner: str
    reason: Optional[str]
    details: Optional[str]
    status: str
    user_id: int
    workspace_id: Optional[int]
    created_at: Optional[str]


@dataclass
class BlacklistLog:
    id: int
    owner: str
    action: str
    reason: Optional[str]
    details: Optional[str]
    amount: Optional[int]
    user_id: int
    workspace_id: Optional[int]
    created_at: Optional[str]


class MySQLBlacklistRepo:
    @staticmethod
    def _table_exists(cursor: mysql.connector.cursor.MySQLCursor, table_name: str) -> bool:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = %s
            LIMIT 1
            """,
            (table_name,),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _get_table_columns(cursor: mysql.connector.cursor.MySQLCursor, table_name: str) -> set[str]:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = %s
            """,
            (table_name,),
        )
        return {row[0] for row in cursor.fetchall() or []}

    def _get_conn(self) -> mysql.connector.MySQLConnection:
        return get_base_connection()

    @staticmethod
    def _normalize_owner(owner: str) -> str:
        return str(owner or "").strip().lower()

    def list_blacklist(
        self,
        user_id: int,
        workspace_id: int | None = None,
        *,
        query: str | None = None,
        status: str | None = None,
    ) -> list[BlacklistEntry]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            meta_cursor = conn.cursor()
            if not self._table_exists(meta_cursor, "blacklist"):
                return []
            columns = self._get_table_columns(meta_cursor, "blacklist")
            has_workspace_id = "workspace_id" in columns
            has_details = "details" in columns
            has_status = "status" in columns
            params: list = [int(user_id)]
            where = "WHERE user_id = %s"
            if workspace_id is not None and has_workspace_id:
                where += " AND (workspace_id = %s OR workspace_id IS NULL)"
                params.append(int(workspace_id))
            if query:
                where += " AND owner LIKE %s"
                params.append(f"%{query.strip().lower()}%")
            if status and has_status:
                where += " AND status = %s"
                params.append(status)
            details_select = "details" if has_details else "NULL AS details"
            status_select = "status" if has_status else "'confirmed' AS status"
            workspace_select = "workspace_id" if has_workspace_id else "NULL AS workspace_id"
            cursor.execute(
                f"""
                SELECT id, owner, reason, {details_select}, {status_select}, user_id, {workspace_select}, created_at
                FROM blacklist
                {where}
                ORDER BY created_at DESC, id DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall() or []
            return [
                BlacklistEntry(
                    id=int(row["id"]),
                    owner=row["owner"],
                    reason=row.get("reason"),
                    details=row.get("details"),
                    status=row.get("status") or "confirmed",
                    user_id=int(row["user_id"]),
                    workspace_id=row.get("workspace_id"),
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def list_blacklist_logs(
        self,
        user_id: int,
        workspace_id: int | None = None,
        *,
        limit: int = 100,
    ) -> list[BlacklistLog]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            meta_cursor = conn.cursor()
            if not self._table_exists(meta_cursor, "blacklist_logs"):
                return []
            columns = self._get_table_columns(meta_cursor, "blacklist_logs")
            has_workspace_id = "workspace_id" in columns
            has_details = "details" in columns
            has_amount = "amount" in columns
            params: list = [int(user_id)]
            where = "WHERE user_id = %s"
            if workspace_id is not None and has_workspace_id:
                where += " AND (workspace_id = %s OR workspace_id IS NULL)"
                params.append(int(workspace_id))
            details_select = "details" if has_details else "NULL AS details"
            amount_select = "amount" if has_amount else "NULL AS amount"
            workspace_select = "workspace_id" if has_workspace_id else "NULL AS workspace_id"
            cursor.execute(
                f"""
                SELECT id, owner, action, reason, {details_select}, {amount_select}, user_id, {workspace_select}, created_at
                FROM blacklist_logs
                {where}
                ORDER BY id DESC
                LIMIT %s
                """,
                tuple(params + [int(max(1, min(limit, 500)))]),
            )
            rows = cursor.fetchall() or []
            return [
                BlacklistLog(
                    id=int(row["id"]),
                    owner=row["owner"],
                    action=row["action"],
                    reason=row.get("reason"),
                    details=row.get("details"),
                    amount=row.get("amount"),
                    user_id=int(row["user_id"]),
                    workspace_id=row.get("workspace_id"),
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def is_blacklisted(self, owner: str, user_id: int, workspace_id: int | None = None) -> bool:
        owner_key = self._normalize_owner(owner)
        if not owner_key:
            return False
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist"):
                return False
            columns = self._get_table_columns(cursor, "blacklist")
            has_workspace_id = "workspace_id" in columns
            has_status = "status" in columns
            if workspace_id is None or not has_workspace_id:
                status_clause = " AND status = 'confirmed'" if has_status else ""
                cursor.execute(
                    f"SELECT 1 FROM blacklist WHERE owner = %s AND user_id = %s{status_clause} LIMIT 1",
                    (owner_key, int(user_id)),
                )
            else:
                status_clause = " AND status = 'confirmed'" if has_status else ""
                cursor.execute(
                    f"""
                    SELECT 1 FROM blacklist
                    WHERE owner = %s AND user_id = %s{status_clause}
                      AND (workspace_id = %s OR workspace_id IS NULL)
                    LIMIT 1
                    """,
                    (owner_key, int(user_id), int(workspace_id)),
                )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def add_blacklist_entry(
        self,
        owner: str,
        reason: str | None,
        user_id: int,
        workspace_id: int | None = None,
        *,
        status: str = "confirmed",
        details: str | None = None,
    ) -> bool:
        owner_key = self._normalize_owner(owner)
        if not owner_key:
            return False
        reason_value = reason.strip() if isinstance(reason, str) and reason.strip() else None
        details_value = details.strip() if isinstance(details, str) and details.strip() else None
        status_value = str(status or "confirmed").strip().lower() or "confirmed"
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist"):
                return False
            columns = self._get_table_columns(cursor, "blacklist")
            has_workspace_id = "workspace_id" in columns
            has_details = "details" in columns
            has_status = "status" in columns
            effective_workspace_id = workspace_id if has_workspace_id else None
            details_clause = ", details = %s" if has_details else ""
            status_clause = ", status = %s" if has_status else ""
            if effective_workspace_id is None:
                workspace_condition = " AND workspace_id IS NULL" if has_workspace_id else ""
                status_select = ", status" if has_status else ""
                cursor.execute(
                    f"""
                    SELECT id{status_select} FROM blacklist
                    WHERE owner = %s AND user_id = %s{workspace_condition}
                    LIMIT 1
                    """,
                    (owner_key, int(user_id)),
                )
                existing = cursor.fetchone()
                if existing:
                    existing_status = existing[1] if has_status and len(existing) > 1 else "confirmed"
                    if reason_value is None and status_value == existing_status:
                        return False
                    cursor.execute(
                        f"""
                        UPDATE blacklist
                        SET reason = %s{details_clause}{status_clause}
                        WHERE owner = %s AND user_id = %s{workspace_condition}
                        """,
                        (
                            reason_value,
                            *([details_value] if has_details else []),
                            *([status_value] if has_status else []),
                            owner_key,
                            int(user_id),
                        ),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            insert_columns = ["owner", "reason", "user_id"]
            insert_values: list[object] = [owner_key, reason_value, int(user_id)]
            if has_details:
                insert_columns.append("details")
                insert_values.append(details_value)
            if has_status:
                insert_columns.append("status")
                insert_values.append(status_value)
            if has_workspace_id:
                insert_columns.append("workspace_id")
                insert_values.append(int(effective_workspace_id) if effective_workspace_id is not None else None)
            columns_sql = ", ".join(insert_columns)
            values_sql = ", ".join(["%s"] * len(insert_columns))
            try:
                cursor.execute(
                    f"""
                    INSERT INTO blacklist ({columns_sql})
                    VALUES ({values_sql})
                    """,
                    tuple(insert_values),
                )
                conn.commit()
                return True
            except mysql.connector.Error as exc:
                if exc.errno != errorcode.ER_DUP_ENTRY:
                    raise
                if reason_value is None and details_value is None and status_value == "confirmed":
                    return False
                workspace_condition = " AND workspace_id <=> %s" if has_workspace_id else ""
                cursor.execute(
                    f"""
                    UPDATE blacklist
                    SET reason = %s{details_clause}{status_clause}
                    WHERE owner = %s AND user_id = %s{workspace_condition}
                    """,
                    (
                        reason_value,
                        *([details_value] if has_details else []),
                        *([status_value] if has_status else []),
                        owner_key,
                        int(user_id),
                        *([int(effective_workspace_id)] if has_workspace_id else []),
                    ),
                )
                conn.commit()
                return cursor.rowcount > 0
        finally:
            conn.close()

    def update_blacklist_entry(
        self,
        entry_id: int,
        owner: str,
        reason: str | None,
        user_id: int,
        workspace_id: int | None = None,
        *,
        status: str | None = None,
    ) -> bool:
        owner_key = self._normalize_owner(owner)
        if not owner_key:
            return False
        reason_value = reason.strip() if isinstance(reason, str) and reason.strip() else None
        status_value = str(status).strip().lower() if status is not None else None
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist"):
                return False
            columns = self._get_table_columns(cursor, "blacklist")
            has_workspace_id = "workspace_id" in columns
            has_status = "status" in columns
            if workspace_id is None or not has_workspace_id:
                cursor.execute(
                    "SELECT 1 FROM blacklist WHERE owner = %s AND user_id = %s AND id != %s LIMIT 1",
                    (owner_key, int(user_id), int(entry_id)),
                )
            else:
                cursor.execute(
                    """
                    SELECT 1 FROM blacklist
                    WHERE owner = %s AND user_id = %s AND workspace_id = %s AND id != %s
                    LIMIT 1
                    """,
                    (owner_key, int(user_id), int(workspace_id), int(entry_id)),
                )
            if cursor.fetchone():
                return False
            status_clause = ", status = %s" if status_value is not None and has_status else ""
            workspace_clause = " AND workspace_id = %s" if workspace_id is not None and has_workspace_id else ""
            cursor.execute(
                f"""
                UPDATE blacklist
                SET owner = %s, reason = %s{status_clause}
                WHERE id = %s AND user_id = %s{workspace_clause}
                """,
                (
                    owner_key,
                    reason_value,
                    *([status_value] if status_clause else []),
                    int(entry_id),
                    int(user_id),
                    *([int(workspace_id)] if workspace_clause else []),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def remove_blacklist_entries(
        self,
        owners: list[str],
        user_id: int,
        workspace_id: int | None = None,
    ) -> int:
        owners_clean = [self._normalize_owner(o) for o in owners if self._normalize_owner(o)]
        if not owners_clean:
            return 0
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist"):
                return 0
            columns = self._get_table_columns(cursor, "blacklist")
            has_workspace_id = "workspace_id" in columns
            placeholders = ", ".join(["%s"] * len(owners_clean))
            params: list = owners_clean + [int(user_id)]
            workspace_clause = ""
            if workspace_id is not None and has_workspace_id:
                workspace_clause = " AND workspace_id = %s"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                DELETE FROM blacklist
                WHERE owner IN ({placeholders}) AND user_id = %s{workspace_clause}
                """,
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount or 0
        finally:
            conn.close()

    def clear_blacklist(self, user_id: int, workspace_id: int | None = None) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist"):
                return 0
            columns = self._get_table_columns(cursor, "blacklist")
            has_workspace_id = "workspace_id" in columns
            params: list = [int(user_id)]
            workspace_clause = ""
            if workspace_id is not None and has_workspace_id:
                workspace_clause = " AND workspace_id = %s"
                params.append(int(workspace_id))
            cursor.execute(
                f"DELETE FROM blacklist WHERE user_id = %s{workspace_clause}",
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount or 0
        finally:
            conn.close()

    def log_blacklist_event(
        self,
        owner: str,
        action: str,
        *,
        reason: str | None = None,
        details: str | None = None,
        amount: int | None = None,
        user_id: int,
        workspace_id: int | None = None,
    ) -> None:
        owner_key = self._normalize_owner(owner)
        if not owner_key:
            return
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist_logs"):
                return
            columns = self._get_table_columns(cursor, "blacklist_logs")
            insert_columns = ["owner", "action", "reason", "user_id"]
            insert_values: list[object] = [
                owner_key,
                action,
                reason.strip() if isinstance(reason, str) and reason.strip() else None,
                int(user_id),
            ]
            if "details" in columns:
                insert_columns.append("details")
                insert_values.append(details.strip() if isinstance(details, str) and details.strip() else None)
            if "amount" in columns:
                insert_columns.append("amount")
                insert_values.append(int(amount) if amount is not None else None)
            if "workspace_id" in columns:
                insert_columns.append("workspace_id")
                insert_values.append(int(workspace_id) if workspace_id is not None else None)
            columns_sql = ", ".join(insert_columns)
            values_sql = ", ".join(["%s"] * len(insert_columns))
            cursor.execute(
                f"""
                INSERT INTO blacklist_logs ({columns_sql})
                VALUES ({values_sql})
                """,
                tuple(insert_values),
            )
            conn.commit()
        finally:
            conn.close()

    def get_blacklist_compensation_total(
        self,
        owner: str,
        user_id: int,
        workspace_id: int | None = None,
    ) -> int:
        owner_key = self._normalize_owner(owner)
        if not owner_key:
            return 0
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist_logs"):
                return 0
            columns = self._get_table_columns(cursor, "blacklist_logs")
            has_workspace_id = "workspace_id" in columns
            params: list = [owner_key, int(user_id)]
            workspace_clause = ""
            if workspace_id is not None and has_workspace_id:
                workspace_clause = " AND workspace_id = %s"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM blacklist_logs
                WHERE owner = %s AND user_id = %s AND action = 'blacklist_comp'{workspace_clause}
                """,
                tuple(params),
            )
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        finally:
            conn.close()

    def remove_blacklist_entry(
        self,
        owner: str,
        user_id: int,
        workspace_id: int | None = None,
    ) -> bool:
        owner_key = self._normalize_owner(owner)
        if not owner_key:
            return False
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._table_exists(cursor, "blacklist"):
                return False
            columns = self._get_table_columns(cursor, "blacklist")
            has_workspace_id = "workspace_id" in columns
            params: list = [owner_key, int(user_id)]
            workspace_clause = ""
            if workspace_id is not None and has_workspace_id:
                workspace_clause = " AND workspace_id = %s"
                params.append(int(workspace_id))
            cursor.execute(
                f"DELETE FROM blacklist WHERE owner = %s AND user_id = %s{workspace_clause}",
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
