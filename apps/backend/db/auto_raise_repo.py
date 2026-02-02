from __future__ import annotations

from dataclasses import dataclass
from db.mysql import get_base_connection


@dataclass
class AutoRaiseLogRecord:
    id: int
    level: str
    source: str | None
    line: int | None
    message: str
    user_id: int
    workspace_id: int | None
    created_at: str | None


@dataclass
class AutoRaiseSettings:
    enabled: bool
    all_workspaces: bool
    interval_minutes: int
    workspaces: dict[int, bool]


class MySQLAutoRaiseRepo:
    def get_settings(self, user_id: int) -> AutoRaiseSettings:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'auto_raise_settings'
                LIMIT 1
                """
            )
            if cursor.fetchone() is None:
                return AutoRaiseSettings(
                    enabled=False,
                    all_workspaces=True,
                    interval_minutes=120,
                    workspaces={},
                )
            cursor.execute(
                """
                SELECT *
                FROM auto_raise_settings
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            rows = cursor.fetchall() or []
            if not rows:
                return AutoRaiseSettings(
                    enabled=False,
                    all_workspaces=True,
                    interval_minutes=120,
                    workspaces={},
                )
            if "workspace_id" not in rows[0]:
                row = rows[-1]
                return AutoRaiseSettings(
                    enabled=bool(row.get("enabled")),
                    all_workspaces=bool(row.get("all_workspaces", True)),
                    interval_minutes=int(row.get("interval_minutes") or 120),
                    workspaces={},
                )
            enabled = False
            all_workspaces = True
            interval_minutes = 120
            workspaces: dict[int, bool] = {}
            for row in rows:
                workspace_id = row.get("workspace_id")
                if workspace_id is None:
                    enabled = bool(row.get("enabled"))
                    all_workspaces = bool(row.get("all_workspaces"))
                    interval_minutes = int(row.get("interval_minutes") or 120)
                else:
                    workspaces[int(workspace_id)] = bool(row.get("enabled"))
            return AutoRaiseSettings(
                enabled=enabled,
                all_workspaces=all_workspaces,
                interval_minutes=interval_minutes,
                workspaces=workspaces,
            )
        finally:
            conn.close()

    def save_settings(self, user_id: int, settings: AutoRaiseSettings) -> None:
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'auto_raise_settings'
                LIMIT 1
                """
            )
            if cursor.fetchone() is None:
                return
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'auto_raise_settings'
                  AND column_name = 'workspace_id'
                LIMIT 1
                """
            )
            has_workspace_id = cursor.fetchone() is not None
            if not has_workspace_id:
                cursor.execute(
                    """
                    INSERT INTO auto_raise_settings (user_id, enabled, all_workspaces, interval_minutes)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        enabled = VALUES(enabled),
                        all_workspaces = VALUES(all_workspaces),
                        interval_minutes = VALUES(interval_minutes)
                    """,
                    (
                        int(user_id),
                        1 if settings.enabled else 0,
                        1 if settings.all_workspaces else 0,
                        int(settings.interval_minutes),
                    ),
                )
                conn.commit()
                return
            cursor.execute(
                """
                INSERT INTO auto_raise_settings (user_id, workspace_id, enabled, all_workspaces, interval_minutes)
                VALUES (%s, NULL, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    enabled = VALUES(enabled),
                    all_workspaces = VALUES(all_workspaces),
                    interval_minutes = VALUES(interval_minutes)
                """,
                (
                    int(user_id),
                    1 if settings.enabled else 0,
                    1 if settings.all_workspaces else 0,
                    int(settings.interval_minutes),
                ),
            )
            cursor.execute(
                "DELETE FROM auto_raise_settings WHERE user_id = %s AND workspace_id IS NOT NULL",
                (int(user_id),),
            )
            if settings.workspaces:
                rows = [
                    (
                        int(user_id),
                        int(workspace_id),
                        1 if enabled else 0,
                        0,
                        int(settings.interval_minutes),
                    )
                    for workspace_id, enabled in settings.workspaces.items()
                ]
                cursor.executemany(
                    """
                    INSERT INTO auto_raise_settings (user_id, workspace_id, enabled, all_workspaces, interval_minutes)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        enabled = VALUES(enabled),
                        all_workspaces = VALUES(all_workspaces),
                        interval_minutes = VALUES(interval_minutes)
                    """,
                    rows,
                )
            conn.commit()
        finally:
            conn.close()

    def list_logs(
        self,
        user_id: int,
        workspace_id: int | None = None,
        limit: int = 200,
    ) -> list[AutoRaiseLogRecord]:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list[object] = [int(user_id)]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND workspace_id = %s"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT id, level, source, line, message, user_id, workspace_id, created_at
                FROM auto_raise_logs
                WHERE user_id = %s{workspace_clause}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (*params, int(limit)),
            )
            rows = cursor.fetchall() or []
            return [
                AutoRaiseLogRecord(
                    id=int(row["id"]),
                    level=row.get("level") or "info",
                    source=row.get("source"),
                    line=int(row["line"]) if row.get("line") is not None else None,
                    message=row.get("message") or "",
                    user_id=int(row["user_id"]),
                    workspace_id=int(row["workspace_id"]) if row.get("workspace_id") is not None else None,
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def create_requests(
        self,
        user_id: int,
        workspace_ids: list[int] | None,
        message: str | None = None,
    ) -> int:
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            ids = workspace_ids if workspace_ids is not None and len(workspace_ids) > 0 else [None]
            rows = [
                (int(user_id), int(ws_id) if ws_id is not None else None, "pending", message)
                for ws_id in ids
            ]
            cursor.executemany(
                """
                INSERT INTO auto_raise_requests (user_id, workspace_id, status, message)
                VALUES (%s, %s, %s, %s)
                """,
                rows,
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
