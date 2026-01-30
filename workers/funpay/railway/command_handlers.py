from __future__ import annotations

import logging
from datetime import datetime, timedelta

import mysql.connector
from FunPayAPI.account import Account

from .account_utils import (
    build_account_message,
    build_display_name,
    build_rental_choice_message,
    resolve_rental_minutes,
)
from .blacklist_utils import is_blacklisted, log_blacklist_event
from .chat_utils import send_chat_message, send_message_by_owner
from .constants import (
    LP_REPLACE_FAILED_MESSAGE,
    LP_REPLACE_MMR_RANGE,
    LP_REPLACE_NO_CODE_MESSAGE,
    LP_REPLACE_NO_MATCH_MESSAGE,
    LP_REPLACE_NO_MMR_MESSAGE,
    LP_REPLACE_SUCCESS_PREFIX,
    LP_REPLACE_TOO_LATE_MESSAGE,
    LP_REPLACE_WINDOW_MINUTES,
    ORDER_ACCOUNT_BUSY,
    RENTAL_ALREADY_PAUSED_MESSAGE,
    RENTAL_CODE_BLOCKED_MESSAGE,
    RENTAL_EXPIRE_DELAY_MESSAGE,
    RENTAL_FROZEN_MESSAGE,
    RENTAL_NOT_PAUSED_MESSAGE,
    RENTAL_PAUSED_MESSAGE,
    RENTAL_PAUSE_ALREADY_USED_MESSAGE,
    RENTAL_PAUSE_EXPIRED_MESSAGE,
    RENTAL_PAUSE_IN_MATCH_MESSAGE,
    RENTAL_RESUMED_MESSAGE,
    RENTAL_STARTED_MESSAGE,
    RENTAL_UNFROZEN_MESSAGE,
    RENTALS_EMPTY,
    STOCK_DB_MISSING,
    STOCK_EMPTY,
    STOCK_LIST_LIMIT,
    STOCK_TITLE,
)
from .db_utils import get_mysql_config
from .env_utils import env_int
from .lot_utils import (
    fetch_available_lot_accounts,
    fetch_lot_mapping,
    fetch_owner_accounts,
    replace_rental_account,
    start_rental_for_owner,
)
from .rental_utils import update_rental_freeze_state
from .steam_guard_utils import get_steam_guard_code, steam_id_from_mafile
from .text_utils import (
    _calculate_resume_start,
    _parse_datetime,
    detect_command,
    format_duration_minutes,
    format_penalty_label,
    get_unit_minutes,
    normalize_owner_name,
    parse_account_id_arg,
    parse_command,
    parse_lot_number,
)
from .user_utils import get_user_id_by_username


def build_stock_messages(accounts: list[dict]) -> list[str]:
    lines: list[str] = []
    for acc in accounts:
        name = acc.get("display_name") or acc.get("account_name") or acc.get("login") or "-"
        lot_url = acc.get("lot_url")
        if lot_url:
            lines.append(f"{name} - {lot_url}")
        else:
            lines.append(f"{name}")
    return lines


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

    accounts = fetch_available_lot_accounts(mysql_cfg, user_id, workspace_id)
    if not accounts:
        send_chat_message(logger, account, chat_id, STOCK_EMPTY)
        return True

    lines = build_stock_messages(accounts)
    if not lines:
        send_chat_message(logger, account, chat_id, STOCK_EMPTY)
        return True

    limit = env_int("STOCK_LIST_LIMIT", STOCK_LIST_LIMIT)
    if limit <= 0:
        send_chat_message(logger, account, chat_id, "\n".join([STOCK_TITLE, *lines]))
        return True

    for index in range(0, len(lines), limit):
        chunk = lines[index : index + limit]
        if index == 0:
            message = "\n".join([STOCK_TITLE, *chunk])
        else:
            message = "\n".join(chunk)
        send_chat_message(logger, account, chat_id, message)
    return True


def _select_account_for_command(
    logger: logging.Logger,
    account: Account,
    chat_id: int,
    accounts: list[dict],
    args: str,
    command: str,
) -> dict | None:
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return None
    if len(accounts) == 1:
        return accounts[0]
    account_id = parse_account_id_arg(args)
    if account_id is None:
        send_chat_message(logger, account, chat_id, build_rental_choice_message(accounts, command))
        return None
    for acc in accounts:
        try:
            if int(acc.get("id")) == int(account_id):
                return acc
        except Exception:
            continue
    send_chat_message(logger, account, chat_id, build_rental_choice_message(accounts, command))
    return None


def _select_replacement_account(
    available: list[dict],
    *,
    target_mmr: int,
    exclude_id: int,
    max_delta: int = LP_REPLACE_MMR_RANGE,
) -> dict | None:
    candidates: list[tuple[int, int, dict]] = []
    for acc in available:
        if int(acc.get("id") or 0) == exclude_id:
            continue
        raw_mmr = acc.get("mmr")
        if raw_mmr is None:
            continue
        try:
            mmr = int(raw_mmr)
        except Exception:
            continue
        diff = abs(mmr - target_mmr)
        if diff > max_delta:
            continue
        candidates.append((diff, mmr, acc))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], int(item[2].get("id") or 0)))
    return candidates[0][2]


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

    active_accounts = [acc for acc in accounts if not acc.get("rental_frozen")]
    if not active_accounts:
        send_chat_message(logger, account, chat_id, RENTAL_CODE_BLOCKED_MESSAGE)
        return True

    lines = ["Коды Steam Guard:"]
    started_now = False
    for acc in active_accounts:
        display_name = build_display_name(acc)
        ok, code = get_steam_guard_code(acc.get("mafile_json"))
        login = acc.get("login") or "-"
        if ok:
            lines.append(f"{display_name} ({login}): {code}")
        else:
            lines.append(f"{display_name} ({login}): ошибка {code}")
        if acc.get("rental_start") is None:
            started_now = True

    if started_now:
        start_rental_for_owner(mysql_cfg, int(user_id), sender_username, workspace_id)
        lines.extend(["", RENTAL_STARTED_MESSAGE])

    send_chat_message(logger, account, chat_id, "\n".join(lines))
    return True


