from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class RefundResult:
    order_id: str
    ok: bool
    message: str | None = None


def _normalize_order_id(order_id: str) -> str:
    value = str(order_id or "").strip()
    if value.startswith("#"):
        value = value[1:]
    return value


def _normalize_proxy_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return f"socks5://{value}"


def _build_proxy_config(raw: str | None) -> dict[str, str] | None:
    url = _normalize_proxy_url(raw)
    if not url:
        return None
    return {"http": url, "https": url}


def _fetch_csrf_token(session: requests.Session) -> str:
    response = session.get("https://funpay.com/", timeout=20)
    response.raise_for_status()
    parser = BeautifulSoup(response.text, "html.parser")
    body = parser.find("body")
    if body is None or not body.get("data-app-data"):
        raise RuntimeError("Failed to load FunPay session data.")
    app_data = json.loads(body.get("data-app-data"))
    csrf = app_data.get("csrf-token")
    if not csrf:
        raise RuntimeError("Missing FunPay CSRF token.")
    return csrf


def refund_order(
    *,
    golden_key: str,
    order_id: str,
    proxy_url: str | None = None,
    user_agent: str | None = None,
) -> RefundResult:
    order_key = _normalize_order_id(order_id)
    if not order_key:
        raise ValueError("Order ID is required.")
    session = requests.Session()
    session.headers.update(
        {
            "accept": "*/*",
            "user-agent": user_agent
            or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
    )
    session.cookies.set("golden_key", golden_key)
    session.cookies.set("cookie_prefs", "1")
    proxies = _build_proxy_config(proxy_url)
    if proxies:
        session.proxies.update(proxies)
    csrf_token = _fetch_csrf_token(session)
    response = session.post(
        "https://funpay.com/orders/refund",
        headers={
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
        },
        data={"id": order_key, "csrf_token": csrf_token},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        return RefundResult(order_id=order_key, ok=False, message=payload.get("msg"))
    return RefundResult(order_id=order_key, ok=True, message=payload.get("msg"))
