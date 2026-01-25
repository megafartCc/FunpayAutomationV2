from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class UserRecord:
    id: Optional[int]
    username: str
    password_hash: str
    golden_key: str
    email: Optional[str] = None


class InMemoryUserRepo:
    def __init__(self) -> None:
        self._users: Dict[str, UserRecord] = {}
        self._next_id = 1

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        key = username.lower()
        record = self._users.get(key)
        if record is not None:
            return record
        for existing in self._users.values():
            if existing.email and existing.email.lower() == key:
                return existing
        return None

    def get_by_id(self, user_id: int) -> Optional[UserRecord]:
        for existing in self._users.values():
            if existing.id == user_id:
                return existing
        return None

    def create(self, record: UserRecord) -> Optional[UserRecord]:
        key = record.username.lower()
        if key in self._users:
            return None
        record.id = self._next_id
        self._next_id += 1
        self._users[key] = record
        return record
