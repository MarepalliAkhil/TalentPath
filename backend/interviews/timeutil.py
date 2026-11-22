"""Asia/Kolkata everywhere for people; UTC in the database."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def ist(dt: datetime) -> datetime:
    return dt.astimezone(IST)


def fmt(dt: datetime | None) -> str:
    """Tue 24 Nov 2026, 10:30 IST"""
    if dt is None:
        return ""
    local = ist(dt)
    return local.strftime("%a %d %b %Y, %H:%M IST")


def parse_hhmm(value: str) -> time:
    hours, minutes = str(value).split(":")
    return time(int(hours), int(minutes))


def week_bounds(dt: datetime) -> tuple[datetime, datetime]:
    """Monday 00:00 to next Monday 00:00 in IST, returned as aware datetimes."""
    local = ist(dt)
    monday = datetime.combine(local.date() - timedelta(days=local.weekday()), time(0, 0), tzinfo=IST)
    return monday, monday + timedelta(days=7)


def ceil_to_grid(dt: datetime, minutes: int) -> datetime:
    local = ist(dt).replace(second=0, microsecond=0)
    if dt.second or dt.microsecond:
        local += timedelta(minutes=1)
    remainder = local.minute % minutes
    if remainder:
        local += timedelta(minutes=minutes - remainder)
    return local


def today_ist(now: datetime):
    return ist(now).date()
