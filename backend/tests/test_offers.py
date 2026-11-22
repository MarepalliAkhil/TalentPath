"""Offers: final round first, approval order, PDF letter, accept/decline,
expiry, revoke, encryption at rest and candidate isolation."""

from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.test import APIClient

from accounts.models import Role
from core.models import AuditLog
from interviews.models import InterviewPlan
from interviews.timeutil import today_ist
from offers import services
from offers.events import offer_accepted
from offers.letter import rupees
from offers.models import Offer, OfferStatus


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def terms(**extra):
    today = today_ist(timezone.now())
    return {
        "designation": "Senior Platform Engineer",
        "joining_date": (today + timedelta(days=45)).isoformat(),
        "expires_on": (today + timedelta(days=7)).isoformat(),
        "fixed_pay": 2400000,
        "variable_pay": 300000,
        "joining_bonus": 100000,
        **extra,
    }


@pytest.fixture
def finalist(plan_job, users, apply_as, interviewers, run_round):
    """A candidate at Interview who passed both rounds (HIRA off so nothing is auto-proposed)."""
    from applications.services import move_application

    InterviewPlan.objects.filter(job=plan_job).update(hira_enabled=False)
    application = apply_as(users["candidate"], plan_job)
    move_application(application, "screening", users["recruiter"], silent=True)
    move_application(application, "interview", users["recruiter"], silent=True)
    plan = InterviewPlan.objects.get(job=plan_job)
    run_round(application, plan.rounds.get(order=1), interviewers[:1])
    run_round(application, plan.rounds.get(order=2), interviewers[1:3])
    application.refresh_from_db()
    return application


def draft(finalist, users, **extra):
    response = as_user(users["recruiter"]).post(
        f"/api/applications/{finalist.id}/offers", terms(**extra), format="json"
    )
    assert response.status_code == 201, response.data
    return Offer.objects.get(pk=response.data["id"])


@pytest.mark.django_db
def test_offer_needs_the_final_round_passed(plan_job, users, apply_as, interviewers, run_round):
    from applications.services import move_application

    InterviewPlan.objects.filter(job=plan_job).update(hira_enabled=False)
    application = apply_as(users["candidate"], plan_job)
    move_application(application, "screening", users["recruiter"], silent=True)
    move_application(application, "interview", users["recruiter"], silent=True)
    run_round(application, InterviewPlan.objects.get(job=plan_job).rounds.get(order=1), interviewers[:1])
    response = as_user(users["recruiter"]).post(
        f"/api/applications/{application.id}/offers", terms(), format="json"
    )
    assert response.status_code == 400 and "final interview round" in str(response.data)


@pytest.mark.django_db
def test_terms_are_validated(finalist, users):
    client = as_user(users["recruiter"])
    today = today_ist(timezone.now())
    bad = client.post(
        f"/api/applications/{finalist.id}/offers",
        terms(
            fixed_pay=0, joining_date=today.isoformat(), expires_on=(today + timedelta(days=90)).isoformat()
        ),
        format="json",
    )
    assert bad.status_code == 400
    assert {"fixed_pay", "joining_date", "expires_on"} <= set(bad.data)


@pytest.mark.django_db
def test_approval_order_hiring_manager_then_hr(finalist, users):
    offer = draft(finalist, users)
    assert offer.status == OfferStatus.DRAFT
    recruiter, manager, admin = (
        as_user(users["recruiter"]),
        as_user(users["hiring_manager"]),
        as_user(users["hr_admin"]),
    )
    assert recruiter.post(f"/api/offers/{offer.id}/send").status_code == 400  # not approved yet
    assert recruiter.post(f"/api/offers/{offer.id}/submit").data["approval_step"] == "hiring_manager"
    assert admin.post(f"/api/offers/{offer.id}/approve").status_code == 400  # HR waits for the manager
    assert recruiter.post(f"/api/offers/{offer.id}/approve").status_code == 403  # policy
    step = manager.post(f"/api/offers/{offer.id}/approve").data
    assert step["status"] == "pending_approval" and step["approval_step"] == "hr_admin"
    assert manager.post(f"/api/offers/{offer.id}/approve").status_code == 400  # not twice
    done = admin.post(f"/api/offers/{offer.id}/approve").data
    assert (
        done["status"] == "approved" and done["approvals"]["hr_admin"]["name"] == users["hr_admin"].full_name
    )
    actions = set(AuditLog.objects.filter(target_id=str(offer.id)).values_list("action", flat=True))
    assert {"offers.created", "offers.submitted", "offers.approved_hm", "offers.approved_hr"} <= actions


