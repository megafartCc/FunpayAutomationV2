from __future__ import annotations

from datetime import datetime, timedelta

from .constants import ACCOUNT_HEADER, ACCOUNT_TIMER_NOTE, COMMANDS_RU
from .text_utils import _parse_datetime, format_duration_minutes


def resolve_rental_minutes(account: dict) -> int:
    minutes = account.get("rental_duration_minutes")
    if minutes is None:
        try:
            minutes = int(account.get("rental_duration") or 0) * 60
        except Exception:
            minutes = 0
    try:
        return int(minutes or 0)
    except Exception:
        return 0


def get_remaining_label(account: dict, now: datetime) -> tuple[str | None, str]:
    rental_start = _parse_datetime(account.get("rental_start"))
    total_minutes = account.get("rental_duration_minutes")
    try:
        total_minutes_int = int(total_minutes or 0)
    except Exception:
        total_minutes_int = 0
    if not rental_start or total_minutes_int <= 0:
        return None, "ожидаем !код"
    expiry_time = rental_start + timedelta(minutes=total_minutes_int)
    remaining = expiry_time - now
    if remaining.total_seconds() < 0:
        remaining = timedelta(0)
    hours = int(remaining.total_seconds() // 3600)
    mins = int((remaining.total_seconds() % 3600) // 60)
    remaining_label = f"{hours} ч {mins} мин"
    return expiry_time.strftime("%H:%M:%S"), remaining_label


def build_display_name(account: dict) -> str:
    name = (
        account.get("display_name")
        or account.get("account_name")
        or account.get("login")
        or ""
    ).strip()
    lot_number = account.get("lot_number")
    if lot_number and not name.startswith("№"):
        prefix = f"№{lot_number} "
        name = f"{prefix}{name}" if name else prefix.strip()
    return name or "Аккаунт"


def build_rental_choice_message(accounts: list[dict], command: str) -> str:
    lines = [
        "У вас несколько аренд.",
        f"Укажите ID в команде {command} <ID>",
        "",
    ]
    for acc in accounts:
        display = build_display_name(acc)
        lines.append(f"ID {acc.get('id')}: {display}")
    return "\n".join(str(line) for line in lines)


def build_account_message(account: dict, duration_minutes: int, include_timer_note: bool) -> str:
    display_name = build_display_name(account)
    now = datetime.utcnow()
    expiry_str, remaining_str = get_remaining_label(account, now)
    lines = [
        ACCOUNT_HEADER,
        f"ID: {account.get('id')}",
        f"Название: {display_name}",
        f"Логин: {account.get('login')}",
        f"Пароль: {account.get('password')}",
    ]
    if expiry_str:
        lines.append(f"Истекает: {expiry_str} МСК | Осталось: {remaining_str}")
    else:
        lines.append(f"Аренда: {format_duration_minutes(duration_minutes)}")
        if include_timer_note:
            lines.extend(["", ACCOUNT_TIMER_NOTE])
    lines.extend(["", COMMANDS_RU])
    return "\n".join(str(line) for line in lines)
