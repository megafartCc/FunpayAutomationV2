from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from db.mysql import _pool


@dataclass
class WorkspaceStatusRecord:
    user_id: int
    workspace_id: Optional[int]
    platform: str
    status: str
    message: Optional[str]
    updated_at: Optional[str] = None


class MySQLWorkspaceStatusRepo:
    def list_by_user(
        self,
        user_id: int,
        workspace_id: int | None = None,
        platform: str | None = None,
    ) -> list[WorkspaceStatusRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            clauses = ["user_id = %s"]
            params: list = [user_id]
            if workspace_id is not None:
                clauses.append("workspace_id = %s")
                params.append(workspace_id)
            if platform:
                clauses.append("platform = %s")
                params.append(platform)
            where_clause = " AND ".join(clauses)
            cursor.execute(
                f"""
                SELECT user_id, workspace_id, platform, status, message, updated_at
                FROM workspace_status
                WHERE {where_clause}
                ORDER BY updated_at DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall() or []
            return [
                WorkspaceStatusRecord(
                    user_id=int(row["user_id"]),
                    workspace_id=int(row["workspace_id"]) if row.get("workspace_id") is not None else None,
                    platform=row.get("platform") or "funpay",
                    status=row.get("status") or "",
                    message=row.get("message"),
                    updated_at=str(row.get("updated_at")) if row.get("updated_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()
