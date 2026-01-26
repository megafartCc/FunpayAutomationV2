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
    workspace_id: int | None = None


class MySQLLotRepo:
    def list_by_user(self, user_id: int, workspace_id: int | None = None) -> List[LotRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list = [user_id]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
                params.append(workspace_id)
            cursor.execute(
                f"""
                SELECT l.lot_number, l.account_id, l.lot_url, a.account_name, l.workspace_id
                FROM lots l
                JOIN accounts a ON a.id = l.account_id
                WHERE l.user_id = %s{workspace_clause}
                ORDER BY l.lot_number
                """,
                tuple(params),
            )
            rows = cursor.fetchall() or []
            return [
                LotRecord(
                    lot_number=int(row["lot_number"]),
                    account_id=int(row["account_id"]),
                    account_name=row["account_name"],
                    lot_url=row.get("lot_url"),
                    workspace_id=row.get("workspace_id"),
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
        lot_number: int,
        account_id: int,
        lot_url: Optional[str],
    ) -> Optional[LotRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, account_name, workspace_id FROM accounts WHERE id = %s AND user_id = %s LIMIT 1",
                (account_id, user_id),
            )
            account = cursor.fetchone()
            if not account:
                return None
            if workspace_id is not None and account.get("workspace_id") and int(account["workspace_id"]) != int(workspace_id):
                return None

            cursor = conn.cursor()
            # If creating global mapping (workspace_id is None), ensure only one global per user/lot
            if workspace_id is None:
                cursor.execute(
                    "DELETE FROM lots WHERE user_id = %s AND lot_number = %s AND workspace_id IS NULL",
                    (user_id, lot_number),
                )
            try:
                cursor.execute(
                    """
                    INSERT INTO lots (user_id, workspace_id, lot_number, account_id, lot_url)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, workspace_id, lot_number, account_id, lot_url),
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
                workspace_id=workspace_id,
            )
        finally:
            conn.close()

    def delete(self, user_id: int, lot_number: int, workspace_id: int | None = None) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            params: list = [user_id, lot_number]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND workspace_id = %s"
                params.append(workspace_id)
            cursor.execute(
                f"DELETE FROM lots WHERE user_id = %s AND lot_number = %s{workspace_clause}",
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
