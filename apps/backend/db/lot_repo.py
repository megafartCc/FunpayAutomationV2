from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import get_base_connection


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


def _handle_primary_duplicate(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    *,
    workspace_id: int,
    lot_number: int,
    account_id: int,
) -> None:
    cursor.execute(
        "SELECT 1 FROM lots WHERE workspace_id = %s AND lot_number = %s LIMIT 1",
        (workspace_id, lot_number),
    )
    if cursor.fetchone():
        raise LotCreateError("duplicate_lot_number")
    cursor.execute(
        "SELECT 1 FROM lots WHERE workspace_id = %s AND account_id = %s LIMIT 1",
        (workspace_id, account_id),
    )
    if cursor.fetchone():
        raise LotCreateError("account_already_mapped")
    raise LotCreateError("duplicate")


def _cleanup_lot_unique_indexes(conn: mysql.connector.MySQLConnection) -> None:
    legacy_unique_names = {
        "uniq_account_user",
        "uniq_lot_user",
        "uniq_lot_user_id",
        "uniq_lot_user_number",
    }
    try:
        idx_cursor = conn.cursor(dictionary=True)
        idx_cursor.execute("SHOW INDEX FROM lots")
        index_cols: dict[str, list[tuple[int, str]]] = {}
        index_unique: dict[str, bool] = {}
        for row in idx_cursor.fetchall() or []:
            key = row["Key_name"]
            index_unique[key] = row["Non_unique"] == 0
            index_cols.setdefault(key, []).append((int(row["Seq_in_index"]), row["Column_name"]))
        desired_lot_unique = ["workspace_id", "lot_number"]
        desired_account_unique = ["workspace_id", "account_id"]
        cursor = conn.cursor()
        for key, cols in index_cols.items():
            if key == "PRIMARY":
                continue
            if not index_unique.get(key, False) and key not in legacy_unique_names:
                continue
            columns = [col for _, col in sorted(cols)]
            if columns in (desired_lot_unique, desired_account_unique):
                continue
            if index_unique.get(key, False) and "workspace_id" in columns:
                continue
            try:
                cursor.execute(f"ALTER TABLE lots DROP INDEX `{key}`")
            except mysql.connector.Error:
                pass
        existing_uniques = {
            tuple(col for _, col in sorted(cols))
            for key, cols in index_cols.items()
            if index_unique.get(key, False)
        }
        try:
            if tuple(desired_lot_unique) not in existing_uniques:
                cursor.execute(
                    "ALTER TABLE lots ADD UNIQUE KEY uniq_lot_workspace (workspace_id, lot_number)"
                )
        except mysql.connector.Error:
            pass
        try:
            if tuple(desired_account_unique) not in existing_uniques:
                cursor.execute(
                    "ALTER TABLE lots ADD UNIQUE KEY uniq_account_workspace (workspace_id, account_id)"
                )
        except mysql.connector.Error:
            pass
        conn.commit()
    except mysql.connector.Error:
        pass


class MySQLLotRepo:
    def _get_conn(self) -> mysql.connector.MySQLConnection:
        return get_base_connection()

    def list_by_user(self, user_id: int, workspace_id: int) -> List[LotRecord]:
        conn = self._get_conn()
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
        conn = self._get_conn()
        try:
            cursor_dict = conn.cursor(dictionary=True)
            cursor_dict.execute(
                "SELECT id, account_name, workspace_id FROM accounts WHERE id = %s AND user_id = %s LIMIT 1",
                (account_id, user_id),
            )
            account = cursor_dict.fetchone()
            if not account:
                raise LotCreateError("account_not_found")

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
                    try:
                        conn.rollback()
                    except mysql.connector.Error:
                        pass
                    dup_key = _extract_dup_key(exc)
                    if _dup_key_matches(dup_key, "uniq_lot_workspace"):
                        raise LotCreateError("duplicate_lot_number")
                    if _dup_key_matches(dup_key, "uniq_account_workspace"):
                        raise LotCreateError("account_already_mapped")
                    if _dup_key_matches(dup_key, "PRIMARY"):
                        _handle_primary_duplicate(
                            cursor_dict,
                            workspace_id=workspace_id,
                            lot_number=lot_number,
                            account_id=account_id,
                        )
                    _cleanup_lot_unique_indexes(conn)
                    try:
                        cursor.execute(
                            """
                            INSERT INTO lots (user_id, workspace_id, lot_number, account_id, lot_url)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (user_id, workspace_id, lot_number, account_id, lot_url),
                        )
                        conn.commit()
                    except mysql.connector.Error as retry_exc:
                        if retry_exc.errno == errorcode.ER_DUP_ENTRY:
                            retry_key = _extract_dup_key(retry_exc)
                            if _dup_key_matches(retry_key, "uniq_lot_workspace"):
                                raise LotCreateError("duplicate_lot_number")
                            if _dup_key_matches(retry_key, "uniq_account_workspace"):
                                raise LotCreateError("account_already_mapped")
                            raise LotCreateError("duplicate")
                        raise
                else:
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
        conn = self._get_conn()
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
