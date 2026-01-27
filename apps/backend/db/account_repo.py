from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import get_base_connection


@dataclass
class AccountRecord:
    id: int
    user_id: int
    workspace_id: int | None
    workspace_name: str | None
    last_rented_workspace_id: int | None
    last_rented_workspace_name: str | None
    account_name: str
    login: str
    password: str
    lot_url: Optional[str]
    mmr: Optional[int]
    owner: Optional[str]
    rental_start: Optional[str]
    rental_duration: int
    rental_duration_minutes: Optional[int]
    low_priority: int
    account_frozen: int
    rental_frozen: int
    mafile_json: Optional[str] = None


@dataclass
class AccountSteamRecord:
    id: int
    user_id: int
    workspace_id: int | None
    last_rented_workspace_id: int | None
    account_name: str
    login: str
    password: str
    mafile_json: Optional[str]


@dataclass
class ActiveRentalRecord:
    id: int
    account_name: str
    login: str
    owner: str
    rental_start: Optional[str]
    rental_duration: int
    rental_duration_minutes: Optional[int]
    lot_number: Optional[int]
    mafile_json: Optional[str]
    workspace_id: int | None = None
    workspace_name: str | None = None


class MySQLAccountRepo:
    def _get_conn(self) -> mysql.connector.MySQLConnection:
        return get_base_connection()

    def _column_exists(self, cursor: mysql.connector.cursor.MySQLCursor, column: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'accounts' AND column_name = %s LIMIT 1",
            (column,),
        )
        return cursor.fetchone() is not None

    def _table_exists(self, cursor: mysql.connector.cursor.MySQLCursor, table: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
            (table,),
        )
        return cursor.fetchone() is not None

    def get_by_id(self, account_id: int, user_id: int, workspace_id: int | None = None) -> Optional[dict]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            has_frozen_at = self._column_exists(cursor, "rental_frozen_at")
            has_last_rented = self._column_exists(cursor, "last_rented_workspace_id")
            has_low_priority = self._column_exists(cursor, "low_priority")
            cursor = conn.cursor(dictionary=True)
            columns = (
                "a.id, a.user_id, a.workspace_id, "
                "a.account_name, a.login, a.password, a.lot_url, a.mmr, a.mafile_json, "
                "owner, rental_start, rental_duration, rental_duration_minutes, account_frozen, rental_frozen"
            )
            if has_frozen_at:
                columns += ", rental_frozen_at"
            if has_last_rented:
                columns += ", last_rented_workspace_id"
            if has_low_priority:
                columns += ", `low_priority`"
            cursor.execute(
                f"SELECT {columns} FROM accounts a "
                "WHERE a.id = %s AND a.user_id = %s LIMIT 1",
                (account_id, user_id),
            )
            return cursor.fetchone()
        finally:
            conn.close()

    def list_by_user(self, user_id: int) -> List[AccountRecord]:
        conn = self._get_conn()
        try:
            has_low_priority = self._column_exists(conn.cursor(), "low_priority")
            cursor = conn.cursor(dictionary=True)
            low_priority_select = ", a.`low_priority`" if has_low_priority else ""
            cursor.execute(
                f"""
                SELECT a.id, a.user_id, a.workspace_id,
                       w.name AS workspace_name,
                       a.last_rented_workspace_id,
                       lw.name AS last_rented_workspace_name,
                       a.account_name, a.login, a.password, a.lot_url, a.mmr, a.mafile_json,
                       a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       a.account_frozen, a.rental_frozen{low_priority_select}
                FROM accounts a
                LEFT JOIN workspaces w ON w.id = a.workspace_id
                LEFT JOIN workspaces lw ON lw.id = a.last_rented_workspace_id
                WHERE a.user_id = %s
                ORDER BY a.id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall() or []
            return [
                AccountRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    workspace_id=row.get("workspace_id"),
                    workspace_name=row.get("workspace_name"),
                    last_rented_workspace_id=row.get("last_rented_workspace_id"),
                    last_rented_workspace_name=row.get("last_rented_workspace_name"),
                    account_name=row["account_name"],
                    login=row["login"],
                    password=row["password"],
                    lot_url=row.get("lot_url"),
                    mmr=row.get("mmr"),
                    owner=row.get("owner"),
                    rental_start=row.get("rental_start"),
                    rental_duration=int(row.get("rental_duration") or 0),
                    rental_duration_minutes=row.get("rental_duration_minutes"),
                    low_priority=int(row.get("low_priority") or 0),
                    account_frozen=int(row.get("account_frozen") or 0),
                    rental_frozen=int(row.get("rental_frozen") or 0),
                    mafile_json=row.get("mafile_json"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def list_by_workspace(self, user_id: int, workspace_id: int) -> List[AccountRecord]:
        conn = self._get_conn()
        try:
            has_low_priority = self._column_exists(conn.cursor(), "low_priority")
            cursor = conn.cursor(dictionary=True)
            low_priority_select = ", a.`low_priority`" if has_low_priority else ""
            cursor.execute(
                f"""
                SELECT a.id, a.user_id, a.workspace_id,
                       w.name AS workspace_name,
                       a.last_rented_workspace_id,
                       lw.name AS last_rented_workspace_name,
                       a.account_name, a.login, a.password, a.lot_url, a.mmr, a.mafile_json,
                       a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       a.account_frozen, a.rental_frozen{low_priority_select}
                FROM accounts a
                LEFT JOIN workspaces w ON w.id = a.workspace_id
                LEFT JOIN workspaces lw ON lw.id = a.last_rented_workspace_id
                WHERE a.user_id = %s AND a.workspace_id = %s
                ORDER BY a.id DESC
                """,
                (user_id, workspace_id),
            )
            rows = cursor.fetchall() or []
            return [
                AccountRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    workspace_id=row.get("workspace_id"),
                    workspace_name=row.get("workspace_name"),
                    last_rented_workspace_id=row.get("last_rented_workspace_id"),
                    last_rented_workspace_name=row.get("last_rented_workspace_name"),
                    account_name=row["account_name"],
                    login=row["login"],
                    password=row["password"],
                    lot_url=row.get("lot_url"),
                    mmr=row.get("mmr"),
                    owner=row.get("owner"),
                    rental_start=row.get("rental_start"),
                    rental_duration=int(row.get("rental_duration") or 0),
                    rental_duration_minutes=row.get("rental_duration_minutes"),
                    low_priority=int(row.get("low_priority") or 0),
                    account_frozen=int(row.get("account_frozen") or 0),
                    rental_frozen=int(row.get("rental_frozen") or 0),
                    mafile_json=row.get("mafile_json"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def create(
        self,
        *,
        user_id: int,
        workspace_id: int,
        account_name: str,
        login: str,
        password: str,
        mafile_json: str,
        lot_url: Optional[str],
        mmr: Optional[int],
        rental_duration: int,
        rental_duration_minutes: int,
    ) -> Optional[AccountRecord]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM accounts WHERE user_id = %s AND account_name = %s LIMIT 1",
                (user_id, account_name),
            )
            if cursor.fetchone():
                return None
            has_mafile_json = self._column_exists(cursor, "mafile_json")
            has_path = self._column_exists(cursor, "path_to_maFile")
            has_lot_url = self._column_exists(cursor, "lot_url")

            columns = [
                "user_id",
                "workspace_id",
                "account_name",
                "login",
                "password",
                "mmr",
                "rental_duration",
                "rental_duration_minutes",
            ]
            values: list = [
                user_id,
                workspace_id,
                account_name,
                login,
                password,
                mmr,
                rental_duration,
                rental_duration_minutes,
            ]
            if has_mafile_json:
                columns.append("mafile_json")
                values.append(mafile_json)
            if has_path:
                columns.append("path_to_maFile")
                values.append("")
            if has_lot_url:
                columns.append("lot_url")
                values.append(lot_url)

            placeholders = ", ".join(["%s"] * len(columns))
            columns_sql = ", ".join(columns)
            try:
                cursor.execute(
                    f"INSERT INTO accounts ({columns_sql}) VALUES ({placeholders})",
                    tuple(values),
                )
                conn.commit()
                account_id = cursor.lastrowid
            except mysql.connector.Error as exc:
                if exc.errno == errorcode.ER_DUP_ENTRY:
                    return None
                raise

            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT a.id, a.user_id, a.workspace_id,
                       w.name AS workspace_name,
                       a.last_rented_workspace_id,
                       lw.name AS last_rented_workspace_name,
                       a.account_name, a.login, a.password, a.lot_url, a.mmr,
                       a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       a.account_frozen, a.rental_frozen, a.`low_priority`
                FROM accounts a
                LEFT JOIN workspaces w ON w.id = a.workspace_id
                LEFT JOIN workspaces lw ON lw.id = a.last_rented_workspace_id
                WHERE a.id = %s LIMIT 1
                """,
                (account_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return AccountRecord(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                workspace_id=row.get("workspace_id"),
                workspace_name=row.get("workspace_name"),
                last_rented_workspace_id=row.get("last_rented_workspace_id"),
                last_rented_workspace_name=row.get("last_rented_workspace_name"),
                account_name=row["account_name"],
                login=row["login"],
                password=row["password"],
                lot_url=row.get("lot_url"),
                mmr=row.get("mmr"),
                owner=row.get("owner"),
                rental_start=row.get("rental_start"),
                rental_duration=int(row.get("rental_duration") or 0),
                rental_duration_minutes=row.get("rental_duration_minutes"),
                low_priority=int(row.get("low_priority") or 0),
                account_frozen=int(row.get("account_frozen") or 0),
                rental_frozen=int(row.get("rental_frozen") or 0),
            )
        finally:
            conn.close()

    def get_for_steam(self, account_id: int, user_id: int, workspace_id: int) -> Optional[AccountSteamRecord]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, workspace_id, last_rented_workspace_id, account_name, login, password, mafile_json
                FROM accounts
                WHERE id = %s AND user_id = %s
                LIMIT 1
                """,
                (account_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return AccountSteamRecord(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                workspace_id=row.get("workspace_id"),
                last_rented_workspace_id=row.get("last_rented_workspace_id"),
                account_name=row["account_name"],
                login=row["login"],
                password=row["password"],
                mafile_json=row.get("mafile_json"),
            )
        finally:
            conn.close()

    def list_active_rentals(self, user_id: int, workspace_id: int | None = None) -> List[ActiveRentalRecord]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list = [user_id]
            workspace_clause = ""
            workspace_expr = "COALESCE(a.last_rented_workspace_id, a.workspace_id)"
            lot_join_clause = (
                "LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id "
                f"AND l.workspace_id = {workspace_expr}"
            )
            if workspace_id is not None:
                workspace_clause = f" AND {workspace_expr} = %s"
                params.append(workspace_id)
            cursor.execute(
                f"""
                SELECT a.id, a.account_name, a.login, a.owner, a.mafile_json,
                       a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       {workspace_expr} AS active_workspace_id,
                       lw.name AS active_workspace_name,
                       l.lot_number
                FROM accounts a
                {lot_join_clause}
                LEFT JOIN workspaces lw ON lw.id = {workspace_expr}
                WHERE a.user_id = %s{workspace_clause} AND a.owner IS NOT NULL AND a.owner != ''
                ORDER BY a.rental_start DESC, a.id DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall() or []
            return [
                ActiveRentalRecord(
                    id=int(row["id"]),
                    account_name=row["account_name"],
                    login=row["login"],
                    owner=row["owner"],
                    rental_start=row.get("rental_start"),
                    rental_duration=int(row.get("rental_duration") or 0),
                    rental_duration_minutes=row.get("rental_duration_minutes"),
                    lot_number=row.get("lot_number"),
                    mafile_json=row.get("mafile_json"),
                    workspace_id=row.get("active_workspace_id"),
                    workspace_name=row.get("active_workspace_name"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def list_low_priority(self, user_id: int, workspace_id: int | None = None) -> List[AccountRecord]:
        conn = self._get_conn()
        try:
            if not self._column_exists(conn.cursor(), "low_priority"):
                return []
            cursor = conn.cursor(dictionary=True)
            params: list = [user_id]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND a.workspace_id = %s"
                params.append(workspace_id)
            cursor.execute(
                f"""
                SELECT a.id, a.user_id, a.workspace_id,
                       w.name AS workspace_name,
                       a.last_rented_workspace_id,
                       lw.name AS last_rented_workspace_name,
                       a.account_name, a.login, a.password, a.lot_url, a.mmr, a.mafile_json,
                       a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       a.account_frozen, a.rental_frozen, a.`low_priority`
                FROM accounts a
                LEFT JOIN workspaces w ON w.id = a.workspace_id
                LEFT JOIN workspaces lw ON lw.id = a.last_rented_workspace_id
                WHERE a.user_id = %s AND a.`low_priority` = 1{workspace_clause}
                ORDER BY a.id DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall() or []
            return [
                AccountRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    workspace_id=row.get("workspace_id"),
                    workspace_name=row.get("workspace_name"),
                    last_rented_workspace_id=row.get("last_rented_workspace_id"),
                    last_rented_workspace_name=row.get("last_rented_workspace_name"),
                    account_name=row["account_name"],
                    login=row["login"],
                    password=row["password"],
                    lot_url=row.get("lot_url"),
                    mmr=row.get("mmr"),
                    owner=row.get("owner"),
                    rental_start=row.get("rental_start"),
                    rental_duration=int(row.get("rental_duration") or 0),
                    rental_duration_minutes=row.get("rental_duration_minutes"),
                    low_priority=int(row.get("low_priority") or 0),
                    account_frozen=int(row.get("account_frozen") or 0),
                    rental_frozen=int(row.get("rental_frozen") or 0),
                    mafile_json=row.get("mafile_json"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def set_account_owner(self, account_id: int, user_id: int, workspace_id: int, owner: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE accounts
                SET owner = %s,
                    rental_start = NULL,
                    last_rented_workspace_id = %s
                WHERE id = %s AND user_id = %s AND (owner IS NULL OR owner = '')
                """,
                (owner, workspace_id, account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def release_account(self, account_id: int, user_id: int, workspace_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            has_frozen_at = self._column_exists(cursor, "rental_frozen_at")
            updates = ["owner = NULL", "rental_start = NULL", "rental_frozen = 0"]
            if has_frozen_at:
                updates.append("rental_frozen_at = NULL")
            params: list = [account_id, user_id]
            workspace_clause = ""
            if self._column_exists(cursor, "last_rented_workspace_id"):
                workspace_clause = " AND last_rented_workspace_id = %s"
                params.append(workspace_id)
            cursor.execute(
                f"UPDATE accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s{workspace_clause}",
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def extend_rental_duration(
        self, account_id: int, user_id: int, workspace_id: int, add_hours: int, add_minutes: int
    ) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT rental_duration, rental_duration_minutes FROM accounts "
                "WHERE id = %s AND user_id = %s LIMIT 1",
                (account_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return False
            base_hours = int(row.get("rental_duration") or 0)
            base_minutes = row.get("rental_duration_minutes")
            if base_minutes is None:
                base_minutes = base_hours * 60
            total_minutes = int(base_minutes) + add_hours * 60 + add_minutes
            total_hours = base_hours + add_hours
            cursor = conn.cursor()
            params: list = [total_hours, total_minutes, account_id, user_id]
            workspace_clause = ""
            if self._column_exists(cursor, "last_rented_workspace_id"):
                workspace_clause = " AND last_rented_workspace_id = %s"
                params.append(workspace_id)
            cursor.execute(
                f"""
                UPDATE accounts
                SET rental_duration = %s,
                    rental_duration_minutes = %s
                WHERE id = %s AND user_id = %s{workspace_clause}
                """,
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def set_account_frozen(self, account_id: int, user_id: int, workspace_id: int, frozen: bool) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE accounts SET account_frozen = %s WHERE id = %s AND user_id = %s",
                (1 if frozen else 0, account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def find_replacement_account(
        self,
        *,
        user_id: int,
        workspace_id: int | None,
        target_mmr: int,
        exclude_id: int,
        max_delta: int = 1000,
    ) -> dict | None:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            has_low_priority = self._column_exists(cursor, "low_priority")
            has_account_frozen = self._column_exists(cursor, "account_frozen")
            has_rental_frozen = self._column_exists(cursor, "rental_frozen")
            where = [
                "a.user_id = %s",
                "(a.owner IS NULL OR a.owner = '')",
                "a.id != %s",
                "a.mmr IS NOT NULL",
                "ABS(a.mmr - %s) <= %s",
            ]
            params: list = [int(user_id), int(exclude_id), int(target_mmr), int(max_delta)]
            if workspace_id is not None:
                where.append("a.workspace_id = %s")
                params.append(int(workspace_id))
            if has_account_frozen:
                where.append("(a.account_frozen = 0 OR a.account_frozen IS NULL)")
            if has_rental_frozen:
                where.append("(a.rental_frozen = 0 OR a.rental_frozen IS NULL)")
            if has_low_priority:
                where.append("(a.low_priority = 0 OR a.low_priority IS NULL)")
            cursor.execute(
                f"""
                SELECT a.id, a.account_name, a.login, a.password, a.mmr, a.lot_url,
                       a.rental_duration, a.rental_duration_minutes, a.workspace_id
                FROM accounts a
                WHERE {' AND '.join(where)}
                ORDER BY ABS(a.mmr - %s), a.mmr, a.id
                LIMIT 1
                """,
                tuple(params + [int(target_mmr)]),
            )
            row = cursor.fetchone()
            return row if row else None
        finally:
            conn.close()

    def replace_rental_account(
        self,
        *,
        old_account_id: int,
        new_account_id: int,
        user_id: int,
        owner: str,
        workspace_id: int | None,
        rental_start: str,
        rental_duration: int,
        rental_duration_minutes: int,
    ) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            has_last_rented = self._column_exists(cursor, "last_rented_workspace_id")
            has_low_priority = self._column_exists(cursor, "low_priority")
            has_frozen_at = self._column_exists(cursor, "rental_frozen_at")
            has_account_frozen = self._column_exists(cursor, "account_frozen")
            has_rental_frozen = self._column_exists(cursor, "rental_frozen")
            try:
                conn.start_transaction()
            except Exception:
                pass

            updates = [
                "owner = %s",
                "rental_duration = %s",
                "rental_duration_minutes = %s",
                "rental_start = %s",
                "rental_frozen = 0",
            ]
            params: list = [owner, int(rental_duration), int(rental_duration_minutes), rental_start]
            if has_frozen_at:
                updates.append("rental_frozen_at = NULL")
            if workspace_id is not None and has_last_rented:
                updates.append("last_rented_workspace_id = %s")
                params.append(int(workspace_id))
            params.extend([int(new_account_id), int(user_id)])
            where_clauses = ["id = %s", "user_id = %s", "(owner IS NULL OR owner = '')"]
            if has_account_frozen:
                where_clauses.append("(account_frozen = 0 OR account_frozen IS NULL)")
            if has_rental_frozen:
                where_clauses.append("(rental_frozen = 0 OR rental_frozen IS NULL)")
            if has_low_priority:
                where_clauses.append("(low_priority = 0 OR low_priority IS NULL)")
            cursor.execute(
                f"UPDATE accounts SET {', '.join(updates)} WHERE {' AND '.join(where_clauses)}",
                tuple(params),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return False

            old_updates = ["owner = NULL", "rental_start = NULL", "rental_frozen = 0"]
            if has_frozen_at:
                old_updates.append("rental_frozen_at = NULL")
            if has_low_priority:
                old_updates.append("low_priority = 1")
            old_params: list = [int(old_account_id), int(user_id)]
            old_where = "id = %s AND user_id = %s"
            if owner:
                old_where += " AND LOWER(owner) = %s"
                old_params.append(owner.strip().lower())
            if workspace_id is not None and has_last_rented:
                old_where += " AND last_rented_workspace_id = %s"
                old_params.append(int(workspace_id))
            cursor.execute(
                f"UPDATE accounts SET {', '.join(old_updates)} WHERE {old_where}",
                tuple(old_params),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return False

            conn.commit()
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            conn.close()

    def set_low_priority(self, account_id: int, user_id: int, workspace_id: int, low_priority: bool) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if not self._column_exists(cursor, "low_priority"):
                return False
            cursor.execute(
                "UPDATE accounts SET `low_priority` = %s WHERE id = %s AND user_id = %s",
                (1 if low_priority else 0, account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def set_rental_freeze_state(
        self,
        account_id: int,
        user_id: int,
        workspace_id: int,
        frozen: bool,
        *,
        rental_start: Optional[str] = None,
        frozen_at: Optional[str] = None,
    ) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            has_frozen_at = self._column_exists(cursor, "rental_frozen_at")
            updates = ["rental_frozen = %s"]
            values: list = [1 if frozen else 0]
            if has_frozen_at:
                updates.append("rental_frozen_at = %s")
                values.append(frozen_at)
            if rental_start is not None:
                updates.append("rental_start = %s")
                values.append(rental_start)
            values.extend([account_id, user_id])
            workspace_clause = ""
            if self._column_exists(cursor, "last_rented_workspace_id"):
                workspace_clause = " AND last_rented_workspace_id = %s"
                values.append(workspace_id)
            cursor.execute(
                f"UPDATE accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s{workspace_clause}",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update_account(self, account_id: int, user_id: int, workspace_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            columns = []
            values = []
            for key, value in fields.items():
                columns.append(f"{key} = %s")
                values.append(value)
            values.extend([account_id, user_id])
            cursor.execute(
                f"UPDATE accounts SET {', '.join(columns)} WHERE id = %s AND user_id = %s",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_account_by_id(self, account_id: int, user_id: int, workspace_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM accounts WHERE id = %s AND user_id = %s",
                (account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
