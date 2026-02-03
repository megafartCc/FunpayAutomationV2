from __future__ import annotations

import os
import re
from typing import Iterable

import mysql.connector

from .db_utils import resolve_workspace_mysql_cfg, table_exists

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9]+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


def _ensure_memory_table(cursor: mysql.connector.cursor.MySQLCursor) -> None:
    if table_exists(cursor, "chat_ai_memory"):
        return
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_ai_memory (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            workspace_id BIGINT NULL,
            chat_id BIGINT NOT NULL,
            key_text VARCHAR(255) NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP NULL,
            INDEX idx_ai_memory_chat (user_id, workspace_id, chat_id),
            INDEX idx_ai_memory_key (key_text(191))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )


def _memory_enabled() -> bool:
    return os.getenv("AI_MEMORY_ENABLED", "1").strip().lower() not in {"0", "false", "no"}


def _memory_store_enabled() -> bool:
    return os.getenv("AI_MEMORY_STORE", "1").strip().lower() not in {"0", "false", "no"}


def _memory_fetch_limit() -> int:
    try:
        return max(1, int(os.getenv("AI_MEMORY_FETCH_LIMIT", "4")))
    except Exception:
        return 4


def _memory_max_per_chat() -> int:
    try:
        return max(10, int(os.getenv("AI_MEMORY_MAX_PER_CHAT", "120")))
    except Exception:
        return 120


def _memory_min_chars() -> int:
    try:
        return max(8, int(os.getenv("AI_MEMORY_MIN_CHARS", "24")))
    except Exception:
        return 24


def should_store_memory(user_text: str, ai_text: str) -> bool:
    if not _memory_enabled() or not _memory_store_enabled():
        return False
    if not user_text or not ai_text:
        return False
    if len(user_text.strip()) < _memory_min_chars():
        return False
    lowered = user_text.strip().lower()
    if lowered.startswith("!"):
        return False
    if any(token in lowered for token in ("http://", "https://")):
        return False
    if len(ai_text.strip()) < _memory_min_chars():
        return False
    return True


def _build_key_text(tokens: Iterable[str], max_len: int = 200) -> str:
    seen = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
        if len(seen) >= 12:
            break
    text = " ".join(seen)
    return text[:max_len]


def store_memory(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    user_text: str,
    ai_text: str,
) -> None:
    if not should_store_memory(user_text, ai_text):
        return
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        _ensure_memory_table(cursor)
        tokens = _tokenize(f"{user_text} {ai_text}")
        key_text = _build_key_text(tokens)
        content = f"Q: {user_text.strip()}\nA: {ai_text.strip()}"
        cursor.execute(
            """
            INSERT INTO chat_ai_memory (user_id, workspace_id, chat_id, key_text, content)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
                int(chat_id),
                key_text,
                content,
            ),
        )
        conn.commit()
        max_rows = _memory_max_per_chat()
        if max_rows > 0:
            cursor.execute(
                f"""
                DELETE FROM chat_ai_memory
                WHERE user_id = %s AND workspace_id <=> %s AND chat_id = %s
                  AND id NOT IN (
                    SELECT id FROM (
                      SELECT id FROM chat_ai_memory
                      WHERE user_id = %s AND workspace_id <=> %s AND chat_id = %s
                      ORDER BY created_at DESC
                      LIMIT {max_rows}
                    ) AS t
                  )
                """,
                (
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    int(chat_id),
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    int(chat_id),
                ),
            )
            conn.commit()
    finally:
        conn.close()


def fetch_memory_context(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    query: str,
) -> str | None:
    if not _memory_enabled():
        return None
    tokens = _tokenize(query)
    if not tokens:
        return None
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        _ensure_memory_table(cursor)
        limit = _memory_fetch_limit()
        clauses = []
        params: list = [
            int(user_id),
            int(workspace_id) if workspace_id is not None else None,
            int(chat_id),
        ]
        for token in tokens[:6]:
            clauses.append("(content LIKE %s OR key_text LIKE %s)")
            like = f"%{token}%"
            params.extend([like, like])
        where_clause = " OR ".join(clauses) if clauses else "1=0"
        cursor.execute(
            f"""
            SELECT id, content
            FROM chat_ai_memory
            WHERE user_id = %s AND workspace_id <=> %s AND chat_id = %s
              AND ({where_clause})
            ORDER BY last_used_at DESC, created_at DESC
            LIMIT %s
            """,
            tuple(params + [limit]),
        )
        rows = cursor.fetchall() or []
        if not rows:
            return None
        ids = [int(row["id"]) for row in rows if row.get("id") is not None]
        if ids:
            cursor.execute(
                f"UPDATE chat_ai_memory SET last_used_at = NOW() WHERE id IN ({','.join(['%s'] * len(ids))})",
                tuple(ids),
            )
            conn.commit()
        parts = [row.get("content") for row in rows if row.get("content")]
        return "\n\n".join(parts) if parts else None
    finally:
        conn.close()
