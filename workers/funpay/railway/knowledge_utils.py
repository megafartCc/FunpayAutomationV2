from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any

from .constants import COMMANDS_RU

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9]+")


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text or "")}


DEFAULT_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "id": "commands",
        "keywords": [
            "команд",
            "commands",
            "help",
            "помощ",
            "умеешь",
            "можешь",
            "список",
            "what can you do",
        ],
        "content": COMMANDS_RU,
    },
    {
        "id": "rent_flow",
        "keywords": [
            "аренд",
            "аренда",
            "rent",
            "взять",
            "как взять",
            "как арендовать",
            "оплат",
        ],
        "content": (
            "Как арендовать: выберите лот, оплатите заказ, затем используйте команды:\n"
            "- !акк — получить данные аккаунта\n"
            "- !код — получить Steam Guard (таймер аренды стартует после первого кода)\n"
            "- !сток — посмотреть свободные аккаунты\n"
            "- !продлить <часы> <ID_аккаунта> — продлить аренду\n"
        ),
    },
    {
        "id": "stock",
        "keywords": ["сток", "free", "available", "свобод", "налич", "аккаунт"],
        "content": "Свободные аккаунты: используйте команду !сток.",
    },
    {
        "id": "code",
        "keywords": ["код", "steam", "guard", "steam guard"],
        "content": "Код Steam Guard выдаётся командой !код. Таймер аренды стартует после первого кода.",
    },
    {
        "id": "pause",
        "keywords": ["пауза", "замороз", "freeze", "продолжить", "resume"],
        "content": "Пауза аренды: !пауза <ID> (на 1 час). Возобновить раньше: !продолжить <ID>.",
    },
    {
        "id": "replace",
        "keywords": ["замена", "replace", "лпзамена"],
        "content": "Замена аккаунта: !лпзамена <ID> (доступно в течение 10 минут после !код).",
    },
    {
        "id": "admin_refund",
        "keywords": ["админ", "admin", "refund", "возврат", "деньги"],
        "content": "Связаться с продавцом/вопросы возврата: используйте !админ.",
    },
]


def _load_custom_knowledge(path: str) -> list[dict[str, Any]]:
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("items", [])
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        keywords = item.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        cleaned.append(
            {
                "id": item.get("id") or "custom",
                "keywords": [str(k) for k in keywords if str(k).strip()],
                "content": content.strip(),
            }
        )
    return cleaned


@lru_cache(maxsize=1)
def _knowledge_items() -> list[dict[str, Any]]:
    items = list(DEFAULT_KNOWLEDGE)
    custom_path = os.getenv("AI_KNOWLEDGE_PATH", "").strip()
    items.extend(_load_custom_knowledge(custom_path))
    return items


def build_knowledge_context(question: str, *, max_chars: int, max_items: int) -> str | None:
    if not question:
        return None
    if os.getenv("AI_KNOWLEDGE_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return None
    tokens = _tokenize(question)
    if not tokens:
        return None
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in _knowledge_items():
        keywords = item.get("keywords", [])
        keyword_tokens = _tokenize(" ".join(keywords))
        overlap = len(tokens & keyword_tokens)
        score = overlap * 3
        for kw in keywords:
            if kw and kw.lower() in question.lower():
                score += 2
        if score > 0:
            scored.append((score, item))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    parts: list[str] = []
    for _, item in scored[: max(1, max_items)]:
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        parts.append(content)
    if not parts:
        return None
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text
