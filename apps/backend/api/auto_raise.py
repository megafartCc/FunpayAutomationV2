from __future__ import annotations

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.auto_raise_repo import MySQLAutoRaiseRepo
from db.workspace_repo import MySQLWorkspaceRepo


logger = logging.getLogger("auto_raise")

router = APIRouter()
auto_raise_repo = MySQLAutoRaiseRepo()
workspace_repo = MySQLWorkspaceRepo()


class AutoRaiseSettingsResponse(BaseModel):
    enabled: bool
    categories: list[int]
    interval_hours: int


class AutoRaiseSettingsPayload(BaseModel):
    enabled: bool
    categories: list[int] = Field(default_factory=list)
    interval_hours: int = Field(1, ge=1, le=6)


class AutoRaiseHistoryItem(BaseModel):
    id: int
    workspace_id: int | None = None
    workspace_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    status: str
    message: str | None = None
    created_at: str | None = None


class AutoRaiseHistoryResponse(BaseModel):
    items: list[AutoRaiseHistoryItem]


class FunpayCategoryItem(BaseModel):
    id: int
    name: str
    game: str | None = None
    category: str | None = None
    server: str | None = None


class FunpayCategoriesResponse(BaseModel):
    items: list[FunpayCategoryItem]


def _normalize_proxy_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return f"socks5://{value}"


def _build_proxy_config(raw: str | None) -> dict | None:
    url = _normalize_proxy_url(raw)
    if not url:
        return None
    return {"http": url, "https": url}


def _select_funpay_workspace(user_id: int):
    workspaces = workspace_repo.list_by_user(user_id)
    funpay = [ws for ws in workspaces if (ws.platform or "funpay") == "funpay" and ws.golden_key]
    if not funpay:
        raise HTTPException(status_code=404, detail="No FunPay workspace found.")
    default_ws = next((ws for ws in funpay if ws.is_default), None)
    return default_ws or funpay[0]


def _extract_categories_from_html(html: str) -> dict[int, dict]:
    soup = BeautifulSoup(html, "lxml")
    items: dict[int, dict] = {}
    games_table = soup.find_all("div", {"class": "promo-game-list"})
    if games_table:
        games_table = games_table[1] if len(games_table) > 1 else games_table[0]
        blocks = games_table.find_all("div", {"class": "promo-game-item"})
    else:
        blocks = soup.select(".promo-game-item")

    for block in blocks:
        game_el = block.select_one(".game-title a") or block.select_one(".game-title")
        game_name = (game_el.text or "").strip() if game_el else ""
        if not game_name:
            game_name = "Unknown game"

        server_labels: dict[str, str] = {}
        for btn in block.select("button[data-id]"):
            data_id = (btn.get("data-id") or "").strip()
            if data_id:
                server_labels[data_id] = (btn.text or "").strip()

        for ul in block.select("ul.list-inline"):
            data_id = (ul.get("data-id") or "").strip()
            server = server_labels.get(data_id, "")
            game_label = f"{game_name} ({server})" if server else game_name
            for a in ul.select("a[href*='/lots/']"):
                href = a.get("href") or ""
                match = re.search(r"/lots/(\\d+)", href)
                if not match:
                    continue
                cid = int(match.group(1))
                cat_name = (a.text or "").strip() or f"Category {cid}"
                label = f"{game_label} - {cat_name}"
                if cid not in items:
                    items[cid] = {
                        "id": cid,
                        "name": label,
                        "game": game_label,
                        "category": cat_name,
                        "server": server or None,
                    }

    for a in soup.select("a[href*='/lots/']"):
        href = a.get("href") or ""
        match = re.search(r"/lots/(\\d+)", href)
        if not match:
            continue
        cid = int(match.group(1))
        if cid in items:
            continue
        cat_name = (a.text or "").strip() or f"Category {cid}"
        block = a.find_parent(class_="promo-game-item")
        game_el = None
        if block:
            game_el = block.select_one(".game-title a") or block.select_one(".game-title")
        game_name = (game_el.text or "").strip() if game_el else ""
        ul_parent = a.find_parent("ul", attrs={"data-id": True})
        server = None
        if ul_parent and block:
            data_id = (ul_parent.get("data-id") or "").strip()
            btn = block.select_one(f"button[data-id='{data_id}']")
            if btn:
                server = (btn.text or "").strip() or None
        game_label = f"{game_name} ({server})" if game_name and server else (game_name or "Unknown game")
        label = f"{game_label} - {cat_name}"
        items[cid] = {
            "id": cid,
            "name": label,
            "game": game_label,
            "category": cat_name,
            "server": server,
        }

    return items


