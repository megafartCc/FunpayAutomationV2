from __future__ import annotations

import logging

import mysql.connector
from FunPayAPI.account import Account
from FunPayAPI.common.enums import MessageTypes

from .account_utils import build_account_message, resolve_rental_minutes
from .blacklist_utils import (
    get_blacklist_compensation_total,
    is_blacklisted,
    log_blacklist_event,
    remove_blacklist_entry,
)
from .chat_utils import send_chat_message
from .constants import (
    ORDER_ACCOUNT_NO_REPLACEMENT,
    ORDER_ACCOUNT_REPLACEMENT_PREFIX,
    ORDER_LOT_MISSING,
    ORDER_LOT_UNMAPPED,
    _processed_orders,
    _processed_orders_lock,
)
from .db_utils import column_exists, get_mysql_config, resolve_workspace_mysql_cfg, table_exists
from .env_utils import env_int
from .lot_utils import (
    assign_account_to_buyer,
    extend_rental_for_buyer,
    fetch_lot_mapping,
    fetch_owner_accounts,
    find_replacement_account_for_lot,
)
from .notifications_utils import log_notification_event
from .steam_guard_utils import steam_id_from_mafile
from .text_utils import (
    extract_lot_number_from_order,
    extract_order_id,
    format_duration_minutes,
    format_penalty_label,
    get_unit_minutes,
    normalize_owner_name,
    normalize_username,
)


def _order_key(site_username: str | None, site_user_id: int | None, workspace_id: int | None) -> str:
    user_key = str(site_user_id) if site_user_id is not None else (site_username or "unknown")
    ws_key = str(workspace_id) if workspace_id is not None else "none"
    return f"{user_key}:{ws_key}"


def is_order_processed(site_username: str | None, site_user_id: int | None, workspace_id: int | None, order_id: str) -> bool:
    key = _order_key(site_username, site_user_id, workspace_id)
    with _processed_orders_lock:
        return order_id in _processed_orders.get(key, set())


def mark_order_processed(site_username: str | None, site_user_id: int | None, workspace_id: int | None, order_id: str) -> None:
    key = _order_key(site_username, site_user_id, workspace_id)
    with _processed_orders_lock:
        bucket = _processed_orders.setdefault(key, set())
        bucket.add(order_id)


