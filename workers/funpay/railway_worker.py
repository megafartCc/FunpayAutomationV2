from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

# Allow running from repo root while importing FunPayAPI from this folder.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mysql.connector  # noqa: E402
from FunPayAPI.account import Account  # noqa: E402
from FunPayAPI.common.enums import EventTypes, MessageTypes  # noqa: E402
from FunPayAPI.updater.events import NewMessageEvent  # noqa: E402
from FunPayAPI.updater.runner import Runner  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# Keep ASCII source while matching Cyrillic commands.
COMMAND_PREFIXES = (
    "!\u0441\u0442\u043e\u043a",
    "!\u0430\u043a\u043a",
    "!\u043a\u043e\u0434",
    "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c",
    "!\u043b\u043f\u0437\u0430\u043c\u0435\u043d\u0430",
    "!\u043e\u0442\u043c\u0435\u043d\u0430",
    "!\u0430\u0434\u043c\u0438\u043d",
)
STOCK_LIST_LIMIT = 8
STOCK_TITLE = "\u0421\u0432\u043e\u0431\u043e\u0434\u043d\u044b\u0435 \u043b\u043e\u0442\u044b:"
STOCK_EMPTY = "\u0421\u0432\u043e\u0431\u043e\u0434\u043d\u044b\u0445 \u043b\u043e\u0442\u043e\u0432 \u043d\u0435\u0442."
STOCK_DB_MISSING = (
    "\u0418\u043d\u0432\u0435\u043d\u0442\u0430\u0440\u044c \u043f\u043e\u043a\u0430 \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d."
)


def detect_command(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.strip().lower()
    if not cleaned.startswith("!"):
        return None
    for cmd in COMMAND_PREFIXES:
        if cleaned.startswith(cmd):
            return cmd
    return None


def parse_command(text: str | None) -> tuple[str | None, str]:
    if not text:
        return None, ""
    cleaned = text.strip()
    if not cleaned.startswith("!"):
        return None, ""
    parts = cleaned.split(maxsplit=1)
    command = parts[0].lower()
    if command not in COMMAND_PREFIXES:
        return None, ""
    args = parts[1].strip() if len(parts) > 1 else ""
    return command, args


def send_chat_message(logger: logging.Logger, account: Account, chat_id: int, text: str) -> bool:
    try:
        account.send_message(chat_id, text)
        return True
    except Exception as exc:
        logger.warning("Failed to send chat message: %s", exc)
        return False


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


def fetch_available_lot_accounts(mysql_cfg: dict, user_id: int | None) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "accounts"):
            return []
        has_lots = table_exists(cursor, "lots")
        has_account_user_id = column_exists(cursor, "accounts", "user_id")
        has_lot_user_id = has_lots and column_exists(cursor, "lots", "user_id")
        has_account_lot_url = column_exists(cursor, "accounts", "lot_url")
        has_account_lot_number = column_exists(cursor, "accounts", "lot_number")
        has_account_frozen = column_exists(cursor, "accounts", "account_frozen")
        has_rental_frozen = column_exists(cursor, "accounts", "rental_frozen")

        select_fields = [
            "a.ID AS id",
            "a.account_name AS account_name",
            "a.login AS login",
            "a.owner AS owner",
            "a.rental_start AS rental_start",
            "a.rental_duration AS rental_duration",
            "a.rental_duration_minutes AS rental_duration_minutes",
            "a.mmr AS mmr",
        ]
        if has_lots:
            select_fields.extend(["l.lot_number AS lot_number", "l.lot_url AS lot_url"])
        else:
            select_fields.append(
                "a.lot_number AS lot_number" if has_account_lot_number else "NULL AS lot_number"
            )
            select_fields.append("a.lot_url AS lot_url" if has_account_lot_url else "NULL AS lot_url")

        from_clause = "FROM accounts a"
        if has_lots:
            from_clause += " LEFT JOIN lots l ON l.account_id = a.ID"

        where_clauses = ["a.owner IS NULL"]
        if has_account_frozen:
            where_clauses.append("(a.account_frozen = 0 OR a.account_frozen IS NULL)")
        if has_rental_frozen:
            where_clauses.append("(a.rental_frozen = 0 OR a.rental_frozen IS NULL)")
        if has_lots:
            where_clauses.append("l.lot_number IS NOT NULL")

        params: list = []
        if user_id is not None:
            if has_account_user_id:
                where_clauses.append("a.user_id = %s")
                params.append(user_id)
            elif has_lot_user_id:
                where_clauses.append("l.user_id = %s")
                params.append(user_id)

        if has_lots:
            order_clause = "ORDER BY (l.lot_number IS NULL), l.lot_number"
        elif has_account_lot_number:
            order_clause = "ORDER BY (a.lot_number IS NULL), a.lot_number"
        else:
            order_clause = "ORDER BY a.ID"

        query = f"SELECT {', '.join(select_fields)} {from_clause} WHERE {' AND '.join(where_clauses)} {order_clause}"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return list(rows or [])
    finally:
        conn.close()


