"""Working days, holidays and the per-location work policy."""

from datetime import date, time, timedelta
from decimal import Decimal

from .models import Holiday, WorkPolicy

DEFAULT_WEEKLY_OFF = [6, 7]


def policy_for(location) -> WorkPolicy:
    """The location's work policy; a default (09:30-18:30, Sat/Sun off) is created when missing."""
    policy = WorkPolicy.objects.filter(location=location).first()
    if policy is None:
        policy, _ = WorkPolicy.objects.get_or_create(
            location=location,
            defaults={
                "shift_start": time(9, 30),
                "shift_end": time(18, 30),
                "weekly_off": DEFAULT_WEEKLY_OFF,
                "hr_approval_over_days": Decimal("5"),
                "min_team_available_pct": 50,
            },
        )
    return policy


class DayBook:
    """Answers "is this a working day here?" for one location without a query per day."""

    def __init__(self, location, start: date, end: date):
        self.location = location
        self.policy = policy_for(location)
        self.weekly_off = set(self.policy.weekly_off or DEFAULT_WEEKLY_OFF)
        self.holidays = {
            h.date: h.name
            for h in Holiday.objects.filter(
                location=location, date__gte=start - timedelta(days=14), date__lte=end + timedelta(days=14)
            )
        }

    def is_weekly_off(self, day: date) -> bool:
        return day.isoweekday() in self.weekly_off

    def holiday(self, day: date) -> str | None:
        return self.holidays.get(day)

    def is_working(self, day: date) -> bool:
        return not self.is_weekly_off(day) and day not in self.holidays

    def kind(self, day: date) -> str:
        if day in self.holidays:
            return "holiday"
        if self.is_weekly_off(day):
            return "weekly_off"
        return "working"


def add_working_days(location, start: date, offset: int) -> date:
    """Move `offset` working days from `start` (0 = start itself, or the next working day)."""
    book = DayBook(location, start - timedelta(days=30), start + timedelta(days=60))
    day = start
    if offset >= 0:
        while not book.is_working(day):
            day += timedelta(days=1)
        for _ in range(offset):
            day += timedelta(days=1)
            while not book.is_working(day):
                day += timedelta(days=1)
    else:
        for _ in range(-offset):
            day -= timedelta(days=1)
            while not book.is_working(day):
                day -= timedelta(days=1)
    return day


def date_range(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)
