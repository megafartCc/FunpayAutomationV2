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
from dataclasses import dataclass, field
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
import requests  # noqa: E402
try:  # noqa: E402
    import redis  # type: ignore
except Exception:  # noqa: E402
    redis = None


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
RENTAL_FROZEN_MESSAGE = (
    "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440 \u0437\u0430\u043c\u043e\u0440\u043e\u0437\u0438\u043b \u0432\u0430\u0448\u0443 \u0430\u0440\u0435\u043d\u0434\u0443. \u0414\u043e\u0441\u0442\u0443\u043f \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043f\u0440\u0438\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d."
)
RENTAL_UNFROZEN_MESSAGE = (
    "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440 \u0440\u0430\u0437\u043c\u043e\u0440\u043e\u0437\u0438\u043b \u0432\u0430\u0448\u0443 \u0430\u0440\u0435\u043d\u0434\u0443. \u0414\u043e\u0441\u0442\u0443\u043f \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d."
)
RENTAL_EXPIRED_MESSAGE = "\u0410\u0440\u0435\u043d\u0434\u0430 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0430\u0441\u044c. \u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442."
RENTAL_EXPIRE_DELAY_MESSAGE = (
    "\u0412\u0430\u0448\u0430 \u0430\u0440\u0435\u043d\u0434\u0430 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0430\u0441\u044c, \u043d\u043e \u043c\u044b \u0432\u0438\u0434\u0438\u043c, \u0447\u0442\u043e \u0432\u044b \u0432 \u0438\u0433\u0440\u0435.\n"
    "\u0423 \u0432\u0430\u0441 \u0435\u0441\u0442\u044c \u0432\u0440\u0435\u043c\u044f, \u0447\u0442\u043e\u0431\u044b \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u0442\u044c \u043c\u0430\u0442\u0447. \u0427\u0435\u0440\u0435\u0437 1 \u043c\u0438\u043d\u0443\u0442\u0443 \u044f \u043f\u0440\u043e\u0432\u0435\u0440\u044e \u0441\u043d\u043e\u0432\u0430.\n"
    "\u0414\u043e\u0441\u0442\u0443\u043f \u0431\u0443\u0434\u0435\u0442 \u0437\u0430\u043a\u0440\u044b\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438, \u0435\u0441\u043b\u0438 \u043c\u0430\u0442\u0447 \u0443\u0436\u0435 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u0442\u0441\u044f.\n"
    "\u0415\u0441\u043b\u0438 \u0445\u043e\u0442\u0438\u0442\u0435 \u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u2014 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u0443:\n"
    "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c <\u0447\u0430\u0441\u044b> <ID \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430>"
)
ORDER_ID_RE = RegularExpressions().ORDER_ID
LOT_NUMBER_RE = re.compile(r"(?:\u2116|#)\s*(\d+)")

_processed_orders: dict[str, set[str]] = {}
_processed_orders_lock = threading.Lock()
_redis_client = None


@dataclass
class RentalMonitorState:
    last_check_ts: float = 0.0
    freeze_cache: dict[int, bool] = field(default_factory=dict)
    expire_delay_since: dict[int, datetime] = field(default_factory=dict)
    expire_delay_next_check: dict[int, datetime] = field(default_factory=dict)
    expire_delay_notified: set[int] = field(default_factory=set)


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


def _orders_key(site_username: str | None, site_user_id: int | None, workspace_id: int | None) -> str:
    if site_user_id is not None:
        base = str(site_user_id)
    else:
        base = site_username or "single"
    if workspace_id is not None:
        return f"{base}:{workspace_id}"
    return base


def is_order_processed(
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    order_id: str,
) -> bool:
    key = _orders_key(site_username, site_user_id, workspace_id)
    with _processed_orders_lock:
        return order_id in _processed_orders.get(key, set())


def mark_order_processed(
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    order_id: str,
) -> None:
    key = _orders_key(site_username, site_user_id, workspace_id)
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