@pytest.mark.django_db
def test_either_approver_can_reject_with_a_reason_and_the_recruiter_edits(finalist, users):
    offer = draft(finalist, users)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/submit")
    manager = as_user(users["hiring_manager"])
    assert (
        manager.post(f"/api/offers/{offer.id}/reject", {"reason": "too low"}, format="json").status_code
        == 400
    )
    rejected = manager.post(
        f"/api/offers/{offer.id}/reject", {"reason": "Fixed pay is below band."}, format="json"
    )
    assert (
        rejected.data["status"] == "rejected"
        and rejected.data["rejected"]["reason"] == "Fixed pay is below band."
    )
    edited = as_user(users["recruiter"]).patch(
        f"/api/offers/{offer.id}", {"fixed_pay": 2600000}, format="json"
    )
    assert (
        edited.status_code == 200
        and edited.data["status"] == "draft"
        and edited.data["terms"]["fixed_pay"] == 2600000
    )
    # HR can reject too, at its own step.
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/submit")
    manager.post(f"/api/offers/{offer.id}/approve")
    hr = as_user(users["hr_admin"]).post(
        f"/api/offers/{offer.id}/reject", {"reason": "Joining date clashes with a freeze."}, format="json"
    )
    assert hr.data["status"] == "rejected"


def approved(finalist, users, **extra):
    offer = draft(finalist, users, **extra)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/submit")
    as_user(users["hiring_manager"]).post(f"/api/offers/{offer.id}/approve")
    as_user(users["hr_admin"]).post(f"/api/offers/{offer.id}/approve")
    return offer


@pytest.mark.django_db
def test_sending_generates_a_branded_demo_pdf_and_moves_to_offer(finalist, users):
    offer = approved(finalist, users)
    sent = as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/send")
    assert sent.status_code == 200 and sent.data["status"] == "sent" and sent.data["has_letter"]
    finalist.refresh_from_db()
    assert finalist.status == "offer"
    letter = as_user(users["candidate"]).get(f"/api/offers/{offer.id}/letter")
    assert letter.status_code == 200 and letter["Content-Type"] == "application/pdf"
    import io

    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(letter.content)).pages)
    assert "DEMO" in text and "TalentPath" in text and users["candidate"].full_name in text
    assert "INR 24,00,000" in text and "Senior Platform Engineer" in text


@pytest.mark.django_db
def test_candidate_accepts_by_typing_their_full_name(finalist, users):
    offer = approved(finalist, users)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/send")
    received = []
    offer_accepted.connect(
        lambda sender, offer, **kw: received.append(offer.id), weak=False, dispatch_uid="t-accept"
    )
    try:
        client = as_user(users["candidate"])
        mine = client.get("/api/my/offers").data["results"]
        assert [o["id"] for o in mine] == [str(offer.id)] and mine[0]["can_respond"] is True
        assert "reporting_manager_id" not in mine[0]["terms"]
        wrong = client.post(f"/api/offers/{offer.id}/accept", {"typed_name": "Someone Else"}, format="json")
        assert wrong.status_code == 400
        name = "  " + users["candidate"].full_name.upper() + " "
        ok = client.post(
            f"/api/offers/{offer.id}/accept", {"typed_name": name}, format="json", REMOTE_ADDR="203.0.113.7"
        )
        assert ok.status_code == 200 and ok.data["status"] == "accepted"
    finally:
        offer_accepted.disconnect(dispatch_uid="t-accept")
    offer.refresh_from_db()
    assert (
        offer.responded_at and len(offer.accept_ip_hash) == 64 and "203.0.113.7" not in offer.accept_ip_hash
    )
    assert received == [offer.id]
    finalist.refresh_from_db()
    assert finalist.status == "offer"  # "Hired" stays reserved for week 3B
    assert as_user(users["candidate"]).post(f"/api/offers/{offer.id}/decline").status_code == 400


@pytest.mark.django_db
def test_candidate_can_decline_with_a_reason(finalist, users):
    offer = approved(finalist, users)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/send")
    response = as_user(users["candidate"]).post(
        f"/api/offers/{offer.id}/decline", {"reason": "Accepted elsewhere"}, format="json"
    )
    assert response.data["status"] == "declined"
    seen = as_user(users["recruiter"]).get(f"/api/offers/{offer.id}").data
    assert seen["decline_reason"] == "Accepted elsewhere"


