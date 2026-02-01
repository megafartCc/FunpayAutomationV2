from __future__ import annotations

import mysql.connector

from FunPayAPI.common.enums import SubCategoryTypes

from .db_utils import resolve_workspace_mysql_cfg, table_exists


def upsert_raise_categories(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    categories: list[tuple[int, str]],
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "raise_categories"):
            return
        cursor.execute(
            "DELETE FROM raise_categories WHERE user_id = %s AND workspace_id <=> %s",
            (int(user_id), int(workspace_id) if workspace_id is not None else None),
        )
        if not categories:
            conn.commit()
            return
        rows = [
            (int(user_id), int(workspace_id) if workspace_id is not None else None, int(cat_id), cat_name.strip())
            for cat_id, cat_name in categories
            if cat_name and str(cat_name).strip()
        ]
        if not rows:
            conn.commit()
            return
        cursor.executemany(
            """
            INSERT INTO raise_categories (user_id, workspace_id, category_id, category_name)
            VALUES (%s, %s, %s, %s)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def collect_raise_categories(account) -> list[tuple[int, str]]:
    profile = account.get_user(account.id)
    categories: dict[int, str] = {}
    for subcat in sorted(list(profile.get_sorted_lots(2).keys()), key=lambda x: x.category.position):
        if subcat.type is SubCategoryTypes.CURRENCY:
            continue
        categories[int(subcat.category.id)] = subcat.category.name
    return sorted(categories.items(), key=lambda item: item[0])


def sync_raise_categories(
    mysql_cfg: dict,
    *,
    account,
    user_id: int,
    workspace_id: int | None,
) -> None:
    categories = collect_raise_categories(account)
    upsert_raise_categories(
        mysql_cfg,
        user_id=int(user_id),
        workspace_id=int(workspace_id) if workspace_id is not None else None,
        categories=categories,
    )
