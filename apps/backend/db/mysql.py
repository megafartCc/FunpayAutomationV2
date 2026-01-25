from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

import mysql.connector
from mysql.connector import pooling
from mysql.connector import errorcode

from db.user_repo import UserRecord


class MySQLPool:
    def __init__(self) -> None:
        self._pool: Optional[pooling.MySQLConnectionPool] = None

    def init_pool(self) -> None:
        if self._pool is not None:
            return
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

        self._pool = pooling.MySQLConnectionPool(
            pool_name="funpay_pool",
            pool_size=int(os.getenv("MYSQL_POOL_SIZE", "5")),
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )

    def get_connection(self) -> mysql.connector.MySQLConnection:
        if self._pool is None:
            self.init_pool()
        assert self._pool is not None
        return self._pool.get_connection()


_pool = MySQLPool()


def ensure_schema() -> None:
    conn = _pool.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(128) NOT NULL UNIQUE,
                email VARCHAR(255) NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                golden_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL UNIQUE;")
        except mysql.connector.Error as exc:
            if exc.errno != errorcode.ER_DUP_FIELDNAME:
                raise
        conn.commit()
    finally:
        conn.close()


class MySQLUserRepo:
    def get_by_username(self, username: str) -> Optional[UserRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT username, password_hash, golden_key, email "
                "FROM users WHERE username = %s OR email = %s LIMIT 1",
                (username.lower().strip(), username.lower().strip()),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return UserRecord(
                username=row["username"],
                password_hash=row["password_hash"],
                golden_key=row["golden_key"],
                email=row.get("email"),
            )
        finally:
            conn.close()

    def create(self, record: UserRecord) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, golden_key) VALUES (%s, %s, %s, %s)",
                    (
                        record.username.lower().strip(),
                        (record.email.lower().strip() if record.email else None),
                        record.password_hash,
                        record.golden_key,
                    ),
                )
                conn.commit()
                return True
            except mysql.connector.Error as exc:
                if exc.errno == errorcode.ER_DUP_ENTRY:
                    return False
                raise
        finally:
            conn.close()
