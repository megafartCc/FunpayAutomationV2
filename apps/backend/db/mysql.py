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
            pool_size=int(os.getenv("MYSQL_POOL_SIZE", "30")),
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
                account_name VARCHAR(255) NOT NULL,
                login VARCHAR(255) NOT NULL,
                password TEXT NOT NULL,
                mafile_json LONGTEXT NULL,
                lot_url TEXT NULL,
                mmr INT NULL,
                rental_duration INT NOT NULL DEFAULT 1,
                rental_duration_minutes INT NULL,
                owner VARCHAR(255) DEFAULT NULL,
                rental_start DATETIME DEFAULT NULL,
                account_frozen TINYINT(1) NOT NULL DEFAULT 0,
                rental_frozen TINYINT(1) NOT NULL DEFAULT 0,
                rental_frozen_at DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_accounts_user (user_id),
                INDEX idx_accounts_workspace (workspace_id),
                INDEX idx_accounts_owner (owner),
                UNIQUE KEY uniq_account_user_name (user_id, account_name),
                CONSTRAINT fk_accounts_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # Ensure legacy tables get new columns without manual migrations.
        try:
            cursor.execute("ALTER TABLE accounts ADD COLUMN mafile_json LONGTEXT NULL;")
        except mysql.connector.Error as exc:
            if exc.errno != errorcode.ER_DUP_FIELDNAME:
                raise
        try:
            cursor.execute("ALTER TABLE accounts ADD COLUMN path_to_maFile TEXT NULL;")
        except mysql.connector.Error as exc:
            if exc.errno != errorcode.ER_DUP_FIELDNAME:
                raise
        try:
            cursor.execute("ALTER TABLE accounts MODIFY path_to_maFile TEXT NULL;")
        except mysql.connector.Error as exc:
            if exc.errno != errorcode.ER_BAD_FIELD_ERROR:
                raise
        try:
            cursor.execute("ALTER TABLE accounts ADD COLUMN lot_url TEXT NULL;")
        except mysql.connector.Error as exc:
            if exc.errno != errorcode.ER_DUP_FIELDNAME:
                raise
        try:
            cursor.execute("ALTER TABLE accounts ADD COLUMN workspace_id BIGINT NULL;")
        except mysql.connector.Error as exc:
            if exc.errno != errorcode.ER_DUP_FIELDNAME:
                raise
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
                CONSTRAINT fk_lots_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_lots_account FOREIGN KEY (account_id)
                    REFERENCES accounts(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        try:
            cursor.execute("ALTER TABLE lots ADD COLUMN workspace_id BIGINT NULL;")
        except mysql.connector.Error as exc:
            if exc.errno != errorcode.ER_DUP_FIELDNAME:
                raise
        # Ensure no UNIQUE index blocks duplicate lot_number across workspaces/users.
        try:
            idx_cursor = conn.cursor(dictionary=True)
            idx_cursor.execute("SHOW INDEX FROM lots")
            index_cols: dict[str, list[tuple[int, str]]] = {}
            index_unique: dict[str, bool] = {}
            for row in idx_cursor.fetchall() or []:
                key = row["Key_name"]
                index_unique[key] = row["Non_unique"] == 0
                index_cols.setdefault(key, []).append((int(row["Seq_in_index"]), row["Column_name"]))
            desired_lot_unique = ["user_id", "workspace_id", "lot_number"]
            desired_account_unique = ["workspace_id", "account_id"]
            for key, cols in index_cols.items():
                if key == "PRIMARY":
                    continue
                if not index_unique.get(key, False):
                    continue
                columns = [col for _, col in sorted(cols)]
                if columns in (desired_lot_unique, desired_account_unique):
                    continue
                if "lot_number" not in columns and "account_id" not in columns:
                    continue
                # Drop any other UNIQUE indexes that could block per-workspace mappings.
                # (Legacy schemas used global UNIQUE keys.)
                try:
                    cursor.execute(f"ALTER TABLE lots DROP INDEX `{key}`")
                except mysql.connector.Error:
                    # Ignore if the index can't be dropped (e.g. already removed).
                    pass
        except mysql.connector.Error:
            pass

        # Aliases: multiple FunPay URLs per logical lot_number.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lot_aliases (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                workspace_id BIGINT NULL,
                lot_number INT NOT NULL,
                funpay_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_alias_workspace_url (user_id, workspace_id, funpay_url(191)),
                INDEX idx_alias_user_lot (user_id, lot_number),
                CONSTRAINT fk_alias_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # Ensure alias uniqueness is workspace-scoped.
        try:
            idx_cursor = conn.cursor(dictionary=True)
            idx_cursor.execute("SHOW INDEX FROM lot_aliases")
            index_cols: dict[str, list[tuple[int, str]]] = {}
            index_unique: dict[str, bool] = {}
            for row in idx_cursor.fetchall() or []:
                key = row["Key_name"]
                index_unique[key] = row["Non_unique"] == 0
                index_cols.setdefault(key, []).append((int(row["Seq_in_index"]), row["Column_name"]))
            desired_alias_unique = ["user_id", "workspace_id", "funpay_url"]
            for key, cols in index_cols.items():
                if key == "PRIMARY":
                    continue
                if not index_unique.get(key, False):
                    continue
                columns = [col for _, col in sorted(cols)]
                if columns == desired_alias_unique:
                    continue
                if "funpay_url" not in columns:
                    continue
                try:
                    cursor.execute(f"ALTER TABLE lot_aliases DROP INDEX `{key}`")
                except mysql.connector.Error:
                    pass
        except mysql.connector.Error:
            pass
        try:
            cursor.execute(
                "ALTER TABLE lot_aliases ADD UNIQUE KEY uniq_alias_workspace_url "
                "(user_id, workspace_id, funpay_url(191))"
            )
        except mysql.connector.Error:
            pass

        # Seed default workspaces for legacy users.
        cursor.execute("SELECT id, username, golden_key FROM users")
        for row in cursor.fetchall() or []:
            user_id = row[0]
            golden_key = row[2]
            if not golden_key:
                continue
            cursor.execute(
                "SELECT id FROM workspaces WHERE user_id=%s LIMIT 1",
                (user_id,),
            )
            exists = cursor.fetchone()
            if exists:
                continue
            cursor.execute(
                "INSERT INTO workspaces (user_id, name, golden_key, proxy_url, is_default) "
                "VALUES (%s, %s, %s, %s, 1)",
                (user_id, "Default", golden_key, ""),
            )

        # Backfill workspace_id for existing accounts/lots.
        cursor.execute(
            """
            UPDATE accounts a
            JOIN workspaces w ON w.user_id = a.user_id AND w.is_default = 1
            SET a.workspace_id = w.id
            WHERE a.workspace_id IS NULL
            """
        )
        cursor.execute(
            """
            UPDATE lots l
            JOIN accounts a ON a.id = l.account_id
            SET l.workspace_id = a.workspace_id
            WHERE l.workspace_id IS NULL
            """
        )

        # Backfill aliases from existing lot_url columns.
        cursor.execute(
            """
            INSERT IGNORE INTO lot_aliases (user_id, workspace_id, lot_number, funpay_url)
            SELECT l.user_id, l.workspace_id, l.lot_number, l.lot_url
            FROM lots l
            WHERE l.lot_url IS NOT NULL AND l.lot_url <> ''
            """
        )
        cursor.execute(
            """
            INSERT IGNORE INTO lot_aliases (user_id, workspace_id, lot_number, funpay_url)
            SELECT a.user_id, a.workspace_id, l.lot_number, a.lot_url
            FROM accounts a
            JOIN lots l ON l.account_id = a.id
            WHERE a.lot_url IS NOT NULL AND a.lot_url <> ''
            """
        )

        # Update uniqueness to be workspace-aware.
        try:
            cursor.execute("ALTER TABLE accounts DROP INDEX uniq_account_user_name;")
        except mysql.connector.Error:
            pass
        try:
            cursor.execute(
                "ALTER TABLE accounts ADD UNIQUE KEY uniq_account_workspace_name (workspace_id, account_name)"
            )
        except mysql.connector.Error:
            pass
        try:
            cursor.execute(
                "ALTER TABLE lots ADD UNIQUE KEY uniq_lot_workspace (user_id, workspace_id, lot_number)"
            )
        except mysql.connector.Error:
            pass
        try:
            cursor.execute(
                "ALTER TABLE lots ADD UNIQUE KEY uniq_account_workspace (workspace_id, account_id)"
            )
        except mysql.connector.Error:
            pass

        # Optional foreign keys for workspace_id (safe if already exists).
        try:
            cursor.execute(
                "ALTER TABLE accounts ADD CONSTRAINT fk_accounts_workspace "
                "FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL"
            )
        except mysql.connector.Error:
            pass
        try:
            cursor.execute(
                "ALTER TABLE lots ADD CONSTRAINT fk_lots_workspace "
                "FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL"
            )
        except mysql.connector.Error:
            pass
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
