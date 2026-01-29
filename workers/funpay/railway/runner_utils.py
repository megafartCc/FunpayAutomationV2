from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
from datetime import datetime

import mysql.connector
from FunPayAPI.account import Account
from FunPayAPI.common import exceptions as fp_exceptions
from FunPayAPI.common.enums import EventTypes, MessageTypes
from FunPayAPI.updater.events import NewMessageEvent
from FunPayAPI.updater.runner import Runner
from bs4 import BeautifulSoup

from .chat_time_utils import _extract_datetime_from_html
from .ai_utils import generate_ai_reply
from .chat_utils import (
    insert_chat_message,
    is_first_time_chat,
    process_chat_outbox,
    send_chat_message,
    sync_chats_list,
    upsert_chat_summary,
)
from .command_handlers import build_stock_messages, handle_command
from .constants import COMMANDS_RU, STOCK_EMPTY, STOCK_LIST_LIMIT, STOCK_TITLE
from .env_utils import env_bool, env_int
from .logging_utils import configure_logging
from .models import RentalMonitorState
from .notifications_utils import upsert_workspace_status
from .order_utils import handle_order_purchased
from .presence_utils import clear_lot_cache_on_start
from .proxy_utils import ensure_proxy_isolated, fetch_workspaces, normalize_proxy_url
from .rental_utils import process_rental_monitor
from .db_utils import get_mysql_config
from .lot_utils import fetch_available_lot_accounts, fetch_lot_by_url
from .user_utils import get_user_id_by_username
from .text_utils import parse_command

WELCOME_MESSAGE = os.getenv(
    "FUNPAY_WELCOME_MESSAGE",
    "\u041f\u0440\u0438\u0432\u0435\u0442, "
    "\u0432\u044b\u0434\u0430\u0447\u0430 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u043e\u0432 "
    "\u043f\u043e\u043b\u043d\u043e\u0441\u0442\u044c\u044e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0437\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u0430\u044f."
    "\n\n"
    + COMMANDS_RU,
)

LOT_URL_RE = re.compile(r"https?://funpay\\.com/lots/offer\\?id=\\d+", re.IGNORECASE)


def _extract_lot_url(text: str) -> str | None:
    if not text:
        return None
    url_match = LOT_URL_RE.search(text)
    if url_match:
        return url_match.group(0)
    cleaned = re.sub(r"[^A-Za-z0-9:/?=._-]", "", text)
    url_match = LOT_URL_RE.search(cleaned)
    if url_match:
        return url_match.group(0)
    return None


def _lot_display_name(row: dict) -> str:
    return (
        row.get("display_name")
        or row.get("account_name")
        or row.get("login")
        or row.get("lot_number")
        or "Лот"
    )


def _respond_free_lots(
    logger: logging.Logger,
    account: Account,
    chat_id: int,
    accounts: list[dict],
) -> None:
    if not accounts:
        send_chat_message(logger, account, chat_id, STOCK_EMPTY)
        return
    lines = build_stock_messages(accounts)
    if not lines:
        send_chat_message(logger, account, chat_id, STOCK_EMPTY)
        return
    limit = env_int("STOCK_LIST_LIMIT", STOCK_LIST_LIMIT)
    if limit <= 0:
        send_chat_message(logger, account, chat_id, "\n".join([STOCK_TITLE, *lines]))
        return
    for index in range(0, len(lines), limit):
        chunk = lines[index : index + limit]
        message = "\n".join([STOCK_TITLE, *chunk]) if index == 0 else "\n".join(chunk)
        send_chat_message(logger, account, chat_id, message)


def _is_rental_related(text: str) -> bool:
    if not text:
        return False
    keywords = (
        "аренд",
        "аккаунт",
        "лот",
        "сток",
        "код",
        "steam",
        "доступ",
        "заказ",
        "покуп",
        "оплат",
        "продл",
        "замен",
        "ммр",
        "mmr",
        "логин",
        "парол",
    )
    return any(key in text for key in keywords)


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


