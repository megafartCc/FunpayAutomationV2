from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime

from pydantic import BaseModel

from api.deps import get_current_user
from db.telegram_repo import MySQLTelegramRepo
from settings.config import settings


router = APIRouter()
telegram_repo = MySQLTelegramRepo()


class TelegramStatusResponse(BaseModel):
    connected: bool
    chat_id: int | None = None
    verified_at: datetime | None = None
    token_hint: str | None = None
    start_url: str | None = None


class TelegramVerifyRequest(BaseModel):
    token: str
    chat_id: int


class TelegramVerifyResponse(BaseModel):
    connected: bool
    user_id: int


def _build_start_url(token: str) -> str | None:
    username = settings.telegram_bot_username.strip()
    if not username:
        return None
    username = username.lstrip("@")
    return f"https://t.me/{username}?start={token}"


@router.get("/telegram/status", response_model=TelegramStatusResponse)
def get_status(user=Depends(get_current_user)) -> TelegramStatusResponse:
    status_row = telegram_repo.get_status(int(user.id))
    connected = bool(status_row.get("chat_id")) and bool(status_row.get("verified_at"))
    return TelegramStatusResponse(
        connected=connected,
        chat_id=status_row.get("chat_id"),
        verified_at=status_row.get("verified_at"),
        token_hint=status_row.get("token_hint"),
        start_url=None,
    )


@router.post("/telegram/token", response_model=TelegramStatusResponse)
def create_token(user=Depends(get_current_user)) -> TelegramStatusResponse:
    token = telegram_repo.create_token(int(user.id))
    status_row = telegram_repo.get_status(int(user.id))
    start_url = _build_start_url(token)
    return TelegramStatusResponse(
        connected=False,
        chat_id=status_row.get("chat_id"),
        verified_at=status_row.get("verified_at"),
        token_hint=status_row.get("token_hint"),
        start_url=start_url,
    )


@router.delete("/telegram/connection", response_model=TelegramStatusResponse)
def disconnect(user=Depends(get_current_user)) -> TelegramStatusResponse:
    telegram_repo.disconnect(int(user.id))
    status_row = telegram_repo.get_status(int(user.id))
    return TelegramStatusResponse(
        connected=False,
        chat_id=status_row.get("chat_id"),
        verified_at=status_row.get("verified_at"),
        token_hint=status_row.get("token_hint"),
        start_url=None,
    )


@router.post("/telegram/verify", response_model=TelegramVerifyResponse)
def verify_link(payload: TelegramVerifyRequest) -> TelegramVerifyResponse:
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is required.")
    user_id = telegram_repo.verify_token(token, int(payload.chat_id))
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found.")
    return TelegramVerifyResponse(connected=True, user_id=user_id)
