from __future__ import annotations

import json
import re
import time
from copy import deepcopy
from typing import Any

import mysql.connector

from .constants import COMMAND_PREFIXES
from .db_utils import resolve_workspace_mysql_cfg, table_exists

DEFAULT_COMMANDS: dict[str, str] = {
    "stock": "!сток",
    "account": "!акк",
    "code": "!код",
    "extend": "!продлить",
    "pause": "!пауза",
    "resume": "!продолжить",
    "admin": "!админ",
    "replace": "!лпзамена",
    "cancel": "!отмена",
    "bonus": "!бонус",
}

COMMAND_DEFINITIONS: list[dict[str, str]] = [
    {"key": "account", "desc": "данные аккаунта"},
    {"key": "code", "desc": "код Steam Guard"},
    {"key": "stock", "desc": "наличие аккаунтов"},
    {"key": "extend", "desc": "продлить аренду"},
    {"key": "pause", "desc": "пауза аренды на 1 час"},
    {"key": "resume", "desc": "снять паузу раньше срока"},
    {"key": "admin", "desc": "вызвать продавца"},
    {"key": "replace", "desc": "замена аккаунта (10 минут после кода)"},
    {"key": "cancel", "desc": "отменить аренду"},
    {"key": "bonus", "desc": "применить бонусные часы"},
]

COMMAND_USAGE_SUFFIX = {
    "extend": " <часы> <ID>",
    "pause": " <ID>",
    "resume": " <ID>",
    "replace": " <ID>",
    "cancel": " <ID>",
}

DEFAULT_RESPONSES: dict[str, str] = {
    "greeting": "Привет! Чем могу помочь?",
    "small_talk": "Всё хорошо, спасибо! Чем могу помочь?",
    "refund": "По вопросам возврата напишите !админ — я подключу продавца.",
    "unknown": "Не совсем понял. Можете уточнить?",
    "commands_help": "Команды:\n{commands}",
    "rent_flow": "",
    "pre_rent": "",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "ai_enabled": True,
    "tone": "friendly",
    "persona": "",
    "commands": DEFAULT_COMMANDS,
    "responses": DEFAULT_RESPONSES,
    "review_bonus_hours": 1,
    "blacklist": {
        "compensation_hours": 5,
        "unit_minutes": 60,
        "permanent_message": "Вы в постоянном черном списке. Доступ заблокирован без компенсации.",
        "blocked_message": (
            "Вы в черном списке.\n"
            "Оплатите штраф {penalty}, чтобы разблокировать доступ.\n"
            "Оплачено: {paid}. Осталось: {remaining}.\n"
            "Если хотите продлить — пожалуйста оплатите этот {lot}."
        ),
    },
    "ai": {
        "model": "",
        "temperature": 0.7,
        "max_tokens": 450,
    },
}

