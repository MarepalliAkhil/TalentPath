"""Offer workflow: draft -> pending approval (hiring manager, then hr_admin) ->
approved -> sent -> accepted / declined / expired. Revoke with a reason at any
point before the candidate answers. Every step is audited."""

import re
import unicodedata
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Role, User
from applications.models import ApplicationStatus as S
from core.audit import audit, client_ip
from core.crypto import blind_index
from files.storage import save_file
from interviews.coordinator import final_round_passed, who
from interviews.timeutil import today_ist
from notifications.services import notify

from .events import offer_accepted
from .letter import build_offer_pdf
from .models import CANDIDATE_VISIBLE, LIVE_STATUSES, ApprovalStep, Offer, OfferStatus

MAX_PAY = 100_00_00_000  # INR 100 crore: a sanity cap for a demo
MAX_VALID_DAYS = 60


def _int(value, field, errors, *, required=True, minimum=0):
    if value in (None, ""):
        if required:
            errors[field] = "Required."
        return 0
    try:
        number = int(str(value).replace(",", ""))
    except ValueError:
        errors[field] = "Enter a whole number of rupees."
        return 0
    if number < minimum or number > MAX_PAY:
        errors[field] = "Enter a sensible amount in rupees."
    return number


def _date(value, field, errors) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        errors[field] = "Use a date like 2026-12-01."
        return None


def clean_terms(application, payload: dict, *, today: date) -> tuple[dict, date]:
    """Validate offer terms. Returns (encrypted-details dict, expires_on)."""
    job = application.job
    errors: dict = {}
    designation = str(payload.get("designation") or job.title).strip()[:120]
    if not designation:
        errors["designation"] = "Required."
    manager_id = payload.get("reporting_manager_id") or (
        str(job.hiring_manager_id) if job.hiring_manager_id else ""
    )
    manager = (
        User.objects.filter(pk=manager_id, is_active=True).exclude(role=Role.CANDIDATE).first()
        if manager_id
        else None
    )
    if manager is None:
        errors["reporting_manager_id"] = "Choose an active staff member as the reporting manager."
    joining = _date(payload.get("joining_date"), "joining_date", errors)
    if joining and joining <= today:
        errors["joining_date"] = "The joining date must be in the future."
    expires = _date(payload.get("expires_on"), "expires_on", errors)
    if expires and not (today <= expires <= today + timedelta(days=MAX_VALID_DAYS)):
        errors["expires_on"] = f"Set an expiry between today and {MAX_VALID_DAYS} days from now."
    if expires and joining and expires >= joining:
        errors["expires_on"] = "The offer must expire before the joining date."
    fixed = _int(payload.get("fixed_pay"), "fixed_pay", errors, minimum=1)
    variable = _int(payload.get("variable_pay"), "variable_pay", errors, required=False)
    bonus = _int(payload.get("joining_bonus"), "joining_bonus", errors, required=False)
    if errors:
        raise ValidationError(errors)
    data = {
        "designation": designation,
        "department": str(payload.get("department") or job.department.name)[:120],
        "location": str(payload.get("location") or job.location.name)[:120],
        "reporting_manager_id": str(manager.id),
        "reporting_manager_name": manager.full_name,
        "joining_date": joining.isoformat(),
        "fixed_pay": fixed,
        "variable_pay": variable,
        "joining_bonus": bonus,
        "currency": "INR",
    }
    return data, expires


def visible_offers(user):
    qs = Offer.objects.select_related(
        "application", "application__job", "application__candidate", "created_by"
    )
    if user.role == Role.HR_ADMIN:
        return qs
    if user.role == Role.RECRUITER:
        return qs.filter(application__job__created_by=user)
    if user.role == Role.HIRING_MANAGER:
        return qs.filter(application__job__hiring_manager=user)
    if user.role in (Role.CANDIDATE, Role.EMPLOYEE):
        # Employees see only offers on their own internal applications (week 4A).
        return qs.filter(application__candidate=user, status__in=CANDIDATE_VISIBLE)
    return qs.none()


