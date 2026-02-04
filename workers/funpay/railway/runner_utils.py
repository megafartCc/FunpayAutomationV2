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
    build_recent_chat_context,
    insert_chat_message,
    is_first_time_chat,
    process_chat_outbox,
    send_chat_message,
    send_message_by_owner,
    sync_chats_list,
    upsert_chat_summary,
)
from .account_utils import build_account_message, build_rental_choice_message, get_remaining_label, resolve_rental_minutes
from .command_handlers import build_stock_messages, handle_command
from .constants import (
    BUSY_EMPTY,
    BUSY_TITLE,
    COMMAND_PREFIXES,
    COMMANDS_RU,
    RENT_CONFIRM_MESSAGE,
    RENT_PRE_REQUEST_MESSAGE,
    RENT_STOCK_NOTE,
    RENT_FLOW_MESSAGE,
    RENTAL_REFUND_MESSAGE,
    RENTALS_EMPTY,
    STOCK_EMPTY,
    STOCK_LIST_LIMIT,
    STOCK_TITLE,
)
from .env_utils import env_bool, env_int
from .knowledge_utils import build_knowledge_context
from .memory_utils import fetch_memory_context, store_memory
from .logging_utils import configure_logging
from .models import RentalMonitorState
from .notifications_utils import log_notification_event, upsert_workspace_status
from .order_utils import (
    apply_review_bonus_for_order,
    extract_lot_number_from_order,
    fetch_latest_account_for_owner_lot,
    fetch_order_history_summary,
    handle_order_purchased,
    revert_review_bonus_for_order,
)
from .presence_utils import clear_lot_cache_on_start
from .proxy_utils import ensure_proxy_isolated, fetch_workspaces, normalize_proxy_url
from .raise_utils import auto_raise_loop, sync_raise_categories
from .rental_utils import process_rental_monitor, release_account_in_db
from .db_utils import get_mysql_config
from .lot_utils import (
    fetch_available_lot_accounts,
    fetch_busy_lot_accounts,
    fetch_lot_by_url,
    fetch_owner_accounts,
)
from .user_utils import get_user_id_by_username
from .text_utils import extract_order_id, parse_command

WELCOME_MESSAGE = os.getenv(
    "FUNPAY_WELCOME_MESSAGE",
    "\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435! \u0427\u0442\u043e\u0431\u044b \u0443\u0437\u043d\u0430\u0442\u044c \u043e \u043d\u0430\u043b\u0438\u0447\u0438\u0438 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u043e\u0432, \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u0443 !\u0441\u0442\u043e\u043a. \u042d\u0442\u043e \u043f\u043e\u043a\u0430\u0436\u0435\u0442 \u0442\u0435\u043a\u0443\u0449\u0438\u0439 \u0441\u0442\u0430\u0442\u0443\u0441 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u043e\u0432. \u0415\u0441\u043b\u0438 \u043d\u0443\u0436\u043d\u0430 \u043f\u043e\u043c\u043e\u0449\u044c \u2014 \u043f\u0440\u043e\u0441\u0442\u043e \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435.\n\n"
    + COMMANDS_RU,
)

LOT_URL_RE = re.compile(r"https?://funpay\.com/lots/offer\?id=\d+", re.IGNORECASE)
COMMAND_SUGGESTIONS = {
    "!free": "!сток",
    "!stock": "!сток",
    "!available": "!сток",
    "!avail": "!сток",
    "!acc": "!акк",
    "!account": "!акк",
    "!code": "!код",
    "!help": "!команды",
    "!commands": "!команды",
}


