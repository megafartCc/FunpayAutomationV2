from __future__ import annotations

import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from api.deps import get_current_user


router = APIRouter()

_PRICE_RE = re.compile(r"(\d[\d\s.,]*)")


class PriceDumpRequest(BaseModel):
    url: HttpUrl = Field(..., description="FunPay lot URL")


class PriceDumpResponse(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    prices: list[float]
    currency: str | None = None
    price_texts: list[str]


def _extract_prices(texts: Iterable[str]) -> tuple[list[float], str | None, list[str]]:
    prices: list[float] = []
    price_texts: list[str] = []
    currencies: set[str] = set()
    for raw in texts:
        if not raw:
            continue
        cleaned = " ".join(raw.split())
        match = _PRICE_RE.search(cleaned)
        if not match:
            continue
        value_raw = match.group(1).replace(" ", "").replace(",", ".")
        try:
            value = float(value_raw)
        except ValueError:
            continue
        prices.append(value)
        price_texts.append(cleaned)
        if "₽" in cleaned:
            currencies.add("₽")
        elif "$" in cleaned:
            currencies.add("$")
        elif "€" in cleaned:
            currencies.add("€")
    currency = currencies.pop() if len(currencies) == 1 else None
    return prices, currency, price_texts


def _extract_description(soup: BeautifulSoup) -> str | None:
    selectors = [
        ".lot-desc",
        ".lot-description",
        "#lot-desc",
        ".lot-view__desc",
        ".lot-view-description",
        ".tc-lot__description",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return str(meta.get("content")).strip() or None
    return None


@router.post("/plugins/price-dumper/scrape", response_model=PriceDumpResponse)
def scrape_price_dumper(
    payload: PriceDumpRequest,
    _user=Depends(get_current_user),
) -> PriceDumpResponse:
    try:
        response = requests.get(
            str(payload.url),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch FunPay page: {exc}") from exc

    soup = BeautifulSoup(response.text, "lxml")
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    heading = soup.find("h1")
    if heading and heading.get_text(strip=True):
        title = heading.get_text(strip=True)

    description = _extract_description(soup)

    price_nodes = soup.select(
        ".price, .tc-price, .lot-price, .payment-price, .lot-view-price, .tc-lot__price"
    )
    price_texts = [node.get_text(" ", strip=True) for node in price_nodes]
    prices, currency, extracted_texts = _extract_prices(price_texts)

    return PriceDumpResponse(
        url=str(payload.url),
        title=title,
        description=description,
        prices=prices,
        currency=currency,
        price_texts=extracted_texts,
    )
