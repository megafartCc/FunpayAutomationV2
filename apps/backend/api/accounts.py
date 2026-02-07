from __future__ import annotations

from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.account_repo import MySQLAccountRepo, AccountRecord
from db.workspace_repo import MySQLWorkspaceRepo
from db.notifications_repo import MySQLNotificationsRepo
from services.steam_service import deauthorize_sessions, SteamWorkerError
from services.chat_notify import notify_owner


router = APIRouter()
accounts_repo = MySQLAccountRepo()
workspace_repo = MySQLWorkspaceRepo()
notifications_repo = MySQLNotificationsRepo()


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
    workspace_id: int | None = Field(None, ge=1)


class AssignRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=255)
    hours: int | None = Field(None, ge=0, le=9999)
    minutes: int | None = Field(None, ge=0, le=59)


class FreezeRequest(BaseModel):
    frozen: bool


class ExtendRequest(BaseModel):
    hours: int = Field(0, ge=0, le=9999)
    minutes: int = Field(0, ge=0, le=59)


class LowPriorityRequest(BaseModel):
    low_priority: bool


class AccountItem(BaseModel):
    id: int
    workspace_id: int | None = None
    workspace_name: str | None = None
    last_rented_workspace_id: int | None = None
    last_rented_workspace_name: str | None = None
    account_name: str
    login: str
    password: str
    lot_url: str | None = None
    lot_number: int | None = None
    mmr: int | None = None
    owner: str | None = None
    rental_start: str | None = None
    rental_duration: int
    rental_duration_minutes: int | None = None
    low_priority: int
    account_frozen: int
    rental_frozen: int
    state: str
    steam_id: str | None = None


class AccountListResponse(BaseModel):
    items: list[AccountItem]


def _to_item(record: AccountRecord) -> AccountItem:
    if record.low_priority:
        state = "Low Priority"
    elif record.account_frozen:
        state = "Frozen"
    elif record.owner:
        state = "Rented"
    else:
        state = "Available"
    steam_id = None
    if record.mafile_json:
        try:
            data = json.loads(record.mafile_json) if isinstance(record.mafile_json, str) else record.mafile_json
            session = (data or {}).get("Session") if isinstance(data, dict) else None
            steam_value = None
            if isinstance(session, dict):
                steam_value = session.get("SteamID") or session.get("steamid") or session.get("SteamID64")
            if steam_value is None and isinstance(data, dict):
                steam_value = (
                    data.get("steamid")
                    or data.get("SteamID")
                    or data.get("steam_id")
                    or data.get("steamId")
                    or data.get("steamid64")
                    or data.get("SteamID64")
                )
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
        last_rented_workspace_id=record.last_rented_workspace_id,
        last_rented_workspace_name=record.last_rented_workspace_name,
        account_name=record.account_name,
        login=record.login,
        password=record.password,
        lot_url=record.lot_url,
        lot_number=record.lot_number,
        mmr=record.mmr,
        owner=record.owner,
        rental_start=rental_start,
        rental_duration=record.rental_duration,
        rental_duration_minutes=record.rental_duration_minutes,
        low_priority=record.low_priority,
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
    user_id = int(user.id)
    if workspace_id is None:
        items = accounts_repo.list_by_user(user_id)
        workspaces = workspace_repo.list_by_user(user_id)
        name_map = {ws.id: ws.name for ws in workspaces}
        for item in items:
            item.workspace_name = name_map.get(item.workspace_id)
        return AccountListResponse(items=[_to_item(item) for item in items])
    _ensure_workspace(workspace_id, user_id)
    items = accounts_repo.list_by_workspace(user_id, int(workspace_id))
    workspace = workspace_repo.get_by_id(int(workspace_id), user_id)
    if workspace:
        for item in items:
            item.workspace_name = workspace.name
    return AccountListResponse(items=[_to_item(item) for item in items])