def build_stock_messages(accounts: list[dict]) -> list[str]:
    if not accounts:
        return [STOCK_EMPTY]
    lines: list[str] = []
    for account in accounts:
        lot_number = account.get("lot_number")
        lot_url = account.get("lot_url")
        display_name = account.get("account_name") or account.get("login") or ""
        if not display_name:
            display_name = f"\u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u2116{lot_number}" if lot_number else "\u0410\u043a\u043a\u0430\u0443\u043d\u0442"
        line = f"{display_name} - {lot_url}" if lot_url else display_name
        lines.append(line)

    batches: list[str] = []
    for i in range(0, len(lines), STOCK_LIST_LIMIT):
        chunk = lines[i : i + STOCK_LIST_LIMIT]
        if i == 0:
            batches.append("\n".join([STOCK_TITLE, *chunk]))
        else:
            batches.append("\n".join(chunk))
    return batches


def handle_stock_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    if chat_id is None:
        logger.warning("Stock command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Stock command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
        return True

    try:
        accounts = fetch_available_lot_accounts(mysql_cfg, user_id)
    except mysql.connector.Error as exc:
        logger.warning("Stock query failed: %s", exc)
        send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
        return True

    for message in build_stock_messages(accounts):
        send_chat_message(logger, account, chat_id, message)
    return True


def _log_command_stub(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
    action: str,
) -> bool:
    logger.info(
        "user=%s chat=%s author=%s command=%s args=%s action=%s url=%s",
        site_username or "-",
        chat_name,
        sender_username,
        command,
        args or "-",
        action,
        chat_url,
    )
    return True


def handle_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    handlers = {
        "!\u0441\u0442\u043e\u043a": handle_stock_command,
        "!\u0430\u043a\u043a": lambda *a: _log_command_stub(*a, action="account"),
        "!\u043a\u043e\u0434": lambda *a: _log_command_stub(*a, action="code"),
        "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c": lambda *a: _log_command_stub(*a, action="extend"),
        "!\u043b\u043f\u0437\u0430\u043c\u0435\u043d\u0430": lambda *a: _log_command_stub(
            *a, action="lp_replace"
        ),
        "!\u043e\u0442\u043c\u0435\u043d\u0430": lambda *a: _log_command_stub(*a, action="cancel"),
        "!\u0430\u0434\u043c\u0438\u043d": lambda *a: _log_command_stub(*a, action="admin"),
    }
    handler = handlers.get(command)
    if not handler:
        logger.info(
            "user=%s chat=%s author=%s command_unhandled=%s args=%s url=%s",
            site_username or "-",
            chat_name,
            sender_username,
            command,
            args or "-",
            chat_url,
        )
        return False
    return handler(
        logger,
        account,
        site_username,
        site_user_id,
        chat_name,
        sender_username,
        chat_id,
        command,
        args,
        chat_url,
    )


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def get_mysql_config() -> dict:
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


def fetch_users(mysql_cfg: dict) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, golden_key FROM users "
            "WHERE golden_key IS NOT NULL AND golden_key != ''"
        )
        rows = cursor.fetchall()
        return list(rows or [])
    finally:
        conn.close()