@pytest.mark.django_db
def test_offers_expire_and_cannot_be_accepted_afterwards(finalist, users):
    offer = approved(finalist, users)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/send")
    offer.refresh_from_db()
    assert services.expire_offers(timezone.now()) == 0
    assert services.expire_offers(timezone.now() + timedelta(days=9)) == 1
    offer.refresh_from_db()
    assert offer.status == OfferStatus.EXPIRED and offer.expired_at
    response = as_user(users["candidate"]).post(
        f"/api/offers/{offer.id}/accept", {"typed_name": users["candidate"].full_name}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_accepting_a_lapsed_offer_marks_it_expired(finalist, users):
    offer = approved(finalist, users)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/send")
    Offer.objects.filter(pk=offer.pk).update(expires_on=today_ist(timezone.now()) - timedelta(days=1))
    response = as_user(users["candidate"]).post(
        f"/api/offers/{offer.id}/accept", {"typed_name": users["candidate"].full_name}, format="json"
    )
    assert response.status_code == 400
    offer.refresh_from_db()
    assert offer.status == OfferStatus.EXPIRED


@pytest.mark.django_db
def test_recruiter_revokes_with_a_reason(finalist, users):
    offer = approved(finalist, users)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/send")
    client = as_user(users["recruiter"])
    assert client.post(f"/api/offers/{offer.id}/revoke", {"reason": "no"}, format="json").status_code == 400
    response = client.post(
        f"/api/offers/{offer.id}/revoke", {"reason": "Role was put on hold by finance."}, format="json"
    )
    assert response.data["status"] == "revoked"
    assert as_user(users["candidate"]).get(f"/api/offers/{offer.id}").data["status"] == "revoked"
    # A new offer can be drafted after a revoke.
    assert (
        as_user(users["recruiter"])
        .post(f"/api/applications/{finalist.id}/offers", terms(), format="json")
        .status_code
        == 201
    )


@pytest.mark.django_db
def test_offer_details_are_encrypted_at_rest(finalist, users):
    offer = draft(finalist, users)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT details FROM offers_offer WHERE id = %s",
            [offer.id.hex if connection.vendor == "sqlite" else offer.id],
        )
        raw = cursor.fetchone()[0]
    assert raw.startswith("v1:")
    assert "2400000" not in raw and "Senior Platform Engineer" not in raw
    assert offer.data["fixed_pay"] == 2400000


@pytest.mark.django_db
def test_candidates_see_only_their_own_sent_offers(finalist, users, make_user):
    offer = draft(finalist, users)
    candidate = as_user(users["candidate"])
    assert candidate.get(f"/api/offers/{offer.id}").status_code == 404  # drafts are internal
    assert candidate.get(f"/api/offers/{offer.id}/letter").status_code == 404
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/submit")
    as_user(users["hiring_manager"]).post(f"/api/offers/{offer.id}/approve")
    as_user(users["hr_admin"]).post(f"/api/offers/{offer.id}/approve")
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/send")
    assert candidate.get(f"/api/offers/{offer.id}").status_code == 200
    stranger = as_user(make_user(Role.CANDIDATE))
    assert stranger.get(f"/api/offers/{offer.id}").status_code == 404
    assert stranger.get(f"/api/offers/{offer.id}/letter").status_code == 404
    assert (
        stranger.post(f"/api/offers/{offer.id}/accept", {"typed_name": "x"}, format="json").status_code == 404
    )
    assert stranger.get("/api/my/offers").data["results"] == []
    other_recruiter = as_user(make_user(Role.RECRUITER))
    assert other_recruiter.get(f"/api/offers/{offer.id}").status_code == 404
    assert other_recruiter.get("/api/offers").data["results"] == []


@pytest.mark.django_db
def test_approval_queues(finalist, users):
    offer = draft(finalist, users)
    as_user(users["recruiter"]).post(f"/api/offers/{offer.id}/submit")
    assert [
        o["id"] for o in as_user(users["hiring_manager"]).get("/api/offers?awaiting=me").data["results"]
    ] == [str(offer.id)]
    assert as_user(users["hr_admin"]).get("/api/offers?awaiting=me").data["results"] == []
    as_user(users["hiring_manager"]).post(f"/api/offers/{offer.id}/approve")
    assert [o["id"] for o in as_user(users["hr_admin"]).get("/api/offers?awaiting=me").data["results"]] == [
        str(offer.id)
    ]


def test_rupees_use_indian_grouping():
    assert rupees(2400000) == "INR 24,00,000"
    assert rupees(999) == "INR 999"
    assert rupees(12345678) == "INR 1,23,45,678"
