from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.account_repo import MySQLAccountRepo
from db.steam_bridge_repo import MySQLSteamBridgeRepo, SteamBridgeAccountRecord
from services.crypto_service import CryptoError, decrypt_secret, encrypt_secret
from services.presence_service import fetch_presence, presence_status_label
from services.steam_id import extract_steam_id
from services.steam_bridge_service import (
    SteamBridgeError,
    connect_bridge_account,
    disconnect_bridge_account,
    fetch_bridge_status,
    fetch_user_status,
)


router = APIRouter()
bridge_repo = MySQLSteamBridgeRepo()
accounts_repo = MySQLAccountRepo()


class SteamBridgeAccountCreate(BaseModel):
    label: str | None = Field(None, max_length=255)
    login: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)
    shared_secret: str | None = Field(None, max_length=512)
    is_default: bool = False
    auto_connect: bool = True


class SteamBridgeAccountUpdate(BaseModel):
    label: str | None = Field(None, max_length=255)
    login: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = Field(None, min_length=1, max_length=255)
    shared_secret: str | None = Field(None, max_length=512)
    is_default: bool | None = None


class SteamBridgeAccountItem(BaseModel):
    id: int
    label: str | None = None
    login_masked: str
    is_default: bool
    status: str
    last_error: str | None = None
    last_seen: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SteamBridgeAccountList(BaseModel):
    items: list[SteamBridgeAccountItem]


class SteamBridgeStatusItem(BaseModel):
    id: int
    status: str
    last_error: str | None = None
    last_seen: str | None = None
    logged_on: bool | None = None


class SteamBridgeStatusList(BaseModel):
    items: list[SteamBridgeStatusItem]


class SteamPresenceAccountItem(BaseModel):
    account_id: int
    account_name: str
    workspace_id: int | None = None
    workspace_name: str | None = None
    steam_id: str | None = None
    status: str
    hero: str | None = None
    match_time: str | None = None
    in_match: bool = False
    in_game: bool = False
    last_updated: str | None = None


class SteamPresenceAccountList(BaseModel):
    items: list[SteamPresenceAccountItem]


def _mask_login(value: str) -> str:
    if not value:
        return "***"
    if len(value) <= 3:
        return value[0] + "***"
    return f"{value[:2]}***{value[-2:]}"


def _to_item(record: SteamBridgeAccountRecord) -> SteamBridgeAccountItem:
    try:
        login = decrypt_secret(record.login_enc)
        masked = _mask_login(login)
    except CryptoError:
        masked = "***"
    last_seen = record.last_seen.isoformat() if isinstance(record.last_seen, datetime) else None
    created_at = record.created_at.isoformat() if isinstance(record.created_at, datetime) else None
    updated_at = record.updated_at.isoformat() if isinstance(record.updated_at, datetime) else None
    return SteamBridgeAccountItem(
        id=record.id,
        label=record.label,
        login_masked=masked,
        is_default=bool(record.is_default),
        status=record.status or "offline",
        last_error=record.last_error,
        last_seen=last_seen,
        created_at=created_at,
        updated_at=updated_at,
    )