def log_message(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    event: NewMessageEvent,
) -> str | None:
    if event.type is not EventTypes.NEW_MESSAGE:
        return None

    msg = event.message

    sender_username = None

    if getattr(msg, "html", None):
        try:
            soup = BeautifulSoup(msg.html, "lxml")
            link = soup.find("a", {"class": "chat-msg-author-link"})
            if link and link.text:
                sender_username = link.text.strip()
        except Exception:
            sender_username = None

    if not sender_username and msg.author:
        sender_username = msg.author
    if not sender_username and msg.chat_name:
        sender_username = msg.chat_name
    if not sender_username and msg.author_id:
        sender_username = f"user_{msg.author_id}"
    if not sender_username and msg.interlocutor_id:
        sender_username = f"user_{msg.interlocutor_id}"
    if not sender_username:
        sender_username = f"chat_{msg.chat_id}"

    message_text = msg.text or ""
    normalized_text = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", message_text)
    command, command_args = parse_command(message_text)
    if not sender_username or sender_username == "-":
        return None

    chat_id = msg.chat_id
    chat_url = f"https://funpay.com/chat/?node={chat_id}" if chat_id is not None else "-"

    is_system = bool(msg.type and msg.type is not MessageTypes.NON_SYSTEM)
    if msg.author_id == 0 or (sender_username and sender_username.lower() == "funpay"):
        is_system = True

    chat_name = msg.chat_name or msg.author or "-"
    logger.info(
        "user=%s workspace=%s chat=%s author=%s system=%s url=%s: %s",
        site_username or "-",
        workspace_id if workspace_id is not None else "-",
        chat_name,
        sender_username,
        is_system,
        chat_url,
        message_text,
    )
    user_id = site_user_id
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        mysql_cfg = None

    first_time = False
    if mysql_cfg and chat_id is not None:
        if user_id is None and site_username:
            try:
                user_id = get_user_id_by_username(mysql_cfg, site_username)
            except mysql.connector.Error:
                user_id = None
        if user_id is not None:
            try:
                first_time = is_first_time_chat(
                    mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=workspace_id,
                    chat_id=int(chat_id),
                )
            except Exception:
                first_time = False
            try:
                msg_id = int(getattr(msg, "id", 0) or 0)
                if msg_id <= 0:
                    msg_id = int(time.time() * 1000)
                sent_time = _extract_datetime_from_html(getattr(msg, "html", None)) or datetime.utcnow()
                insert_chat_message(
                    mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=workspace_id,
                    chat_id=int(chat_id),
                    message_id=msg_id,
                    author=sender_username,
                    text=message_text,
                    by_bot=bool(getattr(msg, "by_bot", False)),
                    message_type=getattr(msg.type, "name", None),
                    sent_time=sent_time,
                )
                upsert_chat_summary(
                    mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=workspace_id,
                    chat_id=int(chat_id),
                    name=chat_name,
                    last_message_text=message_text,
                    unread=not bool(getattr(msg, "by_bot", False)),
                    last_message_time=sent_time,
                )
            except Exception:
                pass
    if command:
        logger.info(
            "user=%s workspace=%s chat=%s author=%s command=%s args=%s url=%s",
            site_username or "-",
            workspace_id if workspace_id is not None else "-",
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
                workspace_id,
                chat_name,
                sender_username,
                msg.chat_id,
                command,
                command_args,
                chat_url,
            )
    if first_time and not is_system and chat_id is not None and not getattr(msg, "by_bot", False):
        if getattr(msg, "author_id", None) == getattr(account, "id", None):
            return None
        if account.username and sender_username and sender_username.lower() == account.username.lower():
            return None
        send_chat_message(logger, account, int(chat_id), WELCOME_MESSAGE)
        return None
    if not is_system and chat_id is not None and not getattr(msg, "by_bot", False) and not command:
        if getattr(msg, "author_id", None) == getattr(account, "id", None):
            return None
        if account.username and sender_username and sender_username.lower() == account.username.lower():
            return None
        lower_text = normalized_text.lower()
        if not _is_rental_related(lower_text):
            send_chat_message(
                logger,
                account,
                int(chat_id),
                "Я отвечаю только по аренде аккаунтов. Напишите вопрос по аренде или используйте команды:\n"
                + COMMANDS_RU,
            )
            return None
        lot_url = _extract_lot_url(normalized_text)
        if lot_url:
            logger.info(
                "user=%s workspace=%s chat=%s detected_lot_url=%s",
                site_username or "-",
                workspace_id if workspace_id is not None else "-",
                chat_name,
                lot_url,
            )
            if mysql_cfg and user_id is not None:
                row = fetch_lot_by_url(mysql_cfg, lot_url, user_id=int(user_id), workspace_id=workspace_id)
                if row:
                    available = (
                        not row.get("owner")
                        and not row.get("account_frozen")
                        and not row.get("rental_frozen")
                        and not row.get("low_priority")
                    )
                    name = _lot_display_name(row)
                    status = "свободен" if available else "занят"
                    send_chat_message(logger, account, int(chat_id), f"{name}: {status}.")
                else:
                    send_chat_message(logger, account, int(chat_id), "Лот не найден в базе.")
            else:
                send_chat_message(
                    logger,
                    account,
                    int(chat_id),
                    "Не могу проверить лот сейчас. Используйте команду !сток.",
                )
            return None
        if mysql_cfg and user_id is not None:
            wants_stock = ("лот" in lower_text and "свобод" in lower_text) or (
                "free" in lower_text and "lot" in lower_text
            )
            if wants_stock:
                accounts = fetch_available_lot_accounts(mysql_cfg, int(user_id), workspace_id)
                _respond_free_lots(logger, account, int(chat_id), accounts)
                return None
    if not is_system and chat_id is not None and not getattr(msg, "by_bot", False) and not command:
        if getattr(msg, "author_id", None) == getattr(account, "id", None):
            return None
        if account.username and sender_username and sender_username.lower() == account.username.lower():
            return None
        ai_text = generate_ai_reply(
            message_text,
            sender=sender_username,
            chat_name=chat_name,
        )
        if ai_text:
            send_chat_message(logger, account, int(chat_id), ai_text)
    if is_system:
        logger.info(
            "user=%s workspace=%s system_event type=%s chat=%s url=%s raw=%s",
            site_username or "-",
            workspace_id if workspace_id is not None else "-",
            getattr(msg.type, "name", msg.type),
            chat_name,
            chat_url,
            (msg.text or "").strip(),
        )
        if msg.type == MessageTypes.ORDER_PURCHASED:
            handle_order_purchased(logger, account, site_username, site_user_id, workspace_id, msg)
    return None


