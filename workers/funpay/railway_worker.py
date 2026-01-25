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
from FunPayAPI.common.enums import MessageTypes  # noqa: E402
from FunPayAPI.updater.events import NewMessageEvent  # noqa: E402
from FunPayAPI.updater.runner import Runner  # noqa: E402


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
    include_self: bool,
    include_system: bool,
    event: NewMessageEvent,
    last_stack_id: str | None,
) -> str | None:
    stack = event.stack.get_stack() if event.stack else [event]
    stack_id = event.stack.id() if event.stack else f"{event.message.chat_id}:{event.message.id}"
    if stack_id == last_stack_id:
        return last_stack_id

    for item in stack:
        msg = item.message
        if not include_self and account.id is not None and msg.author_id == account.id:
            continue
        if not include_system and msg.type is not None and msg.type != MessageTypes.NON_SYSTEM:
            continue

        text = msg.text or msg.image_link or ""
        text = text.replace("\n", " ").strip()
        if not text:
            continue

        logger.info(
            "user=%s chat_id=%s chat_name=%s author=%s: %s",
            site_username or "-",
            msg.chat_id,
            msg.chat_name or "-",
            msg.author or "-",
            text,
        )

    return stack_id


def run_single_user(logger: logging.Logger) -> None:
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")
    if not golden_key:
        logger.error("FUNPAY_GOLDEN_KEY is required (set FUNPAY_MULTI_USER=1 for DB mode).")
        sys.exit(1)

    user_agent = os.getenv("FUNPAY_USER_AGENT")
    include_self = env_bool("FUNPAY_LOG_INCLUDE_SELF", False)
    include_system = env_bool("FUNPAY_LOG_INCLUDE_SYSTEM", False)
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)

    logger.info("Initializing FunPay account...")
    account = Account(golden_key, user_agent=user_agent)
    account.get()
    logger.info("Bot started for %s.", account.username or "unknown")

    threading.Thread(target=refresh_session_loop, args=(account, 3600, None), daemon=True).start()

    runner = Runner(account, disable_message_requests=False)
    last_stack_id: str | None = None

    logger.info("Listening for new messages...")
    for event in runner.listen(requests_delay=poll_seconds):
        if not isinstance(event, NewMessageEvent):
            continue
        last_stack_id = log_message(
            logger,
            account,
            account.username,
            include_self,
            include_system,
            event,
            last_stack_id,
        )


def user_worker_loop(user: dict, include_self: bool, include_system: bool, user_agent: str | None, poll_seconds: int) -> None:
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
            last_stack_id: str | None = None
            for event in runner.listen(requests_delay=poll_seconds):
                if not isinstance(event, NewMessageEvent):
                    continue
                last_stack_id = log_message(
                    logger,
                    account,
                    site_username,
                    include_self,
                    include_system,
                    event,
                    last_stack_id,
                )
        except Exception:
            logger.exception("%s Worker crashed. Restarting in 30s.", label)
            time.sleep(30)


def run_multi_user(logger: logging.Logger) -> None:
    include_self = env_bool("FUNPAY_LOG_INCLUDE_SELF", False)
    include_system = env_bool("FUNPAY_LOG_INCLUDE_SYSTEM", False)
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
                    args=(user, include_self, include_system, user_agent, poll_seconds),
                    daemon=True,
                )
                thread.start()
            time.sleep(sync_seconds)
        except Exception:
            logger.exception("User sync failed. Retrying in 30s.")
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
