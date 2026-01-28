from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from db.mysql import _pool


def _parse_categories(raw: str | None) -> list[int]:
    if not raw:
        return []
    values: list[int] = []
    for token in str(raw).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except ValueError:
            continue
    return values


def _serialize_categories(values: list[int] | None) -> str:
    if not values:
        return ""
    cleaned: list[str] = []
    for item in values:
        try:
            cleaned.append(str(int(item)))
        except (TypeError, ValueError):
            continue
    return ",".join(cleaned)


@dataclass
class AutoRaiseSettingsRecord:
    user_id: int
    enabled: int
    categories: list[int]
    interval_hours: int
    updated_at: Optional[str] = None


@dataclass
class AutoRaiseHistoryRecord:
    id: int
    user_id: int
    workspace_id: int | None
    workspace_name: str | None
    category_id: int | None
    category_name: str | None
    status: str
    message: str | None
    created_at: Optional[str] = None


class MySQLAutoRaiseRepo:
    def get_settings(self, user_id: int) -> AutoRaiseSettingsRecord:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT user_id, enabled, categories, interval_hours, updated_at
                FROM auto_raise_settings
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return AutoRaiseSettingsRecord(
                    user_id=int(user_id),
                    enabled=0,
                    categories=[],
                    interval_hours=1,
                    updated_at=None,
                )
            return AutoRaiseSettingsRecord(
                user_id=int(row["user_id"]),
                enabled=int(row.get("enabled") or 0),
                categories=_parse_categories(row.get("categories")),
                interval_hours=max(1, int(row.get("interval_hours") or 1)),
                updated_at=str(row.get("updated_at")) if row.get("updated_at") is not None else None,
            )
        finally:
            conn.close()

    def upsert_settings(
        self,
        *,
        user_id: int,
        enabled: bool,
        categories: list[int] | None,
        interval_hours: int,
    ) -> AutoRaiseSettingsRecord:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO auto_raise_settings (user_id, enabled, categories, interval_hours)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    enabled = VALUES(enabled),
                    categories = VALUES(categories),
                    interval_hours = VALUES(interval_hours),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    int(user_id),
                    1 if enabled else 0,
                    _serialize_categories(categories),
                    max(1, int(interval_hours)),
                ),
            )
            conn.commit()
            return self.get_settings(user_id)
        finally:
            conn.close()

    def list_history(self, user_id: int, limit: int = 200) -> list[AutoRaiseHistoryRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT h.id, h.user_id, h.workspace_id, w.name AS workspace_name,
                       h.category_id, h.category_name, h.status, h.message, h.created_at
                FROM auto_raise_history h
                LEFT JOIN workspaces w ON w.id = h.workspace_id
                WHERE h.user_id = %s
                ORDER BY h.id DESC
                LIMIT %s
                """,
                (int(user_id), int(max(1, min(limit, 500)))),
            )
            rows = cursor.fetchall() or []
            return [
                AutoRaiseHistoryRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    workspace_id=int(row["workspace_id"]) if row.get("workspace_id") is not None else None,
                    workspace_name=row.get("workspace_name"),
                    category_id=int(row["category_id"]) if row.get("category_id") is not None else None,
                    category_name=row.get("category_name"),
                    status=row.get("status") or "",
                    message=row.get("message"),
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()
