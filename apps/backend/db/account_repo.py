from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import _pool


@dataclass
class AccountRecord:
    id: int
    user_id: int
    account_name: str
    login: str
    password: str
    lot_url: Optional[str]
    mmr: Optional[int]
    owner: Optional[str]
    rental_start: Optional[str]
    rental_duration: int
    rental_duration_minutes: Optional[int]
    account_frozen: int
    rental_frozen: int
    mafile_json: Optional[str] = None


@dataclass
class AccountSteamRecord:
    id: int
    user_id: int
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


class MySQLAccountRepo:
    def _column_exists(self, cursor: mysql.connector.cursor.MySQLCursor, column: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'accounts' AND column_name = %s LIMIT 1",
            (column,),
        )
        return cursor.fetchone() is not None

    def get_by_id(self, account_id: int, user_id: int) -> Optional[dict]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            has_frozen_at = self._column_exists(cursor, "rental_frozen_at")
            cursor = conn.cursor(dictionary=True)
            columns = (
                "id, user_id, account_name, login, password, lot_url, mmr, mafile_json, "
                "owner, rental_start, rental_duration, rental_duration_minutes, account_frozen, rental_frozen"
            )
            if has_frozen_at:
                columns += ", rental_frozen_at"
            cursor.execute(
                f"SELECT {columns} FROM accounts WHERE id = %s AND user_id = %s LIMIT 1",
                (account_id, user_id),
            )
            return cursor.fetchone()
        finally:
            conn.close()

    def list_by_user(self, user_id: int) -> List[AccountRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, account_name, login, password, lot_url, mmr, mafile_json,
                       owner, rental_start, rental_duration, rental_duration_minutes,
                       account_frozen, rental_frozen
                FROM accounts
                WHERE user_id = %s
                ORDER BY id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall() or []
            return [
                AccountRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    account_name=row["account_name"],
                    login=row["login"],
                    password=row["password"],
                    lot_url=row.get("lot_url"),
                    mmr=row.get("mmr"),
                    owner=row.get("owner"),
                    rental_start=row.get("rental_start"),
                    rental_duration=int(row.get("rental_duration") or 0),
                    rental_duration_minutes=row.get("rental_duration_minutes"),
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
        account_name: str,
        login: str,
        password: str,
        mafile_json: str,
        lot_url: Optional[str],
        mmr: Optional[int],
        rental_duration: int,
        rental_duration_minutes: int,
    ) -> Optional[AccountRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            has_mafile_json = self._column_exists(cursor, "mafile_json")
            has_path = self._column_exists(cursor, "path_to_maFile")
            has_lot_url = self._column_exists(cursor, "lot_url")

            columns = [
                "user_id",
                "account_name",
                "login",
                "password",
                "mmr",
                "rental_duration",
                "rental_duration_minutes",
            ]
            values: list = [
                user_id,
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
                SELECT id, user_id, account_name, login, password, lot_url, mmr,
                       owner, rental_start, rental_duration, rental_duration_minutes,
                       account_frozen, rental_frozen
                FROM accounts
                WHERE id = %s
                LIMIT 1
                """,
                (account_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return AccountRecord(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                account_name=row["account_name"],
                login=row["login"],
                password=row["password"],
                lot_url=row.get("lot_url"),
                mmr=row.get("mmr"),
                owner=row.get("owner"),
                rental_start=row.get("rental_start"),
                rental_duration=int(row.get("rental_duration") or 0),
                rental_duration_minutes=row.get("rental_duration_minutes"),
                account_frozen=int(row.get("account_frozen") or 0),
                rental_frozen=int(row.get("rental_frozen") or 0),
            )
        finally:
            conn.close()

    def get_for_steam(self, account_id: int, user_id: int) -> Optional[AccountSteamRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, account_name, login, password, mafile_json
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
                account_name=row["account_name"],
                login=row["login"],
                password=row["password"],
                mafile_json=row.get("mafile_json"),
            )
        finally:
            conn.close()

    def list_active_rentals(self, user_id: int) -> List[ActiveRentalRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT a.id, a.account_name, a.login, a.owner,
                       a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       l.lot_number
                FROM accounts a
                LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id
                WHERE a.user_id = %s AND a.owner IS NOT NULL AND a.owner != ''
                ORDER BY a.rental_start DESC, a.id DESC
                """,
                (user_id,),
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
                )
                for row in rows
            ]
        finally:
            conn.close()

    def set_account_owner(self, account_id: int, user_id: int, owner: str) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE accounts
                SET owner = %s,
                    rental_start = NULL
                WHERE id = %s AND user_id = %s AND (owner IS NULL OR owner = '')
                """,
                (owner, account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def release_account(self, account_id: int, user_id: int) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            has_frozen_at = self._column_exists(cursor, "rental_frozen_at")
            updates = ["owner = NULL", "rental_start = NULL", "rental_frozen = 0"]
            if has_frozen_at:
                updates.append("rental_frozen_at = NULL")
            cursor.execute(
                f"UPDATE accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s",
                (account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def extend_rental_duration(self, account_id: int, user_id: int, add_hours: int, add_minutes: int) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT rental_duration, rental_duration_minutes FROM accounts WHERE id = %s AND user_id = %s LIMIT 1",
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
            cursor.execute(
                """
                UPDATE accounts
                SET rental_duration = %s,
                    rental_duration_minutes = %s
                WHERE id = %s AND user_id = %s
                """,
                (total_hours, total_minutes, account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def set_account_frozen(self, account_id: int, user_id: int, frozen: bool) -> bool:
        conn = _pool.get_connection()
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

    def set_rental_freeze_state(
        self,
        account_id: int,
        user_id: int,
        frozen: bool,
        *,
        rental_start: Optional[str] = None,
        frozen_at: Optional[str] = None,
    ) -> bool:
        conn = _pool.get_connection()
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
            cursor.execute(
                f"UPDATE accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update_account(self, account_id: int, user_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = _pool.get_connection()
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

    def delete_account_by_id(self, account_id: int, user_id: int) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE id = %s AND user_id = %s", (account_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
