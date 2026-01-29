from __future__ import annotations

import logging
import os

import mysql.connector
import requests


def normalize_proxy_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return f"socks5://{value}"


def build_proxy_config(raw: str | None) -> dict | None:
    url = normalize_proxy_url(raw)
    if not url:
        return None
    return {"http": url, "https": url}


def _fetch_public_ip(proxies: dict | None) -> str | None:
    try:
        resp = requests.get("https://api.ipify.org", proxies=proxies, timeout=10)
        resp.raise_for_status()
        return resp.text.strip()
    except Exception:
        return None


def ensure_proxy_isolated(
    logger: logging.Logger,
    proxy_url: str | None,
    label: str,
    *,
    fatal: bool = False,
) -> dict | None:
    if not proxy_url:
        msg = f"{label} Missing proxy_url, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    proxy_cfg = build_proxy_config(proxy_url)
    if not proxy_cfg:
        msg = f"{label} Invalid proxy_url, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    direct_ip = _fetch_public_ip({"http": None, "https": None})
    if not direct_ip:
        msg = f"{label} Direct IP check failed, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    proxy_ip = _fetch_public_ip(proxy_cfg)
    if not proxy_ip:
        msg = f"{label} Proxy IP check failed, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    if proxy_ip == direct_ip:
        msg = f"{label} Proxy IP matches direct IP, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    logger.info("%s Proxy check passed (direct/proxy IP differ).", label)
    return proxy_cfg


def fetch_workspaces(mysql_cfg: dict) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT w.id AS workspace_id, w.name AS workspace_name, w.golden_key, w.proxy_url,
                   w.user_id, w.platform, u.username
            FROM workspaces w
            JOIN users u ON u.id = w.user_id
            WHERE w.platform = 'funpay'
              AND w.golden_key IS NOT NULL AND w.golden_key != ''
            ORDER BY w.user_id, w.id
            """
        )
        rows = cursor.fetchall()
        return list(rows or [])
    finally:
        conn.close()
