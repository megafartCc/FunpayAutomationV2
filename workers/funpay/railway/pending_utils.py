from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

DEFAULT_TTL_SECONDS = 300


@dataclass(frozen=True)
class PendingCommand:
    command: str
    args_prefix: str
    created_at: datetime
    expires_at: datetime


_PENDING: dict[tuple[str, int, str], PendingCommand] = {}
_LOCK = Lock()


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _make_key(bot_key: str | None, chat_id: int, sender_username: str | None) -> tuple[str, int, str]:
    return (_normalize(bot_key), int(chat_id), _normalize(sender_username))


def set_pending_command(
    bot_key: str | None,
    chat_id: int | None,
    sender_username: str | None,
    command: str,
    args_prefix: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    if chat_id is None:
        return
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=max(10, int(ttl_seconds)))
    key = _make_key(bot_key, chat_id, sender_username)
    pending = PendingCommand(
        command=command,
        args_prefix=args_prefix.strip(),
        created_at=now,
        expires_at=expires_at,
    )
    with _LOCK:
        _PENDING[key] = pending


def get_pending_command(
    bot_key: str | None,
    chat_id: int | None,
    sender_username: str | None,
) -> PendingCommand | None:
    if chat_id is None:
        return None
    key = _make_key(bot_key, chat_id, sender_username)
    now = datetime.utcnow()
    with _LOCK:
        pending = _PENDING.get(key)
        if not pending:
            return None
        if pending.expires_at <= now:
            _PENDING.pop(key, None)
            return None
        return pending


def pop_pending_command(
    bot_key: str | None,
    chat_id: int | None,
    sender_username: str | None,
) -> PendingCommand | None:
    if chat_id is None:
        return None
    key = _make_key(bot_key, chat_id, sender_username)
    now = datetime.utcnow()
    with _LOCK:
        pending = _PENDING.get(key)
        if not pending:
            return None
        if pending.expires_at <= now:
            _PENDING.pop(key, None)
            return None
        _PENDING.pop(key, None)
        return pending


def clear_pending_command(
    bot_key: str | None,
    chat_id: int | None,
    sender_username: str | None,
) -> None:
    if chat_id is None:
        return
    key = _make_key(bot_key, chat_id, sender_username)
    with _LOCK:
        _PENDING.pop(key, None)
