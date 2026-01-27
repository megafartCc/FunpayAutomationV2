from __future__ import annotations

from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.account_repo import MySQLAccountRepo, ActiveRentalRecord
from db.workspace_repo import MySQLWorkspaceRepo
from services.rentals_cache import RentalsCache
from services.presence_service import fetch_presence, presence_status_label
from services.steam_service import deauthorize_sessions, SteamWorkerError
from services.chat_notify import notify_owner


router = APIRouter()
accounts_repo = MySQLAccountRepo()
rentals_cache = RentalsCache()
workspace_repo = MySQLWorkspaceRepo()


class ActiveRentalItem(BaseModel):
    id: int
    account: str
    buyer: str
    started: str
    time_left: str
    workspace_id: int | None = None
    workspace_name: str | None = None
    match_time: str = ""
    hero: str = ""
    status: str = ""


class ActiveRentalResponse(BaseModel):
    items: list[ActiveRentalItem]


class FreezeRequest(BaseModel):
    frozen: bool


class ReplaceRequest(BaseModel):
    mmr_range: int | None = Field(None, ge=0, le=5000)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _format_time_left(started_at: datetime | None, total_minutes: int) -> tuple[str, str]:
    if not started_at or total_minutes <= 0:
        return "-", "\u043e\u0436\u0438\u0434\u0430\u0435\u043c !\u043a\u043e\u0434"
    now = datetime.utcnow()
    expiry = started_at + timedelta(minutes=total_minutes)
    remaining = expiry - now
    if remaining.total_seconds() < 0:
        remaining = timedelta(0)
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    started_label = started_at.strftime("%H:%M:%S")
    time_left_label = f"{hours} \u0447 {minutes} \u043c\u0438\u043d"
    return started_label, time_left_label


def _format_duration_minutes(total_minutes: int) -> str:
    total = max(0, int(total_minutes))
    hours = total // 60
    minutes = total % 60
    if hours and minutes:
        return f"{hours} ч {minutes} мин"
    if hours:
        return f"{hours} ч"
    return f"{minutes} мин"


def _build_admin_replace_message(account: dict, total_minutes: int) -> str:
    name = account.get("account_name") or account.get("login") or f"ID {account.get('id')}"
    lines = [
        "✅ Админ сделал вам замену аккаунта.",
        "Ваш аккаунт:",
        f"ID: {account.get('id')}",
        f"Название: {name}",
        f"Логин: {account.get('login')}",
        f"Пароль: {account.get('password')}",
        f"Аренда: {_format_duration_minutes(total_minutes)}",
        "",
        "⏱️ Отсчет аренды начнется после первого получения кода (!код).",
        "",
        "Команды:",
        "!акк — данные аккаунта",
        "!код — код Steam Guard",
        "!админ — вызвать продавца",
    ]
    return "\n".join(lines)


def _account_label(record: ActiveRentalRecord) -> str:
    name = record.account_name or record.login or f"ID {record.id}"
    if record.lot_number:
        if not name.startswith("\u2116"):
            return f"\u2116{record.lot_number} {name}"
    return name


def _steam_id_from_mafile(mafile_json: str | None) -> str | None:
    if not mafile_json:
        return None
    try:
        data = json.loads(mafile_json) if isinstance(mafile_json, str) else mafile_json
        steam_value = (data or {}).get("Session", {}).get("SteamID")
        if steam_value is None:
            steam_value = (data or {}).get("steamid") or (data or {}).get("SteamID")
        if steam_value is not None:
            return str(int(steam_value))
    except Exception:
        return None
    return None


