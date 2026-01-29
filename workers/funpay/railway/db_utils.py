from __future__ import annotations

from urllib.parse import urlparse

import mysql.connector


_WORKSPACE_DB_CACHE: dict[int, str] = {}


def table_exists(cursor: mysql.connector.cursor.MySQLCursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
        (table,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor: mysql.connector.cursor.MySQLCursor, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s LIMIT 1",
        (table, column),
    )
    return cursor.fetchone() is not None


def get_mysql_config() -> dict:
    import os

    url = os.getenv("MYSQL_URL", "").strip()
    host = os.getenv("MYSQLHOST", "").strip()
    port = os.getenv("MYSQLPORT", "").strip() or "3306"
    user = os.getenv("MYSQLUSER", "").strip()
    password = os.getenv("MYSQLPASSWORD", "").strip()
    database = os.getenv("MYSQLDATABASE", "").strip() or os.getenv("MYSQL_DATABASE", "").strip()

    if url:
        parsed = urlparse(url)
        host = parsed.hostname or host
        if parsed.port:
            port = str(parsed.port)
        user = parsed.username or user
        password = parsed.password or password
        if parsed.path and parsed.path != "/":
            database = parsed.path.lstrip("/")

    if not database:
        raise RuntimeError("MySQL database name missing. Set MYSQLDATABASE or MYSQL_DATABASE.")

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
    }


def get_workspace_db_name(mysql_cfg: dict, workspace_id: int) -> str | None:
    cached = _WORKSPACE_DB_CACHE.get(workspace_id)
    if cached:
        return cached
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT db_name FROM workspaces WHERE id = %s", (workspace_id,))
        row = cursor.fetchone()
        db_name = (row or {}).get("db_name") or ""
        if db_name:
            _WORKSPACE_DB_CACHE[workspace_id] = db_name
            return db_name
        return None
    finally:
        conn.close()


def resolve_workspace_mysql_cfg(mysql_cfg: dict, workspace_id: int | None) -> dict:
    return mysql_cfg
