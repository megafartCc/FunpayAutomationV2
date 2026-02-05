from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL_ENV = "GROQ_MODEL"
INTENT_MODEL_ENV = "AI_INTENT_MODEL"
DEFAULT_MODEL = "llama-3.1-70b-versatile"
DEFAULT_INTENT_MODEL = "llama-3.1-8b-instant"
LOCAL_API_URL_ENV = "AI_API_URL"
LOCAL_MODEL_ENV = "AI_MODEL"
LOCAL_API_KEY_ENV = "AI_API_KEY"
DEFAULT_PROMPT = (
    "Вы — дружелюбный и внимательный помощник поддержки FunPay. "
    "Пишите естественно и по-человечески, без шаблонных фраз. "
    "Не называйте себя ИИ/ботом и не говорите, что вы — FunPay. "
    "На привет отвечайте тепло и коротко, затем мягко предложите помощь. "
    "На небольшие личные вопросы (например, «как дела?») отвечайте кратко и дружелюбно, "
    "а затем спросите, чем можете помочь. "
    "Отвечайте по делу: 1-3 предложения, если не требуется инструкция. "
    "Не упоминайте команды, если пользователь не просит действие или помощь с командами. "
    "Если нужно действие — объясните одну подходящую команду без длинного списка. "
    "Не выдавайте логины, пароли или коды Steam Guard. "
    "Не оформляйте аренды и возвраты — направляйте пользователя к командам или !админ. "
    "Если запрос неясен — задайте короткий уточняющий вопрос. "
    "Контекст (если дан) — только для справки; не пересказывайте и не упоминайте прошлые темы, "
    "если пользователь сам не поднял их, кроме краткого мягкого фоллоу-апа после смолтока."
)
INTENT_LABELS = (
    "stock_list",
    "busy_list",
    "rent_flow",
    "pre_rent",
    "refund",
    "account_info",
    "when_free",
    "commands",
    "greeting",
    "unknown",
)
INTENT_PROMPT = (
    "You are a strict intent classifier for a FunPay rental support bot.\n"
    "Return ONLY valid JSON with keys: intent, confidence, reason.\n"
    "Allowed intents:\n"
    "- stock_list: user wants free/available accounts or asks what's free\n"
    "- busy_list: user asks which accounts are busy/occupied\n"
    "- rent_flow: asks how to rent or what to do to rent\n"
    "- pre_rent: wants multiple accounts or time before payment (e.g., \"need 2 accounts for 3 hours\")\n"
    "- refund: asks to refund or вернуть деньги/средства\n"
    "- account_info: asks for login/password, account data, rental time left\n"
    "- when_free: asks when a specific lot/account will be free\n"
    "- commands: asks for command list or help\n"
    "- greeting: greeting only\n"
    "- unknown: unclear\n"
    "Confidence: 0-1. If unclear, use intent=unknown and confidence<=0.4.\n"
)
CLARIFY_RESPONSE = "Не понял запрос. Пожалуйста, уточните, что вы имеете в виду."
RUDE_RESPONSE = (
    "Пожалуйста, без оскорблений. Я могу помочь с арендой и командами: !сток, !акк, !код."
)
SENSITIVE_RESPONSE = (
    "Я не могу выдавать данные аккаунта или коды. Используйте команды !акк и !код, либо напишите !админ."
)
_ALNUM_RE = re.compile(r"[A-Za-zА-Яа-я0-9]+")
_CODE_RE = re.compile(r"^[A-Za-z0-9]{3,12}$")
_RUDE_KEYWORDS = (
    "долбаеб",
    "долбоеб",
    "идиот",
    "тупой",
    "сука",
    "пидор",
    "ублюдок",
    "хуи",
    "хуй",
    "блять",
    "мразь",
)
_SENSITIVE_KEYWORDS = (
    "логин",
    "пароль",
    "steam guard",
    "steamguard",
    "password",
    "login",
)
_PRICE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:₽|руб\.?|рублей|rub)\b", re.IGNORECASE)
_PRICE_ANALYTICS_KEYWORDS = (
    "ai аналитика",
    "аналитика цены",
    "аналитика цен",
    "анализ цен",
    "анализ цены",
    "рекомендация цены",
    "рекомендуемая цена",
    "рассчитать цену",
    "почти первым",
    "почти первая",
    "в списке",
    "price analysis",
    "price analytics",
    "pricing analysis",
)
_PRICE_SKIP_HINTS = (
    "рекоменд",
    "миним",
    "вторая",
    "всего",
    "средн",
    "анализ",
    "итог",
)


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


