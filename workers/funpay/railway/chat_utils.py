from __future__ import annotations

import logging
import time
from datetime import datetime

import mysql.connector
from FunPayAPI.account import Account

from .chat_time_utils import _extract_datetime_from_html
from .db_utils import resolve_workspace_mysql_cfg, table_exists
from .notifications_utils import log_notification_event
from .env_utils import env_bool, env_int
from .presence_utils import invalidate_chat_cache, should_prefetch_history


def is_first_time_chat(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "chat_messages"):
            return False
        cursor.execute(
            """
            SELECT 1
            FROM chat_messages
            WHERE user_id = %s AND workspace_id <=> %s AND chat_id = %s
            LIMIT 1
            """,
            (int(user_id), int(workspace_id) if workspace_id is not None else None, int(chat_id)),
        )
        return cursor.fetchone() is None
    finally:
        conn.close()


def send_chat_message(logger: logging.Logger, account: Account, chat_id: int, text: str) -> bool:
    try:
        account.send_message(chat_id, text)
        return True
    except Exception as exc:
        logger.warning("Failed to send chat message: %s", exc)
        return False


def send_message_by_owner(logger: logging.Logger, account: Account, owner: str | None, text: str) -> bool:
    if not owner:
        return False
    try:
        chat = account.get_chat_by_name(owner, True)
    except Exception as exc:
        logger.warning("Failed to resolve chat for %s: %s", owner, exc)
        return False
    chat_id = getattr(chat, "id", None)
    if not chat_id:
        logger.warning("Chat not found for %s.", owner)
        return False
    return send_chat_message(logger, account, int(chat_id), text)


def _fetch_latest_chat_times(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    chat_ids: list[int],
) -> dict[int, datetime]:
    if not chat_ids:
        return {}
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(chat_ids))
        params: list = [int(user_id)]
        workspace_clause = " AND workspace_id IS NULL"
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        params.extend([int(cid) for cid in chat_ids])
        cursor.execute(
            f"""
            SELECT chat_id, MAX(sent_time) AS last_time
            FROM chat_messages
            WHERE user_id = %s{workspace_clause} AND chat_id IN ({placeholders})
            GROUP BY chat_id
            """,
            tuple(params),
        )
        rows = cursor.fetchall() or []
        result: dict[int, datetime] = {}
        for row in rows:
            chat_id = row.get("chat_id")
            last_time = row.get("last_time")
            if chat_id is None or last_time is None:
                continue
            try:
                result[int(chat_id)] = (
                    last_time if isinstance(last_time, datetime) else datetime.fromisoformat(str(last_time))
                )
            except Exception:
                continue
        return result
    finally:
        conn.close()


