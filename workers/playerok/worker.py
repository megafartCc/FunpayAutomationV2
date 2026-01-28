from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import mysql.connector
import requests
import tls_requests
import tls_requests.api as tls_api
from playerok_requests_api.chats import PlayerokChatsApi


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
IPIFY_URL = "https://api.ipify.org"


@dataclass
class WorkspaceSession:
    workspace_id: int
    user_id: int
    username: str
    proxy_url: str
    cookies_hash: str
    cookies_path: Path
    chat_api: PlayerokChatsApi
    last_proxy_check: float = 0.0


def configure_logging() -> logging.Logger:
    logging.basicConfig(level=os.getenv("PLAYEROK_LOG_LEVEL", "INFO"), format=LOG_FORMAT)
    return logging.getLogger("playerok.worker")


def _load_mysql_settings() -> dict[str, str | int]:
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


def table_exists(cursor: mysql.connector.cursor.MySQLCursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
        (table,),
    )
    return cursor.fetchone() is not None


def normalize_proxy_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return f"socks5://{value}"


def build_proxy_config(raw: str | None) -> dict[str, str] | None:
    url = normalize_proxy_url(raw)
    if not url:
        return None
    return {"http": url, "https": url}


def _fetch_public_ip(proxies: dict[str, str] | None) -> str | None:
    try:
        resp = requests.get(IPIFY_URL, proxies=proxies, timeout=10)
        resp.raise_for_status()
    except Exception:
        return None
    text = (resp.text or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = resp.json()
            text = str(data.get("ip") or "").strip()
        except Exception:
            return None
    return text or None


def ensure_proxy_isolated(
    logger: logging.Logger,
    proxy_url: str | None,
    label: str,
) -> bool:
    if not proxy_url:
        logger.error("%s Missing proxy_url, worker will not start.", label)
        return False
    proxy_cfg = build_proxy_config(proxy_url)
    if not proxy_cfg:
        logger.error("%s Invalid proxy_url, worker will not start.", label)
        return False
    direct_ip = _fetch_public_ip(None)
    if not direct_ip:
        logger.error("%s Failed to resolve direct IP, aborting.", label)
        return False
    proxy_ip = _fetch_public_ip(proxy_cfg)
    if not proxy_ip:
        logger.error("%s Failed to resolve proxy IP, aborting.", label)
        return False
    if proxy_ip == direct_ip:
        logger.error("%s Proxy IP matches direct IP, aborting.", label)
        return False
    logger.info("%s Proxy check passed (direct/proxy IP differ).", label)
    return True


class TlsProxyPatch:
    def __init__(self, proxy_url: str) -> None:
        self.proxy_url = proxy_url
        self._orig_request = None

    def __enter__(self) -> "TlsProxyPatch":
        self._orig_request = tls_api.request

        def _request(method: str, url: str, *args: Any, **kwargs: Any):
            if kwargs.get("proxy") in (None, ""):
                kwargs["proxy"] = self.proxy_url
            return self._orig_request(method, url, *args, **kwargs)

        tls_api.request = _request
        tls_requests.request = _request  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._orig_request is not None:
            tls_api.request = self._orig_request
            tls_requests.request = self._orig_request  # type: ignore[assignment]


def normalize_graphql_id(raw: Any) -> int | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
        tail = decoded.split(":")[-1]
        if tail.isdigit():
            return int(tail)
    except Exception:
        pass
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16) & 0x7FFFFFFFFFFFFFFF


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def upsert_chat_summary(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int,
    chat_id: int,
    name: str | None,
    last_message_text: str | None,
    unread: bool,
    last_message_time: datetime | None = None,
) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
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
                int(workspace_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_chat_message(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int,
    chat_id: int,
    message_id: int,
    author: str | None,
    text: str | None,
    by_bot: bool,
    message_type: str | None,
    sent_time: datetime | None = None,
) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
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
                int(workspace_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_chat_outbox(mysql_cfg: dict, user_id: int, workspace_id: int, limit: int = 20) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "chat_outbox"):
            return []
        cursor.execute(
            """
            SELECT id, chat_id, text, attempts
            FROM chat_outbox
            WHERE status = 'pending' AND user_id = %s AND workspace_id = %s
            ORDER BY id ASC
            LIMIT %s
            """,
            (int(user_id), int(workspace_id), int(max(1, min(limit, 200)))),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def mark_outbox_sent(mysql_cfg: dict, outbox_id: int) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chat_outbox SET status='sent', sent_at=NOW() WHERE id = %s",
            (int(outbox_id),),
        )
        conn.commit()
    finally:
        conn.close()


def mark_outbox_failed(mysql_cfg: dict, outbox_id: int, error: str, attempts: int) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE chat_outbox
            SET status = 'failed', attempts = %s, last_error = %s
            WHERE id = %s
            """,
            (int(attempts), error[:500], int(outbox_id)),
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_name(mysql_cfg: dict, user_id: int, workspace_id: int, chat_id: int) -> str | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "chats"):
            return None
        cursor.execute(
            """
            SELECT name
            FROM chats
            WHERE user_id = %s AND workspace_id = %s AND chat_id = %s
            LIMIT 1
            """,
            (int(user_id), int(workspace_id), int(chat_id)),
        )
        row = cursor.fetchone()
        return (row or {}).get("name")
    finally:
        conn.close()


def fetch_workspaces(mysql_cfg: dict, workspace_filter: int | None = None) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        params: list[Any] = []
        where = "WHERE w.platform = 'playerok' AND w.golden_key IS NOT NULL AND w.golden_key != ''"
        if workspace_filter is not None:
            where += " AND w.id = %s"
            params.append(int(workspace_filter))
        cursor.execute(
            f"""
            SELECT w.id AS workspace_id, w.name AS workspace_name, w.golden_key, w.proxy_url,
                   w.user_id, u.username
            FROM workspaces w
            JOIN users u ON u.id = w.user_id
            {where}
            ORDER BY w.user_id, w.id
            """,
            tuple(params),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def ensure_cookies_file(cookies_dir: Path, workspace_id: int, cookies_raw: str) -> Path | None:
    if not cookies_raw:
        return None
    try:
        parsed = json.loads(cookies_raw)
    except Exception:
        return None
    if not isinstance(parsed, list):
        return None
    cookies_dir.mkdir(parents=True, exist_ok=True)
    path = cookies_dir / f"playerok_ws_{workspace_id}.json"
    path.write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
    return path


def extract_participant_username(chat: dict, self_id: str | None) -> str | None:
    participants = chat.get("participants") or []
    for participant in participants:
        pid = str(participant.get("id") or "")
        if self_id is not None and pid == str(self_id):
            continue
        username = (participant.get("username") or "").strip()
        if username:
            return username
    return None


def format_last_message_text(last_message: dict | None) -> str | None:
    if not last_message:
        return None
    text = last_message.get("text")
    if isinstance(text, str) and text.strip():
        return text
    if last_message.get("deal"):
        return "Deal update"
    if last_message.get("transaction"):
        return "Transaction update"
    if last_message.get("file"):
        return "File"
    if last_message.get("event"):
        return str(last_message.get("event"))
    typename = last_message.get("__typename")
    return str(typename) if typename else None


def ensure_session(
    logger: logging.Logger,
    mysql_cfg: dict,
    cookies_dir: Path,
    sessions: dict[int, WorkspaceSession],
    workspace: dict,
    proxy_check_interval: int,
) -> WorkspaceSession | None:
    workspace_id = int(workspace["workspace_id"])
    user_id = int(workspace["user_id"])
    label = f"[PlayerOk:{workspace_id}]"
    proxy_url = (workspace.get("proxy_url") or "").strip()
    cookies_raw = (workspace.get("golden_key") or "").strip()
    if not cookies_raw:
        logger.warning("%s Missing cookies JSON, skipping.", label)
        return None
    cookies_hash = hashlib.sha1(cookies_raw.encode("utf-8")).hexdigest()

    session = sessions.get(workspace_id)
    if session and session.cookies_hash == cookies_hash and session.proxy_url == proxy_url:
        if time.time() - session.last_proxy_check > proxy_check_interval:
            if not ensure_proxy_isolated(logger, proxy_url, label):
                return None
            session.last_proxy_check = time.time()
        return session

    cookies_path = ensure_cookies_file(cookies_dir, workspace_id, cookies_raw)
    if not cookies_path:
        logger.error("%s Invalid cookies JSON.", label)
        return None
    if not ensure_proxy_isolated(logger, proxy_url, label):
        return None

    with TlsProxyPatch(proxy_url):
        chat_api = PlayerokChatsApi(cookies_file=str(cookies_path), logger=False)
    if not chat_api.username:
        logger.error("%s Failed to authenticate with provided cookies.", label)
        return None

    session = WorkspaceSession(
        workspace_id=workspace_id,
        user_id=user_id,
        username=chat_api.username,
        proxy_url=proxy_url,
        cookies_hash=cookies_hash,
        cookies_path=cookies_path,
        chat_api=chat_api,
        last_proxy_check=time.time(),
    )
    sessions[workspace_id] = session
    return session


def sync_chats(logger: logging.Logger, mysql_cfg: dict, session: WorkspaceSession) -> None:
    label = f"[PlayerOk:{session.workspace_id}]"
    chat_api = session.chat_api
    with TlsProxyPatch(session.proxy_url):
        chats = chat_api.get_messages_info(unread=False)
    if not chats:
        logger.debug("%s No chats returned.", label)
        return

    for chat_edge in chats:
        chat = chat_edge.get("node") or {}
        raw_chat_id = chat.get("id")
        chat_id = normalize_graphql_id(raw_chat_id)
        if chat_id is None:
            continue
        participant = extract_participant_username(chat, chat_api.id)
        last_message = chat.get("lastMessage") or {}
        last_message_id = normalize_graphql_id(last_message.get("id")) or int(chat_id)
        last_message_time = parse_iso_datetime(last_message.get("createdAt"))
        last_message_text = format_last_message_text(last_message)
        unread_count = int(chat.get("unreadMessagesCounter") or 0)

        upsert_chat_summary(
            mysql_cfg,
            user_id=session.user_id,
            workspace_id=session.workspace_id,
            chat_id=chat_id,
            name=participant,
            last_message_text=last_message_text,
            unread=unread_count > 0,
            last_message_time=last_message_time,
        )

        if last_message:
            author = None
            msg_user = last_message.get("user") or {}
            if isinstance(msg_user, dict):
                author = msg_user.get("username")
            by_bot = False
            if msg_user and str(msg_user.get("id") or "") == str(chat_api.id or ""):
                by_bot = True
            message_type = last_message.get("__typename")
            insert_chat_message(
                mysql_cfg,
                user_id=session.user_id,
                workspace_id=session.workspace_id,
                chat_id=chat_id,
                message_id=last_message_id,
                author=author or participant,
                text=last_message_text,
                by_bot=by_bot,
                message_type=str(message_type) if message_type else None,
                sent_time=last_message_time,
            )


def process_outbox(logger: logging.Logger, mysql_cfg: dict, session: WorkspaceSession) -> None:
    pending = fetch_chat_outbox(mysql_cfg, session.user_id, session.workspace_id, limit=20)
    if not pending:
        return
    for entry in pending:
        outbox_id = int(entry["id"])
        chat_id = int(entry["chat_id"])
        text = str(entry.get("text") or "").strip()
        attempts = int(entry.get("attempts") or 0) + 1
        if not text:
            mark_outbox_failed(mysql_cfg, outbox_id, "Empty message", attempts)
            continue
        chat_name = get_chat_name(mysql_cfg, session.user_id, session.workspace_id, chat_id)
        if not chat_name:
            mark_outbox_failed(mysql_cfg, outbox_id, "Chat not found", attempts)
            continue

        label = f"[PlayerOk:{session.workspace_id}]"
        try:
            with TlsProxyPatch(session.proxy_url):
                result = session.chat_api.on_send_message(chat_name, text)
            if not result:
                mark_outbox_failed(mysql_cfg, outbox_id, "Send failed", attempts)
                continue
            mark_outbox_sent(mysql_cfg, outbox_id)

            msg = (result.get("data") or {}).get("createChatMessage") if isinstance(result, dict) else None
            if isinstance(msg, dict):
                msg_id = normalize_graphql_id(msg.get("id"))
                msg_time = parse_iso_datetime(msg.get("createdAt"))
                msg_text = msg.get("text") if msg.get("text") is not None else text
                insert_chat_message(
                    mysql_cfg,
                    user_id=session.user_id,
                    workspace_id=session.workspace_id,
                    chat_id=chat_id,
                    message_id=msg_id or int(time.time()),
                    author=session.username,
                    text=msg_text,
                    by_bot=True,
                    message_type=str(msg.get("__typename") or "ChatMessage"),
                    sent_time=msg_time,
                )
            logger.info("%s Sent message to %s.", label, chat_name)
        except Exception as exc:
            logger.warning("%s Failed to send message: %s", label, exc)
            mark_outbox_failed(mysql_cfg, outbox_id, str(exc), attempts)


def main() -> None:
    logger = configure_logging()
    mysql_cfg = _load_mysql_settings()
    poll_seconds = int(os.getenv("PLAYEROK_POLL_SECONDS", "15"))
    proxy_check_interval = int(os.getenv("PLAYEROK_PROXY_CHECK_SECONDS", "600"))
    workspace_filter = os.getenv("PLAYEROK_WORKSPACE_ID", "").strip()
    workspace_id = int(workspace_filter) if workspace_filter.isdigit() else None
    cookies_dir = Path(os.getenv("PLAYEROK_COOKIES_DIR", ".playerok_cookies"))

    sessions: dict[int, WorkspaceSession] = {}
    logger.info("PlayerOk worker starting. Poll interval: %ss", poll_seconds)

    while True:
        workspaces = fetch_workspaces(mysql_cfg, workspace_id)
        if not workspaces:
            logger.warning("No PlayerOk workspaces found.")
            time.sleep(poll_seconds)
            continue

        for workspace in workspaces:
            session = ensure_session(
                logger,
                mysql_cfg,
                cookies_dir,
                sessions,
                workspace,
                proxy_check_interval,
            )
            if not session:
                continue
            try:
                sync_chats(logger, mysql_cfg, session)
                process_outbox(logger, mysql_cfg, session)
            except Exception as exc:
                logger.exception("[PlayerOk:%s] Worker error: %s", session.workspace_id, exc)

        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