def _is_rude(text: str) -> bool:
    lowered = (text or "").lower()
    return any(word in lowered for word in _RUDE_KEYWORDS)


def _contains_sensitive(text: str) -> bool:
    lowered = (text or "").lower()
    if any(word in lowered for word in _SENSITIVE_KEYWORDS):
        return True
    if "login:" in lowered or "password:" in lowered:
        return True
    return False


def _is_price_analytics_request(text: str, price_count: int) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    if "запустить ai" in lowered:
        return True
    if any(keyword in lowered for keyword in _PRICE_ANALYTICS_KEYWORDS):
        return True
    if price_count >= 3 and any(
        hint in lowered for hint in ("цена", "цен", "price", "список", "list", "лот", "lots")
    ):
        return True
    return False


def _format_rub_price(value: float) -> str:
    rounded = round(float(value) + 1e-9, 2)
    text = f"{rounded:.2f}".replace(".", ",")
    text = text.rstrip("0").rstrip(",")
    return f"{text} ₽"


def _extract_prices(text: str) -> list[float]:
    prices: list[float] = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        lowered = line.lower()
        if any(hint in lowered for hint in _PRICE_SKIP_HINTS):
            continue
        for match in _PRICE_RE.finditer(line):
            raw = match.group(1)
            try:
                value = float(raw.replace(",", "."))
            except Exception:
                continue
            prices.append(value)
    return prices


