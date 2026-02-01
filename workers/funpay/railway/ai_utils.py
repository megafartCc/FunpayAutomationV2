from __future__ import annotations

import logging
import os
import re
from typing import Any

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_PROMPT = (
    "Вы — дружелюбный помощник поддержки FunPay. "
    "Отвечайте кратко, вежливо и по делу. "
    "На привет отвечайте дружелюбно и предложите помощь. "
    "Сначала отвечайте на сообщение пользователя, а команды упоминайте только если это действительно помогает. "
    "Не перечисляйте все команды без запроса. Если запрос неясен — задайте короткий уточняющий вопрос.\n\n"
    "Команды (упоминать по необходимости):\n"
    "!акк — данные аккаунта\n"
    "!код — код Steam Guard\n"
    "!сток — наличие аккаунтов\n"
    "!продлить <часы> <ID_аккаунта> — продлить аренду\n"
    "!пауза <ID> — пауза аренды на 1 час\n"
    "!продолжить <ID> — снять паузу раньше срока\n"
    "!админ — вызвать продавца\n"
    "!лпзамена <ID> — замена аккаунта (10 минут после !код)\n"
    "!отмена <ID> — отменить аренду"
)
CLARIFY_RESPONSE = "Не понял запрос. Пожалуйста, уточните, что вы имеете в виду."
_ALNUM_RE = re.compile(r"[A-Za-zА-Яа-я0-9]+")
_CODE_RE = re.compile(r"^[A-Za-z0-9]{3,12}$")


def _is_code_like(text: str) -> bool:
    cleaned = re.sub(r"\s+", "", text.strip())
    if not cleaned or not _CODE_RE.match(cleaned):
        return False
    return any(ch.isdigit() for ch in cleaned)


def _is_gibberish(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    tokens = _ALNUM_RE.findall(stripped)
    if not tokens:
        return True
    if len(tokens) == 1 and len(tokens[0]) <= 1:
        return True
    if len(tokens) >= 5:
        avg_len = sum(len(token) for token in tokens) / len(tokens)
        if avg_len <= 2.2:
            return True
    short_tokens = [token for token in tokens if len(token) <= 2]
    if len(tokens) >= 4 and len(short_tokens) / len(tokens) >= 0.7:
        return True
    return False


def _build_payload(
    user_text: str,
    *,
    sender: str | None,
    chat_name: str | None,
    context: str | None = None,
) -> dict[str, Any]:
    system_prompt = os.getenv("GROQ_SYSTEM_PROMPT", DEFAULT_PROMPT)
    user_prefix = f"Покупатель: {sender or '-'}\nЧат: {chat_name or '-'}\nСообщение: "
    if context:
        user_text = f"Context:\n{context}\n\nUser message:\n{user_text}"
    return {
        "model": os.getenv("GROQ_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_prefix}{user_text}"},
        ],
        "temperature": float(os.getenv("GROQ_TEMPERATURE", "0.4")),
        "max_tokens": int(os.getenv("GROQ_MAX_TOKENS", "300")),
    }


def generate_ai_reply(
    user_text: str,
    *,
    sender: str | None,
    chat_name: str | None,
    context: str | None = None,
) -> str | None:
    logger = logging.getLogger("funpay.ai")
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or not user_text:
        if not api_key:
            logger.warning("GROQ_API_KEY is missing; skipping AI reply.")
        return None
    if _is_code_like(user_text):
        return CLARIFY_RESPONSE
    if _is_gibberish(user_text):
        return None
    payload = _build_payload(user_text, sender=sender, chat_name=chat_name, context=context)
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            logger.warning("Groq API error %s: %s", response.status_code, response.text[:200])
            return None
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            logger.warning("Groq API returned empty content.")
        return content or None
    except Exception as exc:
        logger.warning("Groq API request failed: %s", exc)
        return None


