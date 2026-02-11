from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import redis


class SessionService:
    def __init__(self) -> None:
        self._ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "604800"))  # 7 days
        self._secret = (
            os.getenv("SESSION_FALLBACK_SECRET", "").strip()
            or os.getenv("JWT_SECRET", "").strip()
            or "change-me"
        )
        self._revoked_tokens: dict[str, float] = {}
        redis_url = os.getenv("REDIS_URL", "").strip()
        self._client: redis.Redis | None = None
        if redis_url:
            try:
                self._client = redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._client = None

    def create_session(self, user_id: int) -> str:
        # Always issue a stateless signed session id so login remains reliable
        # even when Redis is unavailable or when requests hit different instances.
        session_id = self._create_stateless_session_id(int(user_id))
        if self._client is not None:
            try:
                self._client.set(self._key(session_id), str(user_id), ex=self._ttl_seconds)
            except redis.RedisError:
                pass
        return session_id

    def get_user_id(self, session_id: str) -> Optional[int]:
        if session_id.startswith("st."):
            revoked_until = self._revoked_tokens.get(session_id)
            now = time.time()
            if revoked_until and revoked_until > now:
                return None
            if revoked_until and revoked_until <= now:
                self._revoked_tokens.pop(session_id, None)
            return self._parse_stateless_session_id(session_id)

        # Backward compatibility for legacy Redis-backed sessions.
        if self._client is None:
            return None
        try:
            value = self._client.get(self._key(session_id))
            if value is None:
                return None
            self._client.expire(self._key(session_id), self._ttl_seconds)
            return int(value)
        except (redis.RedisError, ValueError, TypeError):
            return None

    def delete_session(self, session_id: str) -> None:
        # Stateless tokens are invalidated by cookie deletion + TTL expiry.
        if session_id.startswith("st."):
            try:
                expires = int(session_id.split(".")[3])
            except Exception:
                expires = int(time.time()) + self._ttl_seconds
            self._revoked_tokens[session_id] = float(expires)
            return
        if self._client is not None:
            try:
                self._client.delete(self._key(session_id))
            except redis.RedisError:
                pass

    def _create_stateless_session_id(self, user_id: int) -> str:
        issued = int(time.time())
        expires = issued + self._ttl_seconds
        nonce = secrets.token_urlsafe(10)
        payload = f"{user_id}:{issued}:{expires}:{nonce}"
        sig = hmac.new(self._secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"st.{user_id}.{issued}.{expires}.{nonce}.{sig}"

    def _parse_stateless_session_id(self, token: str) -> Optional[int]:
        parts = token.split(".")
        if len(parts) != 6 or parts[0] != "st":
            return None
        user_id_raw, issued_raw, expires_raw, nonce, sig = parts[1:]
        try:
            user_id = int(user_id_raw)
            issued = int(issued_raw)
            expires = int(expires_raw)
        except Exception:
            return None
        now = int(time.time())
        if issued > now + 60 or expires <= now:
            return None
        payload = f"{user_id}:{issued}:{expires}:{nonce}"
        expected = hmac.new(self._secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return user_id

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"