_CACHE: dict[tuple[int, int | None], tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 30


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def normalize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    return _deep_merge(DEFAULT_SETTINGS, raw)


def _parse_json(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _fetch_settings(
    cursor: mysql.connector.cursor.MySQLCursor, user_id: int, workspace_id: int | None
) -> dict[str, Any] | None:
    if workspace_id is None:
        cursor.execute(
            """
            SELECT settings_json FROM bot_customization
            WHERE user_id = %s AND workspace_id IS NULL
            LIMIT 1
            """,
            (int(user_id),),
        )
    else:
        cursor.execute(
            """
            SELECT settings_json FROM bot_customization
            WHERE user_id = %s AND workspace_id = %s
            LIMIT 1
            """,
            (int(user_id), int(workspace_id)),
        )
    row = cursor.fetchone()
    if not row:
        return None
    raw = row[0] if isinstance(row, (list, tuple)) else row.get("settings_json")
    return _parse_json(raw)


def load_bot_settings(mysql_cfg: dict, user_id: int, workspace_id: int | None) -> dict[str, Any]:
    cache_key = (int(user_id), int(workspace_id) if workspace_id is not None else None)
    cached = _CACHE.get(cache_key)
    if cached and time.time() - cached[0] <= _CACHE_TTL_SECONDS:
        return cached[1]
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "bot_customization"):
            settings = normalize_settings(None)
            _CACHE[cache_key] = (time.time(), settings)
            return settings
        cursor = conn.cursor(dictionary=True)
        global_settings = _fetch_settings(cursor, user_id, None)
        workspace_settings = _fetch_settings(cursor, user_id, workspace_id) if workspace_id is not None else None
        merged = normalize_settings(None)
        if global_settings:
            merged = _deep_merge(merged, global_settings)
        if workspace_settings:
            merged = _deep_merge(merged, workspace_settings)
        _CACHE[cache_key] = (time.time(), merged)
        return merged
    finally:
        conn.close()


def _normalize_command_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    raw_tokens: list[str] = []
    if isinstance(value, str):
        raw_tokens = re.split(r"[,\n]", value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str):
                raw_tokens.extend(re.split(r"[,\n]", item))
    cleaned: list[str] = []
    for token in raw_tokens:
        token = token.strip().lower()
        if not token:
            continue
        if not token.startswith("!"):
            token = f"!{token}"
        if token not in cleaned:
            cleaned.append(token)
    return cleaned


def build_command_alias_map(settings: dict[str, Any]) -> tuple[dict[str, str], dict[str, list[str]]]:
    alias_map: dict[str, str] = {}
    display_map: dict[str, list[str]] = {}
    commands = settings.get("commands", {}) if isinstance(settings, dict) else {}
    for key, canonical in DEFAULT_COMMANDS.items():
        aliases = _normalize_command_aliases(commands.get(key))
        display_aliases = aliases if aliases else [canonical]
        all_aliases = list(display_aliases)
        if canonical not in all_aliases:
            all_aliases.append(canonical)
        display_map[key] = display_aliases
        for alias in all_aliases:
            alias_map[alias] = canonical
    return alias_map, display_map


def get_command_label(settings: dict[str, Any], key: str) -> str:
    commands = settings.get("commands", {}) if isinstance(settings, dict) else {}
    aliases = _normalize_command_aliases(commands.get(key))
    if aliases:
        return aliases[0]
    return DEFAULT_COMMANDS.get(key, "")


def build_command_label_map(settings: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key, canonical in DEFAULT_COMMANDS.items():
        labels[canonical] = get_command_label(settings, key)
    return labels


def build_commands_text(settings: dict[str, Any], display_map: dict[str, list[str]] | None = None) -> str:
    if display_map is None:
        _, display_map = build_command_alias_map(settings)
    lines: list[str] = []
    for item in COMMAND_DEFINITIONS:
        key = item["key"]
        aliases = display_map.get(key) or [DEFAULT_COMMANDS.get(key, "")]
        label = " / ".join(str(alias) for alias in aliases)
        suffix = COMMAND_USAGE_SUFFIX.get(key, "")
        lines.append(f"{label}{suffix} — {item['desc']}")
    return "\n".join(lines)


def replace_command_tokens(text: str, command_labels: dict[str, str]) -> str:
    result = text or ""
    for canonical, label in command_labels.items():
        if canonical and label and canonical != label:
            result = result.replace(canonical, label)
    return result


def resolve_response(settings: dict[str, Any], key: str, fallback: str) -> str:
    responses = settings.get("responses", {}) if isinstance(settings, dict) else {}
    value = str(responses.get(key) or "").strip()
    return value if value else fallback


def render_template(
    template: str,
    *,
    commands_text: str | None = None,
    command_labels: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
) -> str:
    result = template or ""
    replacements: dict[str, str] = {}
    if values:
        replacements.update(values)
    if commands_text is not None:
        replacements.setdefault("commands", commands_text)
    if command_labels:
        replacements.setdefault(
            "admin_command", command_labels.get(DEFAULT_COMMANDS["admin"], DEFAULT_COMMANDS["admin"])
        )
        replacements.setdefault(
            "account_command", command_labels.get(DEFAULT_COMMANDS["account"], DEFAULT_COMMANDS["account"])
        )
        replacements.setdefault("code_command", command_labels.get(DEFAULT_COMMANDS["code"], DEFAULT_COMMANDS["code"]))
        replacements.setdefault(
            "stock_command", command_labels.get(DEFAULT_COMMANDS["stock"], DEFAULT_COMMANDS["stock"])
        )
        replacements.setdefault(
            "extend_command", command_labels.get(DEFAULT_COMMANDS["extend"], DEFAULT_COMMANDS["extend"])
        )
        replacements.setdefault(
            "pause_command", command_labels.get(DEFAULT_COMMANDS["pause"], DEFAULT_COMMANDS["pause"])
        )
        replacements.setdefault(
            "resume_command", command_labels.get(DEFAULT_COMMANDS["resume"], DEFAULT_COMMANDS["resume"])
        )
        replacements.setdefault(
            "replace_command", command_labels.get(DEFAULT_COMMANDS["replace"], DEFAULT_COMMANDS["replace"])
        )
        replacements.setdefault(
            "cancel_command", command_labels.get(DEFAULT_COMMANDS["cancel"], DEFAULT_COMMANDS["cancel"])
        )
        replacements.setdefault(
            "bonus_command", command_labels.get(DEFAULT_COMMANDS["bonus"], DEFAULT_COMMANDS["bonus"])
        )
    for key, value in replacements.items():
        result = result.replace(f"{{{key}}}", value)
    if command_labels:
        result = replace_command_tokens(result, command_labels)
    return result


def build_style_prompt(settings: dict[str, Any]) -> str | None:
    tone = str(settings.get("tone") or "").strip()
    persona = str(settings.get("persona") or "").strip()
    lines: list[str] = []
    if tone:
        lines.append(f"Tone: {tone}.")
    if persona:
        lines.append(f"Persona: {persona}.")
    return " ".join(lines) if lines else None


def build_ai_context_additions(settings: dict[str, Any], commands_text: str) -> str | None:
    responses = settings.get("responses", {}) if isinstance(settings, dict) else {}
    lines: list[str] = []
    if commands_text:
        lines.append("Command reference (use only when helpful):")
        lines.append(commands_text)
    preferred = {
        "Greeting": responses.get("greeting"),
        "Small talk": responses.get("small_talk"),
        "Refund": responses.get("refund"),
        "Clarify": responses.get("unknown"),
    }
    preferred_lines = [f"{label}: {text}".strip() for label, text in preferred.items() if text]
    if preferred_lines:
        lines.append("Preferred replies (use when appropriate):")
        lines.extend(preferred_lines)
    return "\n".join(lines) if lines else None


def get_ai_overrides(settings: dict[str, Any]) -> dict[str, Any]:
    ai = settings.get("ai", {}) if isinstance(settings, dict) else {}
    overrides: dict[str, Any] = {}
    model = str(ai.get("model") or "").strip()
    if model:
        overrides["model"] = model
    if ai.get("temperature") is not None:
        overrides["temperature"] = float(ai.get("temperature"))
    if ai.get("max_tokens") is not None:
        overrides["max_tokens"] = int(ai.get("max_tokens"))
    return overrides


def get_review_bonus_minutes(settings: dict[str, Any]) -> int:
    try:
        hours = int(settings.get("review_bonus_hours") or 0)
    except Exception:
        hours = 0
    return max(0, hours) * 60


def get_blacklist_policy(settings: dict[str, Any]) -> dict[str, Any]:
    blacklist = settings.get("blacklist", {}) if isinstance(settings, dict) else {}
    try:
        comp_hours = int(blacklist.get("compensation_hours") or 0)
    except Exception:
        comp_hours = 0
    comp_minutes = max(comp_hours * 60, 5 * 60)
    try:
        unit_minutes = int(blacklist.get("unit_minutes") or 60)
    except Exception:
        unit_minutes = 60
    permanent_message = str(blacklist.get("permanent_message") or DEFAULT_SETTINGS["blacklist"]["permanent_message"])
    blocked_message = str(blacklist.get("blocked_message") or DEFAULT_SETTINGS["blacklist"]["blocked_message"])
    return {
        "compensation_minutes": comp_minutes,
        "unit_minutes": unit_minutes,
        "permanent_message": permanent_message,
        "blocked_message": blocked_message,
    }


def build_allowed_command_list(alias_map: dict[str, str]) -> list[str]:
    if not alias_map:
        return list(COMMAND_PREFIXES)
    return list(set(list(alias_map.keys()) + list(COMMAND_PREFIXES)))
