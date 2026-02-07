from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta

import mysql.connector
import requests
from FunPayAPI.account import Account

from .chat_utils import send_message_by_owner
from .constants import (
    RENTAL_EXPIRE_DELAY_MESSAGE,
    RENTAL_EXPIRED_CONFIRM_MESSAGE,
    RENTAL_EXPIRED_MESSAGE,
    RENTAL_CODE_AUTO_START_MESSAGE,
    RENTAL_FROZEN_MESSAGE,
    RENTAL_PAUSE_EXPIRED_MESSAGE,
    RENTAL_UNFROZEN_MESSAGE,
)
from .db_utils import column_exists, get_mysql_config, resolve_workspace_mysql_cfg, table_exists
from .env_utils import env_bool, env_int
from .models import RentalMonitorState
from .notifications_utils import log_notification_event
from .order_utils import (
    fetch_latest_order_id_for_account,
    fetch_latest_order_id_for_owner_lot,
    resolve_order_id_from_funpay,
)
from .lot_utils import start_rental_for_owner
from .presence_utils import fetch_presence
from .steam_guard_utils import steam_id_from_mafile
from .steam_utils import deauthorize_account_sessions
from .text_utils import _calculate_resume_start, _parse_datetime, build_expire_soon_message, normalize_owner_name
from .user_utils import get_user_id_by_username


