from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import re
import struct
import sys
import threading
import time
from datetime import datetime, timedelta
from hashlib import sha1
from pathlib import Path
from urllib.parse import urlparse

# Allow running from repo root while importing FunPayAPI from this folder.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mysql.connector  # noqa: E402
from FunPayAPI.account import Account  # noqa: E402
from FunPayAPI.common.enums import EventTypes, MessageTypes  # noqa: E402
from FunPayAPI.common.utils import RegularExpressions  # noqa: E402
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
RENTALS_EMPTY = "\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0430\u0440\u0435\u043d\u0434 \u043d\u0435\u0442."
ORDER_LOT_MISSING = (
    "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0438\u0442\u044c \u043b\u043e\u0442. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 !\u0430\u0434\u043c\u0438\u043d."
)
ORDER_LOT_UNMAPPED = (
    "\u041b\u043e\u0442 \u043d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d \u043a \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0443. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 !\u0430\u0434\u043c\u0438\u043d."
)
ORDER_ACCOUNT_BUSY = (
    "\u041b\u043e\u0442 \u0443\u0436\u0435 \u0437\u0430\u043d\u044f\u0442 \u0434\u0440\u0443\u0433\u0438\u043c \u043f\u043e\u043a\u0443\u043f\u0430\u0442\u0435\u043b\u0435\u043c. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 !\u0430\u0434\u043c\u0438\u043d."
)
ACCOUNT_HEADER = "\u0412\u0430\u0448 \u0430\u043a\u043a\u0430\u0443\u043d\u0442:"
ACCOUNT_TIMER_NOTE = (
    "\u23f1\ufe0f \u041e\u0442\u0441\u0447\u0435\u0442 \u0430\u0440\u0435\u043d\u0434\u044b \u043d\u0430\u0447\u043d\u0435\u0442\u0441\u044f \u043f\u043e\u0441\u043b\u0435 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u043a\u043e\u0434\u0430 (!\u043a\u043e\u0434)."
)
COMMANDS_RU = (
    "\u041a\u043e\u043c\u0430\u043d\u0434\u044b:\n"
    "!\u0430\u043a\u043a \u2014 \u0434\u0430\u043d\u043d\u044b\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430\n"
    "!\u043a\u043e\u0434 \u2014 \u043a\u043e\u0434 Steam Guard\n"
    "!\u0441\u0442\u043e\u043a \u2014 \u043d\u0430\u043b\u0438\u0447\u0438\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u043e\u0432\n"
    "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c <\u0447\u0430\u0441\u044b> <ID_\u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430> \u2014 \u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u0430\u0440\u0435\u043d\u0434\u0443\n"
    "!\u0430\u0434\u043c\u0438\u043d \u2014 \u0432\u044b\u0437\u0432\u0430\u0442\u044c \u043f\u0440\u043e\u0434\u0430\u0432\u0446\u0430\n"
    "!\u043b\u043f\u0437\u0430\u043c\u0435\u043d\u0430 <ID> \u2014 \u0437\u0430\u043c\u0435\u043d\u0430 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 (10 \u043c\u0438\u043d\u0443\u0442 \u043f\u043e\u0441\u043b\u0435 !\u043a\u043e\u0434)\n"
    "!\u043e\u0442\u043c\u0435\u043d\u0430 <ID> \u2014 \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c \u0430\u0440\u0435\u043d\u0434\u0443"
)
ORDER_ID_RE = RegularExpressions().ORDER_ID
LOT_NUMBER_RE = re.compile(r"(?:\u2116|#)\s*(\d+)")

_processed_orders: dict[str, set[str]] = {}
_processed_orders_lock = threading.Lock()


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


def normalize_username(name: str | None) -> str:
    return (name or "").strip().lower()


def _orders_key(site_username: str | None, site_user_id: int | None) -> str:
    if site_user_id is not None:
        return str(site_user_id)
    return site_username or "single"


def is_order_processed(site_username: str | None, site_user_id: int | None, order_id: str) -> bool:
    key = _orders_key(site_username, site_user_id)
    with _processed_orders_lock:
        return order_id in _processed_orders.get(key, set())


def mark_order_processed(site_username: str | None, site_user_id: int | None, order_id: str) -> None:
    key = _orders_key(site_username, site_user_id)
    with _processed_orders_lock:
        bucket = _processed_orders.setdefault(key, set())
        bucket.add(order_id)
        if len(bucket) > 5000:
            _processed_orders[key] = set(list(bucket)[-1000:])


