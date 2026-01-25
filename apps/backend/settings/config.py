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
    cookie_secure: bool
    cookie_samesite: str
    session_cookie_name: str
    remember_cookie_name: str
    session_ttl_seconds: int
    remember_days: int

    def __init__(self) -> None:
        self.jwt_secret = _get_env("JWT_SECRET", "change-me")
        self.jwt_algorithm = _get_env("JWT_ALG", "HS256")
        self.jwt_ttl_seconds = _get_int("JWT_TTL_SECONDS", 60 * 60 * 24)
        origins = _get_env("CORS_ORIGINS", "*")
        self.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]
        self.cookie_secure = _get_env("COOKIE_SECURE", "true").lower() in {"1", "true", "yes", "on"}
        self.cookie_samesite = _get_env("COOKIE_SAMESITE", "lax")
        self.session_cookie_name = _get_env("SESSION_COOKIE_NAME", "session_id")
        self.remember_cookie_name = _get_env("REMEMBER_COOKIE_NAME", "diamond_key")
        self.session_ttl_seconds = _get_int("SESSION_TTL_SECONDS", 60 * 60 * 24 * 7)
        self.remember_days = _get_int("REMEMBER_DAYS", 90)


settings = Settings()
