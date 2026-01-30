from __future__ import annotations

import hashlib
import secrets
from typing import Any

from db.mysql import get_base_connection


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MySQLTelegramRepo:
    def get_status(self, user_id: int) -> dict[str, Any]:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT token_hint, chat_id, verified_at, created_at, updated_at
                FROM telegram_links
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "token_hint": None,
                    "chat_id": None,
                    "verified_at": None,
                    "created_at": None,
                    "updated_at": None,
                }
            return {
                "token_hint": row.get("token_hint"),
                "chat_id": row.get("chat_id"),
                "verified_at": row.get("verified_at"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        finally:
            conn.close()

    def create_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(24)
        token_hash = _hash_token(token)
        token_hint = token[-6:]
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO telegram_links (user_id, token_hash, token_hint, chat_id, verified_at)
                VALUES (%s, %s, %s, NULL, NULL)
                ON DUPLICATE KEY UPDATE
                    token_hash = VALUES(token_hash),
                    token_hint = VALUES(token_hint),
                    chat_id = NULL,
                    verified_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (int(user_id), token_hash, token_hint),
            )
            conn.commit()
        finally:
            conn.close()
        return token

    def verify_token(self, token: str, chat_id: int) -> int | None:
        token_hash = _hash_token(token)
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT user_id
                FROM telegram_links
                WHERE token_hash = %s
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            user_id = int(row["user_id"])
            cursor.execute(
                """
                UPDATE telegram_links
                SET chat_id = %s, verified_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                """,
                (int(chat_id), user_id),
            )
            conn.commit()
            return user_id
        finally:
            conn.close()

    def disconnect(self, user_id: int) -> None:
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE telegram_links
                SET chat_id = NULL, verified_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            conn.commit()
        finally:
            conn.close()
