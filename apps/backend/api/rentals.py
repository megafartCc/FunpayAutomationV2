from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_user
from db.account_repo import MySQLAccountRepo, ActiveRentalRecord


router = APIRouter()
accounts_repo = MySQLAccountRepo()


class ActiveRentalItem(BaseModel):
    id: int
    account: str
    buyer: str
    started: str
    time_left: str
    match_time: str = ""
    hero: str = ""
    status: str = ""


class ActiveRentalResponse(BaseModel):
    items: list[ActiveRentalItem]


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


def _account_label(record: ActiveRentalRecord) -> str:
    name = record.account_name or record.login or f"ID {record.id}"
    if record.lot_number:
        if not name.startswith("\u2116"):
            return f"\u2116{record.lot_number} {name}"
    return name


@router.get("/rentals/active", response_model=ActiveRentalResponse)
def list_active_rentals(user=Depends(get_current_user)) -> ActiveRentalResponse:
    records = accounts_repo.list_active_rentals(int(user.id))
    items: list[ActiveRentalItem] = []
    for record in records:
        total_minutes = (
            int(record.rental_duration_minutes or 0)
            if record.rental_duration_minutes is not None
            else int(record.rental_duration or 0) * 60
        )
        started_at = _parse_datetime(record.rental_start)
        started_label, time_left_label = _format_time_left(started_at, total_minutes)
        items.append(
            ActiveRentalItem(
                id=record.id,
                account=_account_label(record),
                buyer=record.owner,
                started=started_label,
                time_left=time_left_label,
                match_time="",
                hero="",
                status="",
            )
        )
    return ActiveRentalResponse(items=items)
