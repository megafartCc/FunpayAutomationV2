from __future__ import annotations

import os
import secrets
import time
from typing import Optional

import redis


class SessionService:
    def __init__(self) -> None:
        self._ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "604800"))  # 7 days
        self._memory_store: dict[str, tuple[int, float]] = {}
        redis_url = os.getenv("REDIS_URL", "").strip()
        self._client: redis.Redis | None = None
        if redis_url:
            try:
                self._client = redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._client = None

    def create_session(self, user_id: int) -> str:
        session_id = secrets.token_urlsafe(32)
        key = self._key(session_id)
        expires_at = time.time() + self._ttl_seconds
        self._memory_store[key] = (int(user_id), expires_at)
        if self._client is not None:
            try:
                self._client.set(key, str(user_id), ex=self._ttl_seconds)
            except redis.RedisError:
                pass
        return session_id

    def get_user_id(self, session_id: str) -> Optional[int]:
        key = self._key(session_id)
        if self._client is not None:
            try:
                value = self._client.get(key)
                if value is not None:
                    self._client.expire(key, self._ttl_seconds)
                    try:
                        uid = int(value)
                    except Exception:
                        uid = None
                    if uid is not None:
                        self._memory_store[key] = (uid, time.time() + self._ttl_seconds)
                    return uid
            except redis.RedisError:
                pass

        cached = self._memory_store.get(key)
        if not cached:
            return None
        user_id, expires_at = cached
        now = time.time()
        if expires_at <= now:
            self._memory_store.pop(key, None)
            return None
        self._memory_store[key] = (user_id, now + self._ttl_seconds)
        return int(user_id)

    def delete_session(self, session_id: str) -> None:
        key = self._key(session_id)
        self._memory_store.pop(key, None)
        if self._client is not None:
            try:
                self._client.delete(key)
            except redis.RedisError:
                pass

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"
