from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import requests


from .env_utils import env_int


def _load_local_deauthorize() -> object | None:
    steam_root = Path(__file__).resolve().parents[2] / "steam"
    if not steam_root.exists():
        return None
    steam_root_str = str(steam_root)
    if steam_root_str not in sys.path:
        sys.path.insert(0, steam_root_str)
    try:
        from SteamHandler.deauthorize import logout_all_steam_sessions  # type: ignore
    except Exception:
        return None
    return logout_all_steam_sessions


def _local_deauthorize(
    logger: logging.Logger,
    *,
    login: str,
    password: str,
    mafile_json: str | dict,
) -> bool:
    logout_all_steam_sessions = _load_local_deauthorize()
    if logout_all_steam_sessions is None:
        logger.warning("Local Steam deauthorize unavailable: SteamHandler not importable.")
        return False
    try:
        return bool(
            asyncio.run(
                logout_all_steam_sessions(
                    steam_login=login,
                    steam_password=password,
                    mafile_json=mafile_json,
                )
            )
        )
    except RuntimeError as exc:
        # In case we're already inside an event loop, avoid crashing the worker.
        logger.warning("Local Steam deauthorize failed (event loop): %s", exc)
    except Exception as exc:
        logger.warning("Local Steam deauthorize failed: %s", exc)
    return False


def deauthorize_account_sessions(
    logger: logging.Logger,
    account_row: dict,
) -> bool:
    login = account_row.get("login") or account_row.get("account_name")
    password = account_row.get("password") or ""
    mafile_json = account_row.get("mafile_json")
    if not login or not password or not mafile_json:
        account_id = account_row.get("id") or account_row.get("account_id")
        logger.warning(
            "Steam deauthorize skipped (missing credentials). account_id=%s login=%s has_password=%s has_mafile=%s",
            account_id,
            login,
            bool(password),
            bool(mafile_json),
        )
        return False
    base = os.getenv("STEAM_WORKER_URL", "").strip()
    if not base:
        logger.warning("STEAM_WORKER_URL is not set. Trying local Steam deauthorize fallback.")
        return _local_deauthorize(logger, login=login, password=password, mafile_json=mafile_json)
    url = f"{base.rstrip('/')}/api/steam/deauthorize"
    timeout = env_int("STEAM_WORKER_TIMEOUT", 90)
    payload = {
        "steam_login": login,
        "steam_password": password,
        "mafile_json": mafile_json,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Steam worker request failed: %s", exc)
        return _local_deauthorize(logger, login=login, password=password, mafile_json=mafile_json)
    if resp.ok:
        return True
    logger.warning("Steam worker error (status %s).", resp.status_code)
    try:
        data = resp.json()
    except ValueError:
        data = None
    if data:
        logger.warning("Steam worker error payload: %s", data)
    return _local_deauthorize(logger, login=login, password=password, mafile_json=mafile_json)
