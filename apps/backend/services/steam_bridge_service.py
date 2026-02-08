from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class SteamBridgeError(Exception):
    message: str
    status_code: int = 502


def _bridge_url() -> str:
    base = os.getenv("STEAM_BRIDGE_URL", "").strip()
    if not base:
        raise SteamBridgeError("Steam bridge URL is not configured.", status_code=503)
    return base.rstrip("/")


def _bridge_token() -> str:
    token = os.getenv("STEAM_BRIDGE_INTERNAL_TOKEN", "").strip()
    if not token:
        raise SteamBridgeError("Steam bridge internal token is not configured.", status_code=503)
    return token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_bridge_token()}"}


def connect_bridge_account(
    *,
    bridge_id: int,
    user_id: int,
    login: str,
    password: str,
    shared_secret: str | None,
    is_default: bool,
) -> dict[str, Any]:
    url = f"{_bridge_url()}/internal/bridge/{bridge_id}/connect"
    payload = {
        "user_id": user_id,
        "login": login,
        "password": password,
        "shared_secret": shared_secret,
        "is_default": bool(is_default),
    }
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=20)
    except requests.RequestException as exc:
        raise SteamBridgeError(f"Steam bridge request failed: {exc}", status_code=503) from exc
    if resp.ok:
        return resp.json() if resp.content else {"ok": True}
    raise SteamBridgeError(
        f"Steam bridge error (status {resp.status_code}).",
        status_code=resp.status_code,
    )


def disconnect_bridge_account(*, bridge_id: int, user_id: int) -> dict[str, Any]:
    url = f"{_bridge_url()}/internal/bridge/{bridge_id}/disconnect"
    payload = {"user_id": user_id}
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise SteamBridgeError(f"Steam bridge request failed: {exc}", status_code=503) from exc
    if resp.ok:
        return resp.json() if resp.content else {"ok": True}
    raise SteamBridgeError(
        f"Steam bridge error (status {resp.status_code}).",
        status_code=resp.status_code,
    )


def fetch_bridge_status(*, bridge_id: int, user_id: int) -> dict[str, Any]:
    url = f"{_bridge_url()}/internal/bridge/{bridge_id}/status"
    try:
        resp = requests.get(url, params={"user_id": user_id}, headers=_headers(), timeout=10)
    except requests.RequestException as exc:
        raise SteamBridgeError(f"Steam bridge request failed: {exc}", status_code=503) from exc
    if resp.ok:
        return resp.json() if resp.content else {"ok": True}
    raise SteamBridgeError(
        f"Steam bridge error (status {resp.status_code}).",
        status_code=resp.status_code,
    )


def fetch_user_status(*, user_id: int) -> dict[str, Any]:
    url = f"{_bridge_url()}/internal/bridge/user/{user_id}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
    except requests.RequestException as exc:
        raise SteamBridgeError(f"Steam bridge request failed: {exc}", status_code=503) from exc
    if resp.ok:
        return resp.json() if resp.content else {"ok": True}
    raise SteamBridgeError(
        f"Steam bridge error (status {resp.status_code}).",
        status_code=resp.status_code,
    )