def create_draft(application, actor, payload: dict, request=None) -> Offer:
    if application.status not in (S.INTERVIEW, S.OFFER):
        raise ValidationError(
            {"application": "Offers are drafted for candidates at the Interview or Offer stage."}
        )
    if not final_round_passed(application):
        raise ValidationError({"application": "The candidate has not passed the final interview round yet."})
    if application.offers.filter(status__in=LIVE_STATUSES).exists():
        raise ValidationError({"application": "This candidate already has an open offer."})
    today = today_ist(timezone.now())
    data, expires = clean_terms(application, payload, today=today)
    offer = Offer(application=application, expires_on=expires, created_by=actor)
    offer.data = data
    offer.save()
    audit(request, "offers.created", actor=actor, target=offer)
    return offer


def update_draft(offer, actor, payload: dict, request=None) -> Offer:
    if offer.status not in (OfferStatus.DRAFT, OfferStatus.REJECTED):
        raise ValidationError({"status": "Only a draft (or an offer with changes requested) can be edited."})
    today = today_ist(timezone.now())
    merged = {
        **offer.data,
        **{k: v for k, v in payload.items() if v is not None},
        "expires_on": payload.get("expires_on") or offer.expires_on.isoformat(),
    }
    data, expires = clean_terms(offer.application, merged, today=today)
    offer.data, offer.expires_on = data, expires
    offer.status, offer.approval_step = OfferStatus.DRAFT, ApprovalStep.NONE
    offer.save()
    audit(request, "offers.updated", actor=actor, target=offer)
    return offer


def submit(offer, actor, request=None) -> Offer:
    if offer.status != OfferStatus.DRAFT:
        raise ValidationError({"status": "Only a draft can be sent for approval."})
    job = offer.application.job
    offer.status = OfferStatus.PENDING_APPROVAL
    offer.approval_step = ApprovalStep.HIRING_MANAGER if job.hiring_manager_id else ApprovalStep.HR_ADMIN
    offer.hm_approved_by = offer.hr_approved_by = None
    offer.hm_approved_at = offer.hr_approved_at = None
    offer.save()
    audit(request, "offers.submitted", actor=actor, target=offer)
    approver = job.hiring_manager if job.hiring_manager_id else None
    targets = [approver] if approver else list(User.objects.filter(role=Role.HR_ADMIN, is_active=True))
    for person in targets:
        notify(
            person,
            kind="offer_approval",
            title=f"Offer to approve: {who(offer.application)} for {job.title}",
            body="An offer is waiting for your approval.",
            link=f"/offers/{offer.id}",
        )
    return offer


def approve(offer, actor, request=None) -> Offer:
    if offer.status != OfferStatus.PENDING_APPROVAL:
        raise ValidationError({"status": "This offer is not waiting for approval."})
    job = offer.application.job
    now = timezone.now()
    if offer.approval_step == ApprovalStep.HIRING_MANAGER:
        if actor.role != Role.HIRING_MANAGER or job.hiring_manager_id != actor.id:
            raise ValidationError({"status": "Waiting for the hiring manager to approve first."})
        offer.hm_approved_by, offer.hm_approved_at = actor, now
        offer.approval_step = ApprovalStep.HR_ADMIN
        offer.save()
        audit(request, "offers.approved_hm", actor=actor, target=offer)
        for person in User.objects.filter(role=Role.HR_ADMIN, is_active=True):
            notify(
                person,
                kind="offer_approval",
                title=f"Offer to approve: {who(offer.application)} for {job.title}",
                body="The hiring manager approved this offer. It now needs HR approval.",
                link=f"/offers/{offer.id}",
            )
        return offer
    if actor.role != Role.HR_ADMIN:
        raise ValidationError({"status": "Waiting for HR to approve."})
    offer.hr_approved_by, offer.hr_approved_at = actor, now
    offer.status, offer.approval_step = OfferStatus.APPROVED, ApprovalStep.NONE
    offer.save()
    audit(request, "offers.approved_hr", actor=actor, target=offer)
    notify(
        job.created_by,
        kind="offer_approved",
        title=f"Offer approved: {who(offer.application)} for {job.title}",
        body="Both approvals are in. You can send the offer to the candidate.",
        link=f"/offers/{offer.id}",
    )
    return offer