def format_duration_minutes(total_minutes: int | None) -> str:
    minutes = int(total_minutes or 0)
    if minutes <= 0:
        return "0 \u043c\u0438\u043d"
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours} \u0447 {mins} \u043c\u0438\u043d"
    if hours:
        return f"{hours} \u0447"
    return f"{mins} \u043c\u0438\u043d"


def parse_lot_number(text: str | None) -> int | None:
    if not text:
        return None
    match = LOT_NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def extract_order_id(text: str | None) -> str | None:
    if not text:
        return None
    match = ORDER_ID_RE.search(text)
    if not match:
        return None
    return match.group(0).lstrip("#")


def get_unit_minutes(account: dict) -> int:
    minutes = account.get("rental_duration_minutes")
    if minutes is not None:
        try:
            val = int(minutes)
            if val > 0:
                return val
        except Exception:
            pass
    hours = account.get("rental_duration")
    try:
        hours_val = int(hours or 0)
    except Exception:
        hours_val = 0
    return max(hours_val * 60, 60)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def get_remaining_label(account: dict, now: datetime) -> tuple[str | None, str]:
    rental_start = _parse_datetime(account.get("rental_start"))
    total_minutes = account.get("rental_duration_minutes")
    try:
        total_minutes_int = int(total_minutes or 0)
    except Exception:
        total_minutes_int = 0
    if not rental_start or total_minutes_int <= 0:
        return None, "\u043e\u0436\u0438\u0434\u0430\u0435\u043c !\u043a\u043e\u0434"
    expiry_time = rental_start + timedelta(minutes=total_minutes_int)
    remaining = expiry_time - now
    if remaining.total_seconds() < 0:
        remaining = timedelta(0)
    hours = int(remaining.total_seconds() // 3600)
    mins = int((remaining.total_seconds() % 3600) // 60)
    remaining_label = f"{hours} \u0447 {mins} \u043c\u0438\u043d"
    return expiry_time.strftime("%H:%M:%S"), remaining_label


def build_display_name(account: dict) -> str:
    name = (account.get("account_name") or account.get("login") or "").strip()
    lot_number = account.get("lot_number")
    if lot_number and not name.startswith("\u2116"):
        prefix = f"\u2116{lot_number} "
        name = f"{prefix}{name}" if name else prefix.strip()
    return name or "\u0410\u043a\u043a\u0430\u0443\u043d\u0442"


def build_account_message(account: dict, duration_minutes: int, include_timer_note: bool) -> str:
    display_name = build_display_name(account)
    now = datetime.utcnow()
    expiry_str, remaining_str = get_remaining_label(account, now)
    lines = [
        ACCOUNT_HEADER,
        f"ID: {account.get('id')}",
        f"\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435: {display_name}",
        f"\u041b\u043e\u0433\u0438\u043d: {account.get('login')}",
        f"\u041f\u0430\u0440\u043e\u043b\u044c: {account.get('password')}",
    ]
    if expiry_str:
        lines.append(f"\u0418\u0441\u0442\u0435\u043a\u0430\u0435\u0442: {expiry_str} \u041c\u0421\u041a | \u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c: {remaining_str}")
    else:
        lines.append(f"\u0410\u0440\u0435\u043d\u0434\u0430: {format_duration_minutes(duration_minutes)}")
        if include_timer_note:
            lines.extend(["", ACCOUNT_TIMER_NOTE])
    lines.extend(["", COMMANDS_RU])
    return "\n".join(lines)


def get_query_time() -> int:
    try:
        import requests

        request = requests.post(
            "https://api.steampowered.com/ITwoFactorService/QueryTime/v0001",
            timeout=15,
        )
        json_data = request.json()
        server_time = int(json_data["response"]["server_time"]) - time.time()
        return int(server_time)
    except Exception:
        return 0


def get_guard_code(shared_secret: str) -> str:
    symbols = "23456789BCDFGHJKMNPQRTVWXY"
    timestamp = time.time() + get_query_time()
    digest = hmac.new(
        base64.b64decode(shared_secret),
        struct.pack(">Q", int(timestamp / 30)),
        sha1,
    ).digest()
    start = digest[19] & 0x0F
    value = struct.unpack(">I", digest[start : start + 4])[0] & 0x7FFFFFFF
    code = ""
    for _ in range(5):
        code += symbols[value % len(symbols)]
        value //= len(symbols)
    return code


def get_steam_guard_code(mafile_json: str | dict | None) -> tuple[bool, str]:
    if not mafile_json:
        return False, "\u041d\u0435\u0442 maFile"
    try:
        data = mafile_json if isinstance(mafile_json, dict) else json.loads(mafile_json)
        shared_secret = data.get("shared_secret")
        if not shared_secret:
            return False, "\u041d\u0435\u0442 shared_secret"
        return True, get_guard_code(shared_secret)
    except Exception as exc:
        return False, str(exc)


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


def fetch_lot_account(mysql_cfg: dict, user_id: int, lot_number: int) -> dict | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen,
                   l.lot_number, l.lot_url
            FROM lots l
            JOIN accounts a ON a.id = l.account_id
            WHERE l.user_id = %s AND l.lot_number = %s
            LIMIT 1
            """,
            (user_id, lot_number),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def assign_account_to_buyer(
    mysql_cfg: dict,
    *,
    account_id: int,
    user_id: int,
    buyer: str,
    units: int,
    total_minutes: int,
) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE accounts
            SET owner = %s,
                rental_duration = %s,
                rental_duration_minutes = %s,
                rental_start = NULL
            WHERE id = %s AND user_id = %s
            """,
            (buyer, int(units), int(total_minutes), int(account_id), int(user_id)),
        )
        conn.commit()
    finally:
        conn.close()


def extend_rental_for_buyer(
    mysql_cfg: dict,
    *,
    account_id: int,
    user_id: int,
    buyer: str,
    add_units: int,
    add_minutes: int,
) -> dict | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, account_name, login, password, mafile_json,
                   owner, rental_start, rental_duration, rental_duration_minutes,
                   account_frozen, rental_frozen,
                   (SELECT lot_number FROM lots WHERE lots.account_id = accounts.id LIMIT 1) AS lot_number,
                   (SELECT lot_url FROM lots WHERE lots.account_id = accounts.id LIMIT 1) AS lot_url
            FROM accounts
            WHERE id = %s AND user_id = %s AND LOWER(owner) = %s
            LIMIT 1
            """,
            (account_id, user_id, normalize_username(buyer)),
        )
        current = cursor.fetchone()
        if not current:
            return None

        base_minutes = current.get("rental_duration_minutes")
        if base_minutes is None:
            base_minutes = int(current.get("rental_duration") or 0) * 60
        try:
            base_minutes_int = int(base_minutes or 0)
        except Exception:
            base_minutes_int = 0

        new_minutes = base_minutes_int + int(add_minutes)
        try:
            base_units = int(current.get("rental_duration") or 0)
        except Exception:
            base_units = 0
        new_units = base_units + int(add_units)

        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE accounts
            SET rental_duration = %s,
                rental_duration_minutes = %s
            WHERE id = %s AND user_id = %s
            """,
            (new_units, new_minutes, account_id, user_id),
        )
        conn.commit()

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen,
                   l.lot_number, l.lot_url
            FROM accounts a
            LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id
            WHERE a.id = %s AND a.user_id = %s
            LIMIT 1
            """,
            (account_id, user_id),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def fetch_owner_accounts(mysql_cfg: dict, user_id: int, owner: str) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen,
                   l.lot_number, l.lot_url
            FROM accounts a
            LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id
            WHERE a.user_id = %s AND LOWER(a.owner) = %s
            ORDER BY a.id
            """,
            (user_id, normalize_username(owner)),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def start_rental_for_owner(mysql_cfg: dict, user_id: int, owner: str) -> int:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE accounts
            SET rental_start = NOW()
            WHERE user_id = %s AND LOWER(owner) = %s AND rental_start IS NULL
            """,
            (user_id, normalize_username(owner)),
        )
        conn.commit()
        return cursor.rowcount
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


def handle_account_command(
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
        logger.warning("Account command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Account command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username)
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    for acc in accounts:
        total_minutes = acc.get("rental_duration_minutes")
        if total_minutes is None:
            total_minutes = get_unit_minutes(acc)
        message = build_account_message(acc, int(total_minutes or 0), include_timer_note=True)
        send_chat_message(logger, account, chat_id, message)
    return True


def handle_code_command(
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
        logger.warning("Code command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Code command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username)
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    lines = ["\u041a\u043e\u0434\u044b Steam Guard:"]
    started_now = False
    for acc in accounts:
        display_name = build_display_name(acc)
        ok, code = get_steam_guard_code(acc.get("mafile_json"))
        login = acc.get("login") or "-"
        if ok:
            lines.append(f"{display_name} ({login}): {code}")
        else:
            lines.append(f"{display_name} ({login}): \u043e\u0448\u0438\u0431\u043a\u0430 {code}")
        if acc.get("rental_start") is None:
            started_now = True

    if started_now:
        start_rental_for_owner(mysql_cfg, user_id, sender_username)
        lines.extend(
            [
                "",
                "\u23f1\ufe0f \u0410\u0440\u0435\u043d\u0434\u0430 \u043d\u0430\u0447\u0430\u043b\u0430\u0441\u044c \u0441\u0435\u0439\u0447\u0430\u0441 (\u0441 \u043c\u043e\u043c\u0435\u043d\u0442\u0430 \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u043a\u043e\u0434\u0430).",
            ]
        )

    send_chat_message(logger, account, chat_id, "\n".join(lines))
    return True


def handle_order_purchased(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    msg: object,
) -> None:
    order_id = extract_order_id(getattr(msg, "text", None) or "")
    if not order_id:
        return
    if is_order_processed(site_username, site_user_id, order_id):
        return

    try:
        order = account.get_order(order_id)
    except Exception as exc:
        logger.warning("Failed to fetch order %s: %s", order_id, exc)
        return

    buyer = str(getattr(order, "buyer_username", "") or "")
    if not buyer:
        logger.warning("Order %s missing buyer username.", order_id)
        return

    chat_id = getattr(order, "chat_id", None)
    if isinstance(chat_id, str) and chat_id.isdigit():
        chat_id = int(chat_id)
    if chat_id is None:
        try:
            chat = account.get_chat_by_name(buyer, True)
            chat_id = getattr(chat, "id", None)
        except Exception:
            chat_id = None
    if chat_id is None:
        logger.warning("Skipping order %s: chat id not found.", order_id)
        return

    description = (
        getattr(order, "full_description", None)
        or getattr(order, "short_description", None)
        or getattr(order, "title", None)
        or ""
    )
    lot_number = parse_lot_number(description)
    if lot_number is None:
        send_chat_message(logger, account, chat_id, ORDER_LOT_MISSING)
        mark_order_processed(site_username, site_user_id, order_id)
        return

    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Order %s skipped: %s", order_id, exc)
        return

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            return

    if user_id is None:
        logger.warning("Order %s skipped: user id missing.", order_id)
        return

    mapping = fetch_lot_account(mysql_cfg, user_id, lot_number)
    if not mapping:
        send_chat_message(logger, account, chat_id, ORDER_LOT_UNMAPPED)
        mark_order_processed(site_username, site_user_id, order_id)
        return

    if mapping.get("account_frozen") or mapping.get("rental_frozen"):
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
        mark_order_processed(site_username, site_user_id, order_id)
        return

    owner = mapping.get("owner")
    if owner and normalize_username(owner) != normalize_username(buyer):
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
        mark_order_processed(site_username, site_user_id, order_id)
        return

    try:
        amount = int(getattr(order, "amount", None) or 1)
    except Exception:
        amount = 1
    if amount <= 0:
        amount = 1

    unit_minutes = get_unit_minutes(mapping)
    total_minutes = unit_minutes * amount

    updated_account = mapping
    if not owner:
        assign_account_to_buyer(
            mysql_cfg,
            account_id=int(mapping["id"]),
            user_id=user_id,
            buyer=buyer,
            units=amount,
            total_minutes=total_minutes,
        )
    else:
        updated_account = extend_rental_for_buyer(
            mysql_cfg,
            account_id=int(mapping["id"]),
            user_id=user_id,
            buyer=buyer,
            add_units=amount,
            add_minutes=total_minutes,
        )
        if not updated_account:
            send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
            mark_order_processed(site_username, site_user_id, order_id)
            return

    message = build_account_message(updated_account or mapping, total_minutes, include_timer_note=True)
    send_chat_message(logger, account, chat_id, message)
    mark_order_processed(site_username, site_user_id, order_id)


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
        "!\u0430\u043a\u043a": handle_account_command,
        "!\u043a\u043e\u0434": handle_code_command,
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
        if msg.type == MessageTypes.ORDER_PURCHASED:
            handle_order_purchased(logger, account, site_username, site_user_id, msg)
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