def _fetch_funpay_categories_live(token: str, proxy: dict | None) -> list[dict]:
    urls = (
        "https://funpay.com/en/",
        "https://funpay.com/",
    )
    merged: dict[int, dict] = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    }

    def fetch_through(session_proxy: dict | None, label: str) -> None:
        with requests.Session() as session:
            session.cookies.set("golden_key", token, domain="funpay.com")
            if session_proxy:
                session.proxies.update(session_proxy)
            for url in urls:
                try:
                    resp = session.get(url, timeout=15, headers=headers, allow_redirects=True)
                    resp.raise_for_status()
                    if not resp.encoding:
                        resp.encoding = resp.apparent_encoding or "utf-8"
                except Exception as exc:
                    logger.warning("Category fetch failed (%s) for %s: %s", label, url, exc)
                    continue
                extracted = _extract_categories_from_html(resp.text)
                for cid, payload in extracted.items():
                    if cid not in merged:
                        merged[cid] = payload

    fetch_through(proxy, "proxy")
    fetch_through(None if proxy else None, "direct")

    return sorted(
        merged.values(),
        key=lambda x: (x.get("game") or "", x.get("category") or x.get("name") or "", x.get("id") or 0),
    )


def _build_funpay_categories(token: str, proxy: dict | None) -> list[dict]:
    live_items = _fetch_funpay_categories_live(token, proxy)
    merged: dict[int, dict] = {item["id"]: item for item in live_items if item.get("id")}

    games_with_categories = {
        (v.get("game") or "").strip()
        for v in merged.values()
        if v.get("category") and (v.get("game") or "").strip()
    }
    pruned = {
        cid: v
        for cid, v in merged.items()
        if not (
            (v.get("game") or "").strip() in games_with_categories
            and (not v.get("category") or v.get("category") == v.get("name"))
            or (
                not (v.get("game") or "").strip()
                and ((v.get("category") or "").strip() in games_with_categories
                     or (v.get("name") or "").strip() in games_with_categories)
            )
        )
    }

    for v in pruned.values():
        if not v.get("game") and not v.get("category"):
            name = (v.get("name") or "").strip()
            if " - " in name:
                game_label, cat_label = [part.strip() for part in name.split(" - ", 1)]
                if game_label and cat_label:
                    v["game"] = game_label
                    v["category"] = cat_label

    filtered = [
        v for v in pruned.values()
        if (v.get("game") or "").strip()
        and (v.get("category") or "").strip()
        and (v.get("category") or "").strip() != (v.get("game") or "").strip()
        and (v.get("category") or "").strip() != (v.get("name") or "").strip()
    ]

    if not filtered and merged:
        logger.warning("Category filter returned 0 items; falling back to unfiltered list")
        items = list(pruned.values())
    else:
        items = filtered

    items = sorted(
        items,
        key=lambda x: (x.get("game") or "", x.get("category") or x.get("name") or "", x.get("id") or 0),
    )
    return items


@router.get("/auto-raise/settings", response_model=AutoRaiseSettingsResponse)
def get_auto_raise_settings(user=Depends(get_current_user)) -> AutoRaiseSettingsResponse:
    settings = auto_raise_repo.get_settings(int(user.id))
    return AutoRaiseSettingsResponse(
        enabled=bool(settings.enabled),
        categories=settings.categories,
        interval_hours=max(1, min(int(settings.interval_hours), 6)),
    )


@router.post("/auto-raise/settings", response_model=AutoRaiseSettingsResponse)
def set_auto_raise_settings(payload: AutoRaiseSettingsPayload, user=Depends(get_current_user)) -> AutoRaiseSettingsResponse:
    settings = auto_raise_repo.upsert_settings(
        user_id=int(user.id),
        enabled=payload.enabled,
        categories=payload.categories,
        interval_hours=payload.interval_hours,
    )
    return AutoRaiseSettingsResponse(
        enabled=bool(settings.enabled),
        categories=settings.categories,
        interval_hours=max(1, min(int(settings.interval_hours), 6)),
    )


@router.get("/auto-raise/history", response_model=AutoRaiseHistoryResponse)
def list_auto_raise_history(
    limit: int = Query(120, ge=1, le=500),
    user=Depends(get_current_user),
) -> AutoRaiseHistoryResponse:
    rows = auto_raise_repo.list_history(int(user.id), limit=limit)
    return AutoRaiseHistoryResponse(items=[AutoRaiseHistoryItem(**row.__dict__) for row in rows])


@router.get("/funpay/categories", response_model=FunpayCategoriesResponse)
def funpay_categories(user=Depends(get_current_user)) -> FunpayCategoriesResponse:
    workspace = _select_funpay_workspace(int(user.id))
    token = workspace.golden_key
    proxy = _build_proxy_config(workspace.proxy_url)
    try:
        items = _build_funpay_categories(token, proxy)
    except Exception as exc:
        logger.warning("Category resolve failed: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to load categories from FunPay") from exc
    return FunpayCategoriesResponse(items=[FunpayCategoryItem(**item) for item in items])
