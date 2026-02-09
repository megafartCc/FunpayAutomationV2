from __future__ import annotations

import json
import os
from typing import Any, Optional

import redis


class QueryCache:
    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL", "").strip()
        self._client: Optional[redis.Redis] = None
        if redis_url:
            self._client = redis.from_url(redis_url, decode_responses=True)

    def get_json(self, key: str) -> Any | None:
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        if not self._client:
            return
        try:
            self._client.set(key, json.dumps(payload, ensure_ascii=False), ex=max(1, int(ttl_seconds)))
        except Exception:
            return

    def delete_pattern(self, pattern: str) -> None:
        if not self._client:
            return
        try:
            batch: list[str] = []
            for key in self._client.scan_iter(match=pattern):
                batch.append(str(key))
                if len(batch) >= 200:
                    self._client.delete(*batch)
                    batch.clear()
            if batch:
                self._client.delete(*batch)
        except Exception:
            return
