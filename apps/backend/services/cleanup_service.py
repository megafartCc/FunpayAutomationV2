from __future__ import annotations

import logging
import os
import threading
import time
from typing import Iterable

from db.mysql import get_base_connection


logger = logging.getLogger("backend.cleanup")
_CLEANUP_THREAD: threading.Thread | None = None
_CLEANUP_LOCK = threading.Lock()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


def _cleanup_enabled() -> bool:
    raw = os.getenv("CLEANUP_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = %s
        LIMIT 1
        """,
        (table,),
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table, column),
    )
    return cursor.fetchone() is not None


def _delete_batches(cursor, table: str, column: str, days: int, limit: int) -> int:
    if days <= 0:
        return 0
    deleted = 0
    while True:
        cursor.execute(
            f"DELETE FROM {table} WHERE {column} < DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s DAY) LIMIT %s",
            (int(days), int(limit)),
        )
        batch = cursor.rowcount or 0
        deleted += batch
        if batch < limit:
            break
    return deleted


def run_cleanup_once() -> dict[str, int]:
    retention = [
        ("order_history", "created_at", "CLEANUP_RETENTION_DAYS_ORDER_HISTORY", 180),
        ("notification_logs", "created_at", "CLEANUP_RETENTION_DAYS_NOTIFICATION_LOGS", 60),
        ("blacklist_logs", "created_at", "CLEANUP_RETENTION_DAYS_BLACKLIST_LOGS", 180),
        ("auto_raise_logs", "created_at", "CLEANUP_RETENTION_DAYS_AUTO_RAISE_LOGS", 30),
        ("auto_raise_requests", "created_at", "CLEANUP_RETENTION_DAYS_AUTO_RAISE_REQUESTS", 30),
        ("auto_price_logs", "created_at", "CLEANUP_RETENTION_DAYS_AUTO_PRICE_LOGS", 30),
        ("price_dumper_history", "created_at", "CLEANUP_RETENTION_DAYS_PRICE_DUMPER_HISTORY", 90),
        ("bonus_history", "created_at", "CLEANUP_RETENTION_DAYS_BONUS_HISTORY", 365),
        ("chat_messages", "created_at", "CLEANUP_RETENTION_DAYS_CHAT_MESSAGES", 30),
        ("chat_outbox", "created_at", "CLEANUP_RETENTION_DAYS_CHAT_OUTBOX", 7),
        ("chat_ai_memory", "created_at", "CLEANUP_RETENTION_DAYS_CHAT_AI_MEMORY", 30),
    ]
    limit = max(100, _env_int("CLEANUP_BATCH_LIMIT", 5000))
    totals: dict[str, int] = {}
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        for table, column, env_name, default_days in retention:
            if not _table_exists(cursor, table) or not _column_exists(cursor, table, column):
                continue
            days = _env_int(env_name, default_days)
            deleted = _delete_batches(cursor, table, column, days, limit)
            totals[table] = deleted
        conn.commit()
    except Exception as exc:
        logger.warning("Cleanup failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return totals


def _cleanup_loop() -> None:
    poll_seconds = max(300, _env_int("CLEANUP_POLL_SECONDS", 21600))
    while True:
        try:
            totals = run_cleanup_once()
            if totals:
                logger.info("Cleanup finished: %s", totals)
        except Exception:
            logger.exception("Cleanup loop failed.")
        time.sleep(poll_seconds)


def start_cleanup_scheduler() -> None:
    global _CLEANUP_THREAD
    if not _cleanup_enabled():
        return
    with _CLEANUP_LOCK:
        if _CLEANUP_THREAD and _CLEANUP_THREAD.is_alive():
            return
        thread = threading.Thread(target=_cleanup_loop, daemon=True)
        _CLEANUP_THREAD = thread
        thread.start()
