from __future__ import annotations

import os


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


class Settings:
    jwt_secret: str
    jwt_algorithm: str
    jwt_ttl_seconds: int
    cors_origins: list[str]

    def __init__(self) -> None:
        self.jwt_secret = _get_env("JWT_SECRET", "change-me")
        self.jwt_algorithm = _get_env("JWT_ALG", "HS256")
        self.jwt_ttl_seconds = _get_int("JWT_TTL_SECONDS", 60 * 60 * 24)
        origins = _get_env("CORS_ORIGINS", "*")
        self.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]


settings = Settings()
