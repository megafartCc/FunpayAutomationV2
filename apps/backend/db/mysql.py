from __future__ import annotations

import os
from typing import Optional

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
        self._pool = pooling.MySQLConnectionPool(
            pool_name="funpay_pool",
            pool_size=int(os.getenv("MYSQL_POOL_SIZE", "5")),
            host=os.getenv("MYSQLHOST", ""),
            port=int(os.getenv("MYSQLPORT", "3306")),
            user=os.getenv("MYSQLUSER", ""),
            password=os.getenv("MYSQLPASSWORD", ""),
            database=os.getenv("MYSQLDATABASE", ""),
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
                password_hash VARCHAR(255) NOT NULL,
                golden_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        conn.commit()
    finally:
        conn.close()


class MySQLUserRepo:
    def get_by_username(self, username: str) -> Optional[UserRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT username, password_hash, golden_key FROM users WHERE username = %s",
                (username.lower().strip(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return UserRecord(
                username=row["username"],
                password_hash=row["password_hash"],
                golden_key=row["golden_key"],
            )
        finally:
            conn.close()

    def create(self, record: UserRecord) -> bool:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, golden_key) VALUES (%s, %s, %s)",
                    (
                        record.username.lower().strip(),
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
