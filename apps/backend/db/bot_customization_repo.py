from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from db.mysql import get_base_connection


DEFAULT_BOT_SETTINGS: dict[str, Any] = {
    "ai_enabled": True,
    "tone": "friendly",
    "persona": "",
    "commands": {
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
    },
    "responses": {
        "greeting": "Привет! Чем могу помочь?",
        "small_talk": "Всё хорошо, спасибо! Чем могу помочь?",
        "refund": "По вопросам возврата напишите !админ — я подключу продавца.",
        "unknown": "Не совсем понял. Можете уточнить?",
        "commands_help": "Команды:\n{commands}",
        "rent_flow": "",
        "pre_rent": "",
    },
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


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def normalize_bot_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    return _deep_merge(DEFAULT_BOT_SETTINGS, raw)


class MySQLBotCustomizationRepo:
    def _fetch_settings_json(self, cursor, user_id: int, workspace_id: int | None) -> dict[str, Any] | None:
        if workspace_id is None:
            cursor.execute(
                """
                SELECT settings_json
                FROM bot_customization
                WHERE user_id = %s AND workspace_id IS NULL
                LIMIT 1
                """,
                (int(user_id),),
            )
        else:
            cursor.execute(
                """
                SELECT settings_json
                FROM bot_customization
                WHERE user_id = %s AND workspace_id = %s
                LIMIT 1
                """,
                (int(user_id), int(workspace_id)),
            )
        row = cursor.fetchone()
        if not row:
            return None
        raw = row.get("settings_json") if isinstance(row, dict) else row[0]
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    def get_settings(self, user_id: int, workspace_id: int | None = None) -> tuple[dict[str, Any], str]:
        conn = get_base_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'bot_customization'
                LIMIT 1
                """
            )
            if cursor.fetchone() is None:
                return normalize_bot_settings(None), "default"
            global_settings = self._fetch_settings_json(cursor, user_id, None)
            if workspace_id is not None:
                workspace_settings = self._fetch_settings_json(cursor, user_id, workspace_id)
                if workspace_settings:
                    merged = _deep_merge(normalize_bot_settings(None), global_settings or {})
                    merged = _deep_merge(merged, workspace_settings)
                    return merged, "workspace"
                if global_settings:
                    return normalize_bot_settings(global_settings), "global"
                return normalize_bot_settings(None), "default"
            if global_settings:
                return normalize_bot_settings(global_settings), "global"
            return normalize_bot_settings(None), "default"
        finally:
            conn.close()

    def save_settings(self, user_id: int, workspace_id: int | None, settings: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_bot_settings(settings)
        payload = json.dumps(normalized, ensure_ascii=False)
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            if workspace_id is None:
                cursor.execute(
                    """
                    INSERT INTO bot_customization (user_id, workspace_id, settings_json)
                    VALUES (%s, NULL, %s)
                    ON DUPLICATE KEY UPDATE settings_json = VALUES(settings_json)
                    """,
                    (int(user_id), payload),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO bot_customization (user_id, workspace_id, settings_json)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE settings_json = VALUES(settings_json)
                    """,
                    (int(user_id), int(workspace_id), payload),
                )
            conn.commit()
        finally:
            conn.close()
        return normalized

    def delete_settings(self, user_id: int, workspace_id: int | None) -> int:
        conn = get_base_connection()
        try:
            cursor = conn.cursor()
            if workspace_id is None:
                cursor.execute(
                    "DELETE FROM bot_customization WHERE user_id = %s AND workspace_id IS NULL",
                    (int(user_id),),
                )
            else:
                cursor.execute(
                    "DELETE FROM bot_customization WHERE user_id = %s AND workspace_id = %s",
                    (int(user_id), int(workspace_id)),
                )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
