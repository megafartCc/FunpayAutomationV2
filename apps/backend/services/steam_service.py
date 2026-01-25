from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass
class SteamWorkerError(Exception):
    message: str
    status_code: int = 502


def _worker_url() -> str:
    base = os.getenv("STEAM_WORKER_URL", "").strip()
    if not base:
        raise SteamWorkerError("Steam worker URL is not configured.", status_code=503)
    return base.rstrip("/")


def deauthorize_sessions(*, steam_login: str, steam_password: str, mafile_json: str) -> None:
    url = f"{_worker_url()}/api/steam/deauthorize"
    timeout = int(os.getenv("STEAM_WORKER_TIMEOUT", "90"))
    payload = {
        "steam_login": steam_login,
        "steam_password": steam_password,
        "mafile_json": mafile_json,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise SteamWorkerError(f"Steam worker request failed: {exc}", status_code=503) from exc

    if resp.ok:
        return

    detail = None
    try:
        data = resp.json()
        detail = data.get("detail") if isinstance(data, dict) else None
    except Exception:
        detail = None

    message = detail or f"Steam worker error (status {resp.status_code})."
    raise SteamWorkerError(message, status_code=resp.status_code)

