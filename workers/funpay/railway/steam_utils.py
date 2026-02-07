from __future__ import annotations

import logging
import os

import requests


from .env_utils import env_int


def deauthorize_account_sessions(
    logger: logging.Logger,
    account_row: dict,
) -> bool:
    base = os.getenv("STEAM_WORKER_URL", "").strip()
    if not base:
        return False
    login = account_row.get("login") or account_row.get("account_name")
    password = account_row.get("password") or ""
    mafile_json = account_row.get("mafile_json")
    if not login or not password or not mafile_json:
        return False
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
        return False
    if resp.ok:
        return True
    logger.warning("Steam worker error (status %s).", resp.status_code)
    try:
        data = resp.json()
    except ValueError:
        data = None
    if data:
        logger.warning("Steam worker error payload: %s", data)
    return False
