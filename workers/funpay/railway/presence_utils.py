from __future__ import annotations

import json
import os
import time

import requests

from .constants import _chat_history_prefetch_lock, _chat_history_prefetch_seen, _redis_client


def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis  # type: ignore
    except Exception:
        _redis_client = None
        return None
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        _redis_client = None
        return None
    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    except Exception:
        _redis_client = None
    return _redis_client


def clear_lot_cache_on_start() -> None:
    cache = get_redis_client()
    if not cache:
        return
    patterns = ["lot:*", "lot_mapping:*", "lot:list:*", "lot:stock:*"]
    for pattern in patterns:
        keys = list(cache.scan_iter(match=pattern))
        if keys:
            cache.delete(*keys)


def presence_cache_key(steam_id: str, user_id: int | None, bridge_id: int | None) -> str:
    user_part = str(int(user_id)) if user_id is not None else "global"
    bridge_part = str(int(bridge_id)) if bridge_id is not None else "default"
    return f"presence:{user_part}:{bridge_part}:{steam_id}"


def presence_cache_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_TTL_SECONDS", "15"))


def presence_cache_empty_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_EMPTY_TTL_SECONDS", "5"))


def chat_history_prefetch_cooldown_seconds() -> int:
    return int(os.getenv("CHAT_HISTORY_PREFETCH_COOLDOWN_SECONDS", "600"))


def should_prefetch_history(user_id: int, workspace_id: int | None, chat_id: int) -> bool:
    now = time.time()
    key = (int(user_id), int(workspace_id) if workspace_id is not None else -1, int(chat_id))
    cooldown = chat_history_prefetch_cooldown_seconds()
    with _chat_history_prefetch_lock:
        last = _chat_history_prefetch_seen.get(key)
        if last is not None and now - last < cooldown:
            return False
        _chat_history_prefetch_seen[key] = now
    return True


def chat_cache_workspace_key(workspace_id: int | None) -> str:
    return "none" if workspace_id is None else str(int(workspace_id))


def chat_list_cache_pattern(user_id: int, workspace_id: int | None) -> str:
    return f"chat:list:{int(user_id)}:{chat_cache_workspace_key(workspace_id)}:*"


def chat_history_cache_pattern(user_id: int, workspace_id: int | None, chat_id: int) -> str:
    return f"chat:history:{int(user_id)}:{chat_cache_workspace_key(workspace_id)}:{int(chat_id)}:*"


def invalidate_chat_cache(user_id: int, workspace_id: int | None, chat_id: int) -> None:
    cache = get_redis_client()
    if not cache:
        return
    patterns = [
        chat_list_cache_pattern(user_id, workspace_id),
        chat_history_cache_pattern(user_id, workspace_id, chat_id),
    ]
    for pattern in patterns:
        try:
            batch: list[str] = []
            for key in cache.scan_iter(match=pattern):
                batch.append(str(key))
                if len(batch) >= 200:
                    cache.delete(*batch)
                    batch.clear()
            if batch:
                cache.delete(*batch)
        except Exception:
            continue


def fetch_presence(steam_id: str | None, *, user_id: int | None = None, bridge_id: int | None = None) -> dict:
    if not steam_id:
        return {}
    cache = get_redis_client()
    if cache:
        try:
            cached_raw = cache.get(presence_cache_key(steam_id, user_id, bridge_id))
        except Exception:
            cached_raw = None
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
            except Exception:
                cached = None
            return cached if isinstance(cached, dict) else {}
    base = os.getenv("STEAM_PRESENCE_URL", "").strip() or os.getenv("STEAM_BRIDGE_URL", "").strip()
    if not base:
        return {}
    base = base.rstrip("/")
    try:
        params = {}
        if user_id is not None:
            params["user_id"] = str(int(user_id))
        if bridge_id is not None:
            params["bridge_id"] = str(int(bridge_id))
        headers = {}
        token = os.getenv("STEAM_BRIDGE_INTERNAL_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = requests.get(
            f"{base}/presence/{steam_id}",
            timeout=10,
            params=params or None,
            headers=headers or None,
        )
        resp.raise_for_status()
        payload = resp.json()
        data = payload if isinstance(payload, dict) else {}
    except Exception:
        data = {}
    if cache:
        try:
            ttl = presence_cache_ttl_seconds() if data else presence_cache_empty_ttl_seconds()
            cache.setex(presence_cache_key(steam_id, user_id, bridge_id), ttl, json.dumps(data))
        except Exception:
            pass
    return data
