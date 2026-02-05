from __future__ import annotations

import os
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
    rent_only: bool = Field(True, description="Only include rent offers")


class PriceDumpItem(BaseModel):
    title: str
    price: float
    currency: str | None = None
    url: str | None = None
    raw_price: str | None = None
    rent: bool = False


class PriceDumpResponse(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    prices: list[float]
    currency: str | None = None
    price_texts: list[str]
    labels: list[str]
    items: list[PriceDumpItem]

class PriceDumpAnalysisRequest(BaseModel):
    items: list[PriceDumpItem]
    currency: str | None = None


class PriceDumpAnalysisResponse(BaseModel):
    recommended_price: float | None = None
    currency: str | None = None
    lowest_price: float | None = None
    second_price: float | None = None
    price_count: int = 0
    analysis: str
    model: str | None = None


_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"

def _extract_prices(texts: Iterable[str]) -> tuple[list[float], str | None, list[str], list[str]]:
    prices: list[float] = []
    price_texts: list[str] = []
    labels: list[str] = []
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
        labels.append(cleaned.split("·")[0].strip() or cleaned)
        if "₽" in cleaned:
            currencies.add("₽")
        elif "$" in cleaned:
            currencies.add("$")
        elif "€" in cleaned:
            currencies.add("€")
    currency = currencies.pop() if len(currencies) == 1 else None
    return prices, currency, price_texts, labels


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


def _is_rent_offer(text: str) -> bool:
    return "аренда" in text.lower()


def _extract_items(soup: BeautifulSoup, rent_only: bool) -> list[PriceDumpItem]:
    selectors = [
        ".tc-item",
        ".lot-item",
        ".offer-list .offer",
        ".lot-card",
        ".tc-lot",
        ".lot",
        ".tc",
        ".tc-item-list .tc-item",
        ".offer-item",
    ]
    items: list[PriceDumpItem] = []
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if rent_only and not _is_rent_offer(text):
                continue
            title_node = node.select_one(
                ".tc-item-title, .lot-title, .offer-title, .tc-lot__title, .lot-name, .tc-title, a"
            )
            title = title_node.get_text(" ", strip=True) if title_node else text[:120]
            if rent_only and not _is_rent_offer(title):
                continue
            price_node = node.select_one(".price, .tc-price, .lot-price, .payment-price, .lot-view-price, .tc-lot__price")
            price_text = price_node.get_text(" ", strip=True) if price_node else ""
            prices, currency, _, _ = _extract_prices([price_text])
            if not prices:
                continue
            url = None
            if title_node and title_node.name == "a":
                url = title_node.get("href")
            items.append(
                PriceDumpItem(
                    title=title,
                    price=prices[0],
                    currency=currency,
                    url=url,
                    raw_price=price_text or None,
                    rent=_is_rent_offer(text),
                )
            )
    items.sort(key=lambda item: item.price)
    return items


def _suggest_price(prices: list[float]) -> tuple[float | None, float | None, float | None]:
    if not prices:
        return None, None, None
    sorted_prices = sorted(prices)
    lowest = sorted_prices[0]
    second = sorted_prices[1] if len(sorted_prices) > 1 else None
    if second is not None and second > lowest:
        gap = second - lowest
        delta = max(gap * 0.15, 0.01)
        suggested = min(lowest + delta, second - 0.01)
        if suggested <= lowest:
            suggested = lowest + 0.01
    else:
        suggested = lowest * 0.99
    return suggested, lowest, second


def _format_prices(prices: list[float]) -> str:
    return ", ".join(f"{price:.2f}" for price in prices[:50])


def _analyze_prices_with_groq(
    prices: list[float],
    currency: str | None,
    recommended_price: float | None,
    lowest_price: float | None,
    second_price: float | None,
) -> tuple[str, str | None]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured.")
    model = os.getenv("GROQ_MODEL", _DEFAULT_GROQ_MODEL)
    prompt = (
        "Ты аналитик рынка FunPay. На основе цен конкурентов дай краткий анализ и рекомендацию цены,\n"
        "чтобы быть почти первым в списке (рядом с самым дешевым предложением).\n"
        "Сформулируй ответ кратко на русском: 2-4 пункта и короткая итоговая строка.\n"
        "Данные:\n"
        f"- Цены: { _format_prices(prices) }\n"
        f"- Валюта: {currency or 'не указана'}\n"
        f"- Минимальная цена: {lowest_price}\n"
        f"- Вторая цена: {second_price}\n"
        f"- Рекомендованная цена: {recommended_price}\n"
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 350,
        "top_p": 0.9,
        "messages": [
            {"role": "system", "content": "Ты помогаешь продавцу подобрать конкурентную цену."},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        response = requests.post(
            _GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", None) if hasattr(exc, "response") else None
        message = f"Groq API request failed: {exc}"
        if detail:
            message = f"{message} | {detail}"
        raise HTTPException(status_code=502, detail=message) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Groq API response is not valid JSON.") from exc
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not content:
        raise HTTPException(status_code=502, detail="Groq API returned an empty response.")
    return content, model


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
    prices, currency, extracted_texts, labels = _extract_prices(price_texts)
    prices_sorted = sorted(prices)
    items = _extract_items(soup, payload.rent_only)

    return PriceDumpResponse(
        url=str(payload.url),
        title=title,
        description=description,
        prices=prices_sorted,
        currency=currency,
        price_texts=extracted_texts,
        labels=labels,
        items=items,
    )


@router.post("/plugins/price-dumper/analyze", response_model=PriceDumpAnalysisResponse)
def analyze_price_dumper(
    payload: PriceDumpAnalysisRequest,
    _user=Depends(get_current_user),
) -> PriceDumpAnalysisResponse:
    prices = [item.price for item in payload.items if item.price is not None]
    if not prices:
        raise HTTPException(status_code=400, detail="No prices provided for analysis.")
    recommended_price, lowest_price, second_price = _suggest_price(prices)
    analysis, model = _analyze_prices_with_groq(
        prices=sorted(prices),
        currency=payload.currency,
        recommended_price=recommended_price,
        lowest_price=lowest_price,
        second_price=second_price,
    )
    return PriceDumpAnalysisResponse(
        recommended_price=recommended_price,
        currency=payload.currency,
        lowest_price=lowest_price,
        second_price=second_price,
        price_count=len(prices),
        analysis=analysis,
        model=model,
    )
