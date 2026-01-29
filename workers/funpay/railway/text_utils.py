from __future__ import annotations

from datetime import datetime, timedelta

from .constants import COMMAND_PREFIXES, LOT_NUMBER_RE, ORDER_ID_RE


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


def format_duration_minutes(minutes: int | None) -> str:
    if minutes is None:
        return "0 минут"
    total = max(0, int(minutes))
    hours = total // 60
    remaining = total % 60
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} {format_hours_label(hours)}")
    if remaining or not parts:
        parts.append(f"{remaining} минут")
    return " ".join(parts)


def format_hours_label(value: int) -> str:
    if 11 <= (value % 100) <= 14:
        return "часов"
    last = value % 10
    if last == 1:
        return "час"
    if 2 <= last <= 4:
        return "часа"
    return "часов"


def format_penalty_label(total_minutes: int | None) -> str:
    minutes = int(total_minutes or 0)
    if minutes > 0 and minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} {format_hours_label(hours)}"
    return format_duration_minutes(minutes)


def normalize_owner_name(owner: str | None) -> str:
    return str(owner or "").strip().lower()


def format_time_left(seconds_left: int) -> str:
    total = max(0, int(seconds_left))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours:
        return f"{hours} ч {minutes} мин {seconds} сек"
    if minutes:
        return f"{minutes} мин {seconds} сек"
    return f"{seconds} сек"


def build_expire_soon_message(account_row: dict, seconds_left: int) -> str:
    account_id = account_row.get("id")
    name = account_row.get("account_name") or account_row.get("login") or f"ID {account_id}"
    label = f"{name} (ID {account_id})" if account_id is not None else name
    time_left = format_time_left(seconds_left)
    lot_number = account_row.get("lot_number")
    lot_url = account_row.get("lot_url")
    if lot_number and lot_url:
        lot_label = f"Лот №{lot_number}: {lot_url}"
    elif lot_number:
        lot_label = f"Лот №{lot_number}"
    elif lot_url:
        lot_label = f"Лот: {lot_url}"
    else:
        lot_label = "лот, который привязан к аккаунту"

    return (
        f"⏳ Ваша аренда {label} скоро закончится.\n"
        f"Осталось: {time_left}.\n"
        f"Если хотите продлить — пожалуйста оплатите этот {lot_label}."
    )


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


def parse_account_id_arg(args: str) -> int | None:
    if not args:
        return None
    token = args.strip().split(maxsplit=1)[0]
    if not token.isdigit():
        return None
    try:
        return int(token)
    except ValueError:
        return None


def _calculate_resume_start(rental_start: object, frozen_at: object) -> datetime | None:
    start_dt = _parse_datetime(rental_start)
    frozen_dt = _parse_datetime(frozen_at)
    if not start_dt or not frozen_dt:
        return None
    delta = datetime.utcnow() - frozen_dt
    if delta.total_seconds() < 0:
        delta = timedelta(0)
    return start_dt + delta


def get_unit_minutes(account: dict) -> int:
    return 60


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
