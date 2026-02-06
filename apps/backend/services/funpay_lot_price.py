from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
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


@dataclass
class FunPayLotSnapshot:
    lot_id: int
    title: str
    description: str
    price: float | None
    active: bool


def _build_proxy_config(proxy_url: str | None) -> dict | None:
    raw = (proxy_url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"socks5://{raw}"
    return {"http": raw, "https": raw}


def _create_account(golden_key: str, proxy_url: str | None, user_agent: str | None) -> Account | None:
    if not Account:
        logger.warning("FunPayAPI is not available in backend runtime.")
        return None
    proxy_cfg = _build_proxy_config(proxy_url)
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    return account


def get_funpay_lot_snapshot(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    user_agent: str | None = None,
) -> FunPayLotSnapshot | None:
    account = _create_account(golden_key, proxy_url, user_agent)
    if account is None:
        return None
    lot_fields = account.get_lot_fields(int(lot_id))
    title = (lot_fields.title_ru or lot_fields.title_en or "").strip()
    description = (lot_fields.description_ru or lot_fields.description_en or "").strip()
    return FunPayLotSnapshot(
        lot_id=int(lot_id),
        title=title,
        description=description,
        price=lot_fields.price,
        active=bool(lot_fields.active),
    )


def edit_funpay_lot(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    title: str | None = None,
    description: str | None = None,
    price: float | None = None,
    active: bool | None = None,
    user_agent: str | None = None,
) -> FunPayLotSnapshot | None:
    account = _create_account(golden_key, proxy_url, user_agent)
    if account is None:
        return None
    lot_fields = account.get_lot_fields(int(lot_id))

    if title is not None:
        lot_fields.title_ru = title
    if description is not None:
        lot_fields.description_ru = description
    if price is not None:
        lot_fields.price = round(float(price), 2)
    if active is not None:
        lot_fields.active = bool(active)

    account.save_lot(lot_fields)
    return get_funpay_lot_snapshot(
        golden_key=golden_key,
        proxy_url=proxy_url,
        lot_id=lot_id,
        user_agent=user_agent,
    )


def update_funpay_lot_price(
    *,
    golden_key: str,
    proxy_url: str | None,
    lot_id: int,
    price: float,
    user_agent: str | None = None,
) -> tuple[bool, float | None]:
    account = _create_account(golden_key, proxy_url, user_agent)
    if account is None:
        return False, None
    lot_fields = account.get_lot_fields(int(lot_id))
    current_price = lot_fields.price
    new_price = round(float(price), 2)
    if current_price is not None and abs(float(current_price) - new_price) < 0.01:
        return False, current_price
    lot_fields.price = new_price
    account.save_lot(lot_fields)
    return True, current_price
