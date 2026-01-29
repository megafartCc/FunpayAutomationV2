from __future__ import annotations

import logging
import os
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
from .chat_utils import insert_chat_message, process_chat_outbox, sync_chats_list, upsert_chat_summary
from .command_handlers import handle_command
from .env_utils import env_bool, env_int
from .logging_utils import configure_logging
from .models import RentalMonitorState
from .notifications_utils import upsert_workspace_status
from .order_utils import handle_order_purchased
from .presence_utils import clear_lot_cache_on_start
from .proxy_utils import ensure_proxy_isolated, fetch_workspaces, normalize_proxy_url
from .rental_utils import process_rental_monitor
from .db_utils import get_mysql_config
from .user_utils import get_user_id_by_username
from .text_utils import parse_command


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

    message_text = msg.text
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
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        mysql_cfg = None

    if mysql_cfg and chat_id is not None:
        user_id = site_user_id
        if user_id is None and site_username:
            try:
                user_id = get_user_id_by_username(mysql_cfg, site_username)
            except mysql.connector.Error:
                user_id = None
        if user_id is not None:
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