@router.get("/rentals/active", response_model=ActiveRentalResponse)
def list_active_rentals(workspace_id: int | None = None, user=Depends(get_current_user)) -> ActiveRentalResponse:
    user_id = int(user.id)
    workspace = None
    if workspace_id is not None:
        workspace = workspace_repo.get_by_id(int(workspace_id), user_id)
        if not workspace:
            raise HTTPException(status_code=400, detail="Select a workspace for rentals.")
    cached_items = rentals_cache.get(user_id, workspace_id)
    if cached_items is not None:
        return ActiveRentalResponse(items=[ActiveRentalItem(**item) for item in cached_items])

    records = accounts_repo.list_active_rentals(user_id, workspace_id)
    workspace_name_map: dict[int, str] = {}
    if workspace_id is None:
        workspace_name_map = {ws.id: ws.name for ws in workspace_repo.list_by_user(user_id)}
    elif workspace:
        workspace_name_map = {int(workspace.id): workspace.name}
    items: list[ActiveRentalItem] = []
    for record in records:
        if record.workspace_id is not None:
            record.workspace_name = workspace_name_map.get(int(record.workspace_id))
        total_minutes = (
            int(record.rental_duration_minutes or 0)
            if record.rental_duration_minutes is not None
            else int(record.rental_duration or 0) * 60
        )
        started_at = _parse_datetime(record.rental_start)
        started_label, time_left_label = _format_time_left(started_at, total_minutes)
        steam_id = _steam_id_from_mafile(record.mafile_json)
        presence = fetch_presence(steam_id)
        status = presence_status_label(presence)
        hero = ""
        match_time = ""
        if presence:
            derived = presence.get("derived") if isinstance(presence.get("derived"), dict) else {}
            hero = str(
                derived.get("hero_name")
                or presence.get("hero_name")
                or presence.get("hero")
                or ""
            )
            match_time = str(
                derived.get("match_time")
                or presence.get("match_time")
                or ""
            )
        items.append(
            ActiveRentalItem(
                id=record.id,
                account=_account_label(record),
                buyer=record.owner,
                started=started_label,
                time_left=time_left_label,
                workspace_id=record.workspace_id,
                workspace_name=record.workspace_name,
                match_time=match_time,
                hero=hero,
                status=status,
            )
        )
    rentals_cache.set(user_id, [item.model_dump() for item in items], workspace_id)
    return ActiveRentalResponse(items=items)


