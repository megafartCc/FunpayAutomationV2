from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class UserRecord:
    username: str
    password_hash: str
    golden_key: str


class InMemoryUserRepo:
    def __init__(self) -> None:
        self._users: Dict[str, UserRecord] = {}

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        return self._users.get(username.lower())

    def create(self, record: UserRecord) -> bool:
        key = record.username.lower()
        if key in self._users:
            return False
        self._users[key] = record
        return True
