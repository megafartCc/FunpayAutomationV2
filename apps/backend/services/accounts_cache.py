from __future__ import annotations

import json
import os
from typing import Any, Optional

import redis


class AccountsCache:
    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL", "").strip()
        self._client: Optional[redis.Redis] = None
        if redis_url:
            self._client = redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = int(os.getenv("ACCOUNTS_CACHE_TTL_SECONDS", "30"))

    def get_list(
        self,
        user_id: int,
        workspace_id: int | None,
        *,
        low_priority: bool = False,
    ) -> Optional[list[dict[str, Any]]]:
        if not self._client:
            return None
        try:
            raw = self._client.get(self._key(user_id, workspace_id, low_priority=low_priority))
        except Exception:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        return data if isinstance(data, list) else None

    def set_list(
        self,
        user_id: int,
        workspace_id: int | None,
        items: list[dict[str, Any]],
        *,
        low_priority: bool = False,
    ) -> None:
        if not self._client:
            return
        try:
            self._client.set(
                self._key(user_id, workspace_id, low_priority=low_priority),
                json.dumps(items, ensure_ascii=False),
                ex=max(1, int(self._ttl_seconds)),
            )
        except Exception:
            return

    def clear_user(self, user_id: int) -> None:
        if not self._client:
            return
        self._delete_by_pattern(f"accounts:list:{int(user_id)}:*")

    def _workspace_key(self, workspace_id: int | None) -> str:
        return "all" if workspace_id is None else str(int(workspace_id))

    def _key(self, user_id: int, workspace_id: int | None, *, low_priority: bool) -> str:
        suffix = "low" if low_priority else "all"
        return f"accounts:list:{int(user_id)}:{self._workspace_key(workspace_id)}:{suffix}"

    def _delete_by_pattern(self, pattern: str) -> None:
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

