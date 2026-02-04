from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path


logger = logging.getLogger("backend.funpay.lot_title")

_HERE = Path(__file__).resolve()
for _parent in _HERE.parents:
    if (_parent / "workers").exists():
        if str(_parent) not in sys.path:
            sys.path.append(str(_parent))
        break

try:
    from FunPayAPI.account import Account
except Exception:
    try:
        from workers.funpay.FunPayAPI.account import Account
    except Exception:  # pragma: no cover - optional dependency in backend runtime
        Account = None


_LOT_ID_RE = re.compile(r"(?:offer\?id=|offer/)(\d+)")
_RANK_PREFIX_RE = re.compile(r"^\s*\[[^\]]+\]\s*")
_RANK_WORDS = (
    "\u0420\u0415\u041a\u0420\u0423\u0422",
    "\u0421\u0422\u0420\u0410\u0416",
    "\u0420\u042b\u0426\u0410\u0420\u042c",
    "\u0413\u0415\u0420\u041e\u0419",
    "\u041b\u0415\u0413\u0415\u041d\u0414\u0410",
    "\u0412\u041b\u0410\u0421\u0422\u0415\u041b\u0418\u041d",
    "\u0411\u041e\u0416\u0415\u0421\u0422\u0412\u041e",
    "\u0422\u0418\u0422\u0410\u041d",
)

_RANK_RANGES = (
    (0, 150, "\u0420\u0435\u043a\u0440\u0443\u0442 I"),
    (150, 300, "\u0420\u0435\u043a\u0440\u0443\u0442 II"),
    (300, 460, "\u0420\u0435\u043a\u0440\u0443\u0442 III"),
    (460, 610, "\u0420\u0435\u043a\u0440\u0443\u0442 IV"),
    (610, 770, "\u0420\u0435\u043a\u0440\u0443\u0442 V"),
    (770, 920, "\u0421\u0442\u0440\u0430\u0436 I"),
    (920, 1080, "\u0421\u0442\u0440\u0430\u0436 II"),
    (1080, 1230, "\u0421\u0442\u0440\u0430\u0436 III"),
    (1230, 1400, "\u0421\u0442\u0440\u0430\u0436 IV"),
    (1400, 1540, "\u0421\u0442\u0440\u0430\u0436 V"),
    (1540, 1700, "\u0420\u044b\u0446\u0430\u0440\u044c I"),
    (1700, 1850, "\u0420\u044b\u0446\u0430\u0440\u044c II"),
    (1850, 2000, "\u0420\u044b\u0446\u0430\u0440\u044c III"),
    (2000, 2150, "\u0420\u044b\u0446\u0430\u0440\u044c IV"),
    (2150, 2310, "\u0420\u044b\u0446\u0430\u0440\u044c V"),
    (2310, 2450, "\u0413\u0435\u0440\u043e\u0439 I"),
    (2450, 2610, "\u0413\u0435\u0440\u043e\u0439 II"),
    (2610, 2770, "\u0413\u0435\u0440\u043e\u0439 III"),
    (2770, 2930, "\u0413\u0435\u0440\u043e\u0439 IV"),
    (2930, 3080, "\u0413\u0435\u0440\u043e\u0439 V"),
    (3080, 3230, "\u041b\u0435\u0433\u0435\u043d\u0434\u0430 I"),
    (3230, 3390, "\u041b\u0435\u0433\u0435\u043d\u0434\u0430 II"),
    (3390, 3540, "\u041b\u0435\u0433\u0435\u043d\u0434\u0430 III"),
    (3540, 3700, "\u041b\u0435\u0433\u0435\u043d\u0434\u0430 IV"),
    (3700, 3850, "\u041b\u0435\u0433\u0435\u043d\u0434\u0430 V"),
    (3850, 4000, "\u0412\u043b\u0430\u0441\u0442\u0435\u043b\u0438\u043d I"),
    (4000, 4150, "\u0412\u043b\u0430\u0441\u0442\u0435\u043b\u0438\u043d II"),
    (4150, 4300, "\u0412\u043b\u0430\u0441\u0442\u0435\u043b\u0438\u043d III"),
    (4300, 4460, "\u0412\u043b\u0430\u0441\u0442\u0435\u043b\u0438\u043d IV"),
    (4460, 4620, "\u0412\u043b\u0430\u0441\u0442\u0435\u043b\u0438\u043d V"),
    (4620, 4820, "\u0411\u043e\u0436\u0435\u0441\u0442\u0432\u043e I"),
    (4820, 5020, "\u0411\u043e\u0436\u0435\u0441\u0442\u0432\u043e II"),
    (5020, 5220, "\u0411\u043e\u0436\u0435\u0441\u0442\u0432\u043e III"),
    (5220, 5420, "\u0411\u043e\u0436\u0435\u0441\u0442\u0432\u043e IV"),
)