@router.get("/accounts/low-priority", response_model=AccountListResponse)
def list_low_priority_accounts(
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> AccountListResponse:
    user_id = int(user.id)
    if workspace_id is not None:
        _ensure_workspace(workspace_id, user_id)
    items = accounts_repo.list_low_priority(user_id, workspace_id)
    if workspace_id is None:
        workspaces = workspace_repo.list_by_user(user_id)
        name_map = {ws.id: ws.name for ws in workspaces}
        for item in items:
            item.workspace_name = name_map.get(item.workspace_id)
    else:
        workspace = workspace_repo.get_by_id(int(workspace_id), user_id)
        if workspace:
            for item in items:
                item.workspace_name = workspace.name
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
    if payload.workspace_id is not None:
        target_workspace = workspace_repo.get_by_id(int(payload.workspace_id), int(user.id))
        if not target_workspace:
            raise HTTPException(status_code=400, detail="Select a workspace for this account.")
        fields["workspace_id"] = int(payload.workspace_id)

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
        last_rented_workspace_id=updated.get("last_rented_workspace_id"),
        last_rented_workspace_name=None,
        account_name=updated["account_name"],
        login=updated["login"],
        password=updated["password"],
        lot_url=updated.get("lot_url"),
        mmr=updated.get("mmr"),
        owner=updated.get("owner"),
        rental_start=updated.get("rental_start"),
        rental_duration=int(updated.get("rental_duration") or 0),
        rental_duration_minutes=updated.get("rental_duration_minutes"),
        low_priority=int(updated.get("low_priority") or 0),
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
    hours = payload.hours
    minutes = payload.minutes
    if hours is not None or minutes is not None:
        total_minutes = (hours or 0) * 60 + (minutes or 0)
        if total_minutes <= 0:
            raise HTTPException(status_code=400, detail="Rental duration must be greater than 0")
    success = accounts_repo.set_account_owner(
        account_id,
        int(user.id),
        int(workspace_id),
        payload.owner.strip(),
        rental_hours=hours,
        rental_minutes=minutes,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Account already assigned")
    return {"status": "ok"}


@router.post("/accounts/{account_id}/release")
def release_account(account_id: int, workspace_id: int | None = None, user=Depends(get_current_user)) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    account = accounts_repo.get_by_id(account_id, int(user.id), int(workspace_id))
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    success = accounts_repo.release_account(account_id, int(user.id), int(workspace_id))
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")

    deauth_status = "skipped"
    login = account.get("login") or account.get("account_name")
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
                title="Steam deauthorize on release",
                message="Steam sessions deauthorized after rental release.",
                owner=account.get("owner"),
                account_name=account.get("account_name") or account.get("login"),
                account_id=account_id,
                user_id=int(user.id),
                workspace_id=int(workspace_id) if workspace_id is not None else None,
            )
        except SteamWorkerError as exc:
            deauth_status = "failed"
            notifications_repo.log_notification(
                event_type="deauthorize",
                status="failed",
                title="Steam deauthorize on release",
                message=f"Steam deauthorize after release failed: {exc.message}",
                owner=account.get("owner"),
                account_name=account.get("account_name") or account.get("login"),
                account_id=account_id,
                user_id=int(user.id),
                workspace_id=int(workspace_id) if workspace_id is not None else None,
            )

    return {"status": "ok", "deauthorize": deauth_status}


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
    account = accounts_repo.get_by_id(account_id, int(user.id), int(workspace_id))
    if account and account.get("owner"):
        minutes_total = payload.hours * 60 + payload.minutes
        if minutes_total > 0:
            hours = minutes_total // 60
            minutes = minutes_total % 60
            if hours and minutes:
                label = f"{hours} ч {minutes} мин"
            elif hours:
                label = f"{hours} ч"
            else:
                label = f"{minutes} мин"
            notify_owner(
                user_id=int(user.id),
                workspace_id=int(workspace_id),
                owner=account.get("owner"),
                text=f"Админ продлил вам аренду на {label} для аккаунта {account_id}.",
            )
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
    account = accounts_repo.get_by_id(account_id, int(user.id), int(workspace_id))
    if account and account.get("owner"):
        notify_owner(
            user_id=int(user.id),
            workspace_id=int(workspace_id),
            owner=account.get("owner"),
            text=(
                "Администратор заморозил ваш аккаунт. Доступ приостановлен."
                if payload.frozen
                else "Администратор разморозил ваш аккаунт. Доступ восстановлен. "
                     "Чтобы получить код еще раз, пропишите команду !код."
            ),
        )
    return {"success": True, "frozen": payload.frozen}


@router.post("/accounts/{account_id}/low-priority")
def set_low_priority(
    account_id: int,
    payload: LowPriorityRequest,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    _ensure_workspace(workspace_id, int(user.id))
    success = accounts_repo.set_low_priority(account_id, int(user.id), int(workspace_id), payload.low_priority)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True, "low_priority": payload.low_priority}


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
        notifications_repo.log_notification(
            event_type="deauthorize",
            status="failed",
            title="Manual Steam deauthorize",
            message=exc.message,
            account_name=account.account_name,
            account_id=account.id,
            user_id=int(user.id),
            workspace_id=int(workspace_id),
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    notifications_repo.log_notification(
        event_type="deauthorize",
        status="ok",
        title="Manual Steam deauthorize",
        message="Deauthorize request completed.",
        account_name=account.account_name,
        account_id=account.id,
        user_id=int(user.id),
        workspace_id=int(workspace_id),
    )
    return {"success": True}