def log_order_history(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
    account_id: int | None = None,
    account_name: str | None = None,
    steam_id: str | None = None,
    rental_minutes: int | None = None,
    lot_number: int | None = None,
    amount: int | None = None,
    price: float | None = None,
    action: str = "purchase",
) -> None:
    order_key = str(order_id or "").strip()
    if order_key.startswith("#"):
        order_key = order_key[1:]
    owner_key = normalize_owner_name(owner)
    if not order_key or not owner_key:
        return
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return
        has_steam_id = column_exists(cursor, "order_history", "steam_id")
        if has_steam_id:
            cursor.execute(
                """
                INSERT INTO order_history (
                    order_id, owner, account_name, account_id, steam_id, rental_minutes,
                    lot_number, amount, price, action, user_id, workspace_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_key,
                    owner_key,
                    account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                    int(account_id) if account_id is not None else None,
                    steam_id.strip() if isinstance(steam_id, str) and steam_id.strip() else None,
                    int(rental_minutes) if rental_minutes is not None else None,
                    int(lot_number) if lot_number is not None else None,
                    int(amount) if amount is not None else None,
                    float(price) if price is not None else None,
                    action,
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO order_history (
                    order_id, owner, account_name, account_id, rental_minutes,
                    lot_number, amount, price, action, user_id, workspace_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_key,
                    owner_key,
                    account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                    int(account_id) if account_id is not None else None,
                    int(rental_minutes) if rental_minutes is not None else None,
                    int(lot_number) if lot_number is not None else None,
                    int(amount) if amount is not None else None,
                    float(price) if price is not None else None,
                    action,
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                ),
            )
        conn.commit()
        log_notification_event(
            mysql_cfg,
            event_type="purchase",
            status="ok",
            title="Order activity",
            message=f"Order {order_key} action: {action}.",
            owner=owner_key,
            account_name=account_name,
            account_id=account_id,
            order_id=order_key,
            user_id=user_id,
            workspace_id=workspace_id,
        )
    finally:
        conn.close()


def _normalize_order_id(order_id: str | None) -> str:
    order_key = str(order_id or "").strip()
    if order_key.startswith("#"):
        order_key = order_key[1:]
    return order_key


def fetch_order_history_summary(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
    workspace_id: int | None = None,
) -> dict | None:
    order_key = _normalize_order_id(order_id)
    owner_key = normalize_owner_name(owner)
    if not order_key or not owner_key:
        return None
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "order_history"):
            return None
        params: list = [order_key, owner_key]
        workspace_clause = ""
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT id, account_id, account_name, user_id, workspace_id, rental_minutes, lot_number, action
            FROM order_history
            WHERE order_id = %s AND owner = %s{workspace_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def has_review_bonus(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
    workspace_id: int | None = None,
) -> bool:
    order_key = _normalize_order_id(order_id)
    owner_key = normalize_owner_name(owner)
    if not order_key or not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return False
        params: list = [order_key, owner_key]
        workspace_clause = ""
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT 1
            FROM order_history
            WHERE order_id = %s AND owner = %s AND action = 'review_bonus'{workspace_clause}
            LIMIT 1
            """,
            tuple(params),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def apply_review_bonus_for_order(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
    bonus_minutes: int = 60,
) -> dict | None:
    summary = fetch_order_history_summary(mysql_cfg, order_id=order_id, owner=owner)
    if not summary:
        return None
    if has_review_bonus(mysql_cfg, order_id=order_id, owner=owner, workspace_id=summary.get("workspace_id")) and not has_review_bonus_reverted(
        mysql_cfg, order_id=order_id, owner=owner, workspace_id=summary.get("workspace_id")
    ):
        return None
    account_id = summary.get("account_id")
    user_id = summary.get("user_id")
    if account_id is None or user_id is None:
        return None
    if summary.get("rental_minutes") in (None, 0):
        return None
    updated = extend_rental_for_buyer(
        mysql_cfg,
        account_id=int(account_id),
        user_id=int(user_id),
        buyer=owner,
        add_units=1,
        add_minutes=int(bonus_minutes),
        workspace_id=summary.get("workspace_id"),
    )
    if not updated:
        return None
    log_order_history(
        mysql_cfg,
        order_id=order_id,
        owner=owner,
        user_id=int(user_id),
        workspace_id=summary.get("workspace_id"),
        account_id=int(account_id),
        account_name=summary.get("account_name"),
        rental_minutes=int(bonus_minutes),
        lot_number=summary.get("lot_number"),
        action="review_bonus",
    )
    return updated


def has_review_bonus_reverted(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
    workspace_id: int | None = None,
) -> bool:
    order_key = _normalize_order_id(order_id)
    owner_key = normalize_owner_name(owner)
    if not order_key or not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return False
        params: list = [order_key, owner_key]
        workspace_clause = ""
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT 1
            FROM order_history
            WHERE order_id = %s AND owner = %s AND action = 'review_bonus_revert'{workspace_clause}
            LIMIT 1
            """,
            tuple(params),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def fetch_review_bonus_entry(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
) -> dict | None:
    order_key = _normalize_order_id(order_id)
    owner_key = normalize_owner_name(owner)
    if not order_key or not owner_key:
        return None
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, None)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "order_history"):
            return None
        cursor.execute(
            """
            SELECT account_id, account_name, user_id, workspace_id, rental_minutes, lot_number
            FROM order_history
            WHERE order_id = %s AND owner = %s AND action = 'review_bonus'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (order_key, owner_key),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def revert_review_bonus_for_order(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
    bonus_minutes: int = 60,
) -> dict | None:
    entry = fetch_review_bonus_entry(mysql_cfg, order_id=order_id, owner=owner)
    if not entry:
        return None
    workspace_id = entry.get("workspace_id")
    if has_review_bonus_reverted(mysql_cfg, order_id=order_id, owner=owner, workspace_id=workspace_id):
        return None
    account_id = entry.get("account_id")
    user_id = entry.get("user_id")
    if account_id is None or user_id is None:
        return None
    recorded_minutes = entry.get("rental_minutes")
    try:
        bonus_minutes = int(recorded_minutes if recorded_minutes is not None else bonus_minutes)
    except Exception:
        bonus_minutes = int(bonus_minutes)
    updated = extend_rental_for_buyer(
        mysql_cfg,
        account_id=int(account_id),
        user_id=int(user_id),
        buyer=owner,
        add_units=-1,
        add_minutes=-int(bonus_minutes),
        workspace_id=workspace_id,
    )
    if not updated:
        return None
    log_order_history(
        mysql_cfg,
        order_id=order_id,
        owner=owner,
        user_id=int(user_id),
        workspace_id=workspace_id,
        account_id=int(account_id),
        account_name=entry.get("account_name"),
        rental_minutes=-int(bonus_minutes),
        lot_number=entry.get("lot_number"),
        action="review_bonus_revert",
    )
    return updated


def fetch_latest_order_id_for_account(
    mysql_cfg: dict,
    *,
    account_id: int,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
) -> str | None:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return None
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return None
        workspace_clause = ""
        params: list = [int(user_id), int(account_id), owner_key]
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT order_id
            FROM order_history
            WHERE user_id = %s AND account_id = %s AND owner = %s{workspace_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def fetch_latest_account_for_owner_lot(
    mysql_cfg: dict,
    *,
    owner: str,
    lot_number: int,
    user_id: int,
    workspace_id: int | None,
) -> int | None:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return None
    try:
        lot_number_int = int(lot_number)
    except Exception:
        return None
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return None
        has_workspace = column_exists(cursor, "order_history", "workspace_id")
        workspace_clause = ""
        params: list = [owner_key, int(lot_number_int), int(user_id)]
        if has_workspace and workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT account_id
            FROM order_history
            WHERE owner = %s AND lot_number = %s AND user_id = %s{workspace_clause}
              AND account_id IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return int(row[0]) if row[0] is not None else None
    finally:
        conn.close()


def fetch_latest_order_id_for_owner_lot(
    mysql_cfg: dict,
    *,
    owner: str,
    lot_number: int,
    user_id: int,
    workspace_id: int | None,
) -> str | None:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return None
    try:
        lot_number_int = int(lot_number)
    except Exception:
        return None
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return None
        has_workspace = column_exists(cursor, "order_history", "workspace_id")
        workspace_clause = ""
        params: list = [owner_key, int(lot_number_int), int(user_id)]
        if has_workspace and workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT order_id
            FROM order_history
            WHERE owner = %s AND lot_number = %s AND user_id = %s{workspace_clause}
              AND order_id IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def resolve_order_id_from_funpay(
    account: Account,
    *,
    owner: str,
    lot_number: int | None = None,
    account_name: str | None = None,
) -> str | None:
    owner_key = str(owner or "").strip()
    if not owner_key:
        return None
    try:
        _, orders, _, _ = account.get_sales(
            buyer=owner_key,
            include_paid=True,
            include_closed=True,
            include_refunded=True,
        )
    except Exception as exc:
        logging.getLogger("funpay.worker").warning("Failed to resolve order for %s: %s", owner_key, exc)
        return None
    if not orders:
        return None
    if lot_number is not None:
        lot_str = str(lot_number)
        for order in orders:
            description = str(getattr(order, "description", "") or "")
            if lot_str and lot_str in description:
                return order.id
    if account_name:
        name_key = str(account_name).strip().lower()
        if name_key:
            for order in orders:
                description = str(getattr(order, "description", "") or "").lower()
                if name_key in description:
                    return order.id
    return orders[0].id if orders else None


def handle_order_purchased(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    msg: object,
) -> None:
    if getattr(msg, "type", None) is not MessageTypes.ORDER_PURCHASED:
        return
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
            from .user_utils import get_user_id_by_username

            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            return

    if user_id is None:
        logger.warning("Order %s skipped: user id missing.", order_id)
        return

    try:
        amount = int(getattr(order, "amount", None) or 1)
    except Exception:
        amount = 1
    if amount <= 0:
        amount = 1
    price_value = None
    raw_price = getattr(order, "sum", None)
    if raw_price is None:
        raw_price = getattr(order, "price", None)
    try:
        if raw_price is not None:
            price_value = float(raw_price)
    except Exception:
        price_value = None

    lot_mapping = fetch_lot_mapping(mysql_cfg, int(user_id), int(lot_number), workspace_id)
    steam_id = steam_id_from_mafile(lot_mapping.get("mafile_json")) if lot_mapping else None

    if is_blacklisted(mysql_cfg, buyer, int(user_id), workspace_id):
        comp_threshold_minutes = env_int("BLACKLIST_COMP_MINUTES", 0)
        comp_hours = env_int("BLACKLIST_COMP_HOURS", 5)
        comp_threshold_minutes = max(comp_threshold_minutes, comp_hours * 60, 5 * 60)
        unit_minutes_default = env_int("BLACKLIST_COMP_UNIT_MINUTES", 60)
        unit_minutes = get_unit_minutes(lot_mapping) if lot_mapping else unit_minutes_default
        paid_minutes = max(0, int(unit_minutes) * int(amount))
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=lot_mapping.get("id") if lot_mapping else None,
            account_name=lot_mapping.get("account_name") if lot_mapping else None,
            steam_id=steam_id,
            rental_minutes=paid_minutes,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="blacklist_comp",
        )
        log_blacklist_event(
            mysql_cfg,
            owner=buyer,
            action="blacklist_comp",
            details=f"order={order_id}; lot={lot_number}; amount={amount}",
            amount=paid_minutes,
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
        total_paid = get_blacklist_compensation_total(mysql_cfg, buyer, int(user_id), workspace_id)
        if total_paid >= comp_threshold_minutes:
            removed = remove_blacklist_entry(mysql_cfg, buyer, int(user_id), workspace_id)
            log_blacklist_event(
                mysql_cfg,
                owner=buyer,
                action="auto_unblacklist",
                details=f"total_minutes={total_paid}/{comp_threshold_minutes}; order={order_id}; lot={lot_number}",
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
            if removed:
                send_chat_message(
                    logger,
                    account,
                    chat_id,
                    f"Оплата штрафа получена ({format_duration_minutes(total_paid)}). Доступ разблокирован.",
                )
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return

        remaining = max(comp_threshold_minutes - total_paid, 0)
        lot_url = lot_mapping.get("lot_url") if lot_mapping else None
        lot_label = f"лот №{lot_number}"
        if lot_url:
            lot_label = f"лот {lot_url}"
        send_chat_message(
            logger,
            account,
            chat_id,
            "Вы в черном списке.\n"
            f"Оплатите штраф {format_penalty_label(comp_threshold_minutes)}, чтобы разблокировать доступ.\n"
            f"Оплачено: {format_duration_minutes(total_paid)}. "
            f"Осталось: {format_duration_minutes(remaining)}.\n"
            f"Если хотите продлить — пожалуйста оплатите этот {lot_label}.",
        )
        log_blacklist_event(
            mysql_cfg,
            owner=buyer,
            action="blocked_order",
            details=f"order={order_id}; lot={lot_number}; amount={amount}; paid={total_paid}; remaining={remaining}",
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    mapping = lot_mapping
    if mapping:
        try:
            owner_accounts = fetch_owner_accounts(mysql_cfg, int(user_id), buyer, workspace_id)
        except mysql.connector.Error:
            owner_accounts = []
        for account_row in owner_accounts:
            account_lot = account_row.get("lot_number")
            if account_lot is None:
                continue
            try:
                account_lot_number = int(account_lot)
            except Exception:
                continue
            if account_lot_number == int(lot_number):
                mapping = account_row
                break
        if mapping == lot_mapping and owner_accounts:
            history_account_id = fetch_latest_account_for_owner_lot(
                mysql_cfg,
                owner=buyer,
                lot_number=int(lot_number),
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
            if history_account_id is not None:
                for account_row in owner_accounts:
                    try:
                        if int(account_row.get("id")) == int(history_account_id):
                            mapping = account_row
                            break
                    except Exception:
                        continue
    if not mapping:
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="unmapped",
        )
        send_chat_message(logger, account, chat_id, ORDER_LOT_UNMAPPED)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    if mapping.get("account_frozen") or mapping.get("rental_frozen") or mapping.get("low_priority"):
        replacement = find_replacement_account_for_lot(
            mysql_cfg,
            int(user_id),
            int(lot_number),
            workspace_id,
            target_mmr=mapping.get("mmr"),
            exclude_account_id=mapping.get("id"),
            max_delta=1000,
            match_lot_number=False,
        )
        if replacement:
            unit_minutes = get_unit_minutes(replacement)
            total_minutes = unit_minutes * amount
            assign_account_to_buyer(
                mysql_cfg,
                account_id=int(replacement["id"]),
                user_id=user_id,
                buyer=buyer,
                units=amount,
                total_minutes=total_minutes,
                workspace_id=workspace_id,
            )
            log_order_history(
                mysql_cfg,
                order_id=order_id,
                owner=buyer,
                user_id=int(user_id),
                workspace_id=workspace_id,
                account_id=replacement.get("id"),
                account_name=replacement.get("account_name"),
                steam_id=steam_id,
                rental_minutes=total_minutes,
                lot_number=lot_number,
                amount=amount,
                price=price_value,
                action="replace_assign",
            )
            replacement_info = dict(replacement)
            replacement_info["owner"] = buyer
            replacement_info["rental_duration"] = amount
            replacement_info["rental_duration_minutes"] = total_minutes
            replacement_info["account_frozen"] = 0
            replacement_info["rental_frozen"] = 0
            message = f"{ORDER_ACCOUNT_REPLACEMENT_PREFIX}\n{build_account_message(replacement_info, total_minutes, True)}"
            send_chat_message(logger, account, chat_id, message)
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return

        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="busy",
        )
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_NO_REPLACEMENT)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    owner = mapping.get("owner")
    owner_key = normalize_username(owner)
    buyer_key = normalize_username(buyer)
    if owner_key and owner_key != buyer_key:
        replacement = find_replacement_account_for_lot(
            mysql_cfg,
            int(user_id),
            int(lot_number),
            workspace_id,
            target_mmr=mapping.get("mmr"),
            exclude_account_id=mapping.get("id"),
            max_delta=1000,
            match_lot_number=False,
        )
        if replacement:
            unit_minutes = get_unit_minutes(replacement)
            total_minutes = unit_minutes * amount
            assign_account_to_buyer(
                mysql_cfg,
                account_id=int(replacement["id"]),
                user_id=user_id,
                buyer=buyer,
                units=amount,
                total_minutes=total_minutes,
                workspace_id=workspace_id,
            )
            log_order_history(
                mysql_cfg,
                order_id=order_id,
                owner=buyer,
                user_id=int(user_id),
                workspace_id=workspace_id,
                account_id=replacement.get("id"),
                account_name=replacement.get("account_name"),
                steam_id=steam_id,
                rental_minutes=total_minutes,
                lot_number=lot_number,
                amount=amount,
                price=price_value,
                action="replace_assign",
            )
            replacement_info = dict(replacement)
            replacement_info["owner"] = buyer
            replacement_info["rental_duration"] = amount
            replacement_info["rental_duration_minutes"] = total_minutes
            replacement_info["account_frozen"] = 0
            replacement_info["rental_frozen"] = 0
            message = f"{ORDER_ACCOUNT_REPLACEMENT_PREFIX}\n{build_account_message(replacement_info, total_minutes, True)}"
            send_chat_message(logger, account, chat_id, message)
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return

        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="busy",
        )
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_NO_REPLACEMENT)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    unit_minutes = get_unit_minutes(mapping)
    total_minutes = unit_minutes * amount

    updated_account = mapping
    if not owner_key:
        assign_account_to_buyer(
            mysql_cfg,
            account_id=int(mapping["id"]),
            user_id=user_id,
            buyer=buyer,
            units=amount,
            total_minutes=total_minutes,
            workspace_id=workspace_id,
        )
        updated_account = dict(mapping)
        updated_account["owner"] = buyer
        updated_account["rental_duration"] = amount
        updated_account["rental_duration_minutes"] = total_minutes
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            rental_minutes=total_minutes,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="assign",
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
            log_order_history(
                mysql_cfg,
                order_id=order_id,
                owner=buyer,
                user_id=int(user_id),
                workspace_id=workspace_id,
                account_id=mapping.get("id"),
                account_name=mapping.get("account_name"),
                steam_id=steam_id,
                lot_number=lot_number,
                amount=amount,
                price=price_value,
                action="busy",
            )
            send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_NO_REPLACEMENT)
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            rental_minutes=total_minutes,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="extend",
        )

    display_minutes = resolve_rental_minutes(updated_account or mapping) or total_minutes
    if owner_key:
        account_id = (updated_account or mapping).get("id")
        duration_label = format_duration_minutes(display_minutes)
        id_suffix = f" {account_id}" if account_id is not None else ""
        message = (
            "✅ Оплата получена. Аренда продлена.\n"
            f"Текущая аренда: {duration_label}.\n"
            f"Для данных: !акк{id_suffix}."
        )
    else:
        message = build_account_message(updated_account or mapping, display_minutes, include_timer_note=True)
    send_chat_message(logger, account, chat_id, message)
    mark_order_processed(site_username, site_user_id, workspace_id, order_id)
