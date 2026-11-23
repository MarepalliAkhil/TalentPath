from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from accounts.models import Role
from applications.blind import is_blind
from applications.services import staff_visible_applications
from core.audit import audit
from core.utils import IgnoreClientContentNegotiation, paginate
from core.views import PolicyAPIView
from files.storage import read_file

from . import services
from .letter import rupees
from .models import ApprovalStep, OfferStatus

# Who sees an offer as the person it is made to: candidates, and employees on internal offers.
APPLICANT_ROLES = (Role.CANDIDATE, Role.EMPLOYEE)


def _candidate(offer) -> dict:
    application = offer.application
    blind = is_blind(application)
    return {
        "code": application.candidate_code,
        "full_name": None if blind else application.candidate.full_name,
    }


def offer_brief(offer) -> dict:
    return {
        "id": str(offer.id),
        "status": offer.status,
        "status_label": OfferStatus(offer.status).label,
        "approval_step": offer.approval_step,
        "approval_step_label": ApprovalStep(offer.approval_step).label if offer.approval_step else "",
        "expires_on": offer.expires_on.isoformat(),
        "created_at": offer.created_at.isoformat(),
    }


def _terms(offer) -> dict:
    data = offer.data
    fixed, variable = int(data.get("fixed_pay", 0)), int(data.get("variable_pay", 0))
    return {
        "designation": data.get("designation", ""),
        "department": data.get("department", ""),
        "location": data.get("location", ""),
        "reporting_manager_id": data.get("reporting_manager_id", ""),
        "reporting_manager_name": data.get("reporting_manager_name", ""),
        "joining_date": data.get("joining_date", ""),
        "fixed_pay": fixed,
        "variable_pay": variable,
        "joining_bonus": int(data.get("joining_bonus") or 0),
        "total": fixed + variable,
        "display": {
            "fixed_pay": rupees(fixed),
            "variable_pay": rupees(variable),
            "joining_bonus": rupees(int(data.get("joining_bonus") or 0)),
            "total": rupees(fixed + variable),
        },
        "currency": "INR",
    }


def staff_offer_dict(offer, viewer) -> dict:
    job = offer.application.job
    is_owner = viewer.role == Role.HR_ADMIN or job.created_by_id == viewer.id
    step = offer.approval_step
    can_approve = offer.status == OfferStatus.PENDING_APPROVAL and (
        (
            step == ApprovalStep.HIRING_MANAGER
            and viewer.role == Role.HIRING_MANAGER
            and job.hiring_manager_id == viewer.id
        )
        or (step == ApprovalStep.HR_ADMIN and viewer.role == Role.HR_ADMIN)
    )
    editable = offer.status in (OfferStatus.DRAFT, OfferStatus.REJECTED)
    from hr.models import Employee

    hired = Employee.objects.filter(hired_from=offer).first()
    return {
        **offer_brief(offer),
        "hired": {"employee": str(hired.id), "code": hired.code, "joined_on": hired.joined_on.isoformat()}
        if hired
        else None,
        "application": str(offer.application_id),
        "job": {"id": str(job.id), "title": job.title},
        "candidate": _candidate(offer),
        "terms": _terms(offer),
        "created_by": offer.created_by.full_name,
        "approvals": {
            "hiring_manager": {
                "name": offer.hm_approved_by.full_name if offer.hm_approved_by else None,
                "at": offer.hm_approved_at.isoformat() if offer.hm_approved_at else None,
            },
            "hr_admin": {
                "name": offer.hr_approved_by.full_name if offer.hr_approved_by else None,
                "at": offer.hr_approved_at.isoformat() if offer.hr_approved_at else None,
            },
        },
        "rejected": {"reason": offer.reject_reason, "at": offer.rejected_at.isoformat()}
        if offer.rejected_at and offer.status == OfferStatus.REJECTED
        else None,
        "sent_at": offer.sent_at.isoformat() if offer.sent_at else None,
        "responded_at": offer.responded_at.isoformat() if offer.responded_at else None,
        "decline_reason": offer.decline_reason if offer.status == OfferStatus.DECLINED else "",
        "revoke_reason": offer.revoke_reason if offer.status == OfferStatus.REVOKED else "",
        "has_letter": bool(offer.letter_id),
        "actions": {
            "edit": is_owner and editable,
            "submit": is_owner and offer.status == OfferStatus.DRAFT,
            "approve": can_approve,
            "reject": can_approve,
            "send": is_owner and offer.status == OfferStatus.APPROVED,
            "revoke": is_owner
            and offer.status
            in (
                OfferStatus.DRAFT,
                OfferStatus.PENDING_APPROVAL,
                OfferStatus.APPROVED,
                OfferStatus.SENT,
                OfferStatus.REJECTED,
            ),
            # One-click hire (week 3B): accepted, still at Offer, not yet an employee.
            "hire": is_owner
            and viewer.role in (Role.RECRUITER, Role.HR_ADMIN)
            and offer.status == OfferStatus.ACCEPTED
            and offer.application.status == "offer"
            and hired is None,
        },
    }