def refresh_session_loop(account: Account, interval_seconds: int = 3600, label: str | None = None) -> None:
    sleep_time = interval_seconds
    while True:
        time.sleep(sleep_time)
        try:
            account.get()
            logging.getLogger("funpay.worker").info("%sSession refreshed.", f"{label} " if label else "")
            sleep_time = interval_seconds
        except Exception:
            logging.getLogger("funpay.worker").exception(
                "%sSession refresh failed. Retrying in 60s.", f"{label} " if label else ""
            )
            sleep_time = 60


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format=LOG_FORMAT,
    )
    logging.getLogger("FunPayAPI").setLevel(logging.WARNING)
    return logging.getLogger("funpay.worker")


def log_message(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    event: NewMessageEvent,
) -> str | None:
    if event.type is not EventTypes.NEW_MESSAGE:
        return None

    msg = event.message
    my_name = (account.username or "").strip()

    sender_username = None

    # 1) Try to parse explicit author from message HTML (matches FunPay UI).
    if getattr(msg, "html", None):
        try:
            soup = BeautifulSoup(msg.html, "lxml")
            link = soup.find("a", {"class": "chat-msg-author-link"})
            if link and link.text:
                sender_username = link.text.strip()
        except Exception:
            sender_username = None

    # 2) Use API-provided author.
    if not sender_username and msg.author:
        sender_username = msg.author
    # 3) Use chat_name.
    if not sender_username and msg.chat_name:
        sender_username = msg.chat_name
    # 4) Use IDs if available.
    if not sender_username and msg.author_id:
        sender_username = f"user_{msg.author_id}"
    if not sender_username and msg.interlocutor_id:
        sender_username = f"user_{msg.interlocutor_id}"
    # 5) Last resort: chat id placeholder.
    if not sender_username:
        sender_username = f"chat_{msg.chat_id}"

    message_text = msg.text
    command, command_args = parse_command(message_text)

    # If we don't have a chat name, it's likely not a private chat.
    if not sender_username or sender_username == "-":
        return None

    chat_id = msg.chat_id
    chat_url = f"https://funpay.com/chat/?node={chat_id}" if chat_id is not None else "-"

    is_system = bool(msg.type and msg.type is not MessageTypes.NON_SYSTEM)
    if msg.author_id == 0 or (sender_username and sender_username.lower() == "funpay"):
        is_system = True

    chat_name = msg.chat_name or msg.author or "-"
    logger.info(
        "user=%s chat=%s author=%s system=%s url=%s: %s",
        site_username or "-",
        chat_name,
        sender_username,
        is_system,
        chat_url,
        message_text,
    )
    if command:
        logger.info(
            "user=%s chat=%s author=%s command=%s args=%s url=%s",
            site_username or "-",
            chat_name,
            sender_username,
            command,
            command_args or "-",
            chat_url,
        )
        if not is_system:
            handle_command(
                logger,
                account,
                site_username,
                site_user_id,
                chat_name,
                sender_username,
                msg.chat_id,
                command,
                command_args,
                chat_url,
            )
    if is_system:
        logger.info(
            "user=%s system_event type=%s chat=%s url=%s raw=%s",
            site_username or "-",
            getattr(msg.type, "name", msg.type),
            chat_name,
            chat_url,
            (msg.text or "").strip(),
        )
    return None


def run_single_user(logger: logging.Logger) -> None:
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")
    if not golden_key:
        logger.error("FUNPAY_GOLDEN_KEY is required (set FUNPAY_MULTI_USER=1 for DB mode).")
        sys.exit(1)

    user_agent = os.getenv("FUNPAY_USER_AGENT")
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)

    logger.info("Initializing FunPay account...")
    account = Account(golden_key, user_agent=user_agent)
    account.get()
    logger.info("Bot started for %s.", account.username or "unknown")

    threading.Thread(target=refresh_session_loop, args=(account, 3600, None), daemon=True).start()

    runner = Runner(account, disable_message_requests=False)
    logger.info("Listening for new messages...")
    for event in runner.listen(requests_delay=poll_seconds):
        if isinstance(event, NewMessageEvent):
            log_message(logger, account, account.username, None, event)