def _recommend_price(prices: list[float]) -> float | None:
    if not prices:
        return None
    sorted_prices = sorted(prices)
    avg = sum(sorted_prices) / len(sorted_prices)
    if len(sorted_prices) == 1:
        return round(sorted_prices[0] + 1e-9, 2)

    mid = len(sorted_prices) // 2
    if len(sorted_prices) % 2 == 0:
        median = (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    else:
        median = sorted_prices[mid]

    try:
        front_rank = int(os.getenv("AI_PRICE_FRONT_RANK", "3"))
    except Exception:
        front_rank = 3
    front_rank = max(1, min(front_rank, len(sorted_prices) - 1))

    try:
        max_discount = float(os.getenv("AI_PRICE_MAX_DISCOUNT", "0.2"))
    except Exception:
        max_discount = 0.2
    max_discount = min(max(max_discount, 0.0), 0.9)

    try:
        step = float(os.getenv("AI_PRICE_STEP", "0.01"))
    except Exception:
        step = 0.01
    if step <= 0:
        step = 0.01

    anchor = sorted_prices[front_rank - 1]
    reference = median if median > 0 else avg
    min_allowed = reference * (1.0 - max_discount)
    target = max(anchor + step, min_allowed)
    if target < sorted_prices[0]:
        target = sorted_prices[0]
    if target < 0:
        target = sorted_prices[0]
    return round(target + 1e-9, 2)


def _build_price_analytics_reply(text: str) -> str | None:
    prices = _extract_prices(text)
    if not prices:
        return None
    if not _is_price_analytics_request(text, len(prices)):
        return None
    filtered = [price for price in prices if 0 <= price <= 50]
    if not filtered:
        return None
    lines = [_format_rub_price(price) for price in filtered]
    recommended = _recommend_price(filtered)
    if recommended is None:
        return "\n".join(lines)
    lines.extend(["", _format_rub_price(recommended)])
    return "\n".join(lines)


def _build_payload(
    user_text: str,
    *,
    sender: str | None,
    chat_name: str | None,
    context: str | None = None,
    model: str,
    temperature: float,
    max_tokens: int,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    system_prompt = system_prompt or os.getenv("GROQ_SYSTEM_PROMPT", DEFAULT_PROMPT)
    user_prefix = f"Покупатель: {sender or '-'}\nЧат: {chat_name or '-'}\nСообщение: "
    if context:
        user_text = (
            "Контекст (только для справки, не упоминайте без запроса):\n"
            f"{context}\n\nСообщение пользователя:\n{user_text}"
        )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_prefix}{user_text}"},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def generate_ai_reply(
    user_text: str,
    *,
    sender: str | None,
    chat_name: str | None,
    context: str | None = None,
    system_prompt_extra: str | None = None,
    model_override: str | None = None,
    temperature_override: float | None = None,
    max_tokens_override: int | None = None,
) -> str | None:
    logger = logging.getLogger("funpay.ai")
    if not user_text:
        return None
    analytics_reply = _build_price_analytics_reply(user_text)
    if analytics_reply:
        return analytics_reply
    local_url = os.getenv(LOCAL_API_URL_ENV, "").strip()
    api_url = local_url or GROQ_API_URL
    api_key = os.getenv(LOCAL_API_KEY_ENV if local_url else "GROQ_API_KEY", "").strip()
    if local_url:
        model = os.getenv(LOCAL_MODEL_ENV, DEFAULT_MODEL).strip()
    else:
        model = os.getenv(GROQ_MODEL_ENV, DEFAULT_MODEL).strip()
    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "450"))
    if model_override:
        model = model_override
    if temperature_override is not None:
        temperature = float(temperature_override)
    if max_tokens_override is not None:
        max_tokens = int(max_tokens_override)
    if not api_key and not local_url:
        logger.warning("GROQ_API_KEY is missing; skipping AI reply.")
        return None
    if _is_code_like(user_text):
        return CLARIFY_RESPONSE
    if _is_rude(user_text):
        return RUDE_RESPONSE
    if _is_gibberish(user_text):
        return None
    system_prompt = os.getenv("GROQ_SYSTEM_PROMPT", DEFAULT_PROMPT)
    if system_prompt_extra:
        system_prompt = f"{system_prompt}\n\n{system_prompt_extra.strip()}"
    payload = _build_payload(
        user_text,
        sender=sender,
        chat_name=chat_name,
        context=context,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
    )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.post(
            api_url,
            headers=headers,
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
        if content and _contains_sensitive(content):
            return SENSITIVE_RESPONSE
        return content or None
    except Exception as exc:
        logger.warning("Groq API request failed: %s", exc)
        return None


def _extract_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def classify_intent(
    user_text: str,
    *,
    context: str | None = None,
) -> dict[str, Any] | None:
    logger = logging.getLogger("funpay.ai")
    if not user_text:
        return None
    local_url = os.getenv(LOCAL_API_URL_ENV, "").strip()
    api_url = local_url or GROQ_API_URL
    api_key = os.getenv(LOCAL_API_KEY_ENV if local_url else "GROQ_API_KEY", "").strip()
    if not api_key and not local_url:
        return None
    if local_url:
        model = os.getenv(LOCAL_MODEL_ENV, DEFAULT_INTENT_MODEL).strip()
    else:
        model = os.getenv(INTENT_MODEL_ENV, DEFAULT_INTENT_MODEL).strip()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": INTENT_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\nUser: {user_text}" if context else f"User: {user_text}"
                ),
            },
        ],
        "temperature": 0.0,
        "max_tokens": 120,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=12,
        )
        if response.status_code >= 400:
            logger.warning("Intent API error %s: %s", response.status_code, response.text[:200])
            return None
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            return None
        obj = _extract_json(content)
        if not obj:
            return None
        intent = str(obj.get("intent") or "").strip()
        confidence = float(obj.get("confidence") or 0.0)
        reason = str(obj.get("reason") or "").strip()
        if intent not in INTENT_LABELS:
            return None
        return {"intent": intent, "confidence": confidence, "reason": reason}
    except Exception as exc:
        logger.warning("Intent classification failed: %s", exc)
        return None