@router.post("/rentals/{account_id}/freeze")
def freeze_rental(
    account_id: int,
    payload: FreezeRequest,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for rentals.")
    account = accounts_repo.get_by_id(account_id, int(user.id), int(workspace_id))
    if not account or not account.get("owner"):
        raise HTTPException(status_code=404, detail="Rental not found")

    if payload.frozen:
        if int(account.get("rental_frozen") or 0):
            return {"success": True, "frozen": True}
        now = datetime.utcnow()
        ok = accounts_repo.set_rental_freeze_state(
            account_id,
            int(user.id),
            int(workspace_id),
            True,
            frozen_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        if not ok:
            raise HTTPException(status_code=400, detail="Failed to freeze rental")
        mafile_json = account.get("mafile_json")
        if mafile_json:
            try:
                deauthorize_sessions(
                    steam_login=account.get("login") or account.get("account_name"),
                    steam_password=account.get("password") or "",
                    mafile_json=mafile_json,
                )
            except SteamWorkerError:
                pass
        notify_owner(
            user_id=int(user.id),
            workspace_id=int(workspace_id),
            owner=account.get("owner"),
            text=f"Админ поставил аренду на паузу для аккаунта {account_id}.",
        )
        return {"success": True, "frozen": True}

    if not int(account.get("rental_frozen") or 0):
        return {"success": True, "frozen": False}

    frozen_at = account.get("rental_frozen_at")
    rental_start = account.get("rental_start")
    new_start = None
    if rental_start and frozen_at:
        try:
            start_dt = rental_start if isinstance(rental_start, datetime) else datetime.strptime(
                str(rental_start), "%Y-%m-%d %H:%M:%S"
            )
            frozen_dt = frozen_at if isinstance(frozen_at, datetime) else datetime.strptime(
                str(frozen_at), "%Y-%m-%d %H:%M:%S"
            )
            delta = datetime.utcnow() - frozen_dt
            if delta.total_seconds() < 0:
                delta = timedelta(0)
            new_start = start_dt + delta
        except Exception:
            new_start = None

    ok = accounts_repo.set_rental_freeze_state(
        account_id,
        int(user.id),
        int(workspace_id),
        False,
        rental_start=new_start.strftime("%Y-%m-%d %H:%M:%S") if new_start else None,
        frozen_at=None,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to unfreeze rental")
    notify_owner(
        user_id=int(user.id),
        workspace_id=int(workspace_id),
        owner=account.get("owner"),
        text=f"Админ снял паузу аренды для аккаунта {account_id}.",
    )
    return {"success": True, "frozen": False}


@router.post("/rentals/{account_id}/replace")
def replace_rental(
    account_id: int,
    payload: ReplaceRequest | None = None,
    workspace_id: int | None = None,
    user=Depends(get_current_user),
) -> dict:
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    workspace = workspace_repo.get_by_id(int(workspace_id), int(user.id))
    if not workspace:
        raise HTTPException(status_code=400, detail="Select a workspace for rentals.")
    account = accounts_repo.get_by_id(account_id, int(user.id), int(workspace_id))
    if not account or not account.get("owner"):
        raise HTTPException(status_code=404, detail="Rental not found")
    owner = account.get("owner")
    try:
        target_mmr = int(account.get("mmr"))
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot replace: MMR missing")
    max_delta = payload.mmr_range if payload and payload.mmr_range is not None else 1000
    effective_workspace_id = account.get("last_rented_workspace_id") or account.get("workspace_id") or workspace_id
    if effective_workspace_id is None:
        raise HTTPException(status_code=400, detail="Workspace missing for replacement")
    replacement = accounts_repo.find_replacement_account(
        user_id=int(user.id),
        workspace_id=int(effective_workspace_id),
        target_mmr=target_mmr,
        exclude_id=int(account_id),
        max_delta=int(max_delta),
    )
    if not replacement:
        raise HTTPException(status_code=404, detail="No replacement account found")

    rental_start = account.get("rental_start")
    if isinstance(rental_start, datetime):
        rental_start_str = rental_start.strftime("%Y-%m-%d %H:%M:%S")
    elif rental_start:
        rental_start_str = str(rental_start)
    else:
        rental_start_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    base_minutes = account.get("rental_duration_minutes")
    if base_minutes is None:
        try:
            base_minutes = int(account.get("rental_duration") or 0) * 60
        except Exception:
            base_minutes = 0
    base_minutes = int(base_minutes or 0)
    try:
        base_hours = int(account.get("rental_duration") or 0)
    except Exception:
        base_hours = max(1, (base_minutes + 59) // 60)
    if base_hours <= 0 and base_minutes > 0:
        base_hours = max(1, (base_minutes + 59) // 60)

    ok = accounts_repo.replace_rental_account(
        old_account_id=int(account_id),
        new_account_id=int(replacement.get("id") or 0),
        user_id=int(user.id),
        owner=str(owner),
        workspace_id=int(effective_workspace_id),
        rental_start=rental_start_str,
        rental_duration=base_hours,
        rental_duration_minutes=base_minutes,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to replace rental")

    mafile_json = account.get("mafile_json")
    if mafile_json:
        try:
            deauthorize_sessions(
                steam_login=account.get("login") or account.get("account_name"),
                steam_password=account.get("password") or "",
                mafile_json=mafile_json,
            )
        except SteamWorkerError:
            pass

    notify_owner(
        user_id=int(user.id),
        workspace_id=int(effective_workspace_id),
        owner=owner,
        text=_build_admin_replace_message(replacement, base_minutes),
    )

    return {"success": True, "new_account_id": int(replacement.get("id") or 0)}
