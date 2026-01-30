from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from urllib.parse import urlparse

import bcrypt
import mysql.connector
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


logger = logging.getLogger("telegram-bot")

LOGIN_USERNAME, LOGIN_PASSWORD = range(2)

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/login"), KeyboardButton("/workspaces")],
        [KeyboardButton("/help")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


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


def authenticate_user(username: str, password: str) -> int | None:
    login = (username or "").strip().lower()
    if not login or not password:
        return None
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, password_hash
            FROM users
            WHERE username = %s
            LIMIT 1
            """,
            (login,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        stored_hash = row.get("password_hash") or ""
        try:
            hash_bytes = stored_hash.encode("utf-8")
        except Exception:
            return None
        if not bcrypt.checkpw(password.encode("utf-8"), hash_bytes):
            return None
        return int(row["id"])
    finally:
        conn.close()


def link_chat_to_user(user_id: int, chat_id: int) -> None:
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO telegram_links (user_id, chat_id, verified_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                chat_id = VALUES(chat_id),
                verified_at = VALUES(verified_at),
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(user_id), int(chat_id)),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_id_by_chat(chat_id: int) -> int | None:
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_id
            FROM telegram_links
            WHERE chat_id = %s AND verified_at IS NOT NULL
            LIMIT 1
            """,
            (int(chat_id),),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return int(row["user_id"])
    finally:
        conn.close()


def list_workspaces(user_id: int) -> list[tuple[int, str]]:
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, name
            FROM workspaces
            WHERE user_id = %s
            ORDER BY id ASC
            """,
            (int(user_id),),
        )
        rows = cursor.fetchall() or []
        return [(int(row["id"]), row.get("name") or "-") for row in rows]
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
            reply_markup=MENU_KEYBOARD,
        )
        return
    user_id = verify_token(token, int(update.effective_chat.id))
    if not user_id:
        await update.message.reply_text("That link has expired. Please generate a new one in Settings.")
        return
    await update.message.reply_text(
        "✅ Telegram linked! You will now receive admin-call alerts with direct chat links.",
        reply_markup=MENU_KEYBOARD,
    )


async def login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
        if message:
            await message.reply_text("Enter your username:", reply_markup=ReplyKeyboardRemove())
        return LOGIN_USERNAME
    if not update.effective_chat or not update.message:
        return ConversationHandler.END
    await update.message.reply_text("Enter your username:", reply_markup=ReplyKeyboardRemove())
    return LOGIN_USERNAME


async def login_username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return ConversationHandler.END
    context.user_data["login_username"] = update.message.text.strip()
    await update.message.reply_text("Enter your password:")
    return LOGIN_PASSWORD


async def login_password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_chat or not update.message:
        return ConversationHandler.END
    username = context.user_data.get("login_username", "")
    password = update.message.text or ""
    user_id = authenticate_user(username, password)
    context.user_data.pop("login_username", None)
    if not user_id:
        await update.message.reply_text("Login failed. Check your credentials.", reply_markup=MENU_KEYBOARD)
        return ConversationHandler.END
    link_chat_to_user(user_id, int(update.effective_chat.id))
    await update.message.reply_text("✅ Logged in. Telegram linked to your account.", reply_markup=MENU_KEYBOARD)
    return ConversationHandler.END


async def login_cancel_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Login cancelled.", reply_markup=MENU_KEYBOARD)
    return ConversationHandler.END


async def workspaces_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    chat = update.effective_chat
    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
        chat = update.callback_query.message.chat if update.callback_query.message else update.effective_chat
    if not chat or not message:
        return
    user_id = get_user_id_by_chat(int(chat.id))
    if not user_id:
        await message.reply_text("Please /login first to see your workspaces.", reply_markup=MENU_KEYBOARD)
        return
    rows = list_workspaces(user_id)
    if not rows:
        await message.reply_text("No workspaces found for your account.", reply_markup=MENU_KEYBOARD)
        return
    lines = ["Your workspaces:"]
    for workspace_id, name in rows:
        lines.append(f"- {name} (ID {workspace_id})")
    await message.reply_text("\n".join(lines), reply_markup=MENU_KEYBOARD)


async def help_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
    if not message:
        return
    await message.reply_text(
        "Open the verification link from Settings to connect your account. "
        "Once connected, I will alert you when a buyer requests admin help.",
        reply_markup=MENU_KEYBOARD,
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
    login_flow = ConversationHandler(
        entry_points=[
            CommandHandler("login", login_handler),
        ],
        states={
            LOGIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_username_handler)],
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password_handler)],
        },
        fallbacks=[CommandHandler("cancel", login_cancel_handler)],
    )
    app.add_handler(login_flow)
    app.add_handler(CommandHandler("workspaces", workspaces_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.job_queue.run_repeating(poll_notifications, interval=10, first=5)
    logger.info("Telegram bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
