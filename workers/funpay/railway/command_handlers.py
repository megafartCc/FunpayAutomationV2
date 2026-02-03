from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import mysql.connector
from FunPayAPI.account import Account

from .account_utils import (
    build_account_message,
    build_display_name,
    build_rental_choice_message,
    resolve_rental_minutes,
)
from .blacklist_utils import is_blacklisted, log_blacklist_event, upsert_blacklist_suggestion
from .chat_utils import send_chat_message, send_message_by_owner
from .bonus_utils import adjust_bonus_balance, get_bonus_balance
from .constants import (
    LP_REPLACE_FAILED_MESSAGE,
    LP_REPLACE_MMR_RANGE,
    LP_REPLACE_NO_CODE_MESSAGE,
    LP_REPLACE_NO_MATCH_MESSAGE,
    LP_REPLACE_NO_MMR_MESSAGE,
    LP_REPLACE_SUCCESS_PREFIX,
    LP_REPLACE_TOO_LATE_MESSAGE,
    LP_REPLACE_RATE_LIMIT_MESSAGE,
    LP_REPLACE_WINDOW_MINUTES,
    ORDER_ACCOUNT_BUSY,
    RENTAL_ALREADY_PAUSED_MESSAGE,
    RENTAL_CODE_BLOCKED_MESSAGE,
    RENTAL_NOT_ACTIVE_MESSAGE,
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
    extend_rental_for_buyer,
    replace_rental_account,
    start_rental_for_owner,
)
from .order_utils import fetch_previous_owner_for_account
from .pending_utils import set_pending_command
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

_lp_replace_rate_limit: dict[tuple[int, str], float] = {}


def _get_bot_key(account: Account) -> str:
    return str(getattr(account, "username", None) or getattr(account, "id", "") or "")


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
    sender_username: str,
) -> dict | None:
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return None
    if len(accounts) == 1:
        return accounts[0]
    account_id = parse_account_id_arg(args)
    if account_id is None:
        set_pending_command(_get_bot_key(account), chat_id, sender_username, command, "")
        send_chat_message(logger, account, chat_id, build_rental_choice_message(accounts, command))
        return None
    for acc in accounts:
        try:
            if int(acc.get("id")) == int(account_id):
                return acc
        except Exception:
            continue
    set_pending_command(_get_bot_key(account), chat_id, sender_username, command, "")
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


def _is_rental_active(account_row: dict) -> bool:
    if not account_row:
        return False
    if not account_row.get("owner"):
        return False
    if account_row.get("account_frozen") or account_row.get("rental_frozen"):
        return False
    minutes = account_row.get("rental_duration_minutes")
    if minutes is None:
        try:
            minutes = int(account_row.get("rental_duration") or 0) * 60
        except Exception:
            minutes = 0
    try:
        return int(minutes or 0) > 0
    except Exception:
        return False


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

    def _send_account_choice() -> None:
        lines = ["У вас есть несколько аренд:", ""]
        for acc in accounts:
            display = build_display_name(acc)
            lines.append(f"{display} - ID {acc.get('id')}")
        lines.extend(["", "Выберите, к какому аккаунту хотите получить данные: !акк <ID>"])
        send_chat_message(logger, account, chat_id, "\n".join(lines))

    account_id = parse_account_id_arg(args)
    if len(accounts) > 1 and account_id is None:
        set_pending_command(_get_bot_key(account), chat_id, sender_username, command, "")
        _send_account_choice()
        return True

    selected = None
    if account_id is not None:
        for acc in accounts:
            try:
                if int(acc.get("id")) == int(account_id):
                    selected = acc
                    break
            except Exception:
                continue
        if not selected:
            set_pending_command(_get_bot_key(account), chat_id, sender_username, command, "")
            _send_account_choice()
            return True
    else:
        selected = accounts[0]

    if not _is_rental_active(selected):
        send_chat_message(logger, account, chat_id, RENTAL_NOT_ACTIVE_MESSAGE)
        return True

    total_minutes = selected.get("rental_duration_minutes")
    if total_minutes is None:
        total_minutes = get_unit_minutes(selected)
    message = build_account_message(selected, int(total_minutes or 0), include_timer_note=True)
    send_chat_message(logger, account, chat_id, message)
    return True


