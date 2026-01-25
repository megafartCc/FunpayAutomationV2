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


class MySQLAccountRepo:
    def _column_exists(self, cursor: mysql.connector.cursor.MySQLCursor, column: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'accounts' AND column_name = %s LIMIT 1",
            (column,),
        )
        return cursor.fetchone() is not None

    def list_by_user(self, user_id: int) -> List[AccountRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, account_name, login, password, lot_url, mmr,
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
