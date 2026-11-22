"""Busy-time claims: the single place that books time for people.

Every booking runs inside a transaction that first locks the people involved
(SELECT ... FOR UPDATE on their user rows, always in id order to avoid
deadlocks), releases expired holds, checks for clashes and then inserts. On
PostgreSQL an exclusion constraint (btree_gist) rejects any overlap that slips
past the check, so two concurrent bookings can never both succeed.
"""

from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from accounts.models import User

from .models import BlockedTime, ClaimKind, SlotOffer, SlotStatus, TimeClaim


class SlotTaken(APIException):
    status_code = 409
    default_detail = "That time is no longer free. Please choose another slot."
    default_code = "slot_taken"


def lock_people(person_ids) -> None:
    ids = sorted({str(p) for p in person_ids})
    list(User.objects.select_for_update().filter(id__in=ids).order_by("id").values_list("id", flat=True))


def release_expired_holds(now: datetime | None = None, person_ids=None) -> list:
    """Deactivate holds past their expiry; reopen their slots. Returns affected interview ids."""
    now = now or timezone.now()
    qs = TimeClaim.objects.filter(kind=ClaimKind.HOLD, active=True, expires_at__lte=now)
    if person_ids is not None:
        qs = qs.filter(person_id__in=list(person_ids))
    interview_ids = list(qs.values_list("interview_id", flat=True).distinct())
    slot_ids = list(qs.exclude(slot=None).values_list("slot_id", flat=True).distinct())
    qs.update(active=False)
    SlotOffer.objects.filter(id__in=slot_ids, status=SlotStatus.HELD).update(
        status=SlotStatus.OPEN, held_until=None
    )
    return interview_ids


def clashes(person_ids, start: datetime, end: datetime, *, interviewer_ids=(), now=None):
    now = now or timezone.now()
    claim = (
        TimeClaim.objects.filter(
            person_id__in=list(person_ids), active=True, starts_at__lt=end, ends_at__gt=start
        )
        .exclude(kind=ClaimKind.HOLD, expires_at__lte=now)
        .exists()
    )
    blocked = BlockedTime.objects.filter(
        user_id__in=list(interviewer_ids), starts_at__lt=end, ends_at__gt=start
    ).exists()
    return claim or blocked


def book(
    *,
    people,
    interviewer_ids,
    start: datetime,
    end: datetime,
    kind: str,
    interview,
    slot=None,
    expires_at=None,
    now=None,
) -> list[TimeClaim]:
    """Claim [start, end) for every person, or raise SlotTaken. Call inside transaction.atomic()."""
    now = now or timezone.now()
    people = sorted({str(p) for p in people})
    lock_people(people)
    release_expired_holds(now, people)
    if clashes(people, start, end, interviewer_ids=interviewer_ids, now=now):
        raise SlotTaken()
    rows = [
        TimeClaim(
            person_id=p,
            interview=interview,
            slot=slot,
            kind=kind,
            starts_at=start,
            ends_at=end,
            expires_at=expires_at if kind == ClaimKind.HOLD else None,
        )
        for p in people
    ]
    try:
        with transaction.atomic():
            return TimeClaim.objects.bulk_create(rows)
    except IntegrityError as exc:  # exclusion constraint on PostgreSQL
        raise SlotTaken() from exc


def release(interview, *, kind: str | None = None, person_ids=None) -> int:
    qs = TimeClaim.objects.filter(interview=interview, active=True)
    if kind:
        qs = qs.filter(kind=kind)
    if person_ids is not None:
        qs = qs.filter(person_id__in=[str(p) for p in person_ids])
    return qs.update(active=False)
