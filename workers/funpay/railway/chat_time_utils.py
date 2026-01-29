from __future__ import annotations

import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

_CHAT_TIME_CLASS_KEYS = (
    "contact-item-time",
    "contact-item-date",
    "chat-msg-time",
    "chat-msg-date",
    "chat-msg-date-time",
)
_CHAT_TIME_ATTR_KEYS = (
    "data-time",
    "data-date",
    "data-timestamp",
    "data-last-message-time",
    "data-last-msg-time",
)
_CHAT_TIME_RE_YMD = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_DMY = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_DM = re.compile(r"\b(\d{1,2})[./](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_TIME = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_RU_MONTH = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>[а-яё\.]+)\s*(?P<year>\d{4})?,?\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?\b",
    re.IGNORECASE,
)
_MSK_OFFSET = timedelta(hours=3)
_RU_MONTHS = {
    "января": 1,
    "январь": 1,
    "янв": 1,
    "февраля": 2,
    "февраль": 2,
    "фев": 2,
    "марта": 3,
    "март": 3,
    "мар": 3,
    "апреля": 4,
    "апрель": 4,
    "апр": 4,
    "мая": 5,
    "май": 5,
    "июня": 6,
    "июнь": 6,
    "июл": 7,
    "июля": 7,
    "июль": 7,
    "августа": 8,
    "август": 8,
    "авг": 8,
    "сентября": 9,
    "сентябрь": 9,
    "сен": 9,
    "сент": 9,
    "октября": 10,
    "октябрь": 10,
    "окт": 10,
    "ноября": 11,
    "ноябрь": 11,
    "ноя": 11,
    "декабря": 12,
    "декабрь": 12,
    "дек": 12,
}


def _msk_now() -> datetime:
    return datetime.utcnow() + _MSK_OFFSET


def _msk_to_utc(value: datetime) -> datetime:
    return value - _MSK_OFFSET


def _parse_funpay_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    raw = " ".join(str(text).strip().split())
    if not raw:
        return None

    if raw.isdigit():
        try:
            ts = int(raw)
        except ValueError:
            ts = 0
        if ts > 0:
            if ts > 10**12:
                ts = ts / 1000.0
            try:
                return datetime.utcfromtimestamp(float(ts))
            except Exception:
                return None

    match = _CHAT_TIME_RE_YMD.search(raw)
    if match:
        year, month, day, hour, minute, second = match.groups()
        dt_msk = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    match = _CHAT_TIME_RE_DMY.search(raw)
    if match:
        day, month, year, hour, minute, second = match.groups()
        year_val = int(year)
        if year_val < 100:
            year_val += 2000
        dt_msk = datetime(
            int(year_val),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    match = _CHAT_TIME_RE_DM.search(raw)
    if match:
        day, month, hour, minute, second = match.groups()
        now = _msk_now()
        dt_msk = datetime(
            now.year,
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    lowered = raw.lower()
    yesterday_flag = "вчера" in lowered or "yesterday" in lowered
    match = _CHAT_TIME_RE_RU_MONTH.search(raw)
    if match:
        day = int(match.group("day"))
        month_raw = match.group("month") or ""
        month_key = re.sub(r"[^a-zA-Zа-яА-ЯёЁ]", "", month_raw).lower()
        month = _RU_MONTHS.get(month_key)
        if month:
            year_raw = match.group("year")
            now_msk = _msk_now()
            year_val = int(year_raw) if year_raw else now_msk.year
            dt_msk = datetime(
                year_val,
                month,
                day,
                int(match.group("hour")),
                int(match.group("minute")),
                int(match.group("second") or 0),
            )
            if not year_raw and dt_msk > now_msk + timedelta(days=1):
                dt_msk = dt_msk.replace(year=dt_msk.year - 1)
            return _msk_to_utc(dt_msk)

    match = _CHAT_TIME_RE_TIME.search(raw)
    if match:
        hour, minute, second = match.groups()
        base = _msk_now().date()
        if yesterday_flag:
            base = base - timedelta(days=1)
        dt_msk = datetime(
            base.year,
            base.month,
            base.day,
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    return None


def _extract_datetime_from_html(html: str | None) -> datetime | None:
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return _parse_funpay_datetime(html)

    candidates: list[str] = []
    for attr in _CHAT_TIME_ATTR_KEYS:
        for el in soup.find_all(attrs={attr: True}):
            value = el.get(attr)
            if value:
                candidates.append(str(value))

    for el in soup.find_all("time"):
        text = el.get_text(" ", strip=True)
        if text:
            candidates.append(text)

    for el in soup.find_all(class_=True):
        classes = " ".join(el.get("class", []))
        class_lower = classes.lower()
        if any(key in classes for key in _CHAT_TIME_CLASS_KEYS) or (
            ("time" in class_lower or "date" in class_lower)
            and ("chat" in class_lower or "contact" in class_lower or "msg" in class_lower)
        ):
            title = el.get("title")
            if title:
                candidates.append(str(title))
            text = el.get_text(" ", strip=True)
            if text:
                candidates.append(text)

    for candidate in candidates:
        dt = _parse_funpay_datetime(candidate)
        if dt:
            return dt

    return None
