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

    # If we don't have a chat name, it's likely not a private chat.
    if not sender_username or sender_username == "-":
        return None

    chat_id = msg.chat_id
    chat_url = f"https://funpay.com/chat/?node={chat_id}" if chat_id is not None else "-"

    is_system = bool(msg.type and msg.type is not MessageTypes.NON_SYSTEM)

    logger.info(
        "user=%s chat=%s author=%s system=%s url=%s: %s",
        site_username or "-",
        msg.chat_name or msg.author or "-",
        sender_username,
        is_system,
        chat_url,
        message_text,
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
            log_message(logger, account, account.username, event)


def user_worker_loop(
    user: dict,
    user_agent: str | None,
    poll_seconds: int,
) -> None:
    logger = logging.getLogger("funpay.worker")
    site_username = user.get("username") or f"user-{user.get('id')}"
    golden_key = user.get("golden_key")
    label = f"[{site_username}]"

    while True:
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
            for event in runner.listen(requests_delay=poll_seconds):
                if isinstance(event, NewMessageEvent):
                    log_message(logger, account, site_username, event)
        except Exception as exc:
            # Avoid logging full HTML bodies from failed FunPay requests.
            short = exc.short_str() if hasattr(exc, "short_str") else str(exc)[:200]
            logger.error("%s Worker error: %s. Restarting in 30s.", label, short)
            logger.debug("%s Traceback:", label, exc_info=True)
            time.sleep(30)


def run_multi_user(logger: logging.Logger) -> None:
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)
    sync_seconds = env_int("FUNPAY_USER_SYNC_SECONDS", 60)
    max_users = env_int("FUNPAY_MAX_USERS", 0)
    user_agent = os.getenv("FUNPAY_USER_AGENT")

    mysql_cfg = get_mysql_config()
    logger.info("Multi-user mode enabled. Sync interval: %ss.", sync_seconds)

    running_ids: set[int] = set()

    while True:
        try:
            users = fetch_users(mysql_cfg)
            if max_users > 0:
                users = users[:max_users]

            for user in users:
                user_id = int(user["id"])
                if user_id in running_ids:
                    continue
                running_ids.add(user_id)
                thread = threading.Thread(
                    target=user_worker_loop,
                    args=(user, user_agent, poll_seconds),
                    daemon=True,
                )
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
