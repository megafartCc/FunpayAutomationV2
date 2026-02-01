from __future__ import annotations

import os
import time
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
        attempts = int(os.getenv("MYSQL_POOL_RETRY_ATTEMPTS", "3"))
        delay = float(os.getenv("MYSQL_POOL_RETRY_DELAY", "0.05"))
        for attempt in range(max(1, attempts)):
            try:
                return self._pool.get_connection()
            except mysql.connector.errors.PoolError:
                if attempt + 1 >= attempts:
                    raise
                time.sleep(delay)
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
                platform VARCHAR(32) NOT NULL DEFAULT 'funpay',
                golden_key TEXT NOT NULL,
                proxy_url TEXT NOT NULL,
                is_default TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_workspace_user_platform_name (user_id, platform, name),
                INDEX idx_workspace_user (user_id),
                INDEX idx_workspace_user_platform (user_id, platform),
                CONSTRAINT fk_workspace_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_status (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                platform VARCHAR(32) NOT NULL DEFAULT 'funpay',
                status VARCHAR(32) NOT NULL,
                message TEXT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_workspace_status (user_id, workspace_id, platform),
                INDEX idx_workspace_status_user (user_id),
                INDEX idx_workspace_status_workspace (workspace_id),
                CONSTRAINT fk_workspace_status_workspace FOREIGN KEY (workspace_id)
                    REFERENCES workspaces(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'workspaces' AND column_name = 'platform'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "ALTER TABLE workspaces ADD COLUMN platform VARCHAR(32) NOT NULL DEFAULT 'funpay' AFTER name"
            )
        cursor.execute(
            """
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'workspaces' AND index_name = 'uniq_workspace_user_name'
            LIMIT 1
            """
        )
        if cursor.fetchone() is not None:
            cursor.execute("ALTER TABLE workspaces DROP INDEX uniq_workspace_user_name")
        cursor.execute(
            """
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'workspaces'
              AND index_name = 'uniq_workspace_user_platform_name'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "ALTER TABLE workspaces ADD UNIQUE KEY uniq_workspace_user_platform_name (user_id, platform, name)"
            )
        cursor.execute(
            """
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'workspaces'
              AND index_name = 'idx_workspace_user_platform'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE workspaces ADD INDEX idx_workspace_user_platform (user_id, platform)")
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
                `low_priority` TINYINT(1) NOT NULL DEFAULT 0,
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
            cursor.execute("ALTER TABLE accounts ADD COLUMN `low_priority` TINYINT(1) NOT NULL DEFAULT 0")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lots (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                lot_number INT NOT NULL,
                account_id BIGINT NOT NULL,
                lot_url TEXT NULL,
                display_name VARCHAR(255) NULL,
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
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'lots' AND column_name = 'display_name'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE lots ADD COLUMN display_name VARCHAR(255) NULL AFTER lot_url")
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
            CREATE TABLE IF NOT EXISTS notification_logs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(64) NOT NULL,
                status VARCHAR(16) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NULL,
                owner VARCHAR(255) NULL,
                account_name VARCHAR(255) NULL,
                account_id BIGINT NULL,
                order_id VARCHAR(32) NULL,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_notifications_user_ws (user_id, workspace_id),
                INDEX idx_notifications_event (event_type),
                INDEX idx_notifications_owner (owner),
                INDEX idx_notifications_account (account_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS raise_categories (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                category_id BIGINT NOT NULL,
                category_name VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_raise_category (user_id, workspace_id, category_id),
                INDEX idx_raise_user_ws (user_id, workspace_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_raise_logs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                level VARCHAR(8) NOT NULL,
                source VARCHAR(64) NULL,
                line INT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_auto_raise_logs_user_ws (user_id, workspace_id),
                INDEX idx_auto_raise_logs_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_raise_requests (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                message TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP NULL,
                INDEX idx_auto_raise_req_user_ws (user_id, workspace_id),
                INDEX idx_auto_raise_req_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_raise_settings (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                enabled TINYINT(1) NOT NULL DEFAULT 0,
                all_workspaces TINYINT(1) NOT NULL DEFAULT 1,
                interval_minutes INT NOT NULL DEFAULT 120,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_auto_raise_settings (user_id, workspace_id),
                INDEX idx_auto_raise_settings_user_ws (user_id, workspace_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_raise_state (
                user_id BIGINT PRIMARY KEY,
                next_run_at TIMESTAMP NULL,
                last_workspace_id BIGINT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_auto_raise_state_next (next_run_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_links (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                token_hash CHAR(64) NULL,
                token_hint VARCHAR(12) NULL,
                chat_id BIGINT NULL,
                verified_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_telegram_user (user_id),
                UNIQUE KEY uniq_telegram_token (token_hash),
                INDEX idx_telegram_chat (chat_id),
                CONSTRAINT fk_telegram_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
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
                admin_unread_count INT NOT NULL DEFAULT 0,
                admin_requested TINYINT(1) NOT NULL DEFAULT 0,
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
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'chats' AND column_name = 'admin_unread_count'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE chats ADD COLUMN admin_unread_count INT NOT NULL DEFAULT 0")
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'chats' AND column_name = 'admin_requested'
            LIMIT 1
            """
        )
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE chats ADD COLUMN admin_requested TINYINT(1) NOT NULL DEFAULT 0")
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
