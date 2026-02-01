from __future__ import annotations

import mysql.connector


def get_user_id_by_username(mysql_cfg: dict, username: str) -> int | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE username = %s LIMIT 1",
            (username.lower().strip(),),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


def get_workspace_by_golden_key(mysql_cfg: dict, golden_key: str) -> dict | None:
    key = (golden_key or "").strip()
    if not key:
        return None
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id AS workspace_id, user_id, name FROM workspaces WHERE golden_key = %s LIMIT 1",
            (key,),
        )
        return cursor.fetchone()
    finally:
        conn.close()
