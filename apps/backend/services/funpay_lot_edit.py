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

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None


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
    re.compile(r"^fields\[(decency|politeness|solommr|time|hours|days)\]$", re.IGNORECASE),
    re.compile(r"^fields\[[^\]]*mmr\]$", re.IGNORECASE),
)

_PROTECTED_RAW_KEYS = {
    "csrf_token",
    "form_created_at",
}


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
            if key in _PROTECTED_RAW_KEYS:
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
) -> tuple[Account, Any, dict[str, Any], dict[str, Any]]:
    if not Account:
        raise RuntimeError("FunPayAPI is not available in backend runtime.")
    proxy_cfg = _build_proxy_config(proxy_url)
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    lot_fields = account.get_lot_fields(lot_id)
    # Normalize fields to match a real form submission payload.
    lot_fields.renew_fields()
    fields = {k: ("" if v is None else v) for k, v in dict(lot_fields.fields).items()}
    node_id = str(fields.get("node_id") or "").strip()
    if node_id:
        try:
            extra_fields = _fetch_offer_form_fields(account, lot_id, node_id)
        except Exception as exc:
            logger.warning("Failed to fetch offer form with node_id=%s: %s", node_id, exc)
            extra_fields = {}
        if extra_fields:
            fields.update(extra_fields)
            lot_fields.edit_fields(extra_fields)
    snapshot = _build_snapshot(fields)
    return account, lot_fields, fields, snapshot


def _fetch_offer_form_fields(account: Account, lot_id: int, node_id: str) -> dict[str, Any]:
    if not BeautifulSoup:
        return {}
    headers: dict[str, str] = {}
    response = account.method(
        "get",
        f"lots/offerEdit?node={node_id}&offer={lot_id}",
        headers,
        {},
        raise_not_200=True,
    )
    html_response = response.content.decode()
    bs = BeautifulSoup(html_response, "lxml")
    offer_form = bs.find("form", attrs={"action": lambda x: isinstance(x, str) and "offerSave" in x})
    if not offer_form:
        for form in bs.find_all("form"):
            offer_input = form.find("input", {"name": "offer_id"})
            if offer_input and str(offer_input.get("value", "")).strip() == str(lot_id):
                offer_form = form
                break
    if not offer_form:
        return {}
    result: dict[str, Any] = {}
    result.update(
        {
            field["name"]: field.get("value") or ""
            for field in offer_form.find_all("input")
            if field.get("name")
        }
    )
    result.update(
        {
            field["name"]: field.text or ""
            for field in offer_form.find_all("textarea")
            if field.get("name")
        }
    )
    for field in offer_form.find_all("select"):
        if not field.get("name"):
            continue
        selected_option = field.find("option", selected=True) or field.find("option")
        if selected_option and selected_option.get("value") is not None:
            result[field["name"]] = selected_option["value"]
    result.update(
        {
            field["name"]: "on"
            for field in offer_form.find_all("input", {"type": "checkbox"}, checked=True)
            if field.get("name")
        }
    )
    # Include submit button names (some anti-bot tokens are bound to the submit control name).
    for button in offer_form.find_all(["button", "input"]):
        name = button.get("name")
        if not name or name in result:
            continue
        btn_type = (button.get("type") or "").lower()
        if button.name == "button":
            # HTML <button> defaults to submit if no type is specified.
            btn_type = btn_type or "submit"
        if btn_type in {"submit"}:
            result[name] = button.get("value") or ""
    # Some anti-bot hidden inputs can sit outside the main form. Include them if they don't belong to another form.
    for field in bs.find_all("input"):
        name = field.get("name")
        if not name or name in result:
            continue
        parent_form = field.find_parent("form")
        if parent_form is not None and parent_form is not offer_form:
            continue
        result[name] = field.get("value") or ""
    return result

def _apply_fields_to_lot(lot_fields: Any, fields: dict[str, Any]) -> None:
    def _parse_float(value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).strip().replace(" ", "").replace(",", ".")
        if text == "":
            return None
        try:
            return float(text)
        except Exception:
            return None

    def _parse_int(value: Any) -> int | None:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        try:
            return int(float(text.replace(",", ".")))
        except Exception:
            return None

    if "fields[summary][ru]" in fields:
        lot_fields.title_ru = str(fields.get("fields[summary][ru]") or "")
    if "fields[summary][en]" in fields:
        lot_fields.title_en = str(fields.get("fields[summary][en]") or "")
    if "fields[desc][ru]" in fields:
        lot_fields.description_ru = str(fields.get("fields[desc][ru]") or "")
    if "fields[desc][en]" in fields:
        lot_fields.description_en = str(fields.get("fields[desc][en]") or "")
    if "fields[payment_msg][ru]" in fields:
        lot_fields.payment_msg_ru = str(fields.get("fields[payment_msg][ru]") or "")
    if "fields[payment_msg][en]" in fields:
        lot_fields.payment_msg_en = str(fields.get("fields[payment_msg][en]") or "")

    if "price" in fields:
        lot_fields.price = _parse_float(fields.get("price"))
    if "amount" in fields:
        lot_fields.amount = _parse_int(fields.get("amount"))

    if "fields[images]" in fields:
        raw = str(fields.get("fields[images]") or "")
        images: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                images.append(int(part))
            except Exception:
                continue
        lot_fields.images = images

    if "active" in fields:
        lot_fields.active = bool(fields.get("active") == "on")


