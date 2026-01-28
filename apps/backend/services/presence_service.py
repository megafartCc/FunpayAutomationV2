from __future__ import annotations

import json
import os
from typing import Any, Optional

import redis
import requests

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        _redis_client = None
        return None
    _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def _presence_base_url() -> str:
    base = os.getenv("STEAM_PRESENCE_URL", "").strip()
    if not base:
        base = os.getenv("STEAM_BRIDGE_URL", "").strip()
    return base.rstrip("/")


def _cache_key(steam_id: str) -> str:
    return f"presence:{steam_id}"


def _cache_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_TTL_SECONDS", "15"))


def _cache_empty_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_EMPTY_TTL_SECONDS", "5"))


def fetch_presence(steam_id: str | None, timeout: int = 5) -> dict[str, Any] | None:
    if not steam_id:
        return None
    cache = _get_redis()
    if cache:
        try:
            cached_raw = cache.get(_cache_key(steam_id))
        except Exception:
            cached_raw = None
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
            except Exception:
                cached = None
            return cached if isinstance(cached, dict) else None
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
        if cache:
            try:
                cache.set(_cache_key(steam_id), "null", ex=_cache_empty_ttl_seconds())
            except Exception:
                pass
        return None
    try:
        data = resp.json()
    except Exception:
        if cache:
            try:
                cache.set(_cache_key(steam_id), "null", ex=_cache_empty_ttl_seconds())
            except Exception:
                pass
        return None
    if not isinstance(data, dict):
        if cache:
            try:
                cache.set(_cache_key(steam_id), "null", ex=_cache_empty_ttl_seconds())
            except Exception:
                pass
        return None
    if cache:
        try:
            cache.set(_cache_key(steam_id), json.dumps(data, ensure_ascii=False), ex=_cache_ttl_seconds())
        except Exception:
            pass
    return data


def presence_status_label(presence: dict[str, Any] | None) -> str:
    if not presence:
        return ""
    derived = presence.get("derived") if isinstance(presence.get("derived"), dict) else {}
    in_demo = bool(derived.get("in_demo") or presence.get("in_demo"))
    in_bot = bool(derived.get("in_bot_match") or presence.get("in_bot_match"))
    in_custom = bool(derived.get("in_custom_game") or presence.get("in_custom_game"))
    if in_demo:
        return "Demo Hero"
    if in_bot:
        return "Bot Match"
    if in_custom:
        return "Custom Game"
    in_match = bool(derived.get("in_match") or presence.get("in_match"))
    in_game = bool(derived.get("in_game") or presence.get("in_game"))
    if in_match:
        return "In match"
    if in_game:
        return "In game"
    return "Offline"
