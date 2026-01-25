from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import _pool


@dataclass
class LotRecord:
    lot_number: int
    account_id: int
    account_name: str
    lot_url: Optional[str]


class MySQLLotRepo:
    def list_by_user(self, user_id: int) -> List[LotRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT l.lot_number, l.account_id, l.lot_url, a.account_name
                FROM lots l
                JOIN accounts a ON a.id = l.account_id
                WHERE l.user_id = %s
                ORDER BY l.lot_number
                """,
                (user_id,),
            )
            rows = cursor.fetchall() or []
            return [
                LotRecord(
                    lot_number=int(row["lot_number"]),
                    account_id=int(row["account_id"]),
                    account_name=row["account_name"],
                    lot_url=row.get("lot_url"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def create(
        self,
        *,
        user_id: int,
        lot_number: int,
        account_id: int,
        lot_url: Optional[str],
    ) -> Optional[LotRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, account_name FROM accounts WHERE id = %s AND user_id = %s LIMIT 1",
                (account_id, user_id),
            )
            account = cursor.fetchone()
            if not account:
                return None

            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO lots (user_id, lot_number, account_id, lot_url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, lot_number, account_id, lot_url),
                )
                conn.commit()
            except mysql.connector.Error as exc:
                if exc.errno == errorcode.ER_DUP_ENTRY:
                    return None
                raise

            return LotRecord(
                lot_number=int(lot_number),
                account_id=int(account_id),
                account_name=account["account_name"],
                lot_url=lot_url,
            )
        finally:
            conn.close()

    def delete(self, user_id: int, lot_number: int) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM lots WHERE user_id = %s AND lot_number = %s",
                (user_id, lot_number),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
