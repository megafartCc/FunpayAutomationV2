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