def _parse_last_seen(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(float(value) / 1000.0)
        except Exception:
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


@router.get("/steam-bridge/accounts", response_model=SteamBridgeAccountList)
def list_bridge_accounts(refresh: bool = False, user=Depends(get_current_user)) -> SteamBridgeAccountList:
    user_id = int(user.id)
    records = bridge_repo.list_by_user(user_id)
    items = [_to_item(r) for r in records]
    if refresh and items:
        refreshed: list[SteamBridgeAccountItem] = []
        for record in records:
            try:
                status = fetch_bridge_status(bridge_id=record.id, user_id=user_id)
                status_val = str(status.get("status") or record.status or "offline")
                last_error = status.get("last_error") or None
                last_seen = _parse_last_seen(status.get("last_seen"))
                bridge_repo.update(
                    record.id,
                    user_id,
                    status=status_val,
                    last_error=last_error,
                    last_seen=last_seen,
                )
            except SteamBridgeError:
                pass
            refreshed.append(_to_item(bridge_repo.get_by_id(record.id, user_id) or record))
        items = refreshed
    return SteamBridgeAccountList(items=items)


@router.post("/steam-bridge/accounts", response_model=SteamBridgeAccountItem, status_code=status.HTTP_201_CREATED)
def create_bridge_account(payload: SteamBridgeAccountCreate, user=Depends(get_current_user)) -> SteamBridgeAccountItem:
    user_id = int(user.id)
    try:
        login_enc = encrypt_secret(payload.login.strip())
        password_enc = encrypt_secret(payload.password)
        shared_secret_enc = encrypt_secret(payload.shared_secret) if payload.shared_secret else None
    except CryptoError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    existing = bridge_repo.list_by_user(user_id)
    is_default = payload.is_default or not existing
    record = bridge_repo.create(
        user_id=user_id,
        label=payload.label.strip() if payload.label else None,
        login_enc=login_enc,
        password_enc=password_enc,
        shared_secret_enc=shared_secret_enc,
        is_default=is_default,
    )
    if payload.auto_connect:
        try:
            connect_bridge_account(
                bridge_id=record.id,
                user_id=user_id,
                login=payload.login.strip(),
                password=payload.password,
                shared_secret=payload.shared_secret,
                is_default=is_default,
            )
            bridge_repo.update(record.id, user_id, status="online", last_error=None)
        except SteamBridgeError as exc:
            bridge_repo.update(record.id, user_id, status="error", last_error=exc.message)
    return _to_item(bridge_repo.get_by_id(record.id, user_id) or record)


@router.patch("/steam-bridge/accounts/{bridge_id}", response_model=SteamBridgeAccountItem)
def update_bridge_account(
    bridge_id: int,
    payload: SteamBridgeAccountUpdate,
    user=Depends(get_current_user),
) -> SteamBridgeAccountItem:
    user_id = int(user.id)
    record = bridge_repo.get_by_id(int(bridge_id), user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bridge account not found.")
    login_enc = None
    password_enc = None
    shared_secret_enc = None
    try:
        if payload.login is not None:
            login_enc = encrypt_secret(payload.login.strip())
        if payload.password is not None:
            password_enc = encrypt_secret(payload.password)
        if payload.shared_secret is not None:
            shared_secret_enc = encrypt_secret(payload.shared_secret) if payload.shared_secret else None
    except CryptoError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    updated = bridge_repo.update(
        record.id,
        user_id,
        label=payload.label.strip() if payload.label else None,
        login_enc=login_enc,
        password_enc=password_enc,
        shared_secret_enc=shared_secret_enc,
        is_default=payload.is_default,
    )
    return _to_item(updated or record)


@router.post("/steam-bridge/accounts/{bridge_id}/connect", response_model=SteamBridgeAccountItem)
def connect_account(bridge_id: int, user=Depends(get_current_user)) -> SteamBridgeAccountItem:
    user_id = int(user.id)
    record = bridge_repo.get_by_id(int(bridge_id), user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bridge account not found.")
    try:
        login = decrypt_secret(record.login_enc)
        password = decrypt_secret(record.password_enc)
        shared = decrypt_secret(record.shared_secret_enc) if record.shared_secret_enc else None
    except CryptoError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        connect_bridge_account(
            bridge_id=record.id,
            user_id=user_id,
            login=login,
            password=password,
            shared_secret=shared,
            is_default=bool(record.is_default),
        )
        bridge_repo.update(record.id, user_id, status="online", last_error=None)
    except SteamBridgeError as exc:
        bridge_repo.update(record.id, user_id, status="error", last_error=exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _to_item(bridge_repo.get_by_id(record.id, user_id) or record)


@router.post("/steam-bridge/accounts/{bridge_id}/disconnect", response_model=SteamBridgeAccountItem)
def disconnect_account(bridge_id: int, user=Depends(get_current_user)) -> SteamBridgeAccountItem:
    user_id = int(user.id)
    record = bridge_repo.get_by_id(int(bridge_id), user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bridge account not found.")
    try:
        disconnect_bridge_account(bridge_id=record.id, user_id=user_id)
        bridge_repo.update(record.id, user_id, status="offline", last_error=None)
    except SteamBridgeError as exc:
        bridge_repo.update(record.id, user_id, status="error", last_error=exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _to_item(bridge_repo.get_by_id(record.id, user_id) or record)


@router.post("/steam-bridge/accounts/{bridge_id}/default", response_model=SteamBridgeAccountItem)
def set_default_account(bridge_id: int, user=Depends(get_current_user)) -> SteamBridgeAccountItem:
    user_id = int(user.id)
    record = bridge_repo.set_default(int(bridge_id), user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bridge account not found.")
    return _to_item(record)


@router.delete("/steam-bridge/accounts/{bridge_id}")
def delete_bridge_account(bridge_id: int, user=Depends(get_current_user)) -> dict:
    user_id = int(user.id)
    deleted = bridge_repo.delete(int(bridge_id), user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bridge account not found.")
    return {"ok": True}


@router.get("/steam-bridge/status", response_model=SteamBridgeStatusList)
def list_bridge_status(user=Depends(get_current_user)) -> SteamBridgeStatusList:
    user_id = int(user.id)
    records = bridge_repo.list_by_user(user_id)
    items: list[SteamBridgeStatusItem] = []
    for record in records:
        try:
            status = fetch_bridge_status(bridge_id=record.id, user_id=user_id)
            status_val = str(status.get("status") or record.status or "offline")
            items.append(
                SteamBridgeStatusItem(
                    id=record.id,
                    status=status_val,
                    last_error=status.get("last_error"),
                    last_seen=(_parse_last_seen(status.get("last_seen")).isoformat() if status.get("last_seen") else None),
                    logged_on=bool(status.get("logged_on")),
                )
            )
        except SteamBridgeError:
            items.append(
                SteamBridgeStatusItem(
                    id=record.id,
                    status=record.status or "offline",
                    last_error=record.last_error,
                    last_seen=record.last_seen.isoformat() if isinstance(record.last_seen, datetime) else None,
                    logged_on=None,
                )
            )
    return SteamBridgeStatusList(items=items)


@router.get("/steam-bridge/presence", response_model=SteamPresenceAccountList)
def list_presence_accounts(
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> SteamPresenceAccountList:
    user_id = int(user.id)
    default_bridge_id = None
    try:
        default_bridge_id = bridge_repo.get_default_id(user_id)
    except Exception:
        default_bridge_id = None
    if workspace_id is None:
        accounts = accounts_repo.list_by_user(user_id)
    else:
        accounts = accounts_repo.list_by_workspace(user_id, int(workspace_id))
    items: list[SteamPresenceAccountItem] = []
    for account in accounts:
        steam_id = extract_steam_id(account.mafile_json)
        presence = fetch_presence(steam_id, user_id=user_id, bridge_id=default_bridge_id)
        status = presence_status_label(presence) if presence else ""
        derived = presence.get("derived") if isinstance(presence, dict) and isinstance(presence.get("derived"), dict) else {}
        hero = str(
            derived.get("hero_name")
            or (presence.get("hero_name") if isinstance(presence, dict) else "")
            or (presence.get("hero") if isinstance(presence, dict) else "")
            or ""
        )
        match_time = str(
            derived.get("match_time")
            or (presence.get("match_time") if isinstance(presence, dict) else "")
            or ""
        )
        in_match = bool(derived.get("in_match") or (presence.get("in_match") if isinstance(presence, dict) else False))
        in_game = bool(derived.get("in_game") or (presence.get("in_game") if isinstance(presence, dict) else False))
        last_updated = None
        if isinstance(presence, dict) and presence.get("last_updated"):
            try:
                last_updated = datetime.fromtimestamp(int(presence.get("last_updated")) / 1000).isoformat()
            except Exception:
                last_updated = None
        items.append(
            SteamPresenceAccountItem(
                account_id=account.id,
                account_name=account.account_name,
                workspace_id=account.workspace_id,
                workspace_name=account.workspace_name,
                steam_id=steam_id,
                status=status,
                hero=hero or None,
                match_time=match_time or None,
                in_match=in_match,
                in_game=in_game,
                last_updated=last_updated,
            )
        )
    return SteamPresenceAccountList(items=items)
