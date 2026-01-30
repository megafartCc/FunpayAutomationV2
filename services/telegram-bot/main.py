from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from urllib.parse import urlparse

import mysql.connector
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


logger = logging.getLogger("telegram-bot")


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _load_mysql_settings() -> dict[str, str | int]:
    url = _get_env("MYSQL_URL", "") or ""
    host = _get_env("MYSQLHOST", "") or ""
    port = _get_env("MYSQLPORT", "3306") or "3306"
    user = _get_env("MYSQLUSER", "") or ""
    password = _get_env("MYSQLPASSWORD", "") or ""
    database = _get_env("MYSQLDATABASE", "") or _get_env("MYSQL_DATABASE", "") or ""

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
    settings = _load_mysql_settings()
    return mysql.connector.connect(**settings)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, chat_id: int) -> int | None:
    token_hash = _hash_token(token)
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_id
            FROM telegram_links
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        user_id = int(row["user_id"])
        cursor.execute(
            """
            UPDATE telegram_links
            SET chat_id = %s, verified_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (int(chat_id), user_id),
        )
        conn.commit()
        return user_id
    finally:
        conn.close()


def ensure_telegram_outbox() -> None:
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_outbox (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                notification_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_telegram_outbox_notification (notification_id),
                INDEX idx_telegram_outbox_chat (chat_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        conn.commit()
    finally:
        conn.close()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return
    token = ""
    if context.args:
        token = context.args[0].strip()
    if not token:
        await update.message.reply_text(
            "Hi! Please open the verification link from the dashboard so I can link your account.",
        )
        return
    user_id = verify_token(token, int(update.effective_chat.id))
    if not user_id:
        await update.message.reply_text("That link has expired. Please generate a new one in Settings.")
        return
    await update.message.reply_text(
        "✅ Telegram linked! You will now receive admin-call alerts with direct chat links.",
    )


async def help_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Open the verification link from Settings to connect your account. "
        "Once connected, I will alert you when a buyer requests admin help.",
    )


def _fetch_pending_notifications(limit: int = 50) -> list[dict]:
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT n.id, n.title, n.message, n.owner, n.workspace_id, n.created_at, t.chat_id
            FROM notification_logs n
            JOIN telegram_links t ON t.user_id = n.user_id
            LEFT JOIN telegram_outbox o ON o.notification_id = n.id
            WHERE n.event_type = 'admin_call'
              AND n.status = 'new'
              AND t.chat_id IS NOT NULL
              AND t.verified_at IS NOT NULL
              AND o.notification_id IS NULL
            ORDER BY n.created_at ASC
            LIMIT %s
            """,
            (int(limit),),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def _mark_notification_sent(notification_id: int, chat_id: int) -> None:
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO telegram_outbox (notification_id, chat_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE id = id
            """,
            (int(notification_id), int(chat_id)),
        )
        cursor.execute(
            "UPDATE notification_logs SET status = 'sent' WHERE id = %s",
            (int(notification_id),),
        )
        conn.commit()
    finally:
        conn.close()


async def poll_notifications(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.bot is None:
        return
    pending = _fetch_pending_notifications()
    if not pending:
        return
    for item in pending:
        chat_id = item.get("chat_id")
        if not chat_id:
            continue
        title = item.get("title") or "Admin request"
        message = item.get("message") or ""
        created_at = item.get("created_at")
        timestamp = ""
        if isinstance(created_at, datetime):
            timestamp = created_at.strftime("%Y-%m-%d %H:%M:%S")
        elif created_at:
            timestamp = str(created_at)
        payload = f"{title}\n{message}".strip()
        if timestamp:
            payload = f"{payload}\n\nReceived: {timestamp}"
        try:
            await context.bot.send_message(chat_id=int(chat_id), text=payload)
            _mark_notification_sent(int(item["id"]), int(chat_id))
        except Exception:
            logger.exception("Failed to send Telegram notification.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = _get_env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    ensure_telegram_outbox()
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.job_queue.run_repeating(poll_notifications, interval=10, first=5)
    logger.info("Telegram bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