def reject(offer, actor, reason: str, request=None) -> Offer:
    reason = (reason or "").strip()
    if offer.status != OfferStatus.PENDING_APPROVAL:
        raise ValidationError({"status": "This offer is not waiting for approval."})
    job = offer.application.job
    expected_hm = offer.approval_step == ApprovalStep.HIRING_MANAGER
    if expected_hm and not (actor.role == Role.HIRING_MANAGER and job.hiring_manager_id == actor.id):
        raise ValidationError({"status": "Waiting for the hiring manager."})
    if not expected_hm and actor.role != Role.HR_ADMIN:
        raise ValidationError({"status": "Waiting for HR."})
    if len(reason) < 10:
        raise ValidationError({"reason": "Give a reason of at least 10 characters."})
    offer.status, offer.approval_step = OfferStatus.REJECTED, ApprovalStep.NONE
    offer.rejected_by, offer.rejected_at, offer.reject_reason = actor, timezone.now(), reason[:500]
    offer.save()
    audit(request, "offers.rejected", actor=actor, target=offer)
    notify(
        job.created_by,
        kind="offer_rejected",
        title=f"Changes requested on the offer for {who(offer.application)}",
        body="An approver asked for changes. Open the offer to read the reason and edit it.",
        link=f"/offers/{offer.id}",
    )
    return offer


def letter_bytes(offer, *, issued_on: date | None = None) -> bytes:
    application = offer.application
    return build_offer_pdf(
        candidate_name=application.candidate.full_name,
        job_title=application.job.title,
        data=offer.data,
        expires_on=offer.expires_on.isoformat(),
        issued_on=(issued_on or today_ist(timezone.now())).isoformat(),
    )


def send(offer, actor, request=None) -> Offer:
    from applications.services import move_application

    if offer.status != OfferStatus.APPROVED:
        raise ValidationError({"status": "Only an approved offer can be sent."})
    today = today_ist(timezone.now())
    if offer.expires_on < today:
        raise ValidationError({"expires_on": "The expiry date has passed. Edit the offer first."})
    application = offer.application
    with transaction.atomic():
        pdf = letter_bytes(offer, issued_on=today)
        offer.letter = save_file(
            owner=application.candidate,
            original_name=f"offer-letter-{application.job.slug}.pdf",
            content_type="application/pdf",
            raw=pdf,
        )
        offer.status, offer.sent_at = OfferStatus.SENT, timezone.now()
        offer.save()
        if application.status == S.INTERVIEW:
            move_application(application, S.OFFER, actor, silent=True, request=request)
    audit(request, "offers.sent", actor=actor, target=offer)
    notify(
        application.candidate,
        kind="offer_sent",
        title=f"You have an offer from us: {application.job.title}",
        body=(
            "Congratulations! Open your dashboard to read the offer and the letter. It is valid until "
            f"{offer.expires_on:%d %b %Y}."
        ),
        link=f"/candidate/offers/{offer.id}",
    )
    return offer


def normalise_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"\s+", " ", value).strip()


def _expire_if_due(offer, today) -> bool:
    if offer.status == OfferStatus.SENT and offer.expires_on < today:
        offer.status, offer.expired_at = OfferStatus.EXPIRED, timezone.now()
        offer.save(update_fields=["status", "expired_at", "updated_at"])
        return True
    return False


