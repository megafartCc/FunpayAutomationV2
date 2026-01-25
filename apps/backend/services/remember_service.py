from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from db.mysql import MySQLRememberTokenRepo


class RememberService:
    def __init__(self) -> None:
        self._repo = MySQLRememberTokenRepo()

    def _ttl_days(self) -> int:
        try:
            import os

            value = os.getenv("REMEMBER_DAYS", "").strip()
            if value:
                return int(value)
        except Exception:
            pass
        return 90

    def _hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_token(self, user_id: int, user_agent: Optional[str]) -> str:
        token = secrets.token_urlsafe(48)
        token_hash = self._hash(token)
        expires_at = self._expires_at()
        self._repo.create(user_id, token_hash, user_agent, expires_at)
        return token

    def rotate_token(self, token: str, user_agent: Optional[str]) -> tuple[str, int] | None:
        token_hash = self._hash(token)
        found = self._repo.find_valid(token_hash)
        if not found:
            return None
        token_id, user_id = found
        new_token = secrets.token_urlsafe(48)
        new_hash = self._hash(new_token)
        self._repo.rotate(token_id, new_hash, self._expires_at(), user_agent)
        return new_token, user_id

    def revoke(self, token: str) -> None:
        token_hash = self._hash(token)
        self._repo.revoke(token_hash)

    def _expires_at(self) -> str:
        ttl_days = self._ttl_days()
        expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        return expires.strftime("%Y-%m-%d %H:%M:%S")