def _post_lot_fields_browserlike(account: Account, lot_id: int, node_id: str | None, fields: dict[str, Any]) -> None:
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
        "origin": "https://funpay.com",
    }
    if getattr(account, "user_agent", None):
        headers["user-agent"] = account.user_agent
    if node_id:
        headers["referer"] = f"https://funpay.com/lots/offerEdit?node={node_id}&offer={lot_id}"
    else:
        headers["referer"] = f"https://funpay.com/lots/offerEdit?offer={lot_id}"
    logger.info("FunPay lot sync request for %s: %s", lot_id, {k: fields.get(k) for k in sorted(fields.keys())})
    response = account.method("post", "lots/offerSave", headers, fields, raise_not_200=True)
    try:
        json_response = response.json()
    except Exception as exc:
        logger.warning("FunPay lot sync response parse failed for %s: %s", lot_id, exc)
        raise
    logger.info(
        "FunPay lot sync response for %s (status %s): %s",
        lot_id,
        getattr(response, "status_code", "n/a"),
        json_response,
    )
    errors_dict: dict = {}
    if (errors := json_response.get("errors")) or json_response.get("error"):
        if isinstance(errors, dict):
            errors_dict.update({str(k): str(v) for k, v in errors.items()})
        elif isinstance(errors, (list, tuple)):
            for item in errors:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    key, value = item[0], item[1]
                    errors_dict[str(key)] = str(value)
        logger.warning(
            "FunPay lot sync validation failed for %s. error=%s field_errors=%s",
            lot_id,
            json_response.get("error"),
            errors_dict,
        )
        if fp_exceptions:
            raise fp_exceptions.LotSavingError(response, json_response.get("error"), lot_id, errors_dict)
        raise RuntimeError(f"FunPay save failed: {json_response}")

    if node_id:
        try:
            account.method(
                "get",
                f"lots/{node_id}/trade",
                {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                {},
                raise_not_200=False,
            )
        except Exception:
            pass


def get_funpay_lot_snapshot(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    user_agent: str | None = None,
) -> dict[str, Any]:
    _, _, _, snapshot = _load_lot_fields(
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
    _, _, raw_fields, snapshot = _load_lot_fields(
        golden_key=golden_key,
        proxy_url=proxy_url,
        lot_id=lot_id,
        user_agent=user_agent,
    )
    updated_fields, changes, active_value = _apply_edit(
        fields=raw_fields,
        payload=payload,
    )
    if payload.get("active") is not False:
        if updated_fields.get("active") != "on":
            changes.append({"field": "active", "from": updated_fields.get("active"), "to": "on"})
        updated_fields["active"] = "on"
        active_value = True
    return updated_fields, changes, active_value, snapshot


def save_funpay_lot_edit(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    payload: dict[str, Any],
    user_agent: str | None = None,
) -> list[dict[str, Any]]:
    account, lot_fields, raw_fields, snapshot = _load_lot_fields(
        golden_key=golden_key,
        proxy_url=proxy_url,
        lot_id=lot_id,
        user_agent=user_agent,
    )
    updated_fields, changes, active_value = _apply_edit(
        fields=raw_fields,
        payload=payload,
    )
    if payload.get("active") is not False:
        if updated_fields.get("active") != "on":
            changes.append({"field": "active", "from": updated_fields.get("active"), "to": "on"})
        updated_fields["active"] = "on"
        active_value = True
    if "offer_id" not in updated_fields:
        updated_fields["offer_id"] = str(lot_id)
    updated_fields["csrf_token"] = account.csrf_token
    lot_fields.edit_fields(updated_fields)
    _apply_fields_to_lot(lot_fields, updated_fields)
    node_id = str(updated_fields.get("node_id") or "").strip() or None
    _post_lot_fields_browserlike(account, lot_id, node_id, updated_fields)
    return changes
