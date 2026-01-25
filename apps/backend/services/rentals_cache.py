from __future__ import annotations

import json
import os
from typing import Any, Optional

import redis


class RentalsCache:
    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL", "").strip()
        self._client: Optional[redis.Redis] = None
        if redis_url:
            self._client = redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = int(os.getenv("RENTALS_CACHE_TTL_SECONDS", "5"))

    def get(self, user_id: int) -> Optional[list[dict[str, Any]]]:
        if not self._client:
            return None
        try:
            raw = self._client.get(self._key(user_id))
        except Exception:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        if isinstance(data, list):
            return data
        return None

    def set(self, user_id: int, items: list[dict[str, Any]]) -> None:
        if not self._client:
            return
        try:
            self._client.set(self._key(user_id), json.dumps(items, ensure_ascii=False), ex=self._ttl_seconds)
        except Exception:
            return

    def _key(self, user_id: int) -> str:
        return f"rentals:active:{user_id}"
