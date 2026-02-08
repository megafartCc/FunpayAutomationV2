from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class CryptoError(Exception):
    pass


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.getenv("STEAM_BRIDGE_CRYPT_KEY", "").strip()
    if not key:
        key = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
    if not key:
        raise CryptoError("STEAM_BRIDGE_CRYPT_KEY or DATA_ENCRYPTION_KEY is not configured.")
    try:
        _fernet = Fernet(key)
    except Exception as exc:
        raise CryptoError("Invalid STEAM_BRIDGE_CRYPT_KEY.") from exc
    return _fernet


def encrypt_secret(value: str) -> str:
    if value is None:
        raise CryptoError("Cannot encrypt empty value.")
    token = _get_fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(token: str) -> str:
    if token is None:
        raise CryptoError("Cannot decrypt empty value.")
    try:
        raw = _get_fernet().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise CryptoError("Failed to decrypt secret.") from exc
    return raw.decode("utf-8")
