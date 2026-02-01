from __future__ import annotations

import inspect
import os
import time
from datetime import datetime
from dataclasses import dataclass, field

import mysql.connector

from FunPayAPI.common import exceptions as fp_exceptions
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


def collect_raise_categories_from_profile(profile) -> list[tuple[int, str]]:
    categories: dict[int, str] = {}
    for subcat in sorted(list(profile.get_sorted_lots(2).keys()), key=lambda x: x.category.position):
        if subcat.type is SubCategoryTypes.CURRENCY:
            continue
        categories[int(subcat.category.id)] = subcat.category.name
    return sorted(categories.items(), key=lambda item: item[0])


def collect_raise_categories(account) -> list[tuple[int, str]]:
    profile = account.get_user(account.id)
    return collect_raise_categories_from_profile(profile)


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


def sync_raise_categories_from_profile(
    mysql_cfg: dict,
    *,
    profile,
    user_id: int,
    workspace_id: int | None,
) -> None:
    categories = collect_raise_categories_from_profile(profile)
    upsert_raise_categories(
        mysql_cfg,
        user_id=int(user_id),
        workspace_id=int(workspace_id) if workspace_id is not None else None,
        categories=categories,
    )


def _seconds_to_str(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds - days * 86400) // 3600
    minutes = (seconds - days * 86400 - hours * 3600) // 60
    sec = seconds - days * 86400 - hours * 3600 - minutes * 60
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}мин")
    if sec and not parts:
        parts.append(f"{sec}сек")
    return " ".join(parts) if parts else "0 сек"


def _default_auto_raise_settings() -> dict:
    return {
        "enabled": False,
        "all_workspaces": True,
        "interval_minutes": 120,
        "workspaces": {},
    }


def _coerce_ts(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if hasattr(value, "timestamp"):
        return float(value.timestamp())
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:
        return None


def load_auto_raise_settings(mysql_cfg: dict, user_id: int) -> dict:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "auto_raise_settings"):
            return _default_auto_raise_settings()
        cursor.execute(
            """
            SELECT *
            FROM auto_raise_settings
            WHERE user_id = %s
            """,
            (int(user_id),),
        )
        rows = cursor.fetchall() or []
        if not rows:
            return _default_auto_raise_settings()
        if "workspace_id" not in rows[0]:
            row = rows[-1]
            return {
                "enabled": bool(row.get("enabled")),
                "all_workspaces": bool(row.get("all_workspaces", True)),
                "interval_minutes": int(row.get("interval_minutes") or 120),
                "workspaces": {},
            }
        settings = _default_auto_raise_settings()
        workspaces: dict[int, bool] = {}
        for row in rows:
            workspace_id = row.get("workspace_id")
            if workspace_id is None:
                settings["enabled"] = bool(row.get("enabled"))
                settings["all_workspaces"] = bool(row.get("all_workspaces"))
                settings["interval_minutes"] = int(row.get("interval_minutes") or settings["interval_minutes"])
            else:
                workspaces[int(workspace_id)] = bool(row.get("enabled"))
        settings["workspaces"] = workspaces
        return settings
    finally:
        conn.close()


def load_enabled_workspace_ids(mysql_cfg: dict, user_id: int, settings: dict) -> list[int]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "workspaces"):
            return []
        cursor.execute("SELECT id FROM workspaces WHERE user_id = %s ORDER BY id", (int(user_id),))
        rows = cursor.fetchall() or []
        ids = [int(row.get("id")) for row in rows if row.get("id") is not None]
        if not settings.get("all_workspaces", True):
            enabled_map = settings.get("workspaces") or {}
            ids = [ws_id for ws_id in ids if enabled_map.get(ws_id, True)]
        return ids
    finally:
        conn.close()


def ensure_auto_raise_state(mysql_cfg: dict, user_id: int) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "auto_raise_state"):
            return
        cursor.execute("INSERT IGNORE INTO auto_raise_state (user_id) VALUES (%s)", (int(user_id),))
        conn.commit()
    finally:
        conn.close()


def ensure_auto_raise_global_state(mysql_cfg: dict, user_id: int) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "auto_raise_global_state"):
            return
        cursor.execute(
            "INSERT IGNORE INTO auto_raise_global_state (user_id) VALUES (%s)",
            (int(user_id),),
        )
        conn.commit()
    finally:
        conn.close()


