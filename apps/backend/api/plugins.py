from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from api.deps import get_current_user
from db.mysql import get_base_connection


router = APIRouter()
logger = logging.getLogger("backend.price_dumper")

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
    url: str | None = None


class PriceDumpAnalysisResponse(BaseModel):
    recommended_price: float | None = None
    currency: str | None = None
    lowest_price: float | None = None
    second_price: float | None = None
    price_count: int = 0
    analysis: str
    model: str | None = None


class PriceDumpHistoryItem(BaseModel):
    created_at: str
    avg_price: float | None = None
    median_price: float | None = None
    recommended_price: float | None = None
    lowest_price: float | None = None
    second_price: float | None = None
    price_count: int = 0
    currency: str | None = None


class PriceDumpHistoryResponse(BaseModel):
    url: str | None = None
    items: list[PriceDumpHistoryItem]


class PriceDumpRefreshResponse(BaseModel):
    ok: bool
    processed: int = 0
    urls: list[str] = []


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
    tiers = sorted(set(sorted_prices))
    try:
        target_tier = int(os.getenv("PRICE_DUMPER_TARGET_TIER", "3"))
    except Exception:
        target_tier = 3
    target_tier = max(1, min(target_tier, len(tiers)))

    try:
        blend = float(os.getenv("PRICE_DUMPER_MEDIAN_BLEND", "0.35"))
    except Exception:
        blend = 0.35
    blend = max(0.0, min(blend, 1.0))

    try:
        step = float(os.getenv("PRICE_DUMPER_STEP", "0.01"))
    except Exception:
        step = 0.01
    if step <= 0:
        step = 0.01

    base = tiers[target_tier - 1]
    anchor = base + step

    mid = len(sorted_prices) // 2
    if len(sorted_prices) % 2 == 0:
        median = (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    else:
        median = sorted_prices[mid]

    if median and median > anchor and blend > 0:
        suggested = anchor + (median - anchor) * blend
    else:
        suggested = anchor

    if suggested < anchor:
        suggested = anchor

    return round(suggested + 1e-9, 2), lowest, second


def _format_price(value: float | None, currency: str | None) -> str:
    if value is None:
        return "-"
    unit = currency or "RUB"
    return f"{value:.2f} {unit}"


def _build_analysis_text(
    prices: list[float],
    *,
    currency: str | None,
    suggested: float | None,
    lowest: float | None,
    second: float | None,
) -> str:
    if not prices:
        return "No prices to analyze."
    sorted_prices = sorted(prices)
    total = len(sorted_prices)
    avg = sum(sorted_prices) / total if total else 0.0
    mid = total // 2
    if total % 2 == 0:
        median = (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    else:
        median = sorted_prices[mid]
    tiers = len(set(sorted_prices))
    unit = currency or "RUB"
    return "\n".join(
        [
            "Competitor price analysis:",
            "",
            f"- Prices in 0-50: {total}",
            f"- Average price: {avg:.2f} {unit}",
            f"- Median price: {median:.2f} {unit}",
            f"- Lowest price: {lowest:.2f} {unit}" if lowest is not None else "- Lowest price: -",
            f"- Second price: {second:.2f} {unit}" if second is not None else "- Second price: -",
            f"- Price tiers: {tiers}",
            "",
            "Price recommendation:",
            "",
            f"- Suggested price: { _format_price(suggested, currency) } (after cheapest tiers, no lowballing).",
            "Summary: Slightly above the cheapest cluster and closer to the market median.",
        ]
    )


def _format_prices(prices: list[float], limit: int = 500) -> str:
    limited = prices[:limit]
    return ", ".join(f"{price:.2f}" for price in limited)


def _filter_prices(prices: list[float], min_price: float = 0.0, max_price: float = 50.0) -> list[float]:
    return [price for price in prices if min_price <= price <= max_price]


def _compute_stats(prices: list[float]) -> tuple[float | None, float | None]:
    if not prices:
        return None, None
    sorted_prices = sorted(prices)
    avg = sum(sorted_prices) / len(sorted_prices)
    mid = len(sorted_prices) // 2
    if len(sorted_prices) % 2 == 0:
        median = (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    else:
        median = sorted_prices[mid]
    return avg, median


def _upsert_price_dumper_setting(user_id: int, url: str, interval_hours: int = 24) -> None:
    if not url:
        return
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        next_run = datetime.utcnow() + timedelta(hours=int(interval_hours))
        cursor.execute(
            """
            INSERT INTO price_dumper_settings (user_id, url, enabled, interval_hours, next_run_at)
            VALUES (%s, %s, 1, %s, %s)
            ON DUPLICATE KEY UPDATE
                enabled = VALUES(enabled),
                interval_hours = VALUES(interval_hours)
            """,
            (int(user_id), url[:512], int(interval_hours), next_run),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_price_dumper_history(
    *,
    user_id: int,
    url: str,
    currency: str | None,
    avg_price: float | None,
    median_price: float | None,
    recommended_price: float | None,
    lowest_price: float | None,
    second_price: float | None,
    price_count: int,
) -> None:
    if not url:
        return
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO price_dumper_history (
                user_id, url, avg_price, median_price, recommended_price,
                lowest_price, second_price, price_count, currency
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(user_id),
                url[:512],
                avg_price,
                median_price,
                recommended_price,
                lowest_price,
                second_price,
                int(price_count),
                currency,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _load_latest_price_dumper_url(user_id: int) -> str | None:
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT url
            FROM price_dumper_settings
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cursor.fetchone()
        return str(row["url"]) if row and row.get("url") else None
    finally:
        conn.close()


def _seed_price_dumper_settings_from_lots(user_id: int | None = None) -> int:
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                """
                INSERT IGNORE INTO price_dumper_settings (user_id, url, enabled, interval_hours, next_run_at)
                SELECT DISTINCT l.user_id, LEFT(l.lot_url, 512), 1, 24, NULL
                FROM lots l
                WHERE l.user_id = %s
                  AND l.lot_url IS NOT NULL
                  AND l.lot_url <> ''
                  AND l.lot_url LIKE %s
                """,
                (int(user_id), "%funpay.com/%"),
            )
        else:
            cursor.execute(
                """
                INSERT IGNORE INTO price_dumper_settings (user_id, url, enabled, interval_hours, next_run_at)
                SELECT DISTINCT l.user_id, LEFT(l.lot_url, 512), 1, 24, NULL
                FROM lots l
                WHERE l.lot_url IS NOT NULL
                  AND l.lot_url <> ''
                  AND l.lot_url LIKE %s
                """,
                ("%funpay.com/%",),
            )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def _fetch_price_dumper_urls(user_id: int, limit: int = 5) -> list[str]:
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT url
            FROM price_dumper_settings
            WHERE user_id = %s AND enabled = 1
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (int(user_id), int(limit)),
        )
        rows = cursor.fetchall() or []
        return [str(row.get("url") or "") for row in rows if row.get("url")]
    finally:
        conn.close()


def _fetch_price_dumper_history(user_id: int, url: str, days: int = 30) -> list[PriceDumpHistoryItem]:
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT avg_price, median_price, recommended_price, lowest_price, second_price,
                   price_count, currency, created_at
            FROM price_dumper_history
            WHERE user_id = %s AND url = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY created_at ASC
            """,
            (int(user_id), url[:512], int(max(1, min(days, 365)))),
        )
        rows = cursor.fetchall() or []
        items: list[PriceDumpHistoryItem] = []
        for row in rows:
            created_at = row.get("created_at")
            items.append(
                PriceDumpHistoryItem(
                    created_at=str(created_at) if created_at is not None else "",
                    avg_price=float(row["avg_price"]) if row.get("avg_price") is not None else None,
                    median_price=float(row["median_price"]) if row.get("median_price") is not None else None,
                    recommended_price=float(row["recommended_price"]) if row.get("recommended_price") is not None else None,
                    lowest_price=float(row["lowest_price"]) if row.get("lowest_price") is not None else None,
                    second_price=float(row["second_price"]) if row.get("second_price") is not None else None,
                    price_count=int(row.get("price_count") or 0),
                    currency=row.get("currency"),
                )
            )
        return items
    finally:
        conn.close()


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
    filtered_prices = _filter_prices(prices)
    sorted_prices = sorted(filtered_prices)
    list_limit = int(os.getenv("GROQ_PRICE_LIST_LIMIT", "500"))
    prompt = (
        "You analyze FunPay market prices. Provide 2-4 short bullets and a brief summary.\n"
        "Do not suggest any price lower than recommended_price.\n"
        "Do not suggest ranges; output a single recommended price.\n"
        "Data:\n"
        f"- Total prices: {len(prices)}\n"
        f"- Prices in 0-50: {len(filtered_prices)}\n"
        f"- Price list (0-50, max {list_limit}): {_format_prices(sorted_prices, list_limit)}\n"
        f"- Currency: {currency or 'unknown'}\n"
        f"- Lowest price: {lowest_price}\n"
        f"- Second price: {second_price}\n"
        f"- Recommended price: {recommended_price}\n"
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 250,
        "top_p": 0.9,
        "messages": [
            {"role": "system", "content": "You help a seller choose a competitive price without lowballing."},
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


def _scrape_price_dumper_url(url: str, rent_only: bool) -> PriceDumpResponse:
    try:
        response = requests.get(
            str(url),
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
    items = _extract_items(soup, rent_only)

    return PriceDumpResponse(
        url=str(url),
        title=title,
        description=description,
        prices=prices_sorted,
        currency=currency,
        price_texts=extracted_texts,
        labels=labels,
        items=items,
    )


@router.post("/plugins/price-dumper/scrape", response_model=PriceDumpResponse)
def scrape_price_dumper(
    payload: PriceDumpRequest,
    _user=Depends(get_current_user),
) -> PriceDumpResponse:
    result = _scrape_price_dumper_url(str(payload.url), payload.rent_only)
    try:
        _upsert_price_dumper_setting(int(_user.id), result.url)
    except Exception:
        logger.debug("Price dumper setting upsert failed.", exc_info=True)
    return result


@router.post("/plugins/price-dumper/analyze", response_model=PriceDumpAnalysisResponse)
def analyze_price_dumper(
    payload: PriceDumpAnalysisRequest,
    _user=Depends(get_current_user),
) -> PriceDumpAnalysisResponse:
    prices = [item.price for item in payload.items if item.price is not None]
    if not prices:
        raise HTTPException(status_code=400, detail="No prices provided for analysis.")
    filtered_prices = _filter_prices(prices)
    if not filtered_prices:
        raise HTTPException(status_code=400, detail="No prices in the 0-50 range for analysis.")
    recommended_price, lowest_price, second_price = _suggest_price(filtered_prices)
    avg_price, median_price = _compute_stats(filtered_prices)
    use_groq_flag = os.getenv("PRICE_DUMPER_USE_GROQ", "").strip().lower()
    if use_groq_flag in {"0", "false", "no", "off"}:
        use_groq = False
    elif use_groq_flag in {"1", "true", "yes", "on"}:
        use_groq = True
    else:
        use_groq = bool(os.getenv("GROQ_API_KEY"))
    if use_groq:
        analysis, model = _analyze_prices_with_groq(
            prices=sorted(filtered_prices),
            currency=payload.currency,
            recommended_price=recommended_price,
            lowest_price=lowest_price,
            second_price=second_price,
        )
    else:
        analysis = _build_analysis_text(
            sorted(filtered_prices),
            currency=payload.currency,
            suggested=recommended_price,
            lowest=lowest_price,
            second=second_price,
        )
        model = None
    if payload.url:
        try:
            _upsert_price_dumper_setting(int(_user.id), payload.url)
            _insert_price_dumper_history(
                user_id=int(_user.id),
                url=payload.url,
                currency=payload.currency,
                avg_price=avg_price,
                median_price=median_price,
                recommended_price=recommended_price,
                lowest_price=lowest_price,
                second_price=second_price,
                price_count=len(filtered_prices),
            )
        except Exception:
            logger.debug("Price dumper history insert failed.", exc_info=True)
    return PriceDumpAnalysisResponse(
        recommended_price=recommended_price,
        currency=payload.currency,
        lowest_price=lowest_price,
        second_price=second_price,
        price_count=len(filtered_prices),
        analysis=analysis,
        model=model,
    )


@router.get("/plugins/price-dumper/history", response_model=PriceDumpHistoryResponse)
def price_dumper_history(
    url: str | None = None,
    days: int = 30,
    _user=Depends(get_current_user),
) -> PriceDumpHistoryResponse:
    try:
        _seed_price_dumper_settings_from_lots(int(_user.id))
    except Exception:
        logger.debug("Price dumper settings seed failed.", exc_info=True)
    if not url:
        url = _load_latest_price_dumper_url(int(_user.id))
    if not url:
        return PriceDumpHistoryResponse(url=None, items=[])
    items = _fetch_price_dumper_history(int(_user.id), url, days=days)
    return PriceDumpHistoryResponse(url=url, items=items)


@router.post("/plugins/price-dumper/refresh", response_model=PriceDumpRefreshResponse)
def price_dumper_refresh(_user=Depends(get_current_user)) -> PriceDumpRefreshResponse:
    try:
        _seed_price_dumper_settings_from_lots(int(_user.id))
    except Exception:
        logger.debug("Price dumper settings seed failed.", exc_info=True)
    limit_env = os.getenv("PRICE_DUMPER_REFRESH_LIMIT", "3")
    try:
        limit = int(limit_env)
    except ValueError:
        limit = 3
    limit = max(1, min(limit, 10))
    urls = _fetch_price_dumper_urls(int(_user.id), limit=limit)
    processed = 0
    for url in urls:
        if not url:
            continue
        try:
            _execute_price_dumper_job(int(_user.id), url, use_groq=False)
            processed += 1
        except Exception:
            logger.debug("Price dumper refresh failed for %s.", url, exc_info=True)
    return PriceDumpRefreshResponse(ok=True, processed=processed, urls=urls[:processed])


_PRICE_DUMPER_THREAD: threading.Thread | None = None
_PRICE_DUMPER_LOCK = threading.Lock()


def _price_dumper_should_run() -> bool:
    flag = os.getenv("PRICE_DUMPER_SCHEDULER", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def start_price_dumper_scheduler() -> None:
    global _PRICE_DUMPER_THREAD
    if not _price_dumper_should_run():
        return
    with _PRICE_DUMPER_LOCK:
        if _PRICE_DUMPER_THREAD and _PRICE_DUMPER_THREAD.is_alive():
            return
        thread = threading.Thread(target=_price_dumper_scheduler_loop, daemon=True)
        _PRICE_DUMPER_THREAD = thread
        thread.start()


def _price_dumper_scheduler_loop() -> None:
    poll_seconds = int(os.getenv("PRICE_DUMPER_POLL_SECONDS", "300"))
    while True:
        try:
            _run_due_price_dumper_jobs()
        except Exception:
            logger.exception("Price dumper scheduler failed.")
        time.sleep(max(30, poll_seconds))


def _run_due_price_dumper_jobs(limit: int = 10) -> None:
    try:
        _seed_price_dumper_settings_from_lots()
    except Exception:
        logger.debug("Price dumper settings sync failed.", exc_info=True)
    conn = get_base_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, user_id, url, interval_hours
            FROM price_dumper_settings
            WHERE enabled = 1 AND (next_run_at IS NULL OR next_run_at <= NOW())
            ORDER BY next_run_at ASC
            LIMIT %s
            """,
            (int(limit),),
        )
        rows = cursor.fetchall() or []
    finally:
        conn.close()

    for row in rows:
        setting_id = int(row.get("id") or 0)
        user_id = int(row.get("user_id") or 0)
        url = str(row.get("url") or "")
        interval_hours = int(row.get("interval_hours") or 24)
        if setting_id <= 0 or user_id <= 0 or not url:
            continue
        if not _claim_price_dumper_job(setting_id, interval_hours):
            continue
        _execute_price_dumper_job(user_id, url)


def _claim_price_dumper_job(setting_id: int, interval_hours: int) -> bool:
    conn = get_base_connection()
    try:
        cursor = conn.cursor()
        next_run = datetime.utcnow() + timedelta(hours=int(interval_hours))
        cursor.execute(
            """
            UPDATE price_dumper_settings
            SET last_run_at = NOW(), next_run_at = %s
            WHERE id = %s AND enabled = 1 AND (next_run_at IS NULL OR next_run_at <= NOW())
            """,
            (next_run, int(setting_id)),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def _execute_price_dumper_job(user_id: int, url: str, *, use_groq: bool | None = None) -> None:
    try:
        result = _scrape_price_dumper_url(url, True)
    except Exception as exc:
        logger.warning("Price dumper scrape failed for %s: %s", url, exc)
        return

    prices = [item.price for item in result.items if item.price is not None]
    filtered = _filter_prices(prices)
    if not filtered:
        logger.info("Price dumper skipped (no prices) for %s", url)
        return

    recommended_price, lowest_price, second_price = _suggest_price(filtered)
    avg_price, median_price = _compute_stats(filtered)

    if use_groq is None:
        use_groq_flag = os.getenv("PRICE_DUMPER_USE_GROQ", "").strip().lower()
        if use_groq_flag in {"0", "false", "no", "off"}:
            use_groq = False
        elif use_groq_flag in {"1", "true", "yes", "on"}:
            use_groq = True
        else:
            use_groq = bool(os.getenv("GROQ_API_KEY"))
    if use_groq:
        try:
            _analyze_prices_with_groq(
                prices=sorted(filtered),
                currency=result.currency,
                recommended_price=recommended_price,
                lowest_price=lowest_price,
                second_price=second_price,
            )
        except Exception:
            logger.debug("Price dumper AI analysis failed for %s.", url, exc_info=True)

    try:
        _insert_price_dumper_history(
            user_id=int(user_id),
            url=url,
            currency=result.currency,
            avg_price=avg_price,
            median_price=median_price,
            recommended_price=recommended_price,
            lowest_price=lowest_price,
            second_price=second_price,
            price_count=len(filtered),
        )
    except Exception:
        logger.debug("Price dumper history insert failed for %s.", url, exc_info=True)
