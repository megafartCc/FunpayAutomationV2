from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

import mysql.connector
from mysql.connector import errorcode, pooling

from db.user_repo import UserRecord


class MySQLPool:
    def __init__(self) -> None:
        self._pool: Optional[pooling.MySQLConnectionPool] = None

    def init_pool(self) -> None:
        if self._pool is not None:
            return
        settings = _load_mysql_settings()

        self._pool = pooling.MySQLConnectionPool(
            pool_name="funpay_pool",
            pool_size=int(os.getenv("MYSQL_POOL_SIZE", "30")),
            host=settings["host"],
            port=int(settings["port"]),
            user=settings["user"],
            password=settings["password"],
            database=settings["database"],
        )

    def get_connection(self) -> mysql.connector.MySQLConnection:
        if self._pool is None:
            self.init_pool()
        assert self._pool is not None
        return self._pool.get_connection()


_pool = MySQLPool()

def _load_mysql_settings() -> dict[str, str | int]:
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


def get_base_connection() -> mysql.connector.MySQLConnection:
    return _pool.get_connection()


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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS remember_tokens (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                token_hash CHAR(64) NOT NULL UNIQUE,
                user_agent VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP NULL,
                INDEX idx_remember_user (user_id),
                INDEX idx_remember_expires (expires_at),
                CONSTRAINT fk_remember_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                name VARCHAR(255) NOT NULL,
                golden_key TEXT NOT NULL,
                proxy_url TEXT NOT NULL,
                is_default TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_workspace_user_name (user_id, name),
                INDEX idx_workspace_user (user_id),
                CONSTRAINT fk_workspace_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                last_rented_workspace_id BIGINT NULL,
                account_name VARCHAR(255) NOT NULL,
                login VARCHAR(255) NOT NULL,
                password TEXT NOT NULL,
                mafile_json LONGTEXT NULL,
                path_to_maFile TEXT NULL,
                lot_url TEXT NULL,
                mmr INT NULL,
                rental_duration INT NOT NULL DEFAULT 1,
                rental_duration_minutes INT NULL,
                owner VARCHAR(255) DEFAULT NULL,
                rental_start DATETIME DEFAULT NULL,
                low_priority TINYINT(1) NOT NULL DEFAULT 0,
                account_frozen TINYINT(1) NOT NULL DEFAULT 0,
                rental_frozen TINYINT(1) NOT NULL DEFAULT 0,
                rental_frozen_at DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_accounts_user (user_id),
                INDEX idx_accounts_workspace (workspace_id),
                INDEX idx_accounts_owner (owner),
                UNIQUE KEY uniq_account_workspace_name (workspace_id, account_name),
                CONSTRAINT fk_accounts_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'accounts' AND column_name = 'low_priority'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE accounts ADD COLUMN low_priority TINYINT(1) NOT NULL DEFAULT 0")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lots (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                lot_number INT NOT NULL,
                account_id BIGINT NOT NULL,
                lot_url TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_lots_account (account_id),
                UNIQUE KEY uniq_lot_workspace (workspace_id, lot_number),
                UNIQUE KEY uniq_account_workspace (workspace_id, account_id),
                CONSTRAINT fk_lots_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_lots_account FOREIGN KEY (account_id)
                    REFERENCES accounts(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_history (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                order_id VARCHAR(32) NOT NULL,
                owner VARCHAR(255) NOT NULL,
                account_name VARCHAR(255) NULL,
                account_id BIGINT NULL,
                steam_id VARCHAR(32) NULL,
                rental_minutes INT NULL,
                lot_number INT NULL,
                amount INT DEFAULT 1,
                price DECIMAL(10,2) NULL,
                action VARCHAR(32) NOT NULL,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_order_user_order (user_id, order_id),
                INDEX idx_order_owner_created (owner, created_at),
                INDEX idx_order_workspace (workspace_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'order_history' AND column_name = 'steam_id'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE order_history ADD COLUMN steam_id VARCHAR(32) NULL")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                owner VARCHAR(255) NOT NULL,
                reason TEXT NULL,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_blacklist_owner_user_ws (owner, user_id, workspace_id),
                INDEX idx_blacklist_owner (owner),
                INDEX idx_blacklist_user_ws (user_id, workspace_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklist_logs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                owner VARCHAR(255) NOT NULL,
                action VARCHAR(32) NOT NULL,
                reason TEXT NULL,
                details TEXT NULL,
                amount INT NULL,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_bl_logs_user_ws (user_id, workspace_id),
                INDEX idx_bl_logs_owner (owner, user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                name VARCHAR(255) NULL,
                last_message_text TEXT NULL,
                last_message_time TIMESTAMP NULL,
                unread TINYINT(1) NOT NULL DEFAULT 0,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_chat_user_ws (user_id, workspace_id, chat_id),
                INDEX idx_chats_user_ws (user_id, workspace_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                message_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                author VARCHAR(255) NULL,
                text TEXT NULL,
                sent_time TIMESTAMP NULL,
                by_bot TINYINT(1) NOT NULL DEFAULT 0,
                message_type VARCHAR(32) NULL,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_chat_message (user_id, workspace_id, chat_id, message_id),
                INDEX idx_chat_messages_chat (chat_id, user_id, workspace_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_outbox (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                text TEXT NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                attempts INT NOT NULL DEFAULT 0,
                last_error TEXT NULL,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP NULL,
                INDEX idx_outbox_status (status, user_id, workspace_id)
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
                "SELECT id, username, password_hash, golden_key, email "
                "FROM users WHERE username = %s OR email = %s LIMIT 1",
                (username.lower().strip(), username.lower().strip()),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return UserRecord(
                id=row["id"],
                username=row["username"],
                password_hash=row["password_hash"],
                golden_key=row["golden_key"],
                email=row.get("email"),
            )
        finally:
            conn.close()

    def get_by_id(self, user_id: int) -> Optional[UserRecord]:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, username, password_hash, golden_key, email FROM users WHERE id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return UserRecord(
                id=row["id"],
                username=row["username"],
                password_hash=row["password_hash"],
                golden_key=row["golden_key"],
                email=row.get("email"),
            )
        finally:
            conn.close()

    def create(self, record: UserRecord) -> Optional[UserRecord]:
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
                record.id = cursor.lastrowid
                return record
            except mysql.connector.Error as exc:
                if exc.errno == errorcode.ER_DUP_ENTRY:
                    return None
                raise
        finally:
            conn.close()


class MySQLRememberTokenRepo:
    def create(self, user_id: int, token_hash: str, user_agent: str | None, expires_at: str) -> None:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO remember_tokens (user_id, token_hash, user_agent, expires_at) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, token_hash, user_agent, expires_at),
            )
            conn.commit()
        finally:
            conn.close()

    def find_valid(self, token_hash: str) -> tuple[int, int] | None:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, user_id FROM remember_tokens "
                "WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > NOW()",
                (token_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return int(row["id"]), int(row["user_id"])
        finally:
            conn.close()

    def rotate(self, token_id: int, new_hash: str, new_expires_at: str, user_agent: str | None) -> None:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE remember_tokens SET token_hash=%s, expires_at=%s, last_used=NOW(), user_agent=%s "
                "WHERE id=%s",
                (new_hash, new_expires_at, user_agent, token_id),
            )
            conn.commit()
        finally:
            conn.close()

    def revoke(self, token_hash: str) -> None:
        conn = _pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE remember_tokens SET revoked_at=NOW() WHERE token_hash=%s",
                (token_hash,),
            )
            conn.commit()
        finally:
            conn.close()
