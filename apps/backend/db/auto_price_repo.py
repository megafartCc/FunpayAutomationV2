from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from db.mysql import get_base_connection


@dataclass
class AutoPriceLogRecord:
    id: int
    level: str
    source: str | None
    line: int | None
    message: str
    user_id: int
    workspace_id: int | None
    created_at: str | None


@dataclass
class AutoPriceSettings:
    enabled: bool
    all_workspaces: bool
    interval_minutes: int
    premium_workspace_id: int | None
    premium_delta: float


class MySQLAutoPriceRepo:
    def get_settings(self, user_id: int) -> AutoPriceSettings:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'auto_price_settings'
                LIMIT 1
                """
            )
            if cursor.fetchone() is None:
                return AutoPriceSettings(
                    enabled=False,
                    all_workspaces=True,
                    interval_minutes=60,
                    premium_workspace_id=None,
                    premium_delta=0.75,
                )
            cursor.execute(
                """
                SELECT enabled, all_workspaces, interval_minutes, premium_workspace_id, premium_delta
                FROM auto_price_settings
                WHERE user_id = %s
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            if not row:
                return AutoPriceSettings(
                    enabled=False,
                    all_workspaces=True,
                    interval_minutes=60,
                    premium_workspace_id=None,
                    premium_delta=0.75,
                )
            return AutoPriceSettings(
                enabled=bool(row.get("enabled")),
                all_workspaces=bool(row.get("all_workspaces", True)),
                interval_minutes=int(row.get("interval_minutes") or 60),
                premium_workspace_id=int(row["premium_workspace_id"])
                if row.get("premium_workspace_id") is not None
                else None,
                premium_delta=float(row.get("premium_delta") or 0.75),
            )
        finally:
            conn.close()

    def save_settings(self, user_id: int, settings: AutoPriceSettings) -> None:
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'auto_price_settings'
                LIMIT 1
                """
            )
            if cursor.fetchone() is None:
                return
            next_run = None
            if settings.enabled:
                next_run = datetime.utcnow() + timedelta(seconds=5)
            cursor.execute(
                """
                INSERT INTO auto_price_settings (
                    user_id, enabled, all_workspaces, interval_minutes,
                    premium_workspace_id, premium_delta, next_run_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    enabled = VALUES(enabled),
                    all_workspaces = VALUES(all_workspaces),
                    interval_minutes = VALUES(interval_minutes),
                    premium_workspace_id = VALUES(premium_workspace_id),
                    premium_delta = VALUES(premium_delta),
                    next_run_at = VALUES(next_run_at)
                """,
                (
                    int(user_id),
                    1 if settings.enabled else 0,
                    1 if settings.all_workspaces else 0,
                    int(settings.interval_minutes),
                    settings.premium_workspace_id,
                    float(settings.premium_delta),
                    next_run,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_logs(self, user_id: int, workspace_id: int | None = None, limit: int = 200) -> list[AutoPriceLogRecord]:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            workspace_clause = ""
            params: list = [int(user_id)]
            if workspace_id is not None:
                workspace_clause = " AND workspace_id = %s"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT id, level, source, line, message, user_id, workspace_id, created_at
                FROM auto_price_logs
                WHERE user_id = %s{workspace_clause}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (*params, int(limit)),
            )
            rows = cursor.fetchall() or []
            return [
                AutoPriceLogRecord(
                    id=int(row["id"]),
                    level=str(row.get("level") or "info"),
                    source=row.get("source"),
                    line=int(row["line"]) if row.get("line") is not None else None,
                    message=str(row.get("message") or ""),
                    user_id=int(row.get("user_id") or user_id),
                    workspace_id=int(row["workspace_id"]) if row.get("workspace_id") is not None else None,
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def log(
        self,
        *,
        user_id: int,
        level: str,
        message: str,
        workspace_id: int | None = None,
        source: str | None = None,
        line: int | None = None,
    ) -> None:
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO auto_price_logs (user_id, workspace_id, level, source, line, message)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    str(level or "info"),
                    source,
                    line,
                    message,
                ),
            )
            conn.commit()
        finally:
            conn.close()
