from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any


logger = logging.getLogger("backend.funpay.lot_edit")

_HERE = Path(__file__).resolve()
for _parent in _HERE.parents:
    if (_parent / "workers").exists():
        if str(_parent) not in sys.path:
            sys.path.append(str(_parent))
        break

try:
    from workers.funpay.FunPayAPI.account import Account
    from workers.funpay.FunPayAPI.common import exceptions as fp_exceptions
except Exception:
    try:
        from FunPayAPI.account import Account
        from FunPayAPI.common import exceptions as fp_exceptions
    except Exception:  # pragma: no cover
        Account = None
        fp_exceptions = None

try:
    from services.funpay_lot_title import _force_lot_active, _post_lot_fields
except Exception:  # pragma: no cover
    _force_lot_active = None
    _post_lot_fields = None


def _build_proxy_config(proxy_url: str | None) -> dict | None:
    raw = (proxy_url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"socks5://{raw}"
    return {"http": raw, "https": raw}


def _extract_snapshot(fields: dict[str, Any]) -> dict[str, Any]:
    def _coerce_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(" ", ""))
        except Exception:
            return None

    def _coerce_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except Exception:
            return None

    return {
        "price": _coerce_float(fields.get("price")),
        "amount": _coerce_int(fields.get("amount")),
        "active": bool(fields.get("active") == "on"),
        "summary_ru": str(fields.get("fields[summary][ru]", "") or ""),
        "summary_en": str(fields.get("fields[summary][en]", "") or ""),
        "desc_ru": str(fields.get("fields[desc][ru]", "") or ""),
        "desc_en": str(fields.get("fields[desc][en]", "") or ""),
        "decency": _coerce_int(fields.get("fields[decency]")),
        "solommr": _coerce_int(fields.get("fields[solommr]")),
        "politeness": _coerce_int(fields.get("fields[politeness]")),
        "time": _coerce_int(fields.get("fields[time]")),
        "type1": str(fields.get("fields[type1]", "") or ""),
        "type": str(fields.get("fields[type]", "") or ""),
        "payment_msg_ru": str(fields.get("fields[payment_msg][ru]", "") or ""),
        "payment_msg_en": str(fields.get("fields[payment_msg][en]", "") or ""),
        "images": str(fields.get("fields[images]", "") or ""),
        "auto_delivery": bool(fields.get("auto_delivery") == "on"),
    }


def _build_snapshot(fields: dict[str, Any]) -> dict[str, Any]:
    snapshot = _extract_snapshot(fields)
    snapshot["raw_fields"] = {key: fields.get(key) for key in sorted(fields.keys())}
    return snapshot


_NUMERIC_FIELD_PATTERNS = (
    re.compile(r"^price$", re.IGNORECASE),
    re.compile(r"^amount$", re.IGNORECASE),
    re.compile(r"^fields\\[(decency|politeness|solommr|time|hours|days)\\]$", re.IGNORECASE),
    re.compile(r"^fields\\[[^\\]]*mmr\\]$", re.IGNORECASE),
)


def _is_numeric_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        raw = value.strip().replace(" ", "").replace(",", ".")
        if raw == "":
            return True
        try:
            float(raw)
            return True
        except Exception:
            return False
    return False


def _validate_raw_fields(raw_fields: dict[str, Any]) -> None:
    invalid_keys: list[str] = []
    for key, value in raw_fields.items():
        if key is None:
            continue
        key_str = str(key)
        if any(pattern.match(key_str) for pattern in _NUMERIC_FIELD_PATTERNS):
            if not _is_numeric_value(value):
                invalid_keys.append(key_str)
    if invalid_keys:
        raise ValueError(f"Numeric fields must contain numbers: {', '.join(sorted(invalid_keys))}")


