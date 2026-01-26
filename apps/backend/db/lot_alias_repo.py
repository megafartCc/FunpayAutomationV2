from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import get_workspace_connection


@dataclass
class LotAliasRecord:
    id: int
    user_id: int
    workspace_id: int | None
    lot_number: int
    funpay_url: str


class MySQLLotAliasRepo:
    def _get_conn(self, workspace_id: int) -> mysql.connector.MySQLConnection:
        return get_workspace_connection(workspace_id)

    def list_by_user(self, user_id: int, workspace_id: int | None = None) -> List[LotAliasRecord]:
        if workspace_id is None:
            return []
        conn = self._get_conn(workspace_id)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, workspace_id, lot_number, funpay_url
                FROM lot_aliases
                WHERE user_id = %s AND workspace_id = %s
                ORDER BY lot_number, id
                """,
                (user_id, workspace_id),
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
        if workspace_id is None:
            return None
        conn = self._get_conn(workspace_id)
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
        return False

    def delete_in_workspace(self, alias_id: int, user_id: int, workspace_id: int) -> bool:
        conn = self._get_conn(workspace_id)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM lot_aliases WHERE id = %s AND user_id = %s AND workspace_id = %s",
                (alias_id, user_id, workspace_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def replace_for_lot(
        self, *, user_id: int, workspace_id: int | None, lot_number: int, urls: list[str]
    ) -> None:
        if workspace_id is None:
            return
        conn = self._get_conn(workspace_id)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM lot_aliases WHERE user_id = %s AND lot_number = %s AND workspace_id = %s",
                (user_id, lot_number, workspace_id),
            )
            for url in urls:
                cursor.execute(
                    """
                    INSERT IGNORE INTO lot_aliases (user_id, workspace_id, lot_number, funpay_url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, workspace_id, lot_number, url),
                )
            conn.commit()
        finally:
            conn.close()
