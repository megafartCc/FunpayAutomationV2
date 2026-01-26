from __future__ import annotations

from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.account_repo import MySQLAccountRepo, AccountRecord
from db.workspace_repo import MySQLWorkspaceRepo
from services.steam_service import deauthorize_sessions, SteamWorkerError


router = APIRouter()
accounts_repo = MySQLAccountRepo()
workspace_repo = MySQLWorkspaceRepo()


class AccountCreate(BaseModel):
    workspace_id: int = Field(..., ge=1)
    account_name: str = Field(..., min_length=1, max_length=255)
    login: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)
    mafile_json: str = Field(..., min_length=2)
    lot_url: str | None = None
    mmr: int | None = None
    rental_duration: int = Field(1, ge=1, le=9999)
    rental_minutes: int = Field(0, ge=0, le=59)


class AccountUpdate(BaseModel):
    account_name: str | None = Field(None, min_length=1, max_length=255)
    login: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = Field(None, min_length=1, max_length=255)
    mmr: int | None = Field(None, ge=0)
    rental_duration: int | None = Field(None, ge=1, le=9999)
    rental_minutes: int | None = Field(None, ge=0, le=59)


class AssignRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=255)


class FreezeRequest(BaseModel):
    frozen: bool


class ExtendRequest(BaseModel):
    hours: int = Field(0, ge=0, le=9999)
    minutes: int = Field(0, ge=0, le=59)


class AccountItem(BaseModel):
    id: int
    workspace_id: int | None = None
    workspace_name: str | None = None
    account_name: str
    login: str
    password: str
    lot_url: str | None = None
    mmr: int | None = None
    owner: str | None = None
    rental_start: str | None = None
    rental_duration: int
    rental_duration_minutes: int | None = None
    account_frozen: int
    rental_frozen: int
    state: str
    steam_id: str | None = None


class AccountListResponse(BaseModel):
    items: list[AccountItem]


def _to_item(record: AccountRecord) -> AccountItem:
    state = "Available" if not record.owner else "Rented"
    steam_id = None
    if record.mafile_json:
        try:
            data = json.loads(record.mafile_json) if isinstance(record.mafile_json, str) else record.mafile_json
            steam_value = (data or {}).get("Session", {}).get("SteamID")
            if steam_value is None:
                steam_value = (data or {}).get("steamid") or (data or {}).get("SteamID")
            if steam_value is not None:
                steam_id = str(int(steam_value))
        except Exception:
            steam_id = None
    rental_start = record.rental_start
    if isinstance(rental_start, datetime):
        rental_start = rental_start.isoformat()
    elif rental_start is not None:
        rental_start = str(rental_start)

    return AccountItem(
        id=record.id,
        workspace_id=record.workspace_id,
        workspace_name=record.workspace_name,
        account_name=record.account_name,
        login=record.login,
        password=record.password,
        lot_url=record.lot_url,
        mmr=record.mmr,
        owner=record.owner,
        rental_start=rental_start,
        rental_duration=record.rental_duration,
        rental_duration_minutes=record.rental_duration_minutes,
        account_frozen=record.account_frozen,
        rental_frozen=record.rental_frozen,
        state=state,
        steam_id=steam_id,
    )


def _ensure_workspace(workspace_id: int | None, user_id: int) -> None:
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user_id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for this account.")


@router.get("/accounts", response_model=AccountListResponse)
def list_accounts(workspace_id: int | None = None, user=Depends(get_current_user)) -> AccountListResponse:
    _ensure_workspace(workspace_id, int(user.id))
    items = accounts_repo.list_by_workspace(int(user.id), int(workspace_id))
    return AccountListResponse(items=[_to_item(item) for item in items])