def handle_extend_command(
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
        logger.warning("Extend command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Extend command skipped: %s", exc)
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

    tokens = args.split()
    if not tokens:
        send_chat_message(logger, account, chat_id, "Укажите часы и ID: !продлить <часы> <ID_аккаунта>")
        return True
    try:
        hours = int(tokens[0])
    except Exception:
        hours = 0
    if hours <= 0:
        send_chat_message(logger, account, chat_id, "Укажите часы и ID: !продлить <часы> <ID_аккаунта>")
        return True

    account_id = parse_account_id_arg(" ".join(tokens[1:])) if len(tokens) > 1 else None

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    selected = None
    if account_id is not None:
        for acc in accounts:
            try:
                if int(acc.get("id")) == int(account_id):
                    selected = acc
                    break
            except Exception:
                continue
        if not selected:
            send_chat_message(
                logger,
                account,
                chat_id,
                build_rental_choice_message(accounts, "!продлить"),
            )
            return True
    elif len(accounts) == 1:
        selected = accounts[0]
    else:
        send_chat_message(logger, account, chat_id, build_rental_choice_message(accounts, "!продлить"))
        return True

    duration_label = format_duration_minutes(int(hours) * 60)
    lot_url = selected.get("lot_url")
    lot_number = selected.get("lot_number")
    if not lot_url and lot_number:
        lot_url = f"лот №{lot_number}"
    if lot_url:
        message = (
            f"Чтобы продлить аренду на {duration_label}, оплатите этот лот: {lot_url}.\n"
            "1 шт = 1 час."
        )
    else:
        message = (
            f"Чтобы продлить аренду на {duration_label}, оплатите соответствующий лот.\n"
            "Лот не найден, пожалуйста напишите !админ."
        )
    send_chat_message(
        logger,
        account,
        chat_id,
        message,
    )
    return True


def handle_bonus_command(
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
        logger.warning("Bonus command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Bonus command skipped: %s", exc)
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

    balance = get_bonus_balance(
        mysql_cfg,
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
    )
    accounts = fetch_owner_accounts(mysql_cfg, int(user_id), sender_username, workspace_id)

    account_id = parse_account_id_arg(args)
    if not args or account_id is None:
        if balance <= 0:
            message = "У вас нет бонусных часов."
            send_chat_message(logger, account, chat_id, message)
            return True
        lines = [f"Ваш баланс бонусов (время): {format_duration_minutes(balance)}."]
        if accounts:
            lines.append("Чтобы применить бонус к аренде, напишите: !бонус <ID аккаунта>.")
            for acc in accounts:
                display = build_display_name(acc)
                acc_id = acc.get("id")
                lines.append(f"{display} - ID {acc_id}")
        else:
            lines.append("Активных аренд сейчас нет. Бонус сохранён — примените позже командой !бонус <ID аккаунта>.")
        send_chat_message(logger, account, chat_id, "\n".join(lines))
        return True

    if balance < 60:
        send_chat_message(logger, account, chat_id, f"Недостаточно бонусных часов. Баланс: {format_duration_minutes(balance)}.")
        return True

    selected = None
    for acc in accounts:
        try:
            if int(acc.get("id")) == int(account_id):
                selected = acc
                break
        except Exception:
            continue
    if not selected:
        send_chat_message(logger, account, chat_id, "Укажите корректный ID аренды: !бонус <ID>")
        return True

    updated = extend_rental_for_buyer(
        mysql_cfg,
        account_id=int(selected["id"]),
        user_id=int(user_id),
        buyer=sender_username,
        add_units=1,
        add_minutes=60,
        workspace_id=workspace_id,
    )
    if not updated:
        send_chat_message(logger, account, chat_id, "Не удалось применить бонус. Попробуйте позже.")
        return True

    new_balance, applied = adjust_bonus_balance(
        mysql_cfg,
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
        delta_minutes=-60,
        reason="apply_bonus",
        account_id=int(selected["id"]),
    )
    if applied == 0:
        send_chat_message(logger, account, chat_id, "Недостаточно бонусных часов.")
        return True

    send_chat_message(
        logger,
        account,
        chat_id,
        f"✅ Бонусный час применён. Новый баланс: {format_duration_minutes(new_balance)}.",
    )
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

    active_accounts = [acc for acc in accounts if _is_rental_active(acc)]
    if not active_accounts:
        if any(acc.get("rental_frozen") for acc in accounts):
            send_chat_message(logger, account, chat_id, RENTAL_CODE_BLOCKED_MESSAGE)
        else:
            send_chat_message(logger, account, chat_id, RENTAL_NOT_ACTIVE_MESSAGE)
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
        account_ids = [
            int(acc.get("id"))
            for acc in active_accounts
            if acc.get("rental_start") is None and acc.get("id") is not None
        ]
        start_rental_for_owner(mysql_cfg, int(user_id), sender_username, workspace_id, account_ids)
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
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command, sender_username)
    if not selected:
        return True

    suggestion_reason = "LP replacement request"
    display_name = build_display_name(selected)
    account_login = (selected.get("login") or "-").strip() or "-"
    account_steam_id = steam_id_from_mafile(selected.get("mafile_json"))
    previous_owner = fetch_previous_owner_for_account(
        mysql_cfg,
        account_id=int(selected.get("id") or 0),
        user_id=int(user_id),
        workspace_id=workspace_id,
        current_owner=sender_username,
    )
    suggestion_details = (
        f"Account: {display_name} (ID {selected.get('id')}); "
        f"login={account_login}; steam_id={account_steam_id or 'unknown'}; "
        f"current_owner={sender_username}; previous_owner={previous_owner or 'unknown'}"
    )
    suggestion_added = False
    suggestion_owner = None
    if previous_owner and normalize_owner_name(previous_owner) != normalize_owner_name(sender_username):
        suggestion_owner = previous_owner
        suggestion_added = upsert_blacklist_suggestion(
            mysql_cfg,
            owner=previous_owner,
            user_id=int(user_id),
            workspace_id=workspace_id,
            reason=suggestion_reason,
            details=suggestion_details,
        )

    rental_start = _parse_datetime(selected.get("rental_start"))
    if rental_start is None:
        send_chat_message(logger, account, chat_id, LP_REPLACE_NO_CODE_MESSAGE)
        return True
    if datetime.utcnow() - rental_start > timedelta(minutes=LP_REPLACE_WINDOW_MINUTES):
        send_chat_message(logger, account, chat_id, LP_REPLACE_TOO_LATE_MESSAGE)
        return True
    owner_key = normalize_owner_name(sender_username)
    if owner_key:
        rate_key = (int(user_id), owner_key)
        now = time.time()
        last_request = _lp_replace_rate_limit.get(rate_key)
        if last_request is not None and now - last_request < 3600:
            send_chat_message(logger, account, chat_id, LP_REPLACE_RATE_LIMIT_MESSAGE)
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
        if suggestion_added:
            log_blacklist_event(
                mysql_cfg,
                owner=suggestion_owner or sender_username,
                action="lp_replace_request",
                reason=suggestion_reason,
                details=f"{suggestion_details}; result=failed",
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
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
    if owner_key:
        _lp_replace_rate_limit[(int(user_id), owner_key)] = time.time()
    if suggestion_added:
        log_blacklist_event(
            mysql_cfg,
            owner=suggestion_owner or sender_username,
            action="lp_replace_request",
            reason=suggestion_reason,
            details=f"{suggestion_details}; result=success",
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
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
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command, sender_username)
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
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command, sender_username)
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
        "!продлить": handle_extend_command,
        "!лпзамена": handle_low_priority_replace_command,
        "!отмена": lambda *a: _log_command_stub(*a, action="cancel"),
        "!админ": lambda *a: _log_command_stub(*a, action="admin"),
        "!пауза": handle_pause_command,
        "!продолжить": handle_resume_command,
        "!бонус": handle_bonus_command,
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