def _is_greeting(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    keywords = ("привет", "здрав", "hello", "hi", "добрый", "доброе")
    return any(word in lowered for word in keywords)


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


def _suggest_command(text: str) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned.startswith("!"):
        return None
    token = cleaned.split(maxsplit=1)[0].lower()
    if token in COMMAND_PREFIXES:
        return None
    return COMMAND_SUGGESTIONS.get(token)


def _find_recent_lot_url(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
) -> str | None:
    try:
        lines = build_recent_chat_context(
            mysql_cfg,
            int(user_id),
            int(workspace_id) if workspace_id is not None else None,
            int(chat_id),
            limit=10,
            include_bot=False,
        )
    except Exception:
        lines = []
    for line in reversed(lines):
        match = LOT_URL_RE.search(line)
        if match:
            return match.group(0)
    return None



def _find_recent_lot_urls(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    *,
    limit: int = 6,
) -> list[str]:
    try:
        lines = build_recent_chat_context(
            mysql_cfg,
            int(user_id),
            int(workspace_id) if workspace_id is not None else None,
            int(chat_id),
            limit=12,
            include_bot=True,
        )
    except Exception:
        lines = []
    urls: list[str] = []
    seen: set[str] = set()
    for line in reversed(lines):
        for match in LOT_URL_RE.findall(line):
            if match in seen:
                continue
            seen.add(match)
            urls.append(match)
            if len(urls) >= limit:
                return urls
    return urls

def _wants_when_free(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    keywords = (
        "когда освобод",
        "когда будет свобод",
        "когда свобод",
        "when free",
        "when available",
        "when it will be free",
    )
    return any(word in lowered for word in keywords)


def _format_eta_from_row(row: dict) -> str | None:
    try:
        expiry_str, remaining_str = get_remaining_label(row, datetime.utcnow())
    except Exception:
        return None
    if not expiry_str:
        return None
    return f"Ориентировочно освободится через {remaining_str} (в {expiry_str} МСК)."


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


def _respond_busy_lots(
    logger: logging.Logger,
    account: Account,
    chat_id: int,
    accounts: list[dict],
) -> None:
    if not accounts:
        send_chat_message(logger, account, chat_id, BUSY_EMPTY)
        return
    lines = build_stock_messages(accounts)
    if not lines:
        send_chat_message(logger, account, chat_id, BUSY_EMPTY)
        return
    limit = env_int("STOCK_LIST_LIMIT", STOCK_LIST_LIMIT)
    if limit <= 0:
        send_chat_message(logger, account, chat_id, "\n".join([BUSY_TITLE, *lines]))
        return
    for index in range(0, len(lines), limit):
        chunk = lines[index : index + limit]
        message = "\n".join([BUSY_TITLE, *chunk]) if index == 0 else "\n".join(chunk)
        send_chat_message(logger, account, chat_id, message)


def _wants_low_priority_replace(text: str) -> bool:
    if not text:
        return False
    if "Ð»Ð¿Ð·Ð°Ð¼ÐµÐ½Ð°" in text:
        return True
    if ("Ð·Ð°Ð¼ÐµÐ½" in text or "replace" in text or "replacement" in text) and (
        "Ð°ÐºÐºÐ°ÑÐ½Ñ" in text or "account" in text or "Ð»Ð¾Ñ" in text or "mmr" in text or "Ð»Ð¿" in text
    ):
        return True
    return False






def _wants_refund(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    keywords = (
        "\u0432\u043e\u0437\u0432\u0440\u0430\u0442",
        "\u0432\u0435\u0440\u043d\u0438",
        "\u0432\u0435\u0440\u043d\u0438\u0442\u0435",
        "\u0432\u0435\u0440\u043d\u0443\u0442\u044c",
        "\u0434\u0435\u043d\u044c\u0433\u0438",
        "\u0441\u0440\u0435\u0434\u0441\u0442\u0432\u0430",
        "\u0434\u0435\u043d\u044c\u0433\u0438 \u043e\u0431\u0440\u0430\u0442\u043d\u043e",
        "moneyback",
        "refund",
    )
    return any(key in lowered for key in keywords)


def _wants_account_info(text: str) -> bool:
    if not text:
        return False
    keywords = (
        "данные",
        "логин",
        "парол",
        "акк",
        "аккаунт",
        "мой",
        "мои",
        "скок",
        "сколько",
        "остал",
        "времени",
        "срок",
        "доступ",
        "Ð°ÑÐµÐ½Ð´",
        "Ð°ÑÐµÐ½Ð´Ð°",
        "Ð°ÑÐµÐ½Ð´Ñ",
        "rental",
        "rent",
        "ÑÐµÐºÑÑ",
        "Ð°ÐºÑÐ¸Ð²Ð½",
    )
    return any(key in text for key in keywords)



def _wants_command_list(text: str) -> bool:
    if not text:
        return False
    hints = ("команд", "commands", "help", "помощ", "что умеешь", "что можешь", "список команд")
    return any(word in text for word in hints)


def _wants_stock_list(text: str) -> bool:
    if not text:
        return False
    subjects = (
        "\u0430\u043a\u043a",
        "\u0430\u043a\u043a\u0430\u0443\u043d\u0442",
        "\u0430\u043a\u043a\u0430\u0443\u043d\u0442\u044b",
        "\u043b\u043e\u0442",
        "\u043b\u043e\u0442\u044b",
        "\u0441\u0442\u043e\u043a",
        "stock",
        "account",
        "acc",
    )
    hints = (
        "\u0441\u0432\u043e\u0431\u043e\u0434",
        "\u043d\u0430\u043b\u0438\u0447",
        "\u0435\u0441\u0442\u044c",
        "\u043f\u043e\u043a\u0430\u0437",
        "\u0441\u043f\u0438\u0441\u043e\u043a",
        "free",
        "available",
        "list",
        "show",
    )
    if "\u043a\u0430\u043a\u0438\u0435" in text and any(word in text for word in subjects):
        return True
    if "\u0441\u0432\u043e\u0431\u043e\u0434" in text and (
        "\u0447\u0442\u043e" in text or "\u0447\u0451" in text or "\u0447\u0435" in text or "\u0435\u0441\u0442\u044c" in text
    ):
        return True
    return any(word in text for word in hints) and any(word in text for word in subjects)


def _wants_busy_list(text: str) -> bool:
    if not text:
        return False
    subjects = ("\u0430\u043a\u043a\u0430\u0443\u043d\u0442", "\u0430\u043a\u043a\u0430\u0443\u043d\u0442\u044b", "\u043b\u043e\u0442", "\u043b\u043e\u0442\u044b")
    hints = ("\u0437\u0430\u043d\u044f\u0442", "busy", "occupied", "\u0432 \u0430\u0440\u0435\u043d\u0434\u0435")
    if "\u043a\u0430\u043a\u0438\u0435" in text and any(word in text for word in subjects) and any(word in text for word in hints):
        return True
    return any(word in text for word in hints) and any(word in text for word in subjects)


def _wants_pre_rent_request(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    account_words = (
        "\u0430\u043a\u043a",
        "\u0430\u043a\u043a\u0430\u0443\u043d\u0442",
        "account",
        "acc",
    )
    need_words = (
        "\u043d\u0443\u0436",
        "\u043d\u0430\u0434\u043e",
        "\u0445\u043e\u0447\u0443",
        "\u0441\u0434\u0435\u043b\u0430\u0435\u0448\u044c",
        "\u0441\u0434\u0435\u043b\u0430\u0439",
        "\u043e\u043f\u043b\u0430\u0447",
        "\u043e\u043f\u043b\u0430\u0442",
        "\u043a\u0443\u043f\u043b",
    )
    time_words = (
        "\u0447\u0430\u0441",
        "\u0447\u0430\u0441\u0430",
        "\u0447\u0430\u0441\u043e\u0432",
        "hour",
        "hours",
        "h",
    )
    if not any(word in lowered for word in account_words):
        return False
    if any(word in lowered for word in need_words):
        return True
    if any(word in lowered for word in time_words):
        return True
    if re.search(r"\b\d+\s*(?:\u0430\u043a\u043a|\u0430\u043a\u043a\u0430\u0443\u043d\u0442|acc|account)\b", lowered):
        return True
    return False


def _wants_rent_flow(text: str) -> bool:
    if not text:
        return False
    keywords = (
        "\u0430\u0440\u0435\u043d\u0434",
        "\u0432\u0437\u044f\u0442\u044c \u0430\u0440\u0435\u043d\u0434",
        "\u0445\u043e\u0447\u0443 \u0430\u0440\u0435\u043d\u0434",
        "rent",
        "rental",
    )
    return any(word in text for word in keywords)


def _wants_rent_confirmation(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    triggers = (
        "\u0435\u0441\u043b\u0438 \u044f \u043e\u043f\u043b\u0430",
        "\u043f\u043e\u0441\u043b\u0435 \u043e\u043f\u043b\u0430\u0442",
        "\u043e\u043f\u043b\u0430\u0447\u0443 \u043b\u043e\u0442",
        "\u043a\u0443\u043f\u043b\u044e \u043b\u043e\u0442",
    )
    asks = (
        "\u0432\u044b\u0434\u0430\u0434\u0438\u0442\u0435",
        "\u0432\u044b\u0434\u0430\u0448\u044c",
        "\u0434\u0430\u0434\u0438\u0442\u0435",
        "\u0434\u0430\u0448\u044c",
        "\u043f\u043e\u043b\u0443\u0447\u0443",
        "\u0434\u0430\u043d\u043d\u044b\u0435",
        "\u043b\u043e\u0433\u0438\u043d",
        "\u043f\u0430\u0440\u043e\u043b\u044c",
        "\u0434\u043e\u0441\u0442\u0443\u043f",
    )
    pay_words = (
        "\u043e\u043f\u043b\u0430",
        "\u043e\u043f\u043b\u0430\u0442",
        "\u043e\u043f\u043b\u0430\u0447",
        "\u043f\u043e\u043a\u0443\u043f",
        "\u043a\u0443\u043f\u043b",
    )
    if any(word in lowered for word in triggers):
        return True
    return any(word in lowered for word in pay_words) and any(word in lowered for word in asks)

def _extract_account_id_hint(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"(?:id|ID|Ð°Ð¹Ð´Ð¸|#)\s*(\d{2,})", text)
    if match:
        return match.group(1)
    return ""


def _build_rental_summary(accounts: list[dict], limit: int) -> list[str]:
    if not accounts or limit <= 0:
        return []
    now = datetime.utcnow()
    lines: list[str] = []
    for acc in accounts[:limit]:
        account_id = acc.get("id")
        name = acc.get("display_name") or acc.get("account_name") or f"ID {account_id}"
        expiry_str, remaining_str = get_remaining_label(acc, now)
        if expiry_str:
            remaining = f"{remaining_str} (expires {expiry_str} MSK)"
        else:
            remaining = "awaiting !ÐºÐ¾Ð´"
        status = "frozen" if acc.get("rental_frozen") else "active"
        label = f"ID {account_id}" if account_id is not None else "ID -"
        lines.append(f"{label}: {name} | {status} | remaining {remaining}")
    return lines


def _build_ai_context(
    user_text: str,
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    sender_username: str,
) -> str | None:
    history_limit = env_int("AI_CONTEXT_MESSAGES", 8)
    summary_limit = env_int("AI_RENTAL_SUMMARY_LIMIT", 5)
    history_lines: list[str] = []
    rental_lines: list[str] = []
    knowledge_text = ""
    memory_text = ""
    try:
        history_lines = build_recent_chat_context(
            mysql_cfg,
            int(user_id),
            int(workspace_id) if workspace_id is not None else None,
            int(chat_id),
            limit=history_limit,
            include_bot=False,
        )
    except Exception:
        history_lines = []
    try:
        accounts = fetch_owner_accounts(mysql_cfg, int(user_id), sender_username, workspace_id)
        rental_lines = _build_rental_summary(accounts, summary_limit)
    except Exception:
        rental_lines = []
    try:
        memory_text = fetch_memory_context(
            mysql_cfg,
            user_id=int(user_id),
            workspace_id=workspace_id,
            chat_id=int(chat_id),
            query=user_text,
        ) or ""
    except Exception:
        memory_text = ""
    try:
        knowledge_text = build_knowledge_context(
            user_text,
            max_chars=env_int("AI_KNOWLEDGE_MAX_CHARS", 1400),
            max_items=env_int("AI_KNOWLEDGE_MAX_ITEMS", 3),
        ) or ""
    except Exception:
        knowledge_text = ""
    sections: list[str] = []
    if memory_text:
        sections.append("Long-term memory:")
        sections.append(memory_text)
    if knowledge_text:
        sections.append("Knowledge base:")
        sections.append(knowledge_text)
    if history_lines:
        sections.append("Recent buyer messages:")
        sections.extend(history_lines)
    if rental_lines:
        sections.append("Current rentals summary:")
        sections.extend(rental_lines)
    return "\n".join(sections) if sections else None




def _extract_buyer_from_review_text(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"(?:Покупатель|The buyer)\s+([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    return None


def _extract_buyer_from_refund_text(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"(?:покупателю|buyer)\s+([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def _extract_command_tokens(text: str) -> list[str]:
    if not text:
        return []
    tokens = re.findall(r"![^\s]+", text.lower())
    cleaned: list[str] = []
    for token in tokens:
        token = token.strip(".,;:!?)]}>'\\\"")
        if token == "!":
            continue
        cleaned.append(token)
    return cleaned


def _contains_unknown_commands(text: str) -> bool:
    if not text:
        return False
    allowed = set(COMMAND_PREFIXES)
    for token in _extract_command_tokens(text):
        if token not in allowed:
            return True
    return False


def _format_review_reply_text(text_: str) -> str:
    max_len = 999
    text_ = text_[: max_len + 1]
    if len(text_) > max_len:
        ln = len(text_)
        indexes = []
        for char in (".", "!", "\n"):
            index1 = text_.rfind(char)
            indexes.extend([index1, text_[:index1].rfind(char)])
        text_ = text_[: max(indexes, key=lambda x: (x < ln - 1, x))] + "🐦"
    text_ = text_.strip()
    while text_.count("\n") > 9 and text_.count("\n\n") > 1:
        text_ = text_[::-1].replace("\n\n", "\n", min([text_.count("\n\n") - 1, text_.count("\n") - 9]))[::-1]
    if text_.count("\n") > 9:
        text_ = text_[::-1].replace("\n", " ", text_.count("\n") - 9)[::-1]
    return text_


def _build_review_reply_text(order) -> str | None:
    candidate = getattr(order, "short_description", None) or getattr(order, "title", None)
    if not candidate:
        candidate = getattr(order, "full_description", None) or getattr(order, "lot_params_text", None)
    if not candidate:
        return None
    return _format_review_reply_text(str(candidate))


def _handle_review_bonus(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    msg: object,
    chat_name: str,
    chat_id: int | None,
) -> None:
    if getattr(msg, "type", None) not in (
        MessageTypes.NEW_FEEDBACK,
        MessageTypes.FEEDBACK_CHANGED,
        MessageTypes.FEEDBACK_DELETED,
    ):
        return
    order_id = extract_order_id(getattr(msg, "text", None) or "")
    if not order_id:
        return
    order = None
    try:
        order = account.get_order(order_id)
    except Exception as exc:
        logger.warning("Failed to fetch order %s for review bonus: %s", order_id, exc)
    buyer = None
    if order is not None:
        buyer = getattr(order, "buyer_username", None)
    if not buyer:
        buyer = _extract_buyer_from_review_text(getattr(msg, "text", None) or "") or chat_name
    if not buyer:
        return
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        return
    bonus_minutes = env_int("REVIEW_BONUS_MINUTES", 60)
    bonus_label = f"+{bonus_minutes} минут"
    if int(bonus_minutes) == 60:
        bonus_label = "+1 час"

    def _send_bonus_message(updated: dict | None) -> None:
        if not updated or chat_id is None:
            return
        account_id = updated.get("id")
        account_suffix = f" аккаунту (ID {account_id})" if account_id is not None else ""
        message = f"✅ Продлил аренду на {bonus_label} по отзыву к{account_suffix}."
        send_chat_message(logger, account, int(chat_id), message)

    def _send_revert_message(updated: dict | None, reason: str) -> None:
        if not updated or chat_id is None:
            return
        account_id = updated.get("id")
        account_suffix = f" аккаунту (ID {account_id})" if account_id is not None else ""
        message = f"{reason} — бонус {bonus_label} отменён по{account_suffix}."
        send_chat_message(logger, account, int(chat_id), message)

    if getattr(msg, "type", None) == MessageTypes.FEEDBACK_DELETED:
        updated = revert_review_bonus_for_order(
            mysql_cfg,
            order_id=str(order_id),
            owner=buyer,
            bonus_minutes=int(bonus_minutes),
        )
        _send_revert_message(updated, "Отзыв удалён")
        return

    if order is None:
        return
    review = getattr(order, "review", None)
    stars = getattr(review, "stars", None)
    try:
        stars_value = int(stars)
    except Exception:
        return
    if getattr(msg, "type", None) in (MessageTypes.NEW_FEEDBACK, MessageTypes.FEEDBACK_CHANGED):
        reply_text = None
        if review is not None and getattr(review, "reply", None):
            reply_text = None
        else:
            reply_text = _build_review_reply_text(order)
        if reply_text:
            try:
                account.send_review(order.id, reply_text)
                logger.info("Replied to review for order %s.", order.id)
            except Exception:
                logger.exception("Failed to reply to review for order %s.", order.id)
    if stars_value == 5:
        updated = apply_review_bonus_for_order(
            mysql_cfg,
            order_id=str(order_id),
            owner=buyer,
            bonus_minutes=int(bonus_minutes),
        )
        _send_bonus_message(updated)
        return
    if getattr(msg, "type", None) == MessageTypes.FEEDBACK_CHANGED:
        updated = revert_review_bonus_for_order(
            mysql_cfg,
            order_id=str(order_id),
            owner=buyer,
            bonus_minutes=int(bonus_minutes),
        )
        _send_revert_message(updated, "Отзыв изменён")


def _handle_refund_release(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    msg: object,
    chat_name: str,
) -> None:
    if getattr(msg, "type", None) not in (
        MessageTypes.REFUND,
        MessageTypes.PARTIAL_REFUND,
        MessageTypes.REFUND_BY_ADMIN,
    ):
        return
    order_id = extract_order_id(getattr(msg, "text", None) or "")
    if not order_id:
        return
    order = None
    try:
        order = account.get_order(order_id)
    except Exception as exc:
        logger.warning("Failed to fetch order %s for refund handling: %s", order_id, exc)
    buyer = None
    if order is not None:
        buyer = getattr(order, "buyer_username", None)
    if not buyer:
        buyer = _extract_buyer_from_refund_text(getattr(msg, "text", None) or "") or chat_name
    if not buyer:
        return
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        return
    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            return
    if user_id is None:
        return

    summary = fetch_order_history_summary(
        mysql_cfg,
        order_id=str(order_id),
        owner=buyer,
        workspace_id=workspace_id,
    )
    account_id = summary.get("account_id") if summary else None
    target_workspace_id = (
        summary.get("workspace_id") if summary and summary.get("workspace_id") is not None else workspace_id
    )
    if account_id is None and order is not None:
        lot_number = extract_lot_number_from_order(order)
        if lot_number is not None:
            account_id = fetch_latest_account_for_owner_lot(
                mysql_cfg,
                owner=buyer,
                lot_number=int(lot_number),
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
    if account_id is None:
        try:
            owner_accounts = fetch_owner_accounts(mysql_cfg, int(user_id), buyer, workspace_id)
        except mysql.connector.Error:
            owner_accounts = []
        if len(owner_accounts) == 1:
            account_id = owner_accounts[0].get("id")
    if account_id is None:
        return

    released = release_account_in_db(
        mysql_cfg,
        int(account_id),
        int(user_id),
        target_workspace_id,
    )
    log_notification_event(
        mysql_cfg,
        event_type="refund_release",
        status="ok" if released else "failed",
        title="Rental refunded",
        message="Rental ended after refund." if released else "Refund detected but release failed.",
        owner=buyer,
        account_id=int(account_id),
        user_id=int(user_id),
        workspace_id=target_workspace_id,
        order_id=str(order_id),
    )
    if released:
        send_message_by_owner(logger, account, buyer, RENTAL_REFUND_MESSAGE)

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
    lower_text = ""

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
    lower_text = normalized_text.lower()
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

    if (
        not is_system
        and chat_id is not None
        and not getattr(msg, "by_bot", False)
        and message_text.strip().startswith("!")
        and not command
    ):
        if getattr(msg, "author_id", None) == getattr(account, "id", None):
            return None
        if account.username and sender_username and sender_username.lower() == account.username.lower():
            return None
        suggested = _suggest_command(message_text)
        if suggested:
            reply = (
                "\u041a\u043e\u043c\u0430\u043d\u0434\u0430 \u043d\u0435 \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u043d\u0430. "
                f"\u0412\u043e\u0437\u043c\u043e\u0436\u043d\u043e, \u0432\u044b \u0438\u043c\u0435\u043b\u0438 \u0432 \u0432\u0438\u0434\u0443 {suggested}.\n\n"
                + COMMANDS_RU
            )
        else:
            reply = (
                "\u041a\u043e\u043c\u0430\u043d\u0434\u0430 \u043d\u0435 \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u043d\u0430. "
                "\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u044b:\n"
                + COMMANDS_RU
            )
        send_chat_message(logger, account, int(chat_id), reply)
        return None
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
        if _is_greeting(lower_text):
            send_chat_message(logger, account, int(chat_id), WELCOME_MESSAGE)
            return None
    if not is_system and chat_id is not None and not getattr(msg, "by_bot", False) and not command:
        if getattr(msg, "author_id", None) == getattr(account, "id", None):
            return None
        if account.username and sender_username and sender_username.lower() == account.username.lower():
            return None
        suggested = _suggest_command(message_text)
        if suggested:
            if suggested == "!команды":
                send_chat_message(logger, account, int(chat_id), COMMANDS_RU)
            else:
                send_chat_message(
                    logger,
                    account,
                    int(chat_id),
                    f"Команда не распознана. Возможно, вы имели в виду {suggested}.",
                )
            return None
        if _wants_command_list(lower_text):
            send_chat_message(logger, account, int(chat_id), COMMANDS_RU)
            return None

        if mysql_cfg and user_id is not None:
            wants_busy = _wants_busy_list(lower_text)
            if wants_busy:
                accounts = fetch_busy_lot_accounts(mysql_cfg, int(user_id), workspace_id)
                _respond_busy_lots(logger, account, int(chat_id), accounts)
                return None
            wants_stock = _wants_stock_list(lower_text)
            if wants_stock:
                accounts = fetch_available_lot_accounts(mysql_cfg, int(user_id), workspace_id)
                _respond_free_lots(logger, account, int(chat_id), accounts)
                if _wants_rent_flow(lower_text) or _wants_pre_rent_request(lower_text):
                    send_chat_message(logger, account, int(chat_id), RENT_STOCK_NOTE)
                return None

        if _wants_pre_rent_request(lower_text):
            send_chat_message(logger, account, int(chat_id), RENT_PRE_REQUEST_MESSAGE)
            return None

        if _wants_rent_flow(lower_text):
            send_chat_message(logger, account, int(chat_id), RENT_FLOW_MESSAGE)
            return None

        if _wants_rent_confirmation(lower_text):
            send_chat_message(logger, account, int(chat_id), RENT_CONFIRM_MESSAGE)
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
                    if available:
                        reply = (
                            f"Да, аккаунт {name} сейчас свободен — вы можете его арендовать."
                        )
                    else:
                        eta = _format_eta_from_row(row)
                        if eta:
                            reply = f"Сейчас аккаунт {name} занят. {eta}"
                        else:
                            reply = f"Сейчас аккаунт {name} занят. Пока неизвестно, когда освободится."
                    send_chat_message(logger, account, int(chat_id), reply)
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
        if _wants_when_free(lower_text):
            if not mysql_cfg or user_id is None:
                send_chat_message(
                    logger,
                    account,
                    int(chat_id),
                    "Сейчас я не могу проверить занятость. Проверьте статус через команду !сток.",
                )
                return None
            lot_url = _find_recent_lot_url(mysql_cfg, int(user_id), workspace_id, int(chat_id))
            lot_urls = [lot_url] if lot_url else _find_recent_lot_urls(mysql_cfg, int(user_id), workspace_id, int(chat_id))
            if not lot_urls:
                send_chat_message(
                    logger,
                    account,
                    int(chat_id),
                    "Пожалуйста, пришлите ссылку на лот, чтобы проверить.",
                )
                return None
            if not lot_url and len(lot_urls) > 1:
                lines: list[str] = []
                for url in lot_urls[:5]:
                    row = fetch_lot_by_url(mysql_cfg, url, user_id=int(user_id), workspace_id=workspace_id)
                    if row:
                        name = _lot_display_name(row)
                        if row.get("owner"):
                            eta = _format_eta_from_row(row)
                            if eta:
                                line = f"{name}: {eta}"
                            else:
                                line = f"{name}: занят, время неизвестно."
                        else:
                            line = f"{name}: свободен."
                    else:
                        line = "Лот не найден."
                    lines.append(line)
                message = (
                    "По последним лотам из чата:\n- "
                    + "\n- ".join(lines)
                    + "\nЧтобы узнать точно, пришлите ссылку на конкретный лот."
                )
                send_chat_message(logger, account, int(chat_id), message)
                return None
            lot_url = lot_urls[0]
            row = fetch_lot_by_url(mysql_cfg, lot_url, user_id=int(user_id), workspace_id=workspace_id)
            row = fetch_lot_by_url(mysql_cfg, lot_url, user_id=int(user_id), workspace_id=workspace_id)
            if row and row.get("owner"):
                eta = _format_eta_from_row(row)
                if eta:
                    send_chat_message(logger, account, int(chat_id), eta)
                else:
                    send_chat_message(
                        logger,
                        account,
                        int(chat_id),
                        "Сейчас я не могу оценить время освобождения. Проверьте статус через команду !сток.",
                    )
                return None
            if row and not row.get("owner"):
                send_chat_message(
                    logger,
                    account,
                    int(chat_id),
                    "Этот лот свободен. Можете арендовать.",
                )
                return None
            send_chat_message(
                logger,
                account,
                int(chat_id),
                "Лот не найден. Пришлите ссылку ещё раз.",
            )
            return None
        if mysql_cfg and user_id is not None:
            if _wants_account_info(lower_text):
                accounts = fetch_owner_accounts(mysql_cfg, int(user_id), sender_username, workspace_id)
                if not accounts:
                    send_chat_message(logger, account, int(chat_id), RENTALS_EMPTY)
                    return None
                if len(accounts) > 1:
                    send_chat_message(
                        logger,
                        account,
                        int(chat_id),
                        build_rental_choice_message(accounts, "!\u0430\u043a\u043a"),
                    )
                    return None
                selected = accounts[0]
                message = build_account_message(
                    selected,
                    resolve_rental_minutes(selected),
                    include_timer_note=True,
                )
                send_chat_message(logger, account, int(chat_id), message)
                return None

            if _wants_low_priority_replace(lower_text):
                handle_command(
                    logger,
                    account,
                    site_username,
                    site_user_id,
                    workspace_id,
                    chat_name,
                    sender_username,
                    msg.chat_id,
                    "!Ð»Ð¿Ð·Ð°Ð¼ÐµÐ½Ð°",
                    _extract_account_id_hint(message_text),
                    chat_url,
                )
                return None
        if _wants_refund(lower_text):
            send_chat_message(
                logger,
                account,
                int(chat_id),
                "По вопросам возврата напишите !админ — я подключу продавца, он разберётся.",
            )
            return None
    if not is_system and chat_id is not None and not getattr(msg, "by_bot", False) and not command:
        if getattr(msg, "author_id", None) == getattr(account, "id", None):
            return None
        if account.username and sender_username and sender_username.lower() == account.username.lower():
            return None
        ai_context = None
        if mysql_cfg and user_id is not None and chat_id is not None:
            ai_context = _build_ai_context(
                message_text,
                mysql_cfg,
                int(user_id),
                workspace_id,
                int(chat_id),
                sender_username,
            )
        ai_text = generate_ai_reply(
            message_text,
            sender=sender_username,
            chat_name=chat_name,
            context=ai_context,
        )
        if ai_text:
            if _contains_unknown_commands(ai_text):
                send_chat_message(
                    logger,
                    account,
                    int(chat_id),
                    "Я не выполняю действия напрямую. Используйте команды:\n" + COMMANDS_RU,
                )
                return None
            send_chat_message(logger, account, int(chat_id), ai_text)
            if mysql_cfg and user_id is not None and chat_id is not None:
                try:
                    store_memory(
                        mysql_cfg,
                        user_id=int(user_id),
                        workspace_id=workspace_id,
                        chat_id=int(chat_id),
                        user_text=message_text,
                        ai_text=ai_text,
                    )
                except Exception:
                    pass
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
        if msg.type in (MessageTypes.NEW_FEEDBACK, MessageTypes.FEEDBACK_CHANGED, MessageTypes.FEEDBACK_DELETED):
            _handle_review_bonus(
                logger,
                account,
                site_username,
                site_user_id,
                workspace_id,
                msg,
                chat_name,
                chat_id,
            )
        _handle_refund_release(
            logger,
            account,
            site_username,
            site_user_id,
            workspace_id,
            msg,
            chat_name,
        )
        if msg.type == MessageTypes.ORDER_PURCHASED:
            handle_order_purchased(
                logger,
                account,
                site_username,
                site_user_id,
                workspace_id,
                msg,
            )
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
    raise_sync_interval = env_int("RAISE_CATEGORIES_SYNC_SECONDS", 6 * 3600)
    raise_profile_sync = env_int("RAISE_PROFILE_SYNC_SECONDS", 3600)
    auto_raise_enabled = lambda: True
    raise_sync_last = 0.0

    logger.info("Initializing FunPay account...")
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    logger.info("Bot started for %s.", account.username or "unknown")

    stop_event = threading.Event()
    mysql_cfg = None
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        mysql_cfg = None
    user_id = None
    if mysql_cfg and account.username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, account.username)
        except Exception:
            user_id = None
    threading.Thread(target=refresh_session_loop, args=(account, 3600, None), daemon=True).start()
    threading.Thread(
        target=auto_raise_loop,
        args=(),
        kwargs={
            "account": account,
            "mysql_cfg": mysql_cfg,
            "user_id": user_id,
            "workspace_id": None,
            "enabled_fn": auto_raise_enabled,
            "stop_event": stop_event,
            "profile_sync_seconds": raise_profile_sync,
        },
        daemon=True,
    ).start()

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
                    if time.time() - raise_sync_last >= raise_sync_interval:
                        try:
                            sync_raise_categories(mysql_cfg, account=account, user_id=int(user_id), workspace_id=None)
                        except Exception:
                            logger.debug("Raise categories sync failed.", exc_info=True)
                        raise_sync_last = time.time()
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
    raise_sync_interval = env_int("RAISE_CATEGORIES_SYNC_SECONDS", 6 * 3600)
    raise_sync_last = 0.0
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        mysql_cfg = None
    last_status_ping = 0.0
    status_platform = (workspace.get("platform") or "funpay").lower()
    auto_raise_enabled = lambda: True
    raise_profile_sync = env_int("RAISE_PROFILE_SYNC_SECONDS", 3600)
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
                try:
                    sync_raise_categories(
                        mysql_cfg,
                        account=account,
                        user_id=int(user_id),
                        workspace_id=int(workspace_id) if workspace_id is not None else None,
                    )
                    raise_sync_last = time.time()
                except Exception:
                    logger.debug("%s Raise categories sync failed.", label, exc_info=True)

            threading.Thread(
                target=auto_raise_loop,
                args=(),
                kwargs={
                    "account": account,
                    "mysql_cfg": mysql_cfg,
                    "user_id": int(user_id) if user_id is not None else None,
                    "workspace_id": int(workspace_id) if workspace_id is not None else None,
                    "enabled_fn": auto_raise_enabled,
                    "stop_event": stop_event,
                    "profile_sync_seconds": raise_profile_sync,
                },
                daemon=True,
            ).start()

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
                    if time.time() - raise_sync_last >= raise_sync_interval:
                        try:
                            sync_raise_categories(
                                mysql_cfg,
                                account=account,
                                user_id=int(user_id),
                                workspace_id=int(workspace_id) if workspace_id is not None else None,
                            )
                            raise_sync_last = time.time()
                        except Exception:
                            logger.debug("%s Raise categories sync failed.", label, exc_info=True)
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
