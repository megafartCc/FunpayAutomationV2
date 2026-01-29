from __future__ import annotations

import base64
import hmac
import json
import struct
import time
from hashlib import sha1


def get_query_time() -> int:
    try:
        import requests

        request = requests.post(
            "https://api.steampowered.com/ITwoFactorService/QueryTime/v0001",
            timeout=15,
        )
        json_data = request.json()
        server_time = int(json_data["response"]["server_time"]) - time.time()
        return int(server_time)
    except Exception:
        return 0


def get_guard_code(shared_secret: str) -> str:
    symbols = "23456789BCDFGHJKMNPQRTVWXY"
    timestamp = time.time() + get_query_time()
    digest = hmac.new(
        base64.b64decode(shared_secret),
        struct.pack(">Q", int(timestamp / 30)),
        sha1,
    ).digest()
    start = digest[19] & 0x0F
    value = struct.unpack(">I", digest[start : start + 4])[0] & 0x7FFFFFFF
    code = ""
    for _ in range(5):
        code += symbols[value % len(symbols)]
        value //= len(symbols)
    return code


def get_steam_guard_code(mafile_json: str | dict | None) -> tuple[bool, str]:
    if not mafile_json:
        return False, "Нет maFile"
    try:
        data = mafile_json if isinstance(mafile_json, dict) else json.loads(mafile_json)
        shared_secret = data.get("shared_secret")
        if not shared_secret:
            return False, "Нет shared_secret"
        return True, get_guard_code(shared_secret)
    except Exception as exc:
        return False, str(exc)


def steam_id_from_mafile(mafile_json: str | dict | None) -> str | None:
    if not mafile_json:
        return None
    try:
        data = mafile_json if isinstance(mafile_json, dict) else json.loads(mafile_json)
        steam_value = (data or {}).get("Session", {}).get("SteamID")
        if steam_value is None:
            steam_value = (data or {}).get("steamid") or (data or {}).get("SteamID")
        if steam_value is not None:
            return str(int(steam_value))
    except Exception:
        return None
    return None