def candidate_offer_dict(offer) -> dict:
    return {
        **offer_brief(offer),
        "job": {"title": offer.application.job.title},
        "terms": {k: v for k, v in _terms(offer).items() if k != "reporting_manager_id"},
        "sent_at": offer.sent_at.isoformat() if offer.sent_at else None,
        "responded_at": offer.responded_at.isoformat() if offer.responded_at else None,
        "can_respond": offer.status == OfferStatus.SENT,
        "has_letter": bool(offer.letter_id),
        "acknowledgement": (
            "Typing your full name records that you accept this offer. It is not a legal electronic "
            "signature."
        ),
        "demo": True,
    }


def _payload(request) -> dict:
    return request.data if isinstance(request.data, dict) else {}


class OfferListView(PolicyAPIView):
    policy_action = "offers.list"

    def get(self, request):
        qs = services.visible_offers(request.user)
        state = request.query_params.get("status")
        if state:
            qs = qs.filter(status=state)
        if request.query_params.get("awaiting") == "me":
            if request.user.role == Role.HIRING_MANAGER:
                qs = qs.filter(status=OfferStatus.PENDING_APPROVAL, approval_step=ApprovalStep.HIRING_MANAGER)
            elif request.user.role == Role.HR_ADMIN:
                qs = qs.filter(status=OfferStatus.PENDING_APPROVAL, approval_step=ApprovalStep.HR_ADMIN)
            else:
                qs = qs.filter(status__in=[OfferStatus.APPROVED, OfferStatus.REJECTED])
        return paginate(self, request, qs, lambda o: staff_offer_dict(o, request.user))


class ApplicationOfferCreateView(PolicyAPIView):
    policy_action = "offers.create"

    def post(self, request, pk):
        qs = staff_visible_applications(request.user)
        if request.user.role == Role.RECRUITER:
            qs = qs.filter(job__created_by=request.user)
        application = get_object_or_404(qs, pk=pk)
        offer = services.create_draft(application, request.user, _payload(request), request=request)
        return Response(staff_offer_dict(offer, request.user), status=status.HTTP_201_CREATED)


def _staff_offer(request, pk, *, owner=False):
    qs = services.visible_offers(request.user)
    if owner and request.user.role == Role.RECRUITER:
        qs = qs.filter(application__job__created_by=request.user)
    return get_object_or_404(qs, pk=pk)


class OfferDetailView(PolicyAPIView):
    policy_actions = {"GET": "offers.read", "PATCH": "offers.update"}

    def get(self, request, pk):
        offer = get_object_or_404(services.visible_offers(request.user), pk=pk)
        if request.user.role in APPLICANT_ROLES:
            return Response(candidate_offer_dict(offer))
        return Response(staff_offer_dict(offer, request.user))

    def patch(self, request, pk):
        offer = services.update_draft(
            _staff_offer(request, pk, owner=True), request.user, _payload(request), request=request
        )
        return Response(staff_offer_dict(offer, request.user))


class OfferActionView(PolicyAPIView):
    """POST /api/offers/<id>/<action> for submit, approve, reject, send, revoke, accept, decline."""

    ACTIONS = {
        "submit": "offers.submit",
        "approve": "offers.approve",
        "reject": "offers.reject",
        "send": "offers.send",
        "revoke": "offers.revoke",
        "accept": "offers.accept",
        "decline": "offers.decline",
    }
    action_name = ""

    @property
    def policy_action(self):
        return self.ACTIONS.get(self.action_name)

    def post(self, request, pk):
        name, data, user = self.action_name, _payload(request), request.user
        if name in ("accept", "decline"):
            offer = get_object_or_404(services.visible_offers(user), pk=pk)
            if name == "accept":
                offer = services.accept(offer, user, str(data.get("typed_name") or ""), request=request)
            else:
                offer = services.decline(offer, user, str(data.get("reason") or ""), request=request)
            return Response(candidate_offer_dict(offer))
        offer = _staff_offer(request, pk, owner=name in ("submit", "send", "revoke"))
        if name == "submit":
            offer = services.submit(offer, user, request=request)
        elif name == "approve":
            offer = services.approve(offer, user, request=request)
        elif name == "reject":
            offer = services.reject(offer, user, str(data.get("reason") or ""), request=request)
        elif name == "send":
            offer = services.send(offer, user, request=request)
        else:
            offer = services.revoke(offer, user, str(data.get("reason") or ""), request=request)
        return Response(staff_offer_dict(offer, user))


class OfferLetterView(PolicyAPIView):
    policy_action = "offers.letter"
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, pk):
        offer = get_object_or_404(services.visible_offers(request.user), pk=pk)
        if offer.letter_id:
            pdf = read_file(offer.letter)
        elif request.user.role not in APPLICANT_ROLES:
            pdf = services.letter_bytes(offer)  # staff preview before sending; not stored
        else:
            return Response({"detail": "No letter yet."}, status=status.HTTP_404_NOT_FOUND)
        audit(request, "offers.letter_viewed", target=offer)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="offer-letter-{offer.application.job.slug}.pdf"'
        response["Cache-Control"] = "no-store"
        return response


class MyOffersView(PolicyAPIView):
    policy_action = "offers.mine"

    def get(self, request):
        offers = services.visible_offers(request.user)
        return Response({"results": [candidate_offer_dict(o) for o in offers]})