def run_single_user(logger: logging.Logger) -> None:
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")
    if not golden_key:
        logger.error("FUNPAY_GOLDEN_KEY is required (set FUNPAY_MULTI_USER=1 for DB mode).")
        sys.exit(1)

    proxy_url = normalize_proxy_url(os.getenv("FUNPAY_PROXY_URL"))
    if not proxy_url:
        logger.error("FUNPAY_PROXY_URL is required to start the bot.")
        sys.exit(1)
    proxy_cfg = ensure_proxy_isolated(logger, proxy_url, "[single-user]", fatal=True)
    if not proxy_cfg:
        sys.exit(1)

    user_agent = os.getenv("FUNPAY_USER_AGENT")
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)

    logger.info("Initializing FunPay account...")
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    logger.info("Bot started for %s.", account.username or "unknown")

    threading.Thread(target=refresh_session_loop, args=(account, 3600, None), daemon=True).start()

    runner = Runner(account, disable_message_requests=False)
    logger.info("Listening for new messages...")
    state = RentalMonitorState()
    chat_sync_interval = env_int("CHAT_SYNC_SECONDS", 30)
    chat_sync_last = 0.0
    while True:
        updates = runner.get_updates()
        events = runner.parse_updates(updates)
        for event in events:
            if isinstance(event, NewMessageEvent):
                log_message(logger, account, account.username, None, None, event)
        process_rental_monitor(logger, account, account.username, None, None, state)
        try:
            mysql_cfg = get_mysql_config()
        except RuntimeError:
            mysql_cfg = None
        if mysql_cfg:
            if time.time() - chat_sync_last >= chat_sync_interval:
                user_id = get_user_id_by_username(mysql_cfg, account.username) if account.username else None
                if user_id is not None:
                    sync_chats_list(mysql_cfg, account, user_id=user_id, workspace_id=None)
                    chat_sync_last = time.time()
            if account.username:
                user_id = get_user_id_by_username(mysql_cfg, account.username)
                if user_id is not None:
                    process_chat_outbox(logger, mysql_cfg, account, user_id=user_id, workspace_id=None)
        time.sleep(poll_seconds)


