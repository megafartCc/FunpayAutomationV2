from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from db.mysql import get_base_connection


@dataclass
class RaiseCategoryRecord:
    category_id: int
    category_name: str
    user_id: int
    workspace_id: Optional[int]
    updated_at: Optional[str]


class MySQLRaiseCategoryRepo:
    def list_by_user(self, user_id: int, workspace_id: int | None = None) -> list[RaiseCategoryRecord]:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            params: list[object] = [user_id]
            workspace_clause = ""
            if workspace_id is not None:
                workspace_clause = " AND workspace_id = %s"
                params.append(int(workspace_id))
            cursor.execute(
                f"""
                SELECT category_id, category_name, user_id, workspace_id, updated_at
                FROM raise_categories
                WHERE user_id = %s{workspace_clause}
                ORDER BY category_name
                """,
                tuple(params),
            )
            rows = cursor.fetchall() or []
            return [
                RaiseCategoryRecord(
                    category_id=int(row["category_id"]),
                    category_name=row["category_name"],
                    user_id=int(row["user_id"]),
                    workspace_id=int(row["workspace_id"]) if row.get("workspace_id") is not None else None,
                    updated_at=str(row.get("updated_at")) if row.get("updated_at") is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()
