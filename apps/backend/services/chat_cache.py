from __future__ import annotations

import json
import os
from typing import Any, Optional

import redis


class ChatCache:
    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL", "").strip()
        self._client: Optional[redis.Redis] = None
        if redis_url:
            self._client = redis.from_url(redis_url, decode_responses=True)
        self._list_ttl_seconds = int(os.getenv("CHAT_LIST_CACHE_TTL_SECONDS", "20"))
        self._history_ttl_seconds = int(os.getenv("CHAT_HISTORY_CACHE_TTL_SECONDS", "90"))

    def get_list(
        self,
        user_id: int,
        workspace_id: int | None,
        query: str | None,
        limit: int,
    ) -> Optional[list[dict[str, Any]]]:
        if not self._client or query:
            return None
        return self._get_list(self._list_key(user_id, workspace_id, limit))

    def set_list(
        self,
        user_id: int,
        workspace_id: int | None,
        query: str | None,
        limit: int,
        items: list[dict[str, Any]],
    ) -> None:
        if not self._client or query:
            return
        self._set_list(self._list_key(user_id, workspace_id, limit), items, self._list_ttl_seconds)

    def get_history(
        self,
        user_id: int,
        workspace_id: int | None,
        chat_id: int,
        limit: int,
        after_id: int | None,
    ) -> Optional[list[dict[str, Any]]]:
        if not self._client or after_id:
            return None
        return self._get_list(self._history_key(user_id, workspace_id, chat_id, limit))

    def set_history(
        self,
        user_id: int,
        workspace_id: int | None,
        chat_id: int,
        limit: int,
        after_id: int | None,
        items: list[dict[str, Any]],
    ) -> None:
        if not self._client or after_id:
            return
        self._set_list(self._history_key(user_id, workspace_id, chat_id, limit), items, self._history_ttl_seconds)

    def clear_list(self, user_id: int, workspace_id: int | None) -> None:
        if not self._client:
            return
        self._delete_by_pattern(f"chat:list:{user_id}:{self._workspace_key(workspace_id)}:*")

    def clear_history(self, user_id: int, workspace_id: int | None, chat_id: int) -> None:
        if not self._client:
            return
        self._delete_by_pattern(f"chat:history:{user_id}:{self._workspace_key(workspace_id)}:{int(chat_id)}:*")

    def _workspace_key(self, workspace_id: int | None) -> str:
        return "none" if workspace_id is None else str(int(workspace_id))

    def _list_key(self, user_id: int, workspace_id: int | None, limit: int) -> str:
        return f"chat:list:{int(user_id)}:{self._workspace_key(workspace_id)}:{int(limit)}"

    def _history_key(self, user_id: int, workspace_id: int | None, chat_id: int, limit: int) -> str:
        return f"chat:history:{int(user_id)}:{self._workspace_key(workspace_id)}:{int(chat_id)}:{int(limit)}"

    def _get_list(self, key: str) -> Optional[list[dict[str, Any]]]:
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        return data if isinstance(data, list) else None

    def _set_list(self, key: str, items: list[dict[str, Any]], ttl: int) -> None:
        if not self._client:
            return
        try:
            self._client.set(key, json.dumps(items, ensure_ascii=False), ex=ttl)
        except Exception:
            return

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