@router.post("/accounts", response_model=AccountItem, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, user=Depends(get_current_user)) -> AccountItem:
    total_minutes = payload.rental_duration * 60 + payload.rental_minutes
    if total_minutes <= 0:
        raise HTTPException(status_code=400, detail="Rental duration must be greater than 0")
    workspace = workspace_repo.get_by_id(int(payload.workspace_id), int(user.id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for this account.")

    created = accounts_repo.create(
        user_id=int(user.id),
        workspace_id=int(payload.workspace_id),
        account_name=payload.account_name.strip(),
        login=payload.login.strip(),
        password=payload.password,
        mafile_json=payload.mafile_json.strip(),
        lot_url=payload.lot_url.strip() if payload.lot_url else None,
        mmr=payload.mmr,
        rental_duration=payload.rental_duration,
        rental_duration_minutes=total_minutes,
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
        )
    return _to_item(created)


@router.patch("/accounts/{account_id}", response_model=AccountItem)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> AccountItem:
    _ensure_workspace(workspace_id, int(user.id))
    current = accounts_repo.get_by_id(account_id, int(user.id), int(workspace_id))
    if not current:
        raise HTTPException(status_code=404, detail="Account not found")

    fields: dict = {}
    if payload.account_name:
        fields["account_name"] = payload.account_name.strip()
    if payload.login:
        fields["login"] = payload.login.strip()
    if payload.password:
        fields["password"] = payload.password
    if payload.mmr is not None:
        fields["mmr"] = payload.mmr

    if payload.rental_duration is not None or payload.rental_minutes is not None:
        current_hours = int(current.get("rental_duration") or 0)
        current_minutes_total = current.get("rental_duration_minutes")
        if current_minutes_total is None:
            current_minutes_total = current_hours * 60
        try:
            current_minutes_total = int(current_minutes_total)
        except Exception:
            current_minutes_total = current_hours * 60
        current_minutes = current_minutes_total % 60
        hours = payload.rental_duration if payload.rental_duration is not None else current_hours
        minutes = payload.rental_minutes if payload.rental_minutes is not None else current_minutes
        total_minutes = hours * 60 + minutes
        if total_minutes <= 0:
            raise HTTPException(status_code=400, detail="Rental duration must be greater than 0")
        fields["rental_duration"] = hours
        fields["rental_duration_minutes"] = total_minutes

    if not fields:
        raise HTTPException(status_code=400, detail="No changes provided")

    success = accounts_repo.update_account(account_id, int(user.id), int(workspace_id), fields)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update account")

    updated = accounts_repo.get_by_id(account_id, int(user.id), int(workspace_id))
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")
    return _to_item(AccountRecord(
        id=int(updated["id"]),
        user_id=int(updated["user_id"]),
        workspace_id=updated.get("workspace_id"),
        workspace_name=None,
        account_name=updated["account_name"],
        login=updated["login"],
        password=updated["password"],
        lot_url=updated.get("lot_url"),
        mmr=updated.get("mmr"),
        owner=updated.get("owner"),
        rental_start=updated.get("rental_start"),
        rental_duration=int(updated.get("rental_duration") or 0),
        rental_duration_minutes=updated.get("rental_duration_minutes"),
        account_frozen=int(updated.get("account_frozen") or 0),
        rental_frozen=int(updated.get("rental_frozen") or 0),
        mafile_json=updated.get("mafile_json"),
    ))


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, workspace_id: int | None = None, user=Depends(get_current_user)) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    success = accounts_repo.delete_account_by_id(account_id, int(user.id), int(workspace_id))
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "ok"}


@router.post("/accounts/{account_id}/assign")
def assign_account(
    account_id: int,
    payload: AssignRequest,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    success = accounts_repo.set_account_owner(
        account_id, int(user.id), int(workspace_id), payload.owner.strip()
    )
    if not success:
        raise HTTPException(status_code=400, detail="Account already assigned")
    return {"status": "ok"}


@router.post("/accounts/{account_id}/release")
def release_account(account_id: int, workspace_id: int | None = None, user=Depends(get_current_user)) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    success = accounts_repo.release_account(account_id, int(user.id), int(workspace_id))
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "ok"}


@router.post("/accounts/{account_id}/extend")
def extend_account(
    account_id: int,
    payload: ExtendRequest,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    total_minutes = payload.hours * 60 + payload.minutes
    if total_minutes <= 0:
        raise HTTPException(status_code=400, detail="Extension must be greater than 0")
    success = accounts_repo.extend_rental_duration(
        account_id, int(user.id), int(workspace_id), payload.hours, payload.minutes
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to extend rental")
    return {"status": "ok"}


@router.post("/accounts/{account_id}/freeze")
def freeze_account(
    account_id: int,
    payload: FreezeRequest,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    success = accounts_repo.set_account_frozen(account_id, int(user.id), int(workspace_id), payload.frozen)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True, "frozen": payload.frozen}


@router.post("/accounts/{account_id}/steam/deauthorize")
def steam_deauthorize(account_id: int, workspace_id: int | None = None, user=Depends(get_current_user)) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    account = accounts_repo.get_for_steam(account_id, int(user.id), int(workspace_id))
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.mafile_json:
        raise HTTPException(status_code=400, detail="mafile_json is required for Steam actions")

    try:
        deauthorize_sessions(
            steam_login=account.login or account.account_name,
            steam_password=account.password,
            mafile_json=account.mafile_json,
        )
    except SteamWorkerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {"success": True}
