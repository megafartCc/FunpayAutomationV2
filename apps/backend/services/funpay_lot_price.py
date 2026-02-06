from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


logger = logging.getLogger("backend.funpay.lot_price")

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
    except Exception:  # pragma: no cover
        Account = None


def _build_proxy_config(proxy_url: str | None) -> dict | None:
    raw = (proxy_url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"socks5://{raw}"
    return {"http": raw, "https": raw}


def update_funpay_lot_price(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    price: float,
    user_agent: str | None = None,
) -> tuple[bool, float | None]:
    if not Account:
        logger.warning("FunPayAPI is not available in backend runtime.")
        return False, None
    proxy_cfg = _build_proxy_config(proxy_url)
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    lot_fields = account.get_lot_fields(int(lot_id))
    current_price = lot_fields.price
    new_price = round(float(price), 2)
    if current_price is not None and abs(float(current_price) - new_price) < 0.01:
        return False, current_price
    lot_fields.price = new_price
    account.save_lot(lot_fields)
    return True, current_price