def claim_auto_raise_slot(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int,
    interval_seconds: int,
    allow_same: bool,
) -> bool:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "auto_raise_state"):
            return True
        cursor.execute(
            """
            UPDATE auto_raise_state
            SET next_run_at = DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND),
                last_workspace_id = %s
            WHERE user_id = %s
              AND (next_run_at IS NULL OR next_run_at <= UTC_TIMESTAMP())
              AND (%s = 1 OR last_workspace_id IS NULL OR last_workspace_id <> %s)
            """,
            (
                int(interval_seconds),
                int(workspace_id),
                int(user_id),
                1 if allow_same else 0,
                int(workspace_id),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def claim_auto_raise_global_slot(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int,
    interval_seconds: int,
    allow_same: bool,
) -> bool:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "auto_raise_global_state"):
            return False
        cursor.execute(
            """
            UPDATE auto_raise_global_state
            SET next_run_at = DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND),
                last_workspace_id = %s
            WHERE user_id = %s
              AND (next_run_at IS NULL OR next_run_at <= UTC_TIMESTAMP())
              AND (%s = 1 OR last_workspace_id IS NULL OR last_workspace_id <> %s)
            """,
            (
                int(interval_seconds),
                int(workspace_id),
                int(user_id),
                1 if allow_same else 0,
                int(workspace_id),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_auto_raise_next_run(mysql_cfg: dict, user_id: int) -> float | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "auto_raise_state"):
            return None
        cursor.execute(
            "SELECT next_run_at FROM auto_raise_state WHERE user_id = %s",
            (int(user_id),),
        )
        row = cursor.fetchone() or {}
        return _coerce_ts(row.get("next_run_at"))
    finally:
        conn.close()


def get_auto_raise_global_next_run(mysql_cfg: dict, user_id: int) -> float | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "auto_raise_global_state"):
            return None
        cursor.execute(
            "SELECT next_run_at FROM auto_raise_global_state WHERE user_id = %s",
            (int(user_id),),
        )
        row = cursor.fetchone() or {}
        return _coerce_ts(row.get("next_run_at"))
    finally:
        conn.close()


def log_auto_raise(
    mysql_cfg: dict | None,
    *,
    user_id: int | None,
    workspace_id: int | None,
    level: str,
    message: str,
    source: str | None = None,
    line: int | None = None,
) -> None:
    if not mysql_cfg or user_id is None:
        return
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "auto_raise_logs"):
            return
        if source is None or line is None:
            frame = inspect.currentframe()
            if frame and frame.f_back:
                caller = frame.f_back
                if source is None:
                    source = os.path.basename(caller.f_code.co_filename)
                if line is None:
                    line = caller.f_lineno
        cursor.execute(
            """
            INSERT INTO auto_raise_logs (user_id, workspace_id, level, source, line, message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
                (level or "info")[:8],
                source,
                int(line) if line is not None else None,
                message,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_pending_raise_requests(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    limit: int = 3,
) -> list[dict]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "auto_raise_requests"):
            return []
        cursor.execute(
            """
            SELECT id, workspace_id, status
            FROM auto_raise_requests
            WHERE user_id = %s AND workspace_id <=> %s AND status = 'pending'
            ORDER BY created_at
            LIMIT %s
            """,
            (int(user_id), int(workspace_id) if workspace_id is not None else None, int(limit)),
        )
        return cursor.fetchall() or []
    finally:
        conn.close()


def claim_raise_request(mysql_cfg: dict, request_id: int) -> bool:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE auto_raise_requests SET status = 'running' WHERE id = %s AND status = 'pending'",
            (int(request_id),),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def finish_raise_request(mysql_cfg: dict, request_id: int, status: str) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE auto_raise_requests SET status = %s, processed_at = NOW() WHERE id = %s",
            (status, int(request_id)),
        )
        conn.commit()
    finally:
        conn.close()


@dataclass
class AutoRaiseState:
    raise_time: dict[int, int] = field(default_factory=dict)
    raised_time: dict[int, int] = field(default_factory=dict)
    profile: object | None = None
    profile_updated_at: float = 0.0
    settings: dict | None = None
    settings_updated_at: float = 0.0
    enabled_workspaces: list[int] = field(default_factory=list)
    workspaces_updated_at: float = 0.0
    global_state_available: bool | None = None
    global_state_checked_at: float = 0.0


def refresh_profile(
    *,
    account,
    state: AutoRaiseState,
    mysql_cfg: dict | None,
    user_id: int | None,
    workspace_id: int | None,
) -> object | None:
    log_auto_raise(
        mysql_cfg,
        user_id=user_id,
        workspace_id=workspace_id,
        level="info",
        message="Получаю данные о лотах и категориях...",
    )
    profile = account.get_user(account.id)
    state.profile = profile
    state.profile_updated_at = time.time()
    lots_count = len(profile.get_lots())
    categories_count = len(profile.get_sorted_lots(2))
    log_auto_raise(
        mysql_cfg,
        user_id=user_id,
        workspace_id=workspace_id,
        level="info",
        message=f"Обновил информацию о лотах ({lots_count}) и категориях ({categories_count}) профиля.",
    )
    if mysql_cfg and user_id is not None:
        sync_raise_categories_from_profile(
            mysql_cfg,
            profile=profile,
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
    return profile


def raise_lots_once(
    *,
    account,
    state: AutoRaiseState,
    mysql_cfg: dict | None,
    user_id: int | None,
    workspace_id: int | None,
    profile_sync_seconds: int,
    force_profile: bool = False,
) -> int:
    now = time.time()
    if force_profile or state.profile is None or (now - state.profile_updated_at) >= profile_sync_seconds:
        try:
            refresh_profile(
                account=account,
                state=state,
                mysql_cfg=mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
            )
        except Exception as exc:
            log_auto_raise(
                mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                level="error",
                message=f"Не удалось обновить профиль: {exc}",
            )
            return int(time.time()) + 60

    profile = state.profile
    if not profile or not profile.get_lots():
        return int(time.time()) + 60

    next_call = float("inf")
    for subcat in sorted(list(profile.get_sorted_lots(2).keys()), key=lambda x: x.category.position):
        if subcat.type is SubCategoryTypes.CURRENCY:
            continue
        saved_time = state.raise_time.get(subcat.category.id)
        if saved_time and saved_time > int(time.time()):
            next_call = saved_time if saved_time < next_call else next_call
            continue

        raise_ok = False
        error_text = ""
        time_delta = ""
        try:
            time.sleep(1)
            account.raise_lots(subcat.category.id)
            raise_ok = True
            last_time = state.raised_time.get(subcat.category.id)
            state.raised_time[subcat.category.id] = new_time = int(time.time())
            time_delta = "" if not last_time else f" Последнее поднятие: {_seconds_to_str(new_time - last_time)} назад."
            log_auto_raise(
                mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                level="info",
                message=f'Все лоты категории "{subcat.category.name}" подняты!{time_delta}',
            )
            time.sleep(1)
            account.raise_lots(subcat.category.id)
        except fp_exceptions.RaiseError as exc:
            if exc.error_message is not None:
                error_text = exc.error_message
            if exc.wait_time is not None:
                next_time = int(time.time()) + int(exc.wait_time)
                state.raise_time[subcat.category.id] = next_time
                next_call = next_time if next_time < next_call else next_call
                log_auto_raise(
                    mysql_cfg,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    level="warn",
                    message=(
                        f'Не удалось поднять лоты категории "{subcat.category.name}". FunPay говорит: '
                        f'"{error_text}". Следующая попытка через {_seconds_to_str(int(exc.wait_time))}.'
                    ),
                )
            else:
                log_auto_raise(
                    mysql_cfg,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    level="error",
                    message=f'Произошла непредвиденная ошибка при попытке поднять лоты категории "{subcat.category.name}".',
                )
                time.sleep(10)
                next_time = int(time.time()) + 1
                next_call = next_time if next_time < next_call else next_call
            if not raise_ok:
                continue
        except Exception as exc:
            delay = 10
            if isinstance(exc, fp_exceptions.RequestFailedError) and exc.status_code in (503, 403, 429):
                delay = 60
            time.sleep(delay)
            next_time = int(time.time()) + 1
            next_call = next_time if next_time < next_call else next_call
            log_auto_raise(
                mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                level="error",
                message=f'Ошибка при поднятии категории "{subcat.category.name}": {str(exc)[:200]}',
            )
            if not raise_ok:
                continue
    return next_call if next_call < float("inf") else int(time.time()) + 10


def process_manual_raise_requests(
    *,
    account,
    state: AutoRaiseState,
    mysql_cfg: dict | None,
    user_id: int | None,
    workspace_id: int | None,
    profile_sync_seconds: int,
) -> bool:
    if not mysql_cfg or user_id is None:
        return False
    pending = fetch_pending_raise_requests(mysql_cfg, user_id=int(user_id), workspace_id=workspace_id)
    if not pending:
        return False
    for row in pending:
        request_id = int(row.get("id") or 0)
        if not request_id:
            continue
        if not claim_raise_request(mysql_cfg, request_id):
            continue
        log_auto_raise(
            mysql_cfg,
            user_id=user_id,
            workspace_id=workspace_id,
            level="info",
            message="Запрошено ручное автоподнятие.",
        )
        try:
            raise_lots_once(
                account=account,
                state=state,
                mysql_cfg=mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                profile_sync_seconds=profile_sync_seconds,
                force_profile=True,
            )
            finish_raise_request(mysql_cfg, request_id, "done")
        except Exception as exc:
            log_auto_raise(
                mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                level="error",
                message=f"Ручное автоподнятие завершилось с ошибкой: {str(exc)[:200]}",
            )
            finish_raise_request(mysql_cfg, request_id, "failed")
    return True


def auto_raise_loop(
    *,
    account,
    mysql_cfg: dict | None,
    user_id: int | None,
    workspace_id: int | None,
    enabled_fn,
    stop_event,
    profile_sync_seconds: int,
) -> None:
    state = AutoRaiseState()
    settings_sync_seconds = 30
    workspaces_sync_seconds = 60
    manual_check_interval = 30
    log_auto_raise(
        mysql_cfg,
        user_id=user_id,
        workspace_id=workspace_id,
        level="info",
        message="Цикл автоподнятия лотов запущен (это не значит, что автоподнятие лотов включено).",
    )
    while not stop_event.is_set():
        process_manual_raise_requests(
            account=account,
            state=state,
            mysql_cfg=mysql_cfg,
            user_id=user_id,
            workspace_id=workspace_id,
            profile_sync_seconds=profile_sync_seconds,
        )
        if not enabled_fn():
            stop_event.wait(10)
            continue

        settings = state.settings
        now = time.time()
        if mysql_cfg and user_id is not None:
            if settings is None or (now - state.settings_updated_at) >= settings_sync_seconds:
                try:
                    settings = load_auto_raise_settings(mysql_cfg, int(user_id))
                except Exception:
                    settings = _default_auto_raise_settings()
                state.settings = settings
                state.settings_updated_at = now
        if not settings:
            settings = _default_auto_raise_settings()

        if not settings.get("enabled", False):
            stop_event.wait(10)
            continue
        if workspace_id is not None and not settings.get("all_workspaces", True):
            if not settings.get("workspaces", {}).get(int(workspace_id), True):
                stop_event.wait(10)
                continue

        if not mysql_cfg or user_id is None or workspace_id is None:
            next_time = raise_lots_once(
                account=account,
                state=state,
                mysql_cfg=mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                profile_sync_seconds=profile_sync_seconds,
            )
            delay = next_time - int(time.time())
            if delay > 0:
                stop_event.wait(min(delay, manual_check_interval))
            continue

        if (now - state.workspaces_updated_at) >= workspaces_sync_seconds or not state.enabled_workspaces:
            try:
                state.enabled_workspaces = load_enabled_workspace_ids(mysql_cfg, int(user_id), settings)
            except Exception:
                state.enabled_workspaces = []
            state.workspaces_updated_at = now

        if state.enabled_workspaces and int(workspace_id) not in state.enabled_workspaces:
            stop_event.wait(10)
            continue

        ensure_auto_raise_state(mysql_cfg, int(user_id))
        ensure_auto_raise_global_state(mysql_cfg, int(user_id))
        interval_seconds = int(settings.get("interval_minutes", 120)) * 60
        allow_same = len(state.enabled_workspaces) <= 1
        has_global_state = state.global_state_available
        if has_global_state is None or (now - state.global_state_checked_at) >= 60:
            has_global_state = False
            try:
                conn = mysql.connector.connect(**mysql_cfg)
                try:
                    cursor = conn.cursor()
                    has_global_state = table_exists(cursor, "auto_raise_global_state")
                finally:
                    conn.close()
            except Exception:
                has_global_state = False
            state.global_state_available = has_global_state
            state.global_state_checked_at = now

        if has_global_state:
            claimed = claim_auto_raise_global_slot(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=int(workspace_id),
                interval_seconds=interval_seconds,
                allow_same=allow_same,
            )
        else:
            claimed = claim_auto_raise_slot(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=int(workspace_id),
                interval_seconds=interval_seconds,
                allow_same=allow_same,
            )
        if not claimed:
            next_run = get_auto_raise_global_next_run(mysql_cfg, int(user_id)) if has_global_state else None
            if next_run is None:
                next_run = get_auto_raise_next_run(mysql_cfg, int(user_id))
            if next_run:
                delay = max(1, int(next_run - time.time()))
                stop_event.wait(min(delay, manual_check_interval))
            else:
                stop_event.wait(manual_check_interval)
            continue

        raise_lots_once(
            account=account,
            state=state,
            mysql_cfg=mysql_cfg,
            user_id=user_id,
            workspace_id=workspace_id,
            profile_sync_seconds=profile_sync_seconds,
        )
        stop_event.wait(min(10, manual_check_interval))
