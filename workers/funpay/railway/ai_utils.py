from __future__ import annotations

import logging
import os
from typing import Any

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_PROMPT = (
    "Ты — продавец в магазине аренды аккаунтов FunPay и отвечаешь покупателям. "
    "Отвечай по-русски, кратко и по делу, дружелюбно и уверенно. "
    "Если покупателю нужна помощь — предложи шаги. "
    "Для продления аренды используй команду !продлить <часы> <ID_аккаунта> (не направляй к админу без необходимости). "
    "Если вопрос про доступ, выдачу, команды или что делать дальше — перечисли команды: "
    "!сток (наличие), !акк (данные аккаунта), !код (Steam Guard), !админ (связь с продавцом). "
    "Если вопрос не относится к аренде аккаунтов, вежливо объясни, чем можешь помочь."
)


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