def _is_admin_command(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return "!админ" in lowered or "!admin" in lowered


def upsert_chat_summary(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    name: str | None,
    last_message_text: str | None,
    unread: bool | None,
    last_message_time: datetime | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "chats"):
            return
        cursor.execute(
            """
            INSERT INTO chats (
                chat_id, name, last_message_text, last_message_time, unread,
                admin_unread_count, admin_requested, user_id, workspace_id
            )
            VALUES (%s, %s, %s, %s, %s, 0, 0, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                last_message_text = VALUES(last_message_text),
                last_message_time = CASE
                    WHEN VALUES(last_message_time) IS NULL THEN last_message_time
                    WHEN last_message_text IS NULL OR VALUES(last_message_text) <> last_message_text
                        THEN VALUES(last_message_time)
                    ELSE last_message_time
                END,
                unread = VALUES(unread)
            """,
            (
                int(chat_id),
                name.strip() if isinstance(name, str) and name.strip() else None,
                last_message_text.strip() if isinstance(last_message_text, str) and last_message_text.strip() else None,
                last_message_time,
                1 if unread else 0,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_chat_message(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    message_id: int,
    author: str | None,
    text: str | None,
    by_bot: bool,
    message_type: str | None,
    sent_time: datetime | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "chat_messages"):
            return
        cursor.execute(
            """
            INSERT INTO chat_messages (
                message_id, chat_id, author, text, sent_time, by_bot, message_type, user_id, workspace_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE id = id
            """,
            (
                int(message_id),
                int(chat_id),
                author.strip() if isinstance(author, str) and author.strip() else None,
                text if text is not None else None,
                sent_time,
                1 if by_bot else 0,
                message_type,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        inserted = cursor.rowcount == 1
        if inserted and _is_admin_command(text) and not by_bot:
            cursor.execute(
                """
                UPDATE chats
                SET admin_unread_count = admin_unread_count + 1,
                    admin_requested = 1
                WHERE user_id = %s AND workspace_id <=> %s AND chat_id = %s
                """,
                (
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    int(chat_id),
                ),
            )
            chat_url = f"https://funpay.com/chat/?node={int(chat_id)}"
            log_notification_event(
                mysql_cfg,
                event_type="admin_call",
                status="new",
                title="Admin request received",
                message=f"Buyer requested admin assistance. Open chat: {chat_url}",
                owner=author,
                user_id=int(user_id),
                workspace_id=int(workspace_id) if workspace_id is not None else None,
            )
        conn.commit()
    finally:
        conn.close()
    invalidate_chat_cache(int(user_id), workspace_id, int(chat_id))


def fetch_chat_outbox(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    limit: int = 20,
) -> list[dict]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "chat_outbox"):
            return []
        cursor.execute(
            """
            SELECT id, chat_id, text, attempts
            FROM chat_outbox
            WHERE status = 'pending' AND user_id = %s AND workspace_id <=> %s
            ORDER BY id ASC
            LIMIT %s
            """,
            (int(user_id), int(workspace_id) if workspace_id is not None else None, int(max(1, min(limit, 200)))),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def mark_outbox_sent(mysql_cfg: dict, outbox_id: int, workspace_id: int | None = None) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chat_outbox SET status='sent', sent_at=NOW() WHERE id = %s",
            (int(outbox_id),),
        )
        conn.commit()
    finally:
        conn.close()


def mark_outbox_failed(
    mysql_cfg: dict,
    outbox_id: int,
    error: str,
    attempts: int,
    max_attempts: int,
    workspace_id: int | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        status = "failed" if attempts >= max_attempts else "pending"
        cursor.execute(
            """
            UPDATE chat_outbox
            SET status=%s, attempts=%s, last_error=%s
            WHERE id = %s
            """,
            (status, int(attempts), error[:500], int(outbox_id)),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_chats_missing_history(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_ids: list[int],
) -> list[int]:
    if not chat_ids:
        return []
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "chat_messages"):
            return list(chat_ids)
        placeholders = ", ".join(["%s"] * len(chat_ids))
        cursor.execute(
            f"""
            SELECT DISTINCT chat_id
            FROM chat_messages
            WHERE user_id = %s AND workspace_id <=> %s AND chat_id IN ({placeholders})
            """,
            tuple([int(user_id), int(workspace_id) if workspace_id is not None else None, *chat_ids]),
        )
        existing = {int(row[0]) for row in (cursor.fetchall() or [])}
        return [cid for cid in chat_ids if int(cid) not in existing]
    finally:
        conn.close()


def prefetch_chat_histories(
    logger: logging.Logger,
    mysql_cfg: dict,
    account: Account,
    *,
    user_id: int,
    workspace_id: int | None,
    chats: dict[int, str | None],
) -> None:
    if not env_bool("CHAT_HISTORY_PREFETCH_ENABLED", True):
        return
    max_chats = env_int("CHAT_HISTORY_PREFETCH_LIMIT", 8)
    if max_chats <= 0:
        return
    chat_ids = list(chats.keys())
    missing = fetch_chats_missing_history(
        mysql_cfg,
        user_id=int(user_id),
        workspace_id=workspace_id,
        chat_ids=chat_ids,
    )
    if not missing:
        return
    missing = [cid for cid in missing if should_prefetch_history(int(user_id), workspace_id, cid)]
    if not missing:
        return
    missing = missing[:max_chats]
    batch_size = env_int("CHAT_HISTORY_PREFETCH_BATCH", 4)
    msg_limit = env_int("CHAT_HISTORY_PREFETCH_MESSAGES", 50)
    for idx in range(0, len(missing), max(1, batch_size)):
        chunk = missing[idx : idx + max(1, batch_size)]
        try:
            histories = account.get_chats_histories({cid: chats.get(cid) for cid in chunk}) or {}
        except Exception as exc:
            logger.debug("Chat history prefetch failed: %s", exc)
            continue
        for chat_id, messages in histories.items():
            if not messages:
                continue
            trimmed = messages[-msg_limit:] if msg_limit > 0 else messages
            for msg in trimmed:
                try:
                    sent_time = _extract_datetime_from_html(getattr(msg, "html", None))
                    insert_chat_message(
                        mysql_cfg,
                        user_id=int(user_id),
                        workspace_id=workspace_id,
                        chat_id=int(chat_id),
                        message_id=int(getattr(msg, "id", 0) or 0),
                        author=getattr(msg, "author", None) or getattr(msg, "chat_name", None),
                        text=getattr(msg, "text", None),
                        by_bot=bool(getattr(msg, "by_bot", False)),
                        message_type=getattr(getattr(msg, "type", None), "name", None),
                        sent_time=sent_time,
                    )
                except Exception:
                    continue


def sync_chats_list(
    mysql_cfg: dict,
    account: Account,
    *,
    user_id: int,
    workspace_id: int | None,
) -> None:
    try:
        chats_map = account.get_chats(update=True) or {}
    except Exception:
        return
    chat_ids = [int(chat.id) for chat in chats_map.values() if getattr(chat, "id", None) is not None]
    history_times = _fetch_latest_chat_times(mysql_cfg, int(user_id), workspace_id, chat_ids)
    chat_names: dict[int, str | None] = {}
    for chat in chats_map.values():
        try:
            chat_id = int(chat.id)
            chat_time = _extract_datetime_from_html(getattr(chat, "html", None)) or history_times.get(chat_id)
            upsert_chat_summary(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
                chat_id=chat_id,
                name=chat.name,
                last_message_text=getattr(chat, "last_message_text", None),
                unread=bool(getattr(chat, "unread", False)),
                last_message_time=chat_time,
            )
            chat_names[chat_id] = getattr(chat, "name", None)
        except Exception:
            continue
    if chat_names:
        prefetch_chat_histories(
            logging.getLogger("funpay.worker"),
            mysql_cfg,
            account,
            user_id=int(user_id),
            workspace_id=workspace_id,
            chats=chat_names,
        )


def process_chat_outbox(
    logger: logging.Logger,
    mysql_cfg: dict,
    account: Account,
    *,
    user_id: int,
    workspace_id: int | None,
) -> None:
    pending = fetch_chat_outbox(mysql_cfg, int(user_id), workspace_id, limit=20)
    if not pending:
        return
    max_attempts = env_int("CHAT_OUTBOX_MAX_ATTEMPTS", 3)
    for item in pending:
        outbox_id = int(item.get("id") or 0)
        chat_id = int(item.get("chat_id") or 0)
        text = str(item.get("text") or "")
        attempts = int(item.get("attempts") or 0) + 1
        if not outbox_id or not chat_id or not text:
            continue
        try:
            message = account.send_message(chat_id, text)
            message_id = int(getattr(message, "id", 0) or 0)
            if message_id <= 0:
                message_id = -outbox_id
            insert_chat_message(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
                chat_id=chat_id,
                message_id=message_id,
                author=account.username or "you",
                text=text,
                by_bot=True,
                message_type="manual",
                sent_time=datetime.utcnow(),
            )
            upsert_chat_summary(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
                chat_id=chat_id,
                name=None,
                last_message_text=text,
                unread=False,
                last_message_time=datetime.utcnow(),
            )
            mark_outbox_sent(mysql_cfg, outbox_id, workspace_id=workspace_id)
        except Exception as exc:
            logger.warning("Chat send failed: %s", exc)
            mark_outbox_failed(
                mysql_cfg,
                outbox_id,
                str(exc),
                attempts,
                max_attempts,
                workspace_id=workspace_id,
            )