def workspace_worker_loop(
    workspace: dict,
    user_agent: str | None,
    poll_seconds: int,
    stop_event: threading.Event,
) -> None:
    logger = logging.getLogger("funpay.worker")
    workspace_id = workspace.get("workspace_id")
    workspace_name = workspace.get("workspace_name") or f"Workspace {workspace_id}"
    user_id = workspace.get("user_id")
    site_username = workspace.get("username") or f"user-{user_id}"
    golden_key = workspace.get("golden_key")
    proxy_url = normalize_proxy_url(workspace.get("proxy_url"))
    label = f"[{workspace_name}]"

    state = RentalMonitorState()
    chat_sync_interval = env_int("CHAT_SYNC_SECONDS", 30)
    chat_sync_last = 0.0
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        mysql_cfg = None
    last_status_ping = 0.0
    status_platform = (workspace.get("platform") or "funpay").lower()
    while not stop_event.is_set():
        try:
            if not golden_key:
                logger.warning("%s Missing golden_key, skipping.", label)
                if mysql_cfg and user_id is not None:
                    upsert_workspace_status(
                        mysql_cfg,
                        user_id=int(user_id),
                        workspace_id=int(workspace_id) if workspace_id is not None else None,
                        platform=status_platform,
                        status="unauthorized",
                        message="Missing golden key.",
                    )
                return
            proxy_cfg = ensure_proxy_isolated(logger, proxy_url, label)
            if not proxy_cfg:
                if mysql_cfg and user_id is not None:
                    upsert_workspace_status(
                        mysql_cfg,
                        user_id=int(user_id),
                        workspace_id=int(workspace_id) if workspace_id is not None else None,
                        platform=status_platform,
                        status="error",
                        message="Proxy connection failed.",
                    )
                return

            account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
            account.get()
            logger.info("Bot started for %s (%s).", site_username, workspace_name)
            if mysql_cfg and user_id is not None:
                upsert_workspace_status(
                    mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=int(workspace_id) if workspace_id is not None else None,
                    platform=status_platform,
                    status="ok",
                    message="Connected to FunPay.",
                )
                last_status_ping = time.time()

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
                        log_message(logger, account, site_username, user_id, workspace_id, event)
                process_rental_monitor(logger, account, site_username, user_id, workspace_id, state)
                if mysql_cfg and user_id is not None:
                    if time.time() - chat_sync_last >= chat_sync_interval:
                        sync_chats_list(mysql_cfg, account, user_id=int(user_id), workspace_id=workspace_id)
                        chat_sync_last = time.time()
                    process_chat_outbox(logger, mysql_cfg, account, user_id=int(user_id), workspace_id=workspace_id)
                    if time.time() - last_status_ping >= 60:
                        upsert_workspace_status(
                            mysql_cfg,
                            user_id=int(user_id),
                            workspace_id=int(workspace_id) if workspace_id is not None else None,
                            platform=status_platform,
                            status="ok",
                            message="Connected to FunPay.",
                        )
                        last_status_ping = time.time()
                time.sleep(poll_seconds)
        except Exception as exc:
            if mysql_cfg and user_id is not None:
                status = "error"
                message = None
                if isinstance(exc, fp_exceptions.UnauthorizedError):
                    status = "unauthorized"
                    message = "Authorization required."
                elif isinstance(exc, fp_exceptions.RequestFailedError):
                    message = exc.short_str() if hasattr(exc, "short_str") else str(exc)
                else:
                    message = str(exc)[:200]
                upsert_workspace_status(
                    mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=int(workspace_id) if workspace_id is not None else None,
                    platform=status_platform,
                    status=status,
                    message=message,
                )
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
            workspaces = fetch_workspaces(mysql_cfg)
            if max_users > 0:
                workspaces = workspaces[:max_users]

            desired = {
                int(ws["workspace_id"]): ws
                for ws in workspaces
                if ws.get("workspace_id") is not None
            }

            active_ids = list(workers.keys())
            for workspace_id in active_ids:
                if workspace_id not in desired:
                    worker_info = workers.pop(workspace_id)
                    stop_event = worker_info.get("stop")
                    thread = worker_info.get("thread")
                    if stop_event:
                        stop_event.set()
                    if thread:
                        thread.join(timeout=3)

            for workspace_id, workspace in desired.items():
                golden_key = workspace.get("golden_key")
                proxy_url = workspace.get("proxy_url")
                existing = workers.get(workspace_id)
                if existing:
                    if existing.get("golden_key") == golden_key and existing.get("proxy_url") == proxy_url:
                        continue
                    stop_event = existing.get("stop")
                    thread = existing.get("thread")
                    if stop_event:
                        stop_event.set()
                    if thread:
                        thread.join(timeout=3)
                stop_event = threading.Event()
                thread = threading.Thread(
                    target=workspace_worker_loop,
                    args=(workspace, user_agent, poll_seconds, stop_event),
                    daemon=True,
                )
                workers[workspace_id] = {
                    "golden_key": golden_key,
                    "proxy_url": proxy_url,
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
    clear_lot_cache_on_start()
    explicit_multi = os.getenv("FUNPAY_MULTI_USER")
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")

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
