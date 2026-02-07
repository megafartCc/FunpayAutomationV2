from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path


def _load_local_deauthorize() -> object | None:
    steam_root = Path(__file__).resolve().parents[2] / "steam"
    if not steam_root.exists():
        logging.getLogger(__name__).warning(
            "Local Steam deauthorize unavailable: %s not found.", steam_root
        )
        return None
    steam_root_str = str(steam_root)
    if steam_root_str not in sys.path:
        sys.path.insert(0, steam_root_str)
    try:
        from SteamHandler.deauthorize import logout_all_steam_sessions  # type: ignore
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Local Steam deauthorize unavailable: SteamHandler import failed: %s",
            exc,
        )
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
    # Local-only (Megamind-style) per request: no HTTP worker fallback here.
    if _local_deauthorize(logger, login=login, password=password, mafile_json=mafile_json):
        return True
    logger.warning("Local Steam deauthorize failed; no fallback configured.")
    return False
