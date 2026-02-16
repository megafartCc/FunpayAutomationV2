from __future__ import annotations

import json
import re


_STEAM_ID_RE = re.compile(
    r'"(?:SteamID64|SteamID|steamid64|steamid|steam_id|steamId)"\s*:\s*"?(\d{5,20})"?',
    re.IGNORECASE,
)


def extract_steam_id(mafile_json: str | dict | None) -> str | None:
    if not mafile_json:
        return None

    data: object | None = None
    if isinstance(mafile_json, dict):
        data = mafile_json
    elif isinstance(mafile_json, str):
        match = _STEAM_ID_RE.search(mafile_json)
        if match:
            try:
                return str(int(match.group(1)))
            except Exception:
                return match.group(1)
        try:
            data = json.loads(mafile_json)
        except Exception:
            return None
    else:
        return None

    if not isinstance(data, dict):
        return None

    session = data.get("Session")
    steam_value = None
    if isinstance(session, dict):
        steam_value = session.get("SteamID") or session.get("steamid") or session.get("SteamID64")

    if steam_value is None:
        steam_value = (
            data.get("steamid")
            or data.get("SteamID")
            or data.get("steam_id")
            or data.get("steamId")
            or data.get("steamid64")
            or data.get("SteamID64")
        )

    if steam_value is None:
        return None

    try:
        return str(int(steam_value))
    except Exception:
        try:
            return str(steam_value)
        except Exception:
            return None

