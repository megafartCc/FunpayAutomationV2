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
            params: list = [int(user_id)]
            where = "WHERE user_id = %s"
            if workspace_id is not None:
                where += " AND (workspace_id = %s OR workspace_id IS NULL)"
                params.append(int(workspace_id))
            if query:
                where += " AND owner LIKE %s"
                params.append(f"%{query.strip().lower()}%")
            if status:
                where += " AND status = %s"
                params.append(status)
            cursor.execute(
                f"""
                SELECT id, owner, reason, details, status, user_id, workspace_id, created_at
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
            params: list = [int(user_id)]
            where = "WHERE user_id = %s"
            if workspace_id is not None:
                where += " AND (workspace_id = %s OR workspace_id IS NULL)"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT id, owner, action, reason, details, amount, user_id, workspace_id, created_at
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
            if workspace_id is None:
                cursor.execute(
                    "SELECT 1 FROM blacklist WHERE owner = %s AND user_id = %s AND status = 'confirmed' LIMIT 1",
                    (owner_key, int(user_id)),
                )
            else:
                cursor.execute(
                    """
                    SELECT 1 FROM blacklist
                    WHERE owner = %s AND user_id = %s AND status = 'confirmed'
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
            if workspace_id is None:
                cursor.execute(
                    """
                    SELECT id, status FROM blacklist
                    WHERE owner = %s AND user_id = %s AND workspace_id IS NULL
                    LIMIT 1
                    """,
                    (owner_key, int(user_id)),
                )
                existing = cursor.fetchone()
                if existing:
                    if reason_value is None and status_value == (existing[1] if len(existing) > 1 else "confirmed"):
                        return False
                    cursor.execute(
                        """
                        UPDATE blacklist
                        SET reason = %s, details = %s, status = %s
                        WHERE owner = %s AND user_id = %s AND workspace_id IS NULL
                        """,
                        (reason_value, details_value, status_value, owner_key, int(user_id)),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            try:
                cursor.execute(
                    """
                    INSERT INTO blacklist (owner, reason, details, status, user_id, workspace_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        owner_key,
                        reason_value,
                        details_value,
                        status_value,
                        int(user_id),
                        int(workspace_id) if workspace_id is not None else None,
                    ),
                )
                conn.commit()
                return True
            except mysql.connector.Error as exc:
                if exc.errno != errorcode.ER_DUP_ENTRY:
                    raise
                if reason_value is None and details_value is None and status_value == "confirmed":
                    return False
                cursor.execute(
                    """
                    UPDATE blacklist
                    SET reason = %s, details = %s, status = %s
                    WHERE owner = %s AND user_id = %s AND workspace_id <=> %s
                    """,
                    (
                        reason_value,
                        details_value,
                        status_value,
                        owner_key,
                        int(user_id),
                        int(workspace_id) if workspace_id is not None else None,
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
            if workspace_id is None:
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
            if workspace_id is None:
                if status_value is None:
                    cursor.execute(
                        """
                        UPDATE blacklist
                        SET owner = %s, reason = %s
                        WHERE id = %s AND user_id = %s
                        """,
                        (owner_key, reason_value, int(entry_id), int(user_id)),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE blacklist
                        SET owner = %s, reason = %s, status = %s
                        WHERE id = %s AND user_id = %s
                        """,
                        (owner_key, reason_value, status_value, int(entry_id), int(user_id)),
                    )
            else:
                if status_value is None:
                    cursor.execute(
                        """
                        UPDATE blacklist
                        SET owner = %s, reason = %s
                        WHERE id = %s AND user_id = %s AND workspace_id = %s
                        """,
                        (owner_key, reason_value, int(entry_id), int(user_id), int(workspace_id)),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE blacklist
                        SET owner = %s, reason = %s, status = %s
                        WHERE id = %s AND user_id = %s AND workspace_id = %s
                        """,
                        (owner_key, reason_value, status_value, int(entry_id), int(user_id), int(workspace_id)),
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
            placeholders = ", ".join(["%s"] * len(owners_clean))
            params: list = owners_clean + [int(user_id)]
            workspace_clause = ""
            if workspace_id is not None:
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
            params: list = [int(user_id)]
            workspace_clause = ""
            if workspace_id is not None:
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
            cursor.execute(
                """
                INSERT INTO blacklist_logs (owner, action, reason, details, amount, user_id, workspace_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    owner_key,
                    action,
                    reason.strip() if isinstance(reason, str) and reason.strip() else None,
                    details.strip() if isinstance(details, str) and details.strip() else None,
                    int(amount) if amount is not None else None,
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                ),
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
            params: list = [owner_key, int(user_id)]
            workspace_clause = ""
            if workspace_id is not None:
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
            params: list = [owner_key, int(user_id)]
            workspace_clause = ""
            if workspace_id is not None:
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
