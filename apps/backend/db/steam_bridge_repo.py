from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

import mysql.connector

from db.mysql import get_base_connection


@dataclass
class SteamBridgeAccountRecord:
    id: int
    user_id: int
    label: str | None
    login_enc: str
    password_enc: str
    shared_secret_enc: str | None
    is_default: int
    status: str
    last_error: str | None
    last_seen: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class MySQLSteamBridgeRepo:
    def _get_conn(self) -> mysql.connector.MySQLConnection:
        return get_base_connection()

    def list_by_user(self, user_id: int) -> List[SteamBridgeAccountRecord]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, label, login_enc, password_enc, shared_secret_enc,
                       is_default, status, last_error, last_seen, created_at, updated_at
                FROM steam_bridge_accounts
                WHERE user_id = %s
                ORDER BY is_default DESC, updated_at DESC, id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall() or []
            return [
                SteamBridgeAccountRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    label=row.get("label"),
                    login_enc=row["login_enc"],
                    password_enc=row["password_enc"],
                    shared_secret_enc=row.get("shared_secret_enc"),
                    is_default=int(row.get("is_default") or 0),
                    status=row.get("status") or "offline",
                    last_error=row.get("last_error"),
                    last_seen=row.get("last_seen"),
                    created_at=row.get("created_at"),
                    updated_at=row.get("updated_at"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_by_id(self, account_id: int, user_id: int) -> Optional[SteamBridgeAccountRecord]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, label, login_enc, password_enc, shared_secret_enc,
                       is_default, status, last_error, last_seen, created_at, updated_at
                FROM steam_bridge_accounts
                WHERE id = %s AND user_id = %s
                LIMIT 1
                """,
                (account_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return SteamBridgeAccountRecord(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                label=row.get("label"),
                login_enc=row["login_enc"],
                password_enc=row["password_enc"],
                shared_secret_enc=row.get("shared_secret_enc"),
                is_default=int(row.get("is_default") or 0),
                status=row.get("status") or "offline",
                last_error=row.get("last_error"),
                last_seen=row.get("last_seen"),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
        finally:
            conn.close()

    def create(
        self,
        *,
        user_id: int,
        label: str | None,
        login_enc: str,
        password_enc: str,
        shared_secret_enc: str | None,
        is_default: bool,
    ) -> SteamBridgeAccountRecord:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if is_default:
                cursor.execute(
                    "UPDATE steam_bridge_accounts SET is_default = 0 WHERE user_id = %s",
                    (user_id,),
                )
            cursor.execute(
                """
                INSERT INTO steam_bridge_accounts
                    (user_id, label, login_enc, password_enc, shared_secret_enc, is_default, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'offline')
                """,
                (
                    user_id,
                    label,
                    login_enc,
                    password_enc,
                    shared_secret_enc,
                    1 if is_default else 0,
                ),
            )
            conn.commit()
            new_id = int(cursor.lastrowid)
        finally:
            conn.close()
        record = self.get_by_id(new_id, user_id)
        assert record is not None
        return record

    def update(
        self,
        account_id: int,
        user_id: int,
        *,
        label: str | None = None,
        login_enc: str | None = None,
        password_enc: str | None = None,
        shared_secret_enc: str | None = None,
        is_default: bool | None = None,
        status: str | None = None,
        last_error: str | None = None,
        last_seen: datetime | None = None,
    ) -> Optional[SteamBridgeAccountRecord]:
        updates = []
        params: list = []
        if label is not None:
            updates.append("label = %s")
            params.append(label)
        if login_enc is not None:
            updates.append("login_enc = %s")
            params.append(login_enc)
        if password_enc is not None:
            updates.append("password_enc = %s")
            params.append(password_enc)
        if shared_secret_enc is not None:
            updates.append("shared_secret_enc = %s")
            params.append(shared_secret_enc)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if last_error is not None:
            updates.append("last_error = %s")
            params.append(last_error)
        if last_seen is not None:
            updates.append("last_seen = %s")
            params.append(last_seen)
        if is_default is not None:
            updates.append("is_default = %s")
            params.append(1 if is_default else 0)
        if not updates:
            return self.get_by_id(account_id, user_id)
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if is_default:
                cursor.execute(
                    "UPDATE steam_bridge_accounts SET is_default = 0 WHERE user_id = %s",
                    (user_id,),
                )
            cursor.execute(
                f"UPDATE steam_bridge_accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s",
                (*params, account_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_by_id(account_id, user_id)

    def set_default(self, account_id: int, user_id: int) -> Optional[SteamBridgeAccountRecord]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE steam_bridge_accounts SET is_default = 0 WHERE user_id = %s",
                (user_id,),
            )
            cursor.execute(
                "UPDATE steam_bridge_accounts SET is_default = 1 WHERE id = %s AND user_id = %s",
                (account_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_by_id(account_id, user_id)

    def delete(self, account_id: int, user_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM steam_bridge_accounts WHERE id = %s AND user_id = %s",
                (account_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_default_id(self, user_id: int) -> Optional[int]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM steam_bridge_accounts WHERE user_id = %s AND is_default = 1 ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                return int(row[0])
            cursor.execute(
                "SELECT id FROM steam_bridge_accounts WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] else None
        finally:
            conn.close()
