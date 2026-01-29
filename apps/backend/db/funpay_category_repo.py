from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from db import mysql


@dataclass
class FunpayCategoryCache:
    user_id: int
    payload: list[dict[str, Any]]


class MySQLFunpayCategoryCacheRepo:
    def get_cache(self, user_id: int) -> FunpayCategoryCache | None:
        conn = mysql.get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT payload FROM funpay_categories_cache WHERE user_id = %s LIMIT 1",
                (int(user_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            raw = row.get("payload") or "[]"
            try:
                payload = json.loads(raw)
            except Exception:
                payload = []
            return FunpayCategoryCache(user_id=int(user_id), payload=payload)
        finally:
            conn.close()

    def upsert_cache(self, user_id: int, payload: list[dict[str, Any]]) -> FunpayCategoryCache:
        conn = mysql.get_base_connection()
        try:
            cursor = conn.cursor()
            encoded = json.dumps(payload, ensure_ascii=False)
            cursor.execute(
                """
                INSERT INTO funpay_categories_cache (user_id, payload, updated_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE payload = VALUES(payload), updated_at = NOW()
                """,
                (int(user_id), encoded),
            )
            conn.commit()
            return FunpayCategoryCache(user_id=int(user_id), payload=payload)
        finally:
            conn.close()
