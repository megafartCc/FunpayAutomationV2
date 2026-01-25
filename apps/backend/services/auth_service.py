from __future__ import annotations

from typing import Optional, Protocol
from passlib.context import CryptContext

from db.user_repo import InMemoryUserRepo, UserRecord
from db.mysql import MySQLUserRepo
_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRepo(Protocol):
    def get_by_username(self, username: str) -> Optional[UserRecord]:
        ...

    def get_by_id(self, user_id: int) -> Optional[UserRecord]:
        ...

    def create(self, record: UserRecord) -> Optional[UserRecord]:
        ...


class AuthService:
    def __init__(self, repo: Optional[UserRepo] = None) -> None:
        self._repo = repo or MySQLUserRepo()

    def login(self, username: str, password: str) -> Optional[UserRecord]:
        record = self._repo.get_by_username(username)
        if record is None:
            return None
        if not _password_context.verify(password, record.password_hash):
            return None
        return record

    def register(self, username: str, password: str, golden_key: str) -> Optional[UserRecord]:
        login = username.strip().lower()
        email = login if "@" in login else None
        if self._repo.get_by_username(login):
            return None
        password_hash = _password_context.hash(password)
        record = UserRecord(
            id=None,
            username=login,
            password_hash=password_hash,
            golden_key=golden_key,
            email=email,
        )
        created = self._repo.create(record)
        return created

    def get_user(self, user_id: int) -> Optional[UserRecord]:
        return self._repo.get_by_id(user_id)