def extract_lot_number_from_order(order: object) -> int | None:
    candidates = [
        getattr(order, "full_description", None),
        getattr(order, "short_description", None),
        getattr(order, "title", None),
        getattr(order, "html", None),
    ]
    for item in candidates:
        lot_number = parse_lot_number(item if isinstance(item, str) else None)
        if lot_number is not None:
            return lot_number
    return None


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


def send_message_by_owner(logger: logging.Logger, account: Account, owner: str | None, text: str) -> bool:
    if not owner:
        return False
    try:
        chat = account.get_chat_by_name(owner, True)
    except Exception as exc:
        logger.warning("Failed to resolve chat for %s: %s", owner, exc)
        return False
    chat_id = getattr(chat, "id", None)
    if not chat_id:
        logger.warning("Chat not found for %s.", owner)
        return False
    return send_chat_message(logger, account, int(chat_id), text)


def _steam_id_from_mafile(mafile_json: str | dict | None) -> str | None:
    if not mafile_json:
        return None
    try:
        data = mafile_json if isinstance(mafile_json, dict) else json.loads(mafile_json)
        steam_value = (data or {}).get("Session", {}).get("SteamID")
        if steam_value is None:
            steam_value = (data or {}).get("steamid") or (data or {}).get("SteamID")
        if steam_value is not None:
            return str(int(steam_value))
    except Exception:
        return None
    return None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if redis is None:
        _redis_client = None
        return None
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        _redis_client = None
        return None
    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    except Exception:
        _redis_client = None
    return _redis_client


def _presence_cache_key(steam_id: str) -> str:
    return f"presence:{steam_id}"


def _presence_cache_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_TTL_SECONDS", "15"))


def _presence_cache_empty_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_EMPTY_TTL_SECONDS", "5"))


def fetch_presence(steam_id: str | None) -> dict:
    if not steam_id:
        return {}
    cache = _get_redis()
    if cache:
        try:
            cached_raw = cache.get(_presence_cache_key(steam_id))
        except Exception:
            cached_raw = None
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
            except Exception:
                cached = None
            return cached if isinstance(cached, dict) else {}
    base = os.getenv("STEAM_PRESENCE_URL", "").strip() or os.getenv("STEAM_BRIDGE_URL", "").strip()
    if not base:
        return {}
    base = base.rstrip("/")
    if base.endswith("/presence"):
        url = f"{base}/{steam_id}"
    else:
        url = f"{base}/presence/{steam_id}"
    try:
        resp = requests.get(url, timeout=5)
    except requests.RequestException:
        return {}
    if not resp.ok:
        if cache:
            try:
                cache.set(_presence_cache_key(steam_id), "null", ex=_presence_cache_empty_ttl_seconds())
            except Exception:
                pass
        return {}
    try:
        data = resp.json()
    except Exception:
        if cache:
            try:
                cache.set(_presence_cache_key(steam_id), "null", ex=_presence_cache_empty_ttl_seconds())
            except Exception:
                pass
        return {}
    if not isinstance(data, dict):
        if cache:
            try:
                cache.set(_presence_cache_key(steam_id), "null", ex=_presence_cache_empty_ttl_seconds())
            except Exception:
                pass
        return {}
    if cache:
        try:
            cache.set(
                _presence_cache_key(steam_id),
                json.dumps(data, ensure_ascii=False),
                ex=_presence_cache_ttl_seconds(),
            )
        except Exception:
            pass
    return data


