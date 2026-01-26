from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import mysql.connector
from mysql.connector import errorcode

from db.mysql import _pool, provision_workspace_schema


@dataclass
class WorkspaceRecord:
    id: int
    user_id: int
    name: str
    golden_key: str
    proxy_url: str
    is_default: int
    created_at: Optional[str] = None
    db_name: Optional[str] = None


class MySQLWorkspaceRepo:
    def list_by_user(self, user_id: int) -> list[WorkspaceRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, name, golden_key, proxy_url, is_default, created_at, db_name
                FROM workspaces
                WHERE user_id = %s
                ORDER BY is_default DESC, id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall() or []
            return [
                WorkspaceRecord(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    name=row["name"],
                    golden_key=row.get("golden_key") or "",
                    proxy_url=row.get("proxy_url") or "",
                    is_default=int(row.get("is_default") or 0),
                    created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                    db_name=row.get("db_name"),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_by_id(self, workspace_id: int, user_id: int) -> Optional[WorkspaceRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, user_id, name, golden_key, proxy_url, is_default, created_at, db_name
                FROM workspaces
                WHERE id = %s AND user_id = %s
                LIMIT 1
                """,
                (workspace_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return WorkspaceRecord(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                name=row["name"],
                golden_key=row.get("golden_key") or "",
                proxy_url=row.get("proxy_url") or "",
                is_default=int(row.get("is_default") or 0),
                created_at=str(row.get("created_at")) if row.get("created_at") is not None else None,
                db_name=row.get("db_name"),
            )
        finally:
            conn.close()

    def create(
        self,
        *,
        user_id: int,
        name: str,
        golden_key: str,
        proxy_url: str,
        is_default: bool = False,
    ) -> Optional[WorkspaceRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO workspaces (user_id, name, golden_key, proxy_url, is_default)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, name, golden_key, proxy_url, 1 if is_default else 0),
                )
                workspace_id = cursor.lastrowid
                if is_default:
                    cursor.execute(
                        "UPDATE workspaces SET is_default = 0 WHERE user_id = %s AND id != %s",
                        (user_id, workspace_id),
                    )
                conn.commit()
            except mysql.connector.Error as exc:
                if exc.errno == errorcode.ER_DUP_ENTRY:
                    return None
                raise

            provision_workspace_schema(int(workspace_id))
            return self.get_by_id(int(workspace_id), user_id)
        finally:
            conn.close()

    def update(
        self,
        *,
        workspace_id: int,
        user_id: int,
        fields: dict,
        make_default: bool | None = None,
    ) -> bool:
        if not fields and make_default is None:
            return False
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            if fields:
                columns = []
                values = []
                for key, value in fields.items():
                    columns.append(f"{key} = %s")
                    values.append(value)
                values.extend([workspace_id, user_id])
                cursor.execute(
                    f"UPDATE workspaces SET {', '.join(columns)} WHERE id = %s AND user_id = %s",
                    tuple(values),
                )
            if make_default:
                cursor.execute(
                    "UPDATE workspaces SET is_default = 0 WHERE user_id = %s AND id != %s",
                    (user_id, workspace_id),
                )
                cursor.execute(
                    "UPDATE workspaces SET is_default = 1 WHERE id = %s AND user_id = %s",
                    (workspace_id, user_id),
                )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def set_default(self, workspace_id: int, user_id: int) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE workspaces SET is_default = 0 WHERE user_id = %s AND id != %s",
                (user_id, workspace_id),
            )
            cursor.execute(
                "UPDATE workspaces SET is_default = 1 WHERE id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, workspace_id: int, user_id: int) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT is_default FROM workspaces WHERE id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return False
            is_default = int(row.get("is_default") or 0)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM workspaces WHERE id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            if is_default:
                cursor.execute(
                    "SELECT id FROM workspaces WHERE user_id = %s ORDER BY id DESC LIMIT 1",
                    (user_id,),
                )
                next_row = cursor.fetchone()
                if next_row:
                    next_id = int(next_row[0])
                    cursor.execute(
                        "UPDATE workspaces SET is_default = 1 WHERE id = %s AND user_id = %s",
                        (next_id, user_id),
                    )
            conn.commit()
            return True
        finally:
            conn.close()
