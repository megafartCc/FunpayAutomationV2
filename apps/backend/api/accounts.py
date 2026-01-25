from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.account_repo import MySQLAccountRepo, AccountRecord
from services.steam_service import deauthorize_sessions, SteamWorkerError


router = APIRouter()
accounts_repo = MySQLAccountRepo()


class AccountCreate(BaseModel):
    account_name: str = Field(..., min_length=1, max_length=255)
    login: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)
    mafile_json: str = Field(..., min_length=2)
    lot_url: str | None = None
    mmr: int | None = None
    rental_duration: int = Field(1, ge=1, le=9999)
    rental_minutes: int = Field(0, ge=0, le=59)


class AccountItem(BaseModel):
    id: int
    account_name: str
    login: str
    password: str
    lot_url: str | None = None
    mmr: int | None = None
    owner: str | None = None
    rental_duration: int
    rental_duration_minutes: int | None = None
    account_frozen: int
    rental_frozen: int
    state: str


class AccountListResponse(BaseModel):
    items: list[AccountItem]


def _to_item(record: AccountRecord) -> AccountItem:
    state = "Available" if not record.owner else "Rented"
    return AccountItem(
        id=record.id,
        account_name=record.account_name,
        login=record.login,
        password=record.password,
        lot_url=record.lot_url,
        mmr=record.mmr,
        owner=record.owner,
        rental_duration=record.rental_duration,
        rental_duration_minutes=record.rental_duration_minutes,
        account_frozen=record.account_frozen,
        rental_frozen=record.rental_frozen,
        state=state,
    )


@router.get("/accounts", response_model=AccountListResponse)
def list_accounts(user=Depends(get_current_user)) -> AccountListResponse:
    items = accounts_repo.list_by_user(int(user.id))
    return AccountListResponse(items=[_to_item(item) for item in items])


@router.post("/accounts", response_model=AccountItem, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, user=Depends(get_current_user)) -> AccountItem:
    total_minutes = payload.rental_duration * 60 + payload.rental_minutes
    if total_minutes <= 0:
        raise HTTPException(status_code=400, detail="Rental duration must be greater than 0")

    created = accounts_repo.create(
        user_id=int(user.id),
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


@router.post("/accounts/{account_id}/steam/deauthorize")
def steam_deauthorize(account_id: int, user=Depends(get_current_user)) -> dict:
    account = accounts_repo.get_for_steam(account_id, int(user.id))
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