def fetch_active_rentals_for_monitor(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None = None,
) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        has_workspace = column_exists(cursor, "accounts", "workspace_id")
        params: list = [user_id]
        workspace_clause = ""
        if workspace_id is not None and has_workspace:
            workspace_clause = " AND workspace_id = %s"
            params.append(workspace_id)
        cursor.execute(
            f"""
            SELECT id, owner, rental_start, rental_duration, rental_duration_minutes,
                   account_name, login, password, mafile_json, account_frozen, rental_frozen
            FROM accounts
            WHERE user_id = %s AND owner IS NOT NULL AND owner != ''{workspace_clause}
            """,
            tuple(params),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def release_account_in_db(
    mysql_cfg: dict,
    account_id: int,
    user_id: int,
    workspace_id: int | None = None,
) -> bool:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        has_workspace = column_exists(cursor, "accounts", "workspace_id")
        updates = ["owner = NULL", "rental_start = NULL", "rental_frozen = 0"]
        if has_frozen_at:
            updates.append("rental_frozen_at = NULL")
        workspace_clause = ""
        params: list = [account_id, user_id]
        if workspace_id is not None and has_workspace:
            workspace_clause = " AND workspace_id = %s"
            params.append(workspace_id)
        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s{workspace_clause}",
            tuple(params),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def deauthorize_account_sessions(
    logger: logging.Logger,
    account_row: dict,
) -> bool:
    base = os.getenv("STEAM_WORKER_URL", "").strip()
    if not base:
        return False
    login = account_row.get("login") or account_row.get("account_name")
    password = account_row.get("password") or ""
    mafile_json = account_row.get("mafile_json")
    if not login or not password or not mafile_json:
        return False
    url = f"{base.rstrip('/')}/api/steam/deauthorize"
    timeout = env_int("STEAM_WORKER_TIMEOUT", 90)
    payload = {
        "steam_login": login,
        "steam_password": password,
        "mafile_json": mafile_json,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Steam worker request failed: %s", exc)
        return False
    if resp.ok:
        return True
    logger.warning("Steam worker error (status %s).", resp.status_code)
    return False


def _clear_expire_delay_state(state: RentalMonitorState, account_id: int) -> None:
    state.expire_delay_since.pop(account_id, None)
    state.expire_delay_next_check.pop(account_id, None)
    state.expire_delay_notified.discard(account_id)


def _should_delay_expire(
    logger: logging.Logger,
    account: Account,
    owner: str,
    account_row: dict,
    state: RentalMonitorState,
    now: datetime,
) -> bool:
    if not env_bool("DOTA_MATCH_DELAY_EXPIRE", True):
        return False
    account_id = int(account_row.get("id"))
    next_check = state.expire_delay_next_check.get(account_id)
    if next_check and now < next_check:
        return True

    steam_id = _steam_id_from_mafile(account_row.get("mafile_json"))
    presence = fetch_presence(steam_id)
    in_game = bool(presence.get("in_match") or presence.get("in_game"))
    if not in_game:
        _clear_expire_delay_state(state, account_id)
        return False

    since = state.expire_delay_since.get(account_id)
    if since is None:
        state.expire_delay_since[account_id] = now
        since = now

    grace_minutes = env_int("DOTA_MATCH_GRACE_MINUTES", 90)
    if now - since >= timedelta(minutes=grace_minutes):
        _clear_expire_delay_state(state, account_id)
        return False

    state.expire_delay_next_check[account_id] = now + timedelta(minutes=1)
    if account_id not in state.expire_delay_notified:
        extra = ""
        display = presence.get("presence_display") or presence.get("presence_state")
        if display:
            extra = f"\n\u0421\u0442\u0430\u0442\u0443\u0441: {display}"
        send_message_by_owner(logger, account, owner, f"{RENTAL_EXPIRE_DELAY_MESSAGE}{extra}")
        state.expire_delay_notified.add(account_id)
    return True


def process_rental_monitor(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    state: RentalMonitorState,
) -> None:
    interval = env_int("FUNPAY_RENTAL_CHECK_SECONDS", 30)
    now_ts = time.time()
    if now_ts - state.last_check_ts < interval:
        return
    state.last_check_ts = now_ts

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

    rentals = fetch_active_rentals_for_monitor(mysql_cfg, int(user_id), workspace_id)
    now = datetime.utcnow()
    active_ids = {int(row.get("id")) for row in rentals}
    if state.freeze_cache:
        state.freeze_cache = {k: v for k, v in state.freeze_cache.items() if k in active_ids}
    if state.expire_delay_since:
        state.expire_delay_since = {k: v for k, v in state.expire_delay_since.items() if k in active_ids}
    if state.expire_delay_next_check:
        state.expire_delay_next_check = {
            k: v for k, v in state.expire_delay_next_check.items() if k in active_ids
        }
    if state.expire_delay_notified:
        state.expire_delay_notified = {k for k in state.expire_delay_notified if k in active_ids}

    for row in rentals:
        account_id = int(row.get("id"))
        owner = row.get("owner")
        frozen = bool(row.get("rental_frozen"))
        prev = state.freeze_cache.get(account_id)
        if prev is None:
            state.freeze_cache[account_id] = frozen
        elif prev != frozen:
            state.freeze_cache[account_id] = frozen
            message = RENTAL_FROZEN_MESSAGE if frozen else RENTAL_UNFROZEN_MESSAGE
            send_message_by_owner(logger, account, owner, message)

    for row in rentals:
        account_id = int(row.get("id"))
        owner = row.get("owner")
        if not owner:
            _clear_expire_delay_state(state, account_id)
            continue
        if row.get("rental_frozen"):
            continue
        started = _parse_datetime(row.get("rental_start"))
        total_minutes = row.get("rental_duration_minutes")
        if total_minutes is None:
            total_minutes = int(row.get("rental_duration") or 0) * 60
        try:
            total_minutes_int = int(total_minutes or 0)
        except Exception:
            total_minutes_int = 0
        if not started or total_minutes_int <= 0:
            _clear_expire_delay_state(state, account_id)
            continue
        expiry_time = started + timedelta(minutes=total_minutes_int)
        if now < expiry_time:
            _clear_expire_delay_state(state, account_id)
            continue
        if _should_delay_expire(logger, account, owner, row, state, now):
            continue

        if env_bool("AUTO_STEAM_DEAUTHORIZE_ON_EXPIRE", True):
            deauthorize_account_sessions(logger, row)
        released = release_account_in_db(mysql_cfg, account_id, int(user_id), workspace_id)
        if released:
            send_message_by_owner(logger, account, owner, RENTAL_EXPIRED_MESSAGE)
        _clear_expire_delay_state(state, account_id)


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


def fetch_lot_alias(
    mysql_cfg: dict,
    user_id: int,
    lot_number: int,
    workspace_id: int | None = None,
) -> str | None:
    """
    Return a FunPay URL for the given lot_number, preferring the caller's workspace alias.
    """
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        params: list = [user_id, lot_number]
        workspace_clause = ""
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(workspace_id)
        cursor.execute(
            f"""
            SELECT funpay_url FROM lot_aliases
            WHERE user_id = %s AND lot_number = %s{workspace_clause}
            ORDER BY id ASC
            LIMIT 1
            """,
            tuple(params),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        # Fallback to any alias for this lot_number.
        cursor.execute(
            """
            SELECT funpay_url FROM lot_aliases
            WHERE user_id = %s AND lot_number = %s
            ORDER BY id ASC
            LIMIT 1
            """,
            (user_id, lot_number),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    finally:
        conn.close()


def fetch_available_lot_accounts(
    mysql_cfg: dict,
    user_id: int | None,
    workspace_id: int | None = None,
) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "accounts"):
            return []
        has_lots = table_exists(cursor, "lots")
        has_account_user_id = column_exists(cursor, "accounts", "user_id")
        has_lot_user_id = has_lots and column_exists(cursor, "lots", "user_id")
        has_account_workspace = column_exists(cursor, "accounts", "workspace_id")
        has_lot_workspace = has_lots and column_exists(cursor, "lots", "workspace_id")
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
            "a.workspace_id AS workspace_id",
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
            join_clause = " LEFT JOIN lots l ON l.account_id = a.ID"
            if has_account_workspace and has_lot_workspace and workspace_id is not None:
                join_clause += " AND (l.workspace_id = a.workspace_id OR l.workspace_id IS NULL)"
            from_clause += join_clause

        where_clauses = ["a.owner IS NULL"]
        params: list = []
        if has_account_frozen:
            where_clauses.append("(a.account_frozen = 0 OR a.account_frozen IS NULL)")
        if has_rental_frozen:
            where_clauses.append("(a.rental_frozen = 0 OR a.rental_frozen IS NULL)")
        if has_lots:
            where_clauses.append("l.lot_number IS NOT NULL")
            if has_account_workspace and has_lot_workspace and workspace_id is not None:
                where_clauses.append("(l.workspace_id = %s OR l.workspace_id IS NULL)")
                params.append(int(workspace_id))

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


def fetch_lot_account(
    mysql_cfg: dict,
    user_id: int,
    lot_number: int,
    workspace_id: int | None = None,
) -> dict | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        params: list = [user_id, lot_number]
        join_clause = "JOIN accounts a ON a.id = l.account_id"
        where_workspace = ""
        has_workspace = column_exists(cursor, "lots", "workspace_id")
        order_clause = " ORDER BY a.id"
        if has_workspace and workspace_id is not None:
            where_workspace = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
            params.append(int(workspace_id))
            order_clause = " ORDER BY CASE WHEN l.workspace_id = %s THEN 0 ELSE 1 END, a.id"
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen,
                   l.lot_number, l.lot_url
            FROM lots l
            {join_clause}
            WHERE l.user_id = %s AND l.lot_number = %s
                  {where_workspace}
                  AND (a.owner IS NULL OR a.owner = '')
                  AND (a.account_frozen = 0 OR a.account_frozen IS NULL)
                  AND (a.rental_frozen = 0 OR a.rental_frozen IS NULL)
            {order_clause}
            LIMIT 1
            """,
            tuple(params + ([int(workspace_id)] if has_workspace and workspace_id is not None else [])),
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
    workspace_id: int | None = None,
) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        has_workspace = column_exists(cursor, "accounts", "workspace_id")
        workspace_clause = ""
        params: list = [buyer, int(units), int(total_minutes), int(account_id), int(user_id)]
        if workspace_id is not None and has_workspace:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            UPDATE accounts
            SET owner = %s,
                rental_duration = %s,
                rental_duration_minutes = %s,
                rental_start = NULL
            WHERE id = %s AND user_id = %s{workspace_clause}
            """,
            tuple(params),
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
    workspace_id: int | None = None,
) -> dict | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        has_workspace = column_exists(cursor, "accounts", "workspace_id")
        workspace_clause = ""
        params: list = [account_id, user_id, normalize_username(buyer)]
        if workspace_id is not None and has_workspace:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT id, account_name, login, password, mafile_json,
                   owner, rental_start, rental_duration, rental_duration_minutes,
                   account_frozen, rental_frozen,
                   (SELECT lot_number FROM lots WHERE lots.account_id = accounts.id LIMIT 1) AS lot_number,
                   (SELECT lot_url FROM lots WHERE lots.account_id = accounts.id LIMIT 1) AS lot_url
            FROM accounts
            WHERE id = %s AND user_id = %s AND LOWER(owner) = %s{workspace_clause}
            LIMIT 1
            """,
            tuple(params),
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
        update_workspace_clause = ""
        update_params: list = [new_units, new_minutes, account_id, user_id]
        if workspace_id is not None and has_workspace:
            update_workspace_clause = " AND workspace_id = %s"
            update_params.append(int(workspace_id))
        cursor.execute(
            f"""
            UPDATE accounts
            SET rental_duration = %s,
                rental_duration_minutes = %s
            WHERE id = %s AND user_id = %s{update_workspace_clause}
            """,
            tuple(update_params),
        )
        conn.commit()

        cursor = conn.cursor(dictionary=True)
        has_lot_workspace = column_exists(cursor, "lots", "workspace_id")
        join_clause = "LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id"
        if has_workspace and has_lot_workspace:
            join_clause += " AND l.workspace_id = a.workspace_id"
        final_workspace_clause = ""
        final_params: list = [account_id, user_id]
        if workspace_id is not None and has_workspace:
            final_workspace_clause = " AND a.workspace_id = %s"
            final_params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen,
                   l.lot_number, l.lot_url
            FROM accounts a
            {join_clause}
            WHERE a.id = %s AND a.user_id = %s{final_workspace_clause}
            LIMIT 1
            """,
            tuple(final_params),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def fetch_owner_accounts(
    mysql_cfg: dict,
    user_id: int,
    owner: str,
    workspace_id: int | None = None,
) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        has_workspace = column_exists(cursor, "accounts", "workspace_id")
        has_lot_workspace = column_exists(cursor, "lots", "workspace_id")
        join_clause = "LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id"
        if has_workspace and has_lot_workspace:
            join_clause += " AND l.workspace_id = a.workspace_id"
        workspace_clause = ""
        params: list = [user_id, normalize_username(owner)]
        if workspace_id is not None and has_workspace:
            workspace_clause = " AND a.workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen,
                   l.lot_number, l.lot_url
            FROM accounts a
            {join_clause}
            WHERE a.user_id = %s AND LOWER(a.owner) = %s{workspace_clause}
            ORDER BY a.id
            """,
            tuple(params),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def start_rental_for_owner(
    mysql_cfg: dict,
    user_id: int,
    owner: str,
    workspace_id: int | None = None,
) -> int:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        has_workspace = column_exists(cursor, "accounts", "workspace_id")
        workspace_clause = ""
        params: list = [user_id, normalize_username(owner)]
        if workspace_id is not None and has_workspace:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            UPDATE accounts
            SET rental_start = NOW()
            WHERE user_id = %s AND LOWER(owner) = %s AND rental_start IS NULL{workspace_clause}
            """,
            tuple(params),
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
            display_name = f"Аккаунт №{lot_number}" if lot_number else "Аккаунт"
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
    workspace_id: int | None,
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
        accounts = fetch_available_lot_accounts(mysql_cfg, user_id, workspace_id=workspace_id)

        # Enrich with workspace-specific alias if present.
        if accounts:
            cache_alias: dict[int, str] = {}
            for acc in accounts:
                lot_num = acc.get("lot_number")
                if lot_num is None:
                    continue
                if lot_num in cache_alias:
                    acc["lot_url"] = cache_alias[lot_num]
                    continue
                url = fetch_lot_alias(mysql_cfg, user_id, int(lot_num), workspace_id)
                if url:
                    cache_alias[lot_num] = url
                    acc["lot_url"] = url
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
    workspace_id: int | None,
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

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
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
    workspace_id: int | None,
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

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
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
        start_rental_for_owner(mysql_cfg, user_id, sender_username, workspace_id)
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
    workspace_id: int | None,
    msg: object,
) -> None:
    order_id = extract_order_id(getattr(msg, "text", None) or "")
    if not order_id:
        return
    if is_order_processed(site_username, site_user_id, workspace_id, order_id):
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

    lot_number = extract_lot_number_from_order(order)
    if lot_number is None:
        send_chat_message(logger, account, chat_id, ORDER_LOT_MISSING)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
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

    mapping = fetch_lot_account(mysql_cfg, user_id, lot_number, workspace_id=workspace_id)
    if not mapping:
        send_chat_message(logger, account, chat_id, ORDER_LOT_UNMAPPED)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    if mapping.get("account_frozen") or mapping.get("rental_frozen"):
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    owner = mapping.get("owner")
    if owner and normalize_username(owner) != normalize_username(buyer):
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
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
            workspace_id=workspace_id,
        )
    else:
        updated_account = extend_rental_for_buyer(
            mysql_cfg,
            account_id=int(mapping["id"]),
            user_id=user_id,
            buyer=buyer,
            add_units=amount,
            add_minutes=total_minutes,
            workspace_id=workspace_id,
        )
        if not updated_account:
            send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return

    message = build_account_message(updated_account or mapping, total_minutes, include_timer_note=True)
    send_chat_message(logger, account, chat_id, message)
    mark_order_processed(site_username, site_user_id, workspace_id, order_id)