def _apply_edit(
    *,
    fields: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    updated = dict(fields)
    changes: list[dict[str, Any]] = []

    def set_field(key: str, value: Any) -> None:
        old = updated.get(key)
        if old == value:
            return
        updated[key] = value
        changes.append({"field": key, "from": old, "to": value})

    raw_fields = payload.get("raw_fields")
    if isinstance(raw_fields, dict):
        _validate_raw_fields(raw_fields)
        for raw_key, raw_value in raw_fields.items():
            if raw_key is None:
                continue
            key = str(raw_key).strip()
            if not key:
                continue
            existing = updated.get(key)
            if raw_value is None:
                value: Any = ""
            elif isinstance(raw_value, bool):
                value = "on" if raw_value else ""
            elif isinstance(raw_value, (int, float)) and isinstance(existing, (int, float)):
                value = raw_value
            else:
                value = str(raw_value)
            set_field(key, value)

    if payload.get("price") is not None:
        set_field("price", str(payload["price"]))
    if payload.get("amount") is not None:
        set_field("amount", str(payload["amount"]))
    if payload.get("summary_ru") is not None:
        set_field("fields[summary][ru]", str(payload["summary_ru"]))
    if payload.get("summary_en") is not None:
        set_field("fields[summary][en]", str(payload["summary_en"]))
    if payload.get("desc_ru") is not None:
        set_field("fields[desc][ru]", str(payload["desc_ru"]))
    if payload.get("desc_en") is not None:
        set_field("fields[desc][en]", str(payload["desc_en"]))
    if payload.get("decency") is not None:
        set_field("fields[decency]", str(payload["decency"]))
    if payload.get("solommr") is not None:
        set_field("fields[solommr]", str(payload["solommr"]))
    if payload.get("politeness") is not None:
        set_field("fields[politeness]", str(payload["politeness"]))
    if payload.get("time") is not None:
        set_field("fields[time]", str(payload["time"]))
    if payload.get("type1") is not None:
        set_field("fields[type1]", str(payload["type1"]))
    if payload.get("type") is not None:
        set_field("fields[type]", str(payload["type"]))
    if payload.get("payment_msg_ru") is not None:
        set_field("fields[payment_msg][ru]", str(payload["payment_msg_ru"]))
    if payload.get("payment_msg_en") is not None:
        set_field("fields[payment_msg][en]", str(payload["payment_msg_en"]))
    if payload.get("images") is not None:
        set_field("fields[images]", str(payload["images"]))

    if "auto_delivery" in payload and payload["auto_delivery"] is not None:
        auto_value = payload["auto_delivery"]
        if isinstance(auto_value, bool):
            if auto_value:
                set_field("auto_delivery", "on")
            else:
                if "auto_delivery" in updated:
                    changes.append({"field": "auto_delivery", "from": updated.get("auto_delivery"), "to": None})
                updated.pop("auto_delivery", None)
        else:
            set_field("auto_delivery", str(auto_value))

    active_value: bool | None = None
    if "active" in payload and payload["active"] is not None:
        active_value = bool(payload["active"])

    if active_value is True:
        set_field("active", "on")
    elif active_value is False:
        if "active" in updated:
            changes.append({"field": "active", "from": updated.get("active"), "to": None})
        updated.pop("active", None)

    final_active = bool(updated.get("active") == "on")
    return updated, changes, final_active


def _load_lot_fields(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    user_agent: str | None = None,
) -> tuple[Account, dict[str, Any], dict[str, Any]]:
    if not Account:
        raise RuntimeError("FunPayAPI is not available in backend runtime.")
    proxy_cfg = _build_proxy_config(proxy_url)
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    lot_fields = account.get_lot_fields(lot_id)
    # Normalize fields to match a real form submission payload.
    lot_fields.renew_fields()
    fields = {k: ("" if v is None else v) for k, v in dict(lot_fields.fields).items()}
    snapshot = _build_snapshot(fields)
    return account, fields, snapshot


def get_funpay_lot_snapshot(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    user_agent: str | None = None,
) -> dict[str, Any]:
    _, _, snapshot = _load_lot_fields(
        golden_key=golden_key,
        proxy_url=proxy_url,
        lot_id=lot_id,
        user_agent=user_agent,
    )
    return snapshot


def preview_funpay_lot_edit(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    payload: dict[str, Any],
    user_agent: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool, dict[str, Any]]:
    _, raw_fields, snapshot = _load_lot_fields(
        golden_key=golden_key,
        proxy_url=proxy_url,
        lot_id=lot_id,
        user_agent=user_agent,
    )
    updated_fields, changes, active_value = _apply_edit(
        fields=raw_fields,
        payload=payload,
    )
    return updated_fields, changes, active_value, snapshot


def save_funpay_lot_edit(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    payload: dict[str, Any],
    user_agent: str | None = None,
) -> list[dict[str, Any]]:
    if not _post_lot_fields:
        raise RuntimeError("FunPay lot saver is unavailable.")
    account, raw_fields, snapshot = _load_lot_fields(
        golden_key=golden_key,
        proxy_url=proxy_url,
        lot_id=lot_id,
        user_agent=user_agent,
    )
    updated_fields, changes, active_value = _apply_edit(
        fields=raw_fields,
        payload=payload,
    )
    if "offer_id" not in updated_fields:
        updated_fields["offer_id"] = str(lot_id)
    if not updated_fields.get("csrf_token"):
        updated_fields["csrf_token"] = account.csrf_token
    _post_lot_fields(account, lot_id, updated_fields)
    if active_value and _force_lot_active is not None:
        _force_lot_active(account, lot_id)
    return changes
