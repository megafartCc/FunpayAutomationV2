from __future__ import annotations

import os
import secrets
from typing import Optional

import redis


class SessionService:
    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            raise RuntimeError("REDIS_URL is required for session storage.")
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "604800"))  # 7 days

    def create_session(self, user_id: int) -> str:
        session_id = secrets.token_urlsafe(32)
        key = self._key(session_id)
        self._client.set(key, str(user_id), ex=self._ttl_seconds)
        return session_id

    def get_user_id(self, session_id: str) -> Optional[int]:
        key = self._key(session_id)
        value = self._client.get(key)
        if value is None:
            return None
        # sliding expiration
        self._client.expire(key, self._ttl_seconds)
        try:
            return int(value)
        except Exception:
            return None

    def delete_session(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"
