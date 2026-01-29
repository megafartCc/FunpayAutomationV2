from __future__ import annotations

from datetime import datetime

import mysql.connector

from .db_utils import column_exists, resolve_workspace_mysql_cfg, table_exists
from .text_utils import normalize_owner_name


def fetch_lot_mapping(
    mysql_cfg: dict,
    user_id: int,
    lot_number: int,
    workspace_id: int | None = None,
) -> dict | None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "lots"):
            return None
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_mmr = column_exists(cursor, "accounts", "mmr")
        has_display_name = column_exists(cursor, "lots", "display_name")
        params: list = [int(user_id), int(lot_number)]
        where_workspace = ""
        order_clause = " ORDER BY a.id"
        has_workspace = column_exists(cursor, "lots", "workspace_id")
        if has_workspace and workspace_id is not None:
            where_workspace = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
            params.append(int(workspace_id))
            order_clause = " ORDER BY CASE WHEN l.workspace_id = %s THEN 0 ELSE 1 END, a.id"
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                   a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen
                   {', a.`low_priority` AS `low_priority`' if has_low_priority else ', 0 AS `low_priority`'}
                   {', a.mmr' if has_mmr else ', NULL AS mmr'},
                   l.lot_number, l.lot_url
                   {', l.display_name' if has_display_name else ', NULL AS display_name'}
            FROM lots l
            JOIN accounts a ON a.id = l.account_id
            WHERE l.user_id = %s AND l.lot_number = %s
                  {where_workspace}
            {order_clause}
            LIMIT 1
            """,
            tuple(params + ([int(workspace_id)] if has_workspace and workspace_id is not None else [])),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def fetch_available_lot_accounts(
    mysql_cfg: dict,
    user_id: int | None,
    workspace_id: int | None = None,
) -> list[dict]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
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
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_mmr = column_exists(cursor, "accounts", "mmr")
        has_display_name = has_lots and column_exists(cursor, "lots", "display_name")

        account_filters: list[str] = ["a.owner IS NULL"]
        if has_account_frozen:
            account_filters.append("a.account_frozen = 0")
        if has_rental_frozen:
            account_filters.append("a.rental_frozen = 0")
        if has_low_priority:
            account_filters.append("(a.low_priority = 0 OR a.low_priority IS NULL)")
        params: list = []
        if has_account_user_id and user_id is not None:
            account_filters.append("a.user_id = %s")
            params.append(int(user_id))
        if has_account_workspace and workspace_id is not None and (not has_lots or not has_lot_workspace):
            account_filters.append("a.workspace_id = %s")
            params.append(int(workspace_id))

        if has_lots:
            lot_filters: list[str] = []
            if user_id is not None and not has_account_user_id and has_lot_user_id:
                lot_filters.append("l.user_id = %s")
                params.append(int(user_id))
            if has_lot_workspace and workspace_id is not None:
                lot_filters.append("(l.workspace_id = %s OR l.workspace_id IS NULL)")
                params.append(int(workspace_id))
            lot_where = " AND " + " AND ".join(lot_filters) if lot_filters else ""
            cursor.execute(
                f"""
                SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                       a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       {'a.account_frozen' if has_account_frozen else '0 AS account_frozen'},
                       {'a.rental_frozen' if has_rental_frozen else '0 AS rental_frozen'},
                       {'a.`low_priority` AS `low_priority`' if has_low_priority else '0 AS low_priority'},
                       {'a.mmr' if has_mmr else 'NULL AS mmr'},
                       l.lot_number, l.lot_url
                       {', l.display_name' if has_display_name else ', NULL AS display_name'}
                FROM accounts a
                JOIN lots l ON l.account_id = a.id
                WHERE {" AND ".join(account_filters)}{lot_where}
                ORDER BY l.lot_number ASC, a.id ASC
                """,
                tuple(params),
            )
        else:
            cursor.execute(
                f"""
                SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                       a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       {'a.account_frozen' if has_account_frozen else '0 AS account_frozen'},
                       {'a.rental_frozen' if has_rental_frozen else '0 AS rental_frozen'},
                       {'a.`low_priority` AS `low_priority`' if has_low_priority else '0 AS low_priority'},
                       {'a.mmr' if has_mmr else 'NULL AS mmr'},
                       {'a.lot_number' if has_account_lot_number else 'NULL AS lot_number'},
                       {'a.lot_url' if has_account_lot_url else 'NULL AS lot_url'},
                       NULL AS display_name
                FROM accounts a
                WHERE {" AND ".join(account_filters)}
                ORDER BY a.id ASC
                """,
                tuple(params),
            )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def fetch_owner_accounts(
    mysql_cfg: dict,
    user_id: int,
    owner: str,
    workspace_id: int | None = None,
) -> list[dict]:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return []
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "accounts"):
            return []
        has_lots = table_exists(cursor, "lots")
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_mmr = column_exists(cursor, "accounts", "mmr")
        has_display_name = has_lots and column_exists(cursor, "lots", "display_name")
        has_account_workspace = column_exists(cursor, "accounts", "workspace_id")
        has_lot_workspace = has_lots and column_exists(cursor, "lots", "workspace_id")
        params: list = [owner_key, int(user_id)]
        workspace_clause = ""
        lot_workspace_clause = ""
        if workspace_id is not None and has_account_workspace:
            workspace_clause = " AND a.workspace_id = %s"
            params.append(int(workspace_id))
        if workspace_id is not None and has_lot_workspace:
            lot_workspace_clause = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
            params.append(int(workspace_id))
        if has_lots:
            cursor.execute(
                f"""
                SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                       a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       {'a.account_frozen' if column_exists(cursor, 'accounts', 'account_frozen') else '0 AS account_frozen'},
                       {'a.rental_frozen' if column_exists(cursor, 'accounts', 'rental_frozen') else '0 AS rental_frozen'},
                       {'a.`low_priority` AS `low_priority`' if has_low_priority else '0 AS low_priority'},
                       {'a.mmr' if has_mmr else 'NULL AS mmr'},
                       l.lot_number, l.lot_url
                       {', l.display_name' if has_display_name else ', NULL AS display_name'}
                FROM accounts a
                LEFT JOIN lots l ON l.account_id = a.id
                WHERE LOWER(a.owner) = %s AND a.user_id = %s{workspace_clause}{lot_workspace_clause}
                ORDER BY a.rental_start DESC, a.id DESC
                """,
                tuple(params),
            )
        else:
            cursor.execute(
                f"""
                SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                       a.rental_start, a.rental_duration, a.rental_duration_minutes,
                       {'a.account_frozen' if column_exists(cursor, 'accounts', 'account_frozen') else '0 AS account_frozen'},
                       {'a.rental_frozen' if column_exists(cursor, 'accounts', 'rental_frozen') else '0 AS rental_frozen'},
                       {'a.`low_priority` AS `low_priority`' if has_low_priority else '0 AS low_priority'},
                       {'a.mmr' if has_mmr else 'NULL AS mmr'},
                       NULL AS lot_number,
                       NULL AS lot_url,
                       NULL AS display_name
                FROM accounts a
                WHERE LOWER(a.owner) = %s AND a.user_id = %s{workspace_clause}
                ORDER BY a.rental_start DESC, a.id DESC
                """,
                tuple(params),
            )
        return list(cursor.fetchall() or [])
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
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        owner_key = normalize_owner_name(buyer)
        cursor.execute(
            """
            UPDATE accounts
            SET owner = %s,
                rental_duration = %s,
                rental_duration_minutes = %s,
                rental_start = NOW()
            WHERE id = %s AND user_id = %s AND (owner IS NULL OR owner = '')
            """,
            (owner_key, int(units), int(total_minutes), int(account_id), int(user_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
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
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, owner, rental_start, rental_duration, rental_duration_minutes,
                   account_name, login, password, mafile_json, account_frozen, rental_frozen
            FROM accounts
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (int(account_id), int(user_id)),
        )
        row = cursor.fetchone()
        if not row:
            return None
        owner_key = normalize_owner_name(buyer)
        if normalize_owner_name(row.get("owner")) != owner_key:
            return None
        base_duration = int(row.get("rental_duration") or 0)
        base_minutes = row.get("rental_duration_minutes")
        if base_minutes is None:
            base_minutes = base_duration * 60
        total_minutes = int(base_minutes or 0) + int(add_minutes)
        total_units = base_duration + int(add_units)
        cursor.execute(
            """
            UPDATE accounts
            SET rental_duration = %s,
                rental_duration_minutes = %s
            WHERE id = %s AND user_id = %s
            """,
            (int(total_units), int(total_minutes), int(account_id), int(user_id)),
        )
        conn.commit()
        row["rental_duration"] = total_units
        row["rental_duration_minutes"] = total_minutes
        return row
    finally:
        conn.close()


def find_replacement_account_for_lot(
    mysql_cfg: dict,
    user_id: int,
    lot_number: int,
    workspace_id: int | None = None,
) -> dict | None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "lots") or not table_exists(cursor, "accounts"):
            return None
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_account_frozen = column_exists(cursor, "accounts", "account_frozen")
        has_rental_frozen = column_exists(cursor, "accounts", "rental_frozen")
        params: list = [int(user_id), int(lot_number)]
        workspace_clause = ""
        if workspace_id is not None and column_exists(cursor, "lots", "workspace_id"):
            workspace_clause = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                   a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   {'a.account_frozen' if has_account_frozen else '0 AS account_frozen'},
                   {'a.rental_frozen' if has_rental_frozen else '0 AS rental_frozen'},
                   {'a.`low_priority` AS `low_priority`' if has_low_priority else '0 AS low_priority'},
                   l.lot_number, l.lot_url
            FROM lots l
            JOIN accounts a ON a.id = l.account_id
            WHERE l.user_id = %s AND l.lot_number = %s{workspace_clause}
              AND (a.owner IS NULL OR a.owner = '')
              AND (a.account_frozen = 0 OR a.account_frozen IS NULL)
              AND (a.rental_frozen = 0 OR a.rental_frozen IS NULL)
              {('AND (a.low_priority = 0 OR a.low_priority IS NULL)' if has_low_priority else '')}
            ORDER BY a.id ASC
            LIMIT 1
            """,
            tuple(params),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def replace_rental_account(
    mysql_cfg: dict,
    *,
    old_account_id: int,
    new_account_id: int,
    user_id: int,
    owner: str,
    workspace_id: int | None,
    rental_start: datetime,
    rental_duration: int,
    rental_duration_minutes: int,
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        owner_key = normalize_owner_name(owner)
        if not owner_key:
            return False
        rental_start_str = rental_start.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            UPDATE accounts
            SET owner = %s,
                rental_start = %s,
                rental_duration = %s,
                rental_duration_minutes = %s
            WHERE id = %s AND user_id = %s
            """,
            (owner_key, rental_start_str, int(rental_duration), int(rental_duration_minutes), int(new_account_id), int(user_id)),
        )
        if cursor.rowcount <= 0:
            conn.rollback()
            return False
        cursor.execute(
            """
            UPDATE accounts
            SET owner = NULL,
                rental_start = NULL,
                rental_frozen = 0
            WHERE id = %s AND user_id = %s
            """,
            (int(old_account_id), int(user_id)),
        )
        conn.commit()
        return True
    finally:
        conn.close()