def accept(offer, candidate, typed_name: str, request=None) -> Offer:
    today = today_ist(timezone.now())
    if _expire_if_due(offer, today):  # saved before refusing, so the expiry sticks
        raise ValidationError({"status": "This offer has expired."})
    with transaction.atomic():
        offer = (
            Offer.objects.select_for_update()
            .select_related("application", "application__job")
            .get(pk=offer.pk)
        )
        if offer.status != OfferStatus.SENT:
            raise ValidationError({"status": "This offer is not open for a response."})
        if normalise_name(typed_name) != normalise_name(candidate.full_name):
            raise ValidationError(
                {"typed_name": "Type your full name exactly as it appears on your profile."}
            )
        ip = client_ip(request) or ""
        offer.status, offer.responded_at = OfferStatus.ACCEPTED, timezone.now()
        offer.accepted_name = typed_name.strip()[:120]
        offer.accept_ip_hash = blind_index(ip, "offer-accept-ip") if ip else ""
        offer.save()
    audit(request, "offers.accepted", actor=candidate, target=offer)
    job = offer.application.job
    recipients = {job.created_by_id: job.created_by}
    if job.hiring_manager_id:
        recipients[job.hiring_manager_id] = job.hiring_manager
    for person in recipients.values():
        notify(
            person,
            kind="offer_accepted",
            title=f"Offer accepted: {offer.application.candidate.full_name} for {job.title}",
            body="The candidate accepted the offer. Open it and choose Hire to start onboarding.",
            link=f"/offers/{offer.id}",
        )
    offer_accepted.send(sender=Offer, offer=offer)
    return offer


def decline(offer, candidate, reason: str = "", request=None) -> Offer:
    today = today_ist(timezone.now())
    if _expire_if_due(offer, today):
        raise ValidationError({"status": "This offer has expired."})
    with transaction.atomic():
        offer = (
            Offer.objects.select_for_update()
            .select_related("application", "application__job")
            .get(pk=offer.pk)
        )
        if offer.status != OfferStatus.SENT:
            raise ValidationError({"status": "This offer is not open for a response."})
        offer.status, offer.responded_at = OfferStatus.DECLINED, timezone.now()
        offer.decline_reason = (reason or "").strip()[:500]
        offer.save()
    audit(request, "offers.declined", actor=candidate, target=offer)
    notify(
        offer.application.job.created_by,
        kind="offer_declined",
        title=f"Offer declined: {offer.application.candidate.full_name} for {offer.application.job.title}",
        body="The candidate declined the offer." + (" They left a reason." if offer.decline_reason else ""),
        link=f"/offers/{offer.id}",
    )
    return offer


def revoke(offer, actor, reason: str, request=None) -> Offer:
    reason = (reason or "").strip()
    if offer.status not in (
        OfferStatus.DRAFT,
        OfferStatus.PENDING_APPROVAL,
        OfferStatus.APPROVED,
        OfferStatus.SENT,
        OfferStatus.REJECTED,
    ):
        raise ValidationError({"status": "This offer can no longer be revoked."})
    if len(reason) < 10:
        raise ValidationError({"reason": "Give a reason of at least 10 characters."})
    was_sent = offer.status == OfferStatus.SENT
    offer.status, offer.approval_step = OfferStatus.REVOKED, ApprovalStep.NONE
    offer.revoked_at, offer.revoke_reason = timezone.now(), reason[:500]
    offer.save()
    audit(request, "offers.revoked", actor=actor, target=offer)
    if was_sent:
        notify(
            offer.application.candidate,
            kind="offer_revoked",
            title=f"Update on your offer for {offer.application.job.title}",
            body=(
                "We are sorry: this offer has been withdrawn. The recruiter will be in touch if you have "
                "questions."
            ),
            link=f"/candidate/offers/{offer.id}",
        )
    return offer


def expire_offers(now=None) -> int:
    """Cron: sent offers past their expiry date (IST) become expired."""
    now = now or timezone.now()
    today = today_ist(now)
    count = 0
    for offer in Offer.objects.filter(status=OfferStatus.SENT, expires_on__lt=today).select_related(
        "application", "application__job", "application__candidate"
    ):
        if _expire_if_due(offer, today):
            count += 1
            audit(None, "offers.expired", target=offer)
            notify(
                offer.application.candidate,
                kind="offer_expired",
                title=f"Your offer for {offer.application.job.title} has expired",
                body="The response window has closed. Contact the recruiter if you would still like to talk.",
                link=f"/candidate/offers/{offer.id}",
            )
            notify(
                offer.application.job.created_by,
                kind="offer_expired",
                title=f"Offer expired: {offer.application.candidate.full_name}",
                body=f"The offer for {offer.application.job.title} expired without a response.",
                link=f"/offers/{offer.id}",
            )
    return count