def handle_low_priority_replace_command(
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
        logger.warning("LP replace command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("LP replace skipped: %s", exc)
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
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command)
    if not selected:
        return True

    rental_start = _parse_datetime(selected.get("rental_start"))
    if rental_start is None:
        send_chat_message(logger, account, chat_id, LP_REPLACE_NO_CODE_MESSAGE)
        return True
    if datetime.utcnow() - rental_start > timedelta(minutes=LP_REPLACE_WINDOW_MINUTES):
        send_chat_message(logger, account, chat_id, LP_REPLACE_TOO_LATE_MESSAGE)
        return True
    raw_mmr = selected.get("mmr")
    try:
        target_mmr = int(raw_mmr)
    except Exception:
        target_mmr = None
    if target_mmr is None:
        send_chat_message(logger, account, chat_id, LP_REPLACE_NO_MMR_MESSAGE)
        return True

    try:
        available = fetch_available_lot_accounts(mysql_cfg, user_id, workspace_id=workspace_id)
    except mysql.connector.Error as exc:
        logger.warning("Low priority replace lookup failed: %s", exc)
        send_chat_message(logger, account, chat_id, LP_REPLACE_FAILED_MESSAGE)
        return True

    replacement = _select_replacement_account(
        available,
        target_mmr=target_mmr,
        exclude_id=int(selected.get("id") or 0),
        max_delta=LP_REPLACE_MMR_RANGE,
    )
    if not replacement:
        send_chat_message(logger, account, chat_id, LP_REPLACE_NO_MATCH_MESSAGE)
        return True

    rental_minutes = resolve_rental_minutes(selected)
    try:
        rental_units = int(selected.get("rental_duration") or 0)
    except Exception:
        rental_units = 0
    if rental_units <= 0 and rental_minutes > 0:
        rental_units = max(1, (rental_minutes + 59) // 60)

    ok = replace_rental_account(
        mysql_cfg,
        old_account_id=int(selected["id"]),
        new_account_id=int(replacement["id"]),
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
        rental_start=rental_start,
        rental_duration=rental_units,
        rental_duration_minutes=rental_minutes,
    )
    if not ok:
        send_chat_message(logger, account, chat_id, LP_REPLACE_FAILED_MESSAGE)
        return True

    replacement_info = dict(replacement)
    replacement_info["owner"] = sender_username
    replacement_info["rental_start"] = rental_start
    replacement_info["rental_duration"] = rental_units
    replacement_info["rental_duration_minutes"] = rental_minutes
    replacement_info["account_frozen"] = 0
    replacement_info["rental_frozen"] = 0
    message = f"{LP_REPLACE_SUCCESS_PREFIX}\n{build_account_message(replacement_info, rental_minutes, False)}"
    send_chat_message(logger, account, chat_id, message)
    return True


def handle_pause_command(
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
        logger.warning("Pause command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Pause command skipped: %s", exc)
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
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command)
    if not selected:
        return True

    if selected.get("rental_frozen"):
        send_chat_message(logger, account, chat_id, RENTAL_ALREADY_PAUSED_MESSAGE)
        return True

    ok = update_rental_freeze_state(
        mysql_cfg,
        account_id=int(selected["id"]),
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
        frozen=True,
    )
    if not ok:
        send_chat_message(logger, account, chat_id, RENTAL_PAUSE_EXPIRED_MESSAGE)
        return True

    pause_message = RENTAL_PAUSED_MESSAGE
    if len(accounts) > 1:
        pause_message = f"{pause_message} (ID {selected.get('id')})"
    send_chat_message(logger, account, chat_id, pause_message)
    return True


def handle_resume_command(
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
        logger.warning("Resume command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Resume command skipped: %s", exc)
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
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command)
    if not selected:
        return True

    if not selected.get("rental_frozen"):
        send_chat_message(logger, account, chat_id, RENTAL_NOT_PAUSED_MESSAGE)
        return True

    new_start = _calculate_resume_start(selected.get("rental_start"), selected.get("rental_frozen_at"))
    ok = update_rental_freeze_state(
        mysql_cfg,
        account_id=int(selected["id"]),
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
        frozen=False,
        rental_start=new_start,
    )
    if not ok:
        send_chat_message(logger, account, chat_id, "❌ Не удалось снять паузу.")
        return True

    resume_message = RENTAL_RESUMED_MESSAGE
    if len(accounts) > 1:
        resume_message = f"{resume_message} (ID {selected.get('id')})"
    send_chat_message(logger, account, chat_id, resume_message)
    return True


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
        "!сток": handle_stock_command,
        "!акк": handle_account_command,
        "!код": handle_code_command,
        "!продлить": lambda *a: _log_command_stub(*a, action="extend"),
        "!лпзамена": handle_low_priority_replace_command,
        "!отмена": lambda *a: _log_command_stub(*a, action="cancel"),
        "!админ": lambda *a: _log_command_stub(*a, action="admin"),
        "!пауза": handle_pause_command,
        "!продолжить": handle_resume_command,
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
