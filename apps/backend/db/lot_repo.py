from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import get_workspace_connection


@dataclass
class LotRecord:
    lot_number: int
    account_id: int
    account_name: str
    lot_url: Optional[str]
    workspace_id: int | None = None


class LotCreateError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_DUP_KEY_RE = re.compile(r"for key '([^']+)'")


def _extract_dup_key(exc: mysql.connector.Error) -> str | None:
    msg = getattr(exc, "msg", "") or ""
    match = _DUP_KEY_RE.search(msg)
    if match:
        return match.group(1)
    return None


def _dup_key_matches(dup_key: str | None, expected: str) -> bool:
    if not dup_key:
        return False
    if dup_key == expected:
        return True
    return dup_key.endswith(f".{expected}")


class MySQLLotRepo:
    def _get_conn(self, workspace_id: int) -> mysql.connector.MySQLConnection:
        return get_workspace_connection(workspace_id)

    def list_by_user(self, user_id: int, workspace_id: int) -> List[LotRecord]:
        conn = self._get_conn(workspace_id)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT l.lot_number, l.account_id, l.lot_url, a.account_name, l.workspace_id
                FROM lots l
                JOIN accounts a ON a.id = l.account_id
                WHERE l.user_id = %s AND l.workspace_id = %s
                ORDER BY l.lot_number
                """,
                (user_id, workspace_id),
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
    ) -> LotRecord:
        conn = self._get_conn(workspace_id)
        try:
            cursor_dict = conn.cursor(dictionary=True)
            cursor_dict.execute(
                "SELECT id, account_name, workspace_id FROM accounts WHERE id = %s AND user_id = %s LIMIT 1",
                (account_id, user_id),
            )
            account = cursor_dict.fetchone()
            if not account:
                raise LotCreateError("account_not_found")
            # auto-attach account to workspace if it was missing
            account_workspace_id = account.get("workspace_id")
            if account_workspace_id is None:
                cursor_update = conn.cursor()
                cursor_update.execute(
                    "UPDATE accounts SET workspace_id = %s WHERE id = %s AND user_id = %s",
                    (workspace_id, account_id, user_id),
                )
                conn.commit()
                account_workspace_id = workspace_id
                account["workspace_id"] = workspace_id
            if int(account_workspace_id or 0) != int(workspace_id):
                raise LotCreateError("account_wrong_workspace")

            cursor_dict.execute(
                "SELECT 1 FROM lots WHERE workspace_id = %s AND lot_number = %s LIMIT 1",
                (workspace_id, lot_number),
            )
            if cursor_dict.fetchone():
                raise LotCreateError("duplicate_lot_number")

            cursor_dict.execute(
                "SELECT 1 FROM lots WHERE workspace_id = %s AND account_id = %s LIMIT 1",
                (workspace_id, account_id),
            )
            if cursor_dict.fetchone():
                raise LotCreateError("account_already_mapped")

            cursor = conn.cursor()
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
                    dup_key = _extract_dup_key(exc)
                    if _dup_key_matches(dup_key, "uniq_lot_workspace"):
                        raise LotCreateError("duplicate_lot_number")
                    if _dup_key_matches(dup_key, "uniq_account_workspace"):
                        raise LotCreateError("account_already_mapped")
                    raise LotCreateError("duplicate")
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

    def delete(self, user_id: int, lot_number: int, workspace_id: int) -> bool:
        conn = self._get_conn(workspace_id)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM lots WHERE user_id = %s AND lot_number = %s AND workspace_id = %s",
                (user_id, lot_number, workspace_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
