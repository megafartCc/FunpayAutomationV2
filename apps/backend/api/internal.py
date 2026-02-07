from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from db.account_repo import MySQLAccountRepo
from db.notifications_repo import MySQLNotificationsRepo
from services.chat_notify import notify_owner
from services.steam_service import SteamWorkerError, deauthorize_sessions


router = APIRouter()
accounts_repo = MySQLAccountRepo()
notifications_repo = MySQLNotificationsRepo()


RENTAL_EXPIRED_MESSAGE = "\u0410\u0440\u0435\u043d\u0434\u0430 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0430\u0441\u044c. \u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442."
RENTAL_EXPIRED_CONFIRM_MESSAGE = (
    "\u0417\u0430\u043a\u0430\u0437 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d. "
    "\u041f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, \u0437\u0430\u0439\u0434\u0438\u0442\u0435 \u0432 "
    "\u0440\u0430\u0437\u0434\u0435\u043b \u00ab\u041f\u043e\u043a\u0443\u043f\u043a\u0438\u00bb, "
    "\u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0435\u0433\u043e \u0432 \u0441\u043f\u0438\u0441\u043a\u0435 "
    "\u0438 \u043d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 "
    "\u00ab\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435 \u0437\u0430\u043a\u0430\u0437\u0430\u00bb."
)


def _require_worker_token(x_worker_token: str | None = Header(default=None, alias="X-Worker-Token")) -> None:
    token = os.getenv("BACKEND_INTERNAL_TOKEN", "").strip()
    if not token or not x_worker_token or x_worker_token != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid worker token")


class InternalExpireRequest(BaseModel):
    account_id: int = Field(..., ge=1)
    user_id: int = Field(..., ge=1)
    workspace_id: int = Field(..., ge=1)
    owner: str | None = None
    account_name: str | None = None
    login: str | None = None
    confirm_url: str | None = None


@router.post("/internal/rentals/expire", dependencies=[Depends(_require_worker_token)])
def internal_rental_expire(payload: InternalExpireRequest) -> dict:
    account = accounts_repo.get_by_id(int(payload.account_id), int(payload.user_id), int(payload.workspace_id))
    owner = payload.owner or (account.get("owner") if account else None)
    account_name = payload.account_name or (account.get("account_name") if account else None)
    login = payload.login or (account.get("login") if account else None)

    released = accounts_repo.release_account(int(payload.account_id), int(payload.user_id), int(payload.workspace_id))

    deauth_status = "skipped"
    if account:
        password = account.get("password") or ""
        mafile_json = account.get("mafile_json")
        if login and password and mafile_json:
            try:
                deauthorize_sessions(
                    steam_login=login,
                    steam_password=password,
                    mafile_json=mafile_json,
                )
                deauth_status = "ok"
                notifications_repo.log_notification(
                    event_type="deauthorize",
                    status="ok",
                    title="Steam deauthorize on expiry",
                    message="Steam sessions deauthorized after rental expiration.",
                    owner=owner,
                    account_name=account_name or login,
                    account_id=int(payload.account_id),
                    user_id=int(payload.user_id),
                    workspace_id=int(payload.workspace_id),
                )
            except SteamWorkerError as exc:
                deauth_status = "failed"
                notifications_repo.log_notification(
                    event_type="deauthorize",
                    status="failed",
                    title="Steam deauthorize on expiry",
                    message=f"Steam deauthorize failed: {exc.message}",
                    owner=owner,
                    account_name=account_name or login,
                    account_id=int(payload.account_id),
                    user_id=int(payload.user_id),
                    workspace_id=int(payload.workspace_id),
                )

    if released:
        notifications_repo.log_notification(
            event_type="rental_expired",
            status="ok",
            title="Rental expired",
            message="Rental expired and account was released.",
            owner=owner,
            account_name=account_name or login,
            account_id=int(payload.account_id),
            user_id=int(payload.user_id),
            workspace_id=int(payload.workspace_id),
        )

    if owner:
        notify_owner(
            user_id=int(payload.user_id),
            workspace_id=int(payload.workspace_id),
            owner=owner,
            text=RENTAL_EXPIRED_MESSAGE,
        )
        confirm_message = RENTAL_EXPIRED_CONFIRM_MESSAGE
        if payload.confirm_url:
            confirm_message = (
                f"{RENTAL_EXPIRED_CONFIRM_MESSAGE}\n\n"
                f"\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u0442\u0443\u0442 -> {payload.confirm_url}"
            )
        notify_owner(
            user_id=int(payload.user_id),
            workspace_id=int(payload.workspace_id),
            owner=owner,
            text=confirm_message,
        )

    return {"status": "ok", "released": released, "deauthorize": deauth_status}
