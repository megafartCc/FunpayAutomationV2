from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Iterable, Tuple
from urllib.parse import urlparse

import mysql.connector


DEFAULT_SYSTEM_PROMPT = (
    "Вы — дружелюбный помощник поддержки FunPay. "
    "Отвечайте кратко, вежливо и по делу. "
    "На привет отвечайте дружелюбно и предложите помощь. "
    "Сначала отвечайте на сообщение пользователя, а команды упоминайте только если это действительно помогает. "
    "Не перечисляйте все команды без запроса. Если запрос неясен — задайте короткий уточняющий вопрос."
)

SENSITIVE_KEYWORDS = (
    "пароль",
    "password",
    "логин",
    "login",
    "steam guard",
    "steamguard",
)


def _mysql_config() -> dict:
    url = os.getenv("MYSQL_URL", "").strip()
    host = os.getenv("MYSQLHOST", "").strip()
    port = os.getenv("MYSQLPORT", "").strip() or "3306"
    user = os.getenv("MYSQLUSER", "").strip()
    password = os.getenv("MYSQLPASSWORD", "").strip()
    database = os.getenv("MYSQLDATABASE", "").strip() or os.getenv("MYSQL_DATABASE", "").strip()

    if url:
        parsed = urlparse(url)
        host = parsed.hostname or host
        if parsed.port:
            port = str(parsed.port)
        user = parsed.username or user
        password = parsed.password or password
        if parsed.path and parsed.path != "/":
            database = parsed.path.lstrip("/")

    if not database:
        raise RuntimeError("MySQL database name missing. Set MYSQLDATABASE or MYSQL_DATABASE.")

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
    }


def _split_qa(content: str) -> Tuple[str, str] | None:
    if not content:
        return None
    marker = "\nA:"
    if marker not in content:
        return None
    q_part, a_part = content.split(marker, 1)
    if q_part.startswith("Q:"):
        q_part = q_part[2:]
    q = q_part.strip()
    a = a_part.strip()
    if not q or not a:
        return None
    return q, a


def _is_sensitive(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def _dedupe_pairs(pairs: Iterable[Tuple[str, str]]) -> list[Tuple[str, str]]:
    seen = set()
    unique = []
    for q, a in pairs:
        key = (q.strip().lower(), a.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append((q, a))
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="Export chat_ai_memory to JSONL for fine-tuning.")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--limit", type=int, default=2000, help="Max memory rows to export (0 = all)")
    parser.add_argument("--min-chars", type=int, default=24, help="Minimum length for Q and A")
    parser.add_argument("--workspace-id", type=int, default=None)
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--chat-id", type=int, default=None)
    parser.add_argument("--allow-sensitive", action="store_true", help="Include sensitive content")
    parser.add_argument("--dedupe", action="store_true", help="Remove duplicate Q/A pairs")
    parser.add_argument("--system-prompt", default=os.getenv("AI_TRAIN_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT))
    args = parser.parse_args()

    cfg = _mysql_config()
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        filters = []
        params = []
        if args.user_id is not None:
            filters.append("user_id = %s")
            params.append(int(args.user_id))
        if args.workspace_id is not None:
            filters.append("workspace_id <=> %s")
            params.append(int(args.workspace_id))
        if args.chat_id is not None:
            filters.append("chat_id = %s")
            params.append(int(args.chat_id))
        where_clause = " AND ".join(filters) if filters else "1=1"
        limit_clause = "" if args.limit == 0 else "LIMIT %s"
        if args.limit != 0:
            params.append(int(args.limit))
        cursor.execute(
            f"""
            SELECT content
            FROM chat_ai_memory
            WHERE {where_clause}
            ORDER BY created_at DESC
            {limit_clause}
            """,
            tuple(params),
        )
        rows = cursor.fetchall() or []
    finally:
        conn.close()

    pairs: list[Tuple[str, str]] = []
    for row in rows:
        content = row.get("content") if isinstance(row, dict) else None
        if not content:
            continue
        qa = _split_qa(str(content))
        if not qa:
            continue
        q, a = qa
        if len(q) < args.min_chars or len(a) < args.min_chars:
            continue
        if not args.allow_sensitive and (_is_sensitive(q) or _is_sensitive(a)):
            continue
        pairs.append((q, a))

    if args.dedupe:
        pairs = _dedupe_pairs(pairs)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for q, a in pairs:
            record = {
                "conversations": [
                    {"from": "system", "value": args.system_prompt},
                    {"from": "human", "value": q},
                    {"from": "gpt", "value": a},
                ]
            }
            f.write(json.dumps(record, ensure_ascii=True))
            f.write("\n")

    print(f"Exported {len(pairs)} items to {out_path}")


if __name__ == "__main__":
    main()
