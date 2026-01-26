from __future__ import annotations

import os
from typing import Any

import requests


def _presence_base_url() -> str:
    base = os.getenv("STEAM_PRESENCE_URL", "").strip()
    if not base:
        base = os.getenv("STEAM_BRIDGE_URL", "").strip()
    return base.rstrip("/")


def fetch_presence(steam_id: str | None, timeout: int = 5) -> dict[str, Any] | None:
    if not steam_id:
        return None
    base = _presence_base_url()
    if not base:
        return None
    base = base.rstrip("/")
    if base.endswith("/presence"):
        url = f"{base}/{steam_id}"
    else:
        url = f"{base}/presence/{steam_id}"
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return None
    if not resp.ok:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    if isinstance(data, dict):
        return data
    return None


def presence_status_label(presence: dict[str, Any] | None) -> str:
    if not presence:
        return ""
    if presence.get("in_match"):
        return "In match"
    if presence.get("in_game"):
        return "In game"
    return "Offline"