def _build_proxy_config(proxy_url: str | None) -> dict | None:
    raw = (proxy_url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"socks5://{raw}"
    return {"http": raw, "https": raw}


def _parse_lot_id(lot_url: str | None) -> int | None:
    if not lot_url:
        return None
    match = _LOT_ID_RE.search(lot_url)
    if not match:
        match = re.search(r"id=(\\d+)", lot_url)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _rank_label(mmr: int) -> str | None:
    if mmr < 0:
        return None
    for low, high, label in _RANK_RANGES:
        if low <= mmr < high:
            return label
    if mmr >= 5420:
        return "\u0422\u0438\u0442\u0430\u043d"
    return None


def _strip_rank_prefix(title: str) -> str:
    if not title:
        return title
    match = _RANK_PREFIX_RE.match(title)
    if not match:
        return title
    tag = match.group(0).upper()
    if any(word in tag for word in _RANK_WORDS):
        return title[match.end() :].lstrip()
    return title


def _compose_ranked_title(title: str, rank_label: str, max_len: int | None = None) -> str:
    base = _strip_rank_prefix(title)
    tag = f"[{rank_label.upper()}]"
    if base:
        result = f"{tag} {base}"
    else:
        result = tag
    if max_len is not None and max_len > 0 and len(result) > max_len:
        if base:
            max_base_len = max_len - len(tag) - 1
            if max_base_len <= 0:
                return tag[:max_len]
            trimmed = base[:max_base_len].rstrip()
            return f"{tag} {trimmed}"
        return tag[:max_len]
    return result


def update_funpay_lot_title(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    rank_label: str,
    user_agent: str | None = None,
) -> bool:
    if not Account:
        logger.warning("FunPayAPI is not available in backend runtime.")
        return False
    proxy_cfg = _build_proxy_config(proxy_url)
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    lot_fields = account.get_lot_fields(lot_id)
    current_title = lot_fields.title_ru or lot_fields.title_en or ""
    if not current_title:
        logger.warning("Lot %s has empty title, skipping.", lot_id)
        return False
    new_title = _compose_ranked_title(current_title, rank_label, max_len=len(current_title))
    if new_title == lot_fields.title_ru:
        return False
    lot_fields.title_ru = new_title
    account.save_lot(lot_fields)
    return True


def maybe_update_funpay_lot_title(
    *,
    workspace: object,
    account: object | None,
    lot_url: str | None,
) -> bool:
    if not workspace:
        return False
    platform = _get_value(workspace, "platform")
    if platform != "funpay":
        return False
    if not env_enabled():
        return False
    if not account:
        return False
    mmr = _get_value(account, "mmr")
    try:
        mmr_value = int(mmr)
    except (TypeError, ValueError):
        return False
    rank_label = _rank_label(mmr_value)
    if not rank_label:
        return False
    lot_id = _parse_lot_id(lot_url)
    if not lot_id:
        return False
    golden_key = str(_get_value(workspace, "golden_key") or "").strip()
    if not golden_key:
        return False
    user_agent = os.getenv("FUNPAY_USER_AGENT")
    try:
        return update_funpay_lot_title(
            golden_key=golden_key,
            proxy_url=_get_value(workspace, "proxy_url"),
            lot_id=lot_id,
            rank_label=rank_label,
            user_agent=user_agent,
        )
    except Exception as exc:
        logger.warning("Failed to update FunPay lot title: %s", exc)
        return False


def env_enabled() -> bool:
    raw = os.getenv("FUNPAY_LOT_RANK_PREFIX", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _get_value(obj: object, key: str, default: object | None = None) -> object | None:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
