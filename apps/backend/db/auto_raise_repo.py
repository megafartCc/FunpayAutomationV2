from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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


class MySQLAutoRaiseRepo:
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
