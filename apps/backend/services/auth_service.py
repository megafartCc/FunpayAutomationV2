from __future__ import annotations

import time
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from db.user_repo import InMemoryUserRepo, UserRecord
from settings.config import settings

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, repo: Optional[InMemoryUserRepo] = None) -> None:
        self._repo = repo or InMemoryUserRepo()

    def login(self, username: str, password: str) -> Optional[str]:
        record = self._repo.get_by_username(username)
        if record is None:
            return None
        if not _password_context.verify(password, record.password_hash):
            return None
        return self._issue_token(record.username)

    def register(self, username: str, password: str, golden_key: str) -> Optional[str]:
        if self._repo.get_by_username(username):
            return None
        password_hash = _password_context.hash(password)
        record = UserRecord(username=username, password_hash=password_hash, golden_key=golden_key)
        if not self._repo.create(record):
            return None
        return self._issue_token(record.username)

    def _issue_token(self, username: str) -> str:
        now = int(time.time())
        payload = {
            "sub": username,
            "iat": now,
            "exp": now + settings.jwt_ttl_seconds,
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