def _log_command_stub(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
    action: str,
) -> bool:
    logger.info(
        "user=%s workspace=%s chat=%s author=%s command=%s args=%s action=%s url=%s",
        site_username or "-",
        workspace_id if workspace_id is not None else "-",
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
    workspace_id: int | None,
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
            "user=%s workspace=%s chat=%s author=%s command_unhandled=%s args=%s url=%s",
            site_username or "-",
            workspace_id if workspace_id is not None else "-",
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
        workspace_id,
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


def normalize_proxy_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return f"socks5://{value}"


def build_proxy_config(raw: str | None) -> dict | None:
    url = normalize_proxy_url(raw)
    if not url:
        return None
    return {"http": url, "https": url}


def fetch_workspaces(mysql_cfg: dict) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT w.id AS workspace_id, w.name AS workspace_name, w.golden_key, w.proxy_url,
                   w.user_id, u.username
            FROM workspaces w
            JOIN users u ON u.id = w.user_id
            WHERE w.golden_key IS NOT NULL AND w.golden_key != ''
            ORDER BY w.user_id, w.id
            """
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
    workspace_id: int | None,
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
        "user=%s workspace=%s chat=%s author=%s system=%s url=%s: %s",
        site_username or "-",
        workspace_id if workspace_id is not None else "-",
        chat_name,
        sender_username,
        is_system,
        chat_url,
        message_text,
    )
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

    user_agent = os.getenv("FUNPAY_USER_AGENT")
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)

    logger.info("Initializing FunPay account...")
    account = Account(golden_key, user_agent=user_agent, proxy=build_proxy_config(proxy_url))
    account.get()
    logger.info("Bot started for %s.", account.username or "unknown")

    threading.Thread(target=refresh_session_loop, args=(account, 3600, None), daemon=True).start()

    runner = Runner(account, disable_message_requests=False)
    logger.info("Listening for new messages...")
    state = RentalMonitorState()
    while True:
        updates = runner.get_updates()
        events = runner.parse_updates(updates)
        for event in events:
            if isinstance(event, NewMessageEvent):
                log_message(logger, account, account.username, None, None, event)
        process_rental_monitor(logger, account, account.username, None, None, state)
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
    while not stop_event.is_set():
        try:
            if not golden_key:
                logger.warning("%s Missing golden_key, skipping.", label)
                return
            if not proxy_url:
                logger.warning("%s Missing proxy_url, bot will not start.", label)
                return
            proxy_cfg = build_proxy_config(proxy_url)
            if not proxy_cfg:
                logger.warning("%s Invalid proxy_url, bot will not start.", label)
                return

            account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
            account.get()
            logger.info("Bot started for %s (%s).", site_username, workspace_name)

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
            workspaces = fetch_workspaces(mysql_cfg)
            if max_users > 0:
                workspaces = workspaces[:max_users]

            desired = {
                int(w["workspace_id"]): w
                for w in workspaces
                if w.get("golden_key") and str(w.get("golden_key")).strip()
            }

            # Stop removed workspaces.
            for workspace_id in list(workers.keys()):
                if workspace_id not in desired:
                    workers[workspace_id]["stop"].set()
                    workers[workspace_id]["thread"].join(timeout=5)
                    workers.pop(workspace_id, None)

            for workspace_id, workspace in desired.items():
                golden_key = (workspace.get("golden_key") or "").strip()
                proxy_url = normalize_proxy_url(workspace.get("proxy_url"))
                existing = workers.get(workspace_id)
                if (
                    existing
                    and existing.get("golden_key") == golden_key
                    and existing.get("proxy_url") == proxy_url
                ):
                    continue
                if existing:
                    existing["stop"].set()
                    existing["thread"].join(timeout=5)
                    workers.pop(workspace_id, None)

                if not proxy_url:
                    logger.warning(
                        "Workspace %s missing proxy_url, bot will not start.",
                        workspace.get("workspace_name") or workspace_id,
                    )
                    continue

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