def _notify_expired_via_backend(
    logger: logging.Logger,
    *,
    account_id: int,
    user_id: int,
    workspace_id: int | None,
    owner: str | None,
    account_name: str | None,
    login: str | None,
    confirm_url: str | None,
) -> bool:
    base = os.getenv("BACKEND_INTERNAL_URL", "").strip()
    token = os.getenv("BACKEND_INTERNAL_TOKEN", "").strip()
    if not base or not token:
        return False
    if workspace_id is None:
        logger.warning("Backend expire skipped: workspace_id is required for internal notify.")
        return False
    payload = {
        "account_id": int(account_id),
        "user_id": int(user_id),
        "workspace_id": int(workspace_id),
        "owner": owner,
        "account_name": account_name,
        "login": login,
        "confirm_url": confirm_url,
    }
    try:
        resp = requests.post(
            f"{base.rstrip('/')}/api/internal/rentals/expire",
            json=payload,
            headers={"X-Worker-Token": token},
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("Backend expire request failed: %s", exc)
        return False
    if not resp.ok:
        logger.warning("Backend expire failed (status %s).", resp.status_code)
        return False
    return True


def fetch_active_rentals_for_monitor(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
) -> tuple[list[dict], bool]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "accounts"):
            return []
        has_lots = table_exists(cursor, "lots")
        has_display_name = has_lots and column_exists(cursor, "lots", "display_name")
        has_workspace = column_exists(cursor, "accounts", "workspace_id")
        has_rental_frozen = column_exists(cursor, "accounts", "rental_frozen")
        has_rental_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        has_account_frozen = column_exists(cursor, "accounts", "account_frozen")
        has_rental_assigned_at = column_exists(cursor, "accounts", "rental_assigned_at")
        params: list = [int(user_id)]
        workspace_clause = ""
        lot_workspace_clause = ""
        if has_workspace and workspace_id is not None:
            workspace_clause = " AND a.workspace_id = %s"
            params.append(int(workspace_id))
        if has_lots and workspace_id is not None and column_exists(cursor, "lots", "workspace_id"):
            lot_workspace_clause = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                   a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   {'a.rental_assigned_at' if has_rental_assigned_at else 'NULL AS rental_assigned_at'},
                   {'a.account_frozen' if has_account_frozen else '0 AS account_frozen'},
                   {'a.rental_frozen' if has_rental_frozen else '0 AS rental_frozen'},
                   {'a.rental_frozen_at' if has_rental_frozen_at else 'NULL AS rental_frozen_at'},
                   l.lot_number, l.lot_url
                   {', l.display_name' if has_display_name else ', NULL AS display_name'}
            FROM accounts a
            LEFT JOIN lots l ON l.account_id = a.id
            WHERE a.user_id = %s AND a.owner IS NOT NULL AND a.owner != ''{workspace_clause}{lot_workspace_clause}
            ORDER BY a.rental_start DESC, a.id DESC
            """,
            tuple(params),
        )
        return list(cursor.fetchall() or []), has_rental_assigned_at
    finally:
        conn.close()


def release_account_in_db(
    mysql_cfg: dict,
    account_id: int,
    user_id: int,
    workspace_id: int | None = None,
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        updates = ["owner = NULL", "rental_start = NULL", "rental_frozen = 0"]
        if has_frozen_at:
            updates.append("rental_frozen_at = NULL")
        if column_exists(cursor, "accounts", "rental_assigned_at"):
            updates.append("rental_assigned_at = NULL")
        if column_exists(cursor, "accounts", "last_code_at"):
            updates.append("last_code_at = NULL")
        params: list = [int(account_id), int(user_id)]
        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s",
            tuple(params),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _touch_rental_assigned_at(
    mysql_cfg: dict,
    account_id: int,
    user_id: int,
    workspace_id: int | None,
    owner: str,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not column_exists(cursor, "accounts", "rental_assigned_at"):
            return
        cursor.execute(
            """
            UPDATE accounts
            SET rental_assigned_at = UTC_TIMESTAMP()
            WHERE id = %s AND user_id = %s AND rental_start IS NULL AND LOWER(owner) = %s
              AND (rental_assigned_at IS NULL)
            """,
            (int(account_id), int(user_id), normalize_owner_name(owner)),
        )
        conn.commit()
    finally:
        conn.close()


def update_rental_freeze_state(
    mysql_cfg: dict,
    *,
    account_id: int,
    user_id: int,
    owner: str,
    workspace_id: int | None,
    frozen: bool,
    rental_start: datetime | None = None,
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        updates = ["rental_frozen = %s"]
        params: list = [1 if frozen else 0]
        if has_frozen_at:
            updates.append("rental_frozen_at = %s")
            params.append(datetime.utcnow() if frozen else None)
        if rental_start is not None:
            updates.append("rental_start = %s")
            params.append(rental_start.strftime("%Y-%m-%d %H:%M:%S"))
        params.extend([int(account_id), int(user_id), normalize_owner_name(owner)])
        cursor.execute(
            f"""
            UPDATE accounts
            SET {', '.join(updates)}
            WHERE id = %s AND user_id = %s AND LOWER(owner) = %s
            """,
            tuple(params),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _clear_expire_delay_state(state: RentalMonitorState, account_id: int) -> None:
    state.expire_delay_since.pop(account_id, None)
    state.expire_delay_next_check.pop(account_id, None)
    state.expire_delay_notified.discard(account_id)


def _is_match_active(presence: dict) -> bool:
    if not presence or not isinstance(presence, dict):
        return False
    if presence.get("in_match"):
        return True
    derived = presence.get("derived") if isinstance(presence.get("derived"), dict) else {}
    if derived.get("in_match") or derived.get("match_time"):
        return True
    if presence.get("match_time"):
        return True
    status_bits = " ".join(
        str(presence.get(key) or "")
        for key in ("presence_state", "presence_display", "status", "state")
    ).lower()
    return any(token in status_bits for token in ("match", "матч", "game", "dota"))


def _should_delay_expire(
    logger: logging.Logger,
    account: Account,
    owner: str,
    account_row: dict,
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    state: RentalMonitorState,
    now: datetime,
) -> bool:
    if not env_bool("DOTA_MATCH_DELAY_EXPIRE", True):
        return False
    account_id = int(account_row.get("id"))
    next_check = state.expire_delay_next_check.get(account_id)
    if next_check and now < next_check:
        return True

    steam_id = steam_id_from_mafile(account_row.get("mafile_json"))
    presence = fetch_presence(steam_id)
    in_match = _is_match_active(presence)
    if not in_match:
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
            extra = f"\nСтатус: {display}"
        lot_url = account_row.get("lot_url") or ""
        lot_line = f"\nЕсли хотите продлить - оплатите лот: {lot_url}" if lot_url else ""
        send_message_by_owner(
            logger,
            account,
            owner,
            f"{RENTAL_EXPIRE_DELAY_MESSAGE}{lot_line}{extra}",
            mysql_cfg=mysql_cfg,
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
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

    rentals, has_assigned_at = fetch_active_rentals_for_monitor(mysql_cfg, int(user_id), workspace_id)
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
    if state.expire_soon_notified:
        state.expire_soon_notified = {
            k: v for k, v in state.expire_soon_notified.items() if k in active_ids
        }

    code_grace_minutes = env_int("RENTAL_CODE_GRACE_MINUTES", 10)
    for row in rentals:
        if (
            code_grace_minutes > 0
            and row.get("rental_start") is None
            and not row.get("rental_frozen")
            and not row.get("account_frozen")
        ):
            owner = row.get("owner")
            if not owner:
                continue
            assigned_at = _parse_datetime(row.get("rental_assigned_at"))
            if assigned_at is None:
                if has_assigned_at:
                    _touch_rental_assigned_at(
                        mysql_cfg,
                        account_id=int(row.get("id") or 0),
                        user_id=int(user_id),
                        workspace_id=workspace_id,
                        owner=owner,
                    )
                continue
            if now >= assigned_at + timedelta(minutes=code_grace_minutes):
                started_count = start_rental_for_owner(
                    mysql_cfg,
                    int(user_id),
                    owner,
                    workspace_id,
                    account_ids=[int(row.get("id") or 0)],
                )
                if started_count:
                    send_message_by_owner(
                        logger,
                        account,
                        owner,
                        RENTAL_CODE_AUTO_START_MESSAGE,
                        mysql_cfg=mysql_cfg,
                        user_id=int(user_id),
                        workspace_id=workspace_id,
                    )
                continue
        account_id = int(row.get("id"))
        owner = row.get("owner")
        frozen = bool(row.get("rental_frozen"))
        frozen_at = _parse_datetime(row.get("rental_frozen_at"))
        if frozen and frozen_at and now >= frozen_at + timedelta(hours=1):
            new_start = _calculate_resume_start(row.get("rental_start"), frozen_at)
            unfrozen = update_rental_freeze_state(
                mysql_cfg,
                account_id=account_id,
                user_id=int(user_id),
                owner=owner,
                workspace_id=workspace_id,
                frozen=False,
                rental_start=new_start,
            )
            if unfrozen:
                frozen = False
                row["rental_frozen"] = 0
                send_message_by_owner(
                    logger,
                    account,
                    owner,
                    RENTAL_PAUSE_EXPIRED_MESSAGE,
                    mysql_cfg=mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=workspace_id,
                )
                state.freeze_cache[account_id] = False
                continue
        prev = state.freeze_cache.get(account_id)
        if prev is None:
            state.freeze_cache[account_id] = frozen
        elif prev != frozen:
            state.freeze_cache[account_id] = frozen
            message = RENTAL_FROZEN_MESSAGE if frozen else RENTAL_UNFROZEN_MESSAGE
            send_message_by_owner(
                logger,
                account,
                owner,
                message,
                mysql_cfg=mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
            )

    for row in rentals:
        account_id = int(row.get("id"))
        owner = row.get("owner")
        if not owner:
            _clear_expire_delay_state(state, account_id)
            state.expire_soon_notified.pop(account_id, None)
            continue
        if row.get("rental_frozen"):
            state.expire_soon_notified.pop(account_id, None)
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
            state.expire_soon_notified.pop(account_id, None)
            continue
        expiry_time = started + timedelta(minutes=total_minutes_int)
        if now < expiry_time:
            _clear_expire_delay_state(state, account_id)
            remind_minutes = env_int("RENTAL_EXPIRE_REMIND_MINUTES", 10)
            if remind_minutes > 0:
                seconds_left = int((expiry_time - now).total_seconds())
                expiry_ts = int(expiry_time.timestamp())
                if 0 < seconds_left <= remind_minutes * 60:
                    if state.expire_soon_notified.get(account_id) != expiry_ts:
                        message = build_expire_soon_message(row, seconds_left)
                        send_message_by_owner(
                            logger,
                            account,
                            owner,
                            message,
                            mysql_cfg=mysql_cfg,
                            user_id=int(user_id),
                            workspace_id=workspace_id,
                        )
                        state.expire_soon_notified[account_id] = expiry_ts
                else:
                    state.expire_soon_notified.pop(account_id, None)
            continue

        if _should_delay_expire(logger, account, owner, row, mysql_cfg, int(user_id), workspace_id, state, now):
            continue

        order_id = fetch_latest_order_id_for_account(
            mysql_cfg,
            account_id=account_id,
            owner=owner,
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
        if not order_id and row.get("lot_number") is not None:
            order_id = fetch_latest_order_id_for_owner_lot(
                mysql_cfg,
                owner=owner,
                lot_number=int(row.get("lot_number")),
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
        if not order_id:
            order_id = resolve_order_id_from_funpay(
                account,
                owner=owner,
                lot_number=row.get("lot_number"),
                account_name=row.get("account_name") or row.get("login"),
            )
        confirm_url = f"https://funpay.com/orders/{order_id}/" if order_id else None

        if _notify_expired_via_backend(
            logger,
            account_id=account_id,
            user_id=int(user_id),
            workspace_id=workspace_id,
            owner=owner,
            account_name=row.get("account_name"),
            login=row.get("login"),
            confirm_url=confirm_url,
        ):
            _clear_expire_delay_state(state, account_id)
            continue

        if env_bool("AUTO_STEAM_DEAUTHORIZE_ON_EXPIRE", True):
            deauth_ok = deauthorize_account_sessions(logger, row)
            log_notification_event(
                mysql_cfg,
                event_type="deauthorize",
                status="ok" if deauth_ok else "failed",
                title="Steam deauthorize on expiry",
                message="Auto deauthorize triggered by rental expiration.",
                owner=owner,
                account_name=row.get("account_name") or row.get("login"),
                account_id=account_id,
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
        released = release_account_in_db(mysql_cfg, account_id, int(user_id), workspace_id)
        log_notification_event(
            mysql_cfg,
            event_type="rental_expired",
            status="ok" if released else "failed",
            title="Rental expired",
            message="Rental expired and account was released." if released else "Rental expired but release failed.",
            owner=owner,
            account_name=row.get("account_name") or row.get("login"),
            account_id=account_id,
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
        if released:
            send_message_by_owner(
                logger,
                account,
                owner,
                RENTAL_EXPIRED_MESSAGE,
                mysql_cfg=mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
            confirm_message = RENTAL_EXPIRED_CONFIRM_MESSAGE
            if confirm_url:
                confirm_message = (
                    f"{RENTAL_EXPIRED_CONFIRM_MESSAGE}\n\n"
                    f"\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u0442\u0443\u0442 -> {confirm_url}"
                )
            send_message_by_owner(
                logger,
                account,
                owner,
                confirm_message,
                mysql_cfg=mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
        _clear_expire_delay_state(state, account_id)
