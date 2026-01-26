from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import _pool


@dataclass
class LotAliasRecord:
    id: int
    user_id: int
    workspace_id: int | None
    lot_number: int
    funpay_url: str


class MySQLLotAliasRepo:
    def list_by_user(self, user_id: int, workspace_id: int | None = None) -> List[LotAliasRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list = [user_id]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND workspace_id = %s"
                params.append(workspace_id)
            cursor.execute(
                f"""
                SELECT id, user_id, workspace_id, lot_number, funpay_url
                FROM lot_aliases
                WHERE user_id = %s{workspace_clause}
                ORDER BY lot_number, id
                """,
                tuple(params),
            )
            rows = cursor.fetchall() or []
            return [
                LotAliasRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    workspace_id=row.get("workspace_id"),
                    lot_number=int(row["lot_number"]),
                    funpay_url=row["funpay_url"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def create(
        self,
        *,
        user_id: int,
        workspace_id: int | None,
        lot_number: int,
        funpay_url: str,
    ) -> Optional[LotAliasRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO lot_aliases (user_id, workspace_id, lot_number, funpay_url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, workspace_id, lot_number, funpay_url),
                )
                conn.commit()
            except mysql.connector.Error as exc:
                if exc.errno == errorcode.ER_DUP_ENTRY:
                    return None
                raise
            alias_id = cursor.lastrowid
            return LotAliasRecord(
                id=int(alias_id),
                user_id=user_id,
                workspace_id=workspace_id,
                lot_number=lot_number,
                funpay_url=funpay_url,
            )
        finally:
            conn.close()

    def delete(self, alias_id: int, user_id: int) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM lot_aliases WHERE id = %s AND user_id = %s",
                (alias_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