def user_worker_loop(
    user: dict,
    user_agent: str | None,
    poll_seconds: int,
    stop_event: threading.Event,
) -> None:
    logger = logging.getLogger("funpay.worker")
    site_username = user.get("username") or f"user-{user.get('id')}"
    golden_key = user.get("golden_key")
    label = f"[{site_username}]"

    while not stop_event.is_set():
        try:
            if not golden_key:
                logger.warning("%s Missing golden_key, skipping.", label)
                return
            account = Account(golden_key, user_agent=user_agent)
            account.get()
            logger.info("Bot started for %s.", site_username)

            threading.Thread(
                target=refresh_session_loop,
                args=(account, 3600, label),
                daemon=True,
            ).start()

            runner = Runner(account, disable_message_requests=False)
            while not stop_event.is_set():
                updates = runner.get_updates()
                events = runner.parse_updates(updates)
                for event in events:
                    if stop_event.is_set():
                        break
                    if isinstance(event, NewMessageEvent):
                        log_message(logger, account, site_username, user.get("id"), event)
                time.sleep(poll_seconds)
        except Exception as exc:
            # Avoid logging full HTML bodies from failed FunPay requests.
            short = exc.short_str() if hasattr(exc, "short_str") else str(exc)[:200]
            logger.error("%s Worker error: %s. Restarting in 30s.", label, short)
            logger.debug("%s Traceback:", label, exc_info=True)
            time.sleep(30)
    logger.info("%s Worker stopped (key updated or removed).", label)


def run_multi_user(logger: logging.Logger) -> None:
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)
    sync_seconds = env_int("FUNPAY_USER_SYNC_SECONDS", 60)
    max_users = env_int("FUNPAY_MAX_USERS", 0)
    user_agent = os.getenv("FUNPAY_USER_AGENT")

    mysql_cfg = get_mysql_config()
    logger.info("Multi-user mode enabled. Sync interval: %ss.", sync_seconds)

    workers: dict[int, dict] = {}

    while True:
        try:
            users = fetch_users(mysql_cfg)
            if max_users > 0:
                users = users[:max_users]

            desired = {
                int(u["id"]): u
                for u in users
                if u.get("golden_key") and str(u.get("golden_key")).strip()
            }

            # Stop removed users or users without keys.
            for user_id in list(workers.keys()):
                if user_id not in desired:
                    workers[user_id]["stop"].set()
                    workers[user_id]["thread"].join(timeout=5)
                    workers.pop(user_id, None)

            for user_id, user in desired.items():
                golden_key = user.get("golden_key") or ""
                existing = workers.get(user_id)
                if existing and existing["golden_key"] == golden_key:
                    continue
                if existing:
                    existing["stop"].set()
                    existing["thread"].join(timeout=5)
                    workers.pop(user_id, None)

                stop_event = threading.Event()
                thread = threading.Thread(
                    target=user_worker_loop,
                    args=(user, user_agent, poll_seconds, stop_event),
                    daemon=True,
                )
                workers[user_id] = {
                    "golden_key": golden_key,
                    "thread": thread,
                    "stop": stop_event,
                }
                thread.start()
            time.sleep(sync_seconds)
        except Exception as exc:
            short = exc.short_str() if hasattr(exc, "short_str") else str(exc)[:200]
            logger.error("User sync failed: %s. Retrying in 30s.", short)
            logger.debug("User sync traceback:", exc_info=True)
            time.sleep(30)


def main() -> None:
    logger = configure_logging()
    explicit_multi = os.getenv("FUNPAY_MULTI_USER")
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")

    # Auto-mode:
    # - If FUNPAY_MULTI_USER is explicitly set, respect it.
    # - Else if a single key is provided, run single-user.
    # - Else try multi-user (DB mode).
    if explicit_multi is not None:
        multi_user = env_bool("FUNPAY_MULTI_USER", False)
    else:
        multi_user = False if golden_key else True

    if multi_user:
        run_multi_user(logger)
    else:
        run_single_user(logger)


if __name__ == "__main__":
    main()
