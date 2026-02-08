from __future__ import annotations

import logging
import sys
from pathlib import Path


logger = logging.getLogger("backend.funpay.refund")

_HERE = Path(__file__).resolve()
for _parent in _HERE.parents:
    if (_parent / "workers").exists():
        if str(_parent) not in sys.path:
            sys.path.append(str(_parent))
        break

try:
    from FunPayAPI.account import Account
    from FunPayAPI.common import exceptions as fp_exceptions
except Exception:
    try:
        from workers.funpay.FunPayAPI.account import Account
        from workers.funpay.FunPayAPI.common import exceptions as fp_exceptions
    except Exception:  # pragma: no cover - optional dependency in backend runtime
        Account = None
        fp_exceptions = None


def _build_proxy_config(proxy_url: str | None) -> dict | None:
    raw = (proxy_url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"socks5://{raw}"
    return {"http": raw, "https": raw}


def _normalize_order_id(order_id: str) -> str:
    value = str(order_id or "").strip()
    if value.startswith("#"):
        value = value[1:]
    return value


def refund_order(
    *,
    golden_key: str,
    proxy_url: str | None,
    order_id: str,
    user_agent: str | None = None,
) -> float | None:
    if not Account:
        raise RuntimeError("FunPayAPI is not available in backend runtime.")
    normalized = _normalize_order_id(order_id)
    if not normalized:
        raise ValueError("order_id is required")
    proxy_cfg = _build_proxy_config(proxy_url)
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    refund_amount: float | None = None
    try:
        order = account.get_order(normalized)
        if order is not None:
            order_sum = getattr(order, "sum", None)
            if order_sum is not None:
                refund_amount = float(order_sum)
    except Exception as exc:
        logger.warning("Failed to fetch order %s before refund: %s", normalized, exc)
    account.refund(normalized)
    return refund_amount
