"""One-click hire to onboard: atomic, audited role change, withdrawn applications,
openings and job closing, buddy rules, prorated leave, checklist and first week."""

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from applications.models import ApplicationStatus
from applications.services import apply_to_job
from core.models import AuditLog
from hr import leave as engine
from hr import onboarding
from hr.models import Employee, EmployeeStatus, FirstWeekSession, LeaveLedger, LeaveType, OnboardingTask
from interviews.timeutil import today_ist
from jobs.models import JobStatus
from offers.models import Offer, OfferStatus


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def accepted(users, make_job, team, pdf_bytes):
    """An accepted offer for the demo candidate, reporting to the hiring manager, joining in 3 weeks."""
    job = make_job(title="Platform Engineer")
    application = apply_to_job(candidate=users["candidate"], job=job, filename="cv.pdf", data=pdf_bytes)
    application.status = ApplicationStatus.OFFER
    application.save(update_fields=["status"])
    joining = today_ist(timezone.now()) + timedelta(days=21)
    offer = Offer(
        application=application,
        status=OfferStatus.ACCEPTED,
        expires_on=today_ist(timezone.now()) + timedelta(days=5),
        created_by=users["recruiter"],
    )
    offer.data = {
        "designation": "Platform Engineer",
        "department": "Engineering",
        "location": "Hyderabad",
        "joining_date": joining.isoformat(),
        "reporting_manager_id": str(users["hiring_manager"].id),
        "reporting_manager_name": users["hiring_manager"].full_name,
        "fixed_pay": 2400000,
    }
    offer.save()
    return offer


def hire(offer, user):
    return as_user(user).post(f"/api/offers/{offer.id}/hire", {}, format="json")


@pytest.mark.django_db
def test_hire_creates_everything_in_one_go(accepted, users, team):
    response = hire(accepted, users["recruiter"])
    assert response.status_code == 201, response.data
    candidate = users["candidate"]
    candidate.refresh_from_db()
    employee = Employee.objects.get(user=candidate)

    accepted.application.refresh_from_db()
    assert accepted.application.status == ApplicationStatus.HIRED
    assert employee.code.startswith("LW") and employee.status == EmployeeStatus.ONBOARDING
    assert employee.designation == "Platform Engineer"
    assert employee.manager == team["boss"]  # the offer's reporting manager
    assert employee.hired_from == accepted
    assert candidate.role == Role.EMPLOYEE  # same login, new role

    titles = set(OnboardingTask.objects.filter(employee=employee).values_list("title", flat=True))
    assert "Upload ID and address proof" in titles
    assert "Set up the development environment" in titles  # Engineering adds its own items
    assert "Shadow two customer calls" not in titles  # another department's item
    for task in employee.tasks.all():
        assert task.due_on is not None
        if task.owner_kind == "employee":
            assert task.owner == candidate
        if task.owner_kind == "manager":
            assert task.owner == users["hiring_manager"]
    assert FirstWeekSession.objects.filter(employee=employee).count() == 7
    assert LeaveLedger.objects.filter(employee=employee).exists()

    body = response.data
    assert body["employee"]["code"] == employee.code
    assert body["manager"]["name"] == users["hiring_manager"].full_name
    assert body["progress"]["total"] == len(titles) and body["progress"]["done"] == 0


@pytest.mark.django_db
def test_role_change_is_audited_and_sessions_revoked(accepted, users):
    with mock.patch("hr.onboarding.revoke_sessions") as revoke:
        assert hire(accepted, users["hr_admin"]).status_code == 201
    revoke.assert_called_once_with(users["candidate"])
    change = AuditLog.objects.get(action="users.role_changed")
    assert change.actor == users["hr_admin"]
    assert change.meta["old"] == Role.CANDIDATE and change.meta["new"] == Role.EMPLOYEE
    hired = AuditLog.objects.get(action="onboarding.hired")
    assert hired.meta["tasks"] > 0 and hired.meta["sessions"] == 7


@pytest.mark.django_db
def test_nothing_is_saved_when_a_step_fails(accepted, users):
    with mock.patch("hr.onboarding.generate_first_week", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            hire(accepted, users["recruiter"])
    candidate = users["candidate"]
    candidate.refresh_from_db()
    accepted.application.refresh_from_db()
    assert candidate.role == Role.CANDIDATE
    assert accepted.application.status == ApplicationStatus.OFFER
    assert not Employee.objects.filter(user=candidate).exists()
    assert not OnboardingTask.objects.exists()
    assert not LeaveLedger.objects.filter(employee__user=candidate).exists()
    assert not AuditLog.objects.filter(action="users.role_changed").exists()


@pytest.mark.django_db
def test_only_accepted_offers_can_be_hired_and_only_once(accepted, users):
    Offer.objects.filter(pk=accepted.pk).update(status=OfferStatus.SENT)
    response = hire(accepted, users["recruiter"])
    assert response.status_code == 400 and "accepted" in str(response.data)

    Offer.objects.filter(pk=accepted.pk).update(status=OfferStatus.ACCEPTED)
    assert hire(accepted, users["recruiter"]).status_code == 201
    again = hire(accepted, users["recruiter"])
    assert again.status_code == 400


@pytest.mark.django_db
def test_recruiters_hire_only_for_their_own_jobs(accepted, users, make_user):
    other = make_user(Role.RECRUITER)
    assert hire(accepted, other).status_code == 404
    for role in ("hiring_manager", "employee", "candidate"):
        assert hire(accepted, users[role]).status_code == 403


@pytest.mark.django_db
def test_other_applications_are_withdrawn_and_the_job_closes_when_filled(
    accepted, users, make_job, pdf_bytes
):
    candidate = users["candidate"]
    other_job = make_job(title="Data Engineer")
    other = apply_to_job(candidate=candidate, job=other_job, filename="cv.pdf", data=pdf_bytes)
    job = accepted.application.job
    job.openings = 1
    job.save(update_fields=["openings"])

    assert hire(accepted, users["recruiter"]).status_code == 201
    other.refresh_from_db()
    job.refresh_from_db()
    assert other.status == ApplicationStatus.WITHDRAWN
    assert other.events.last().reason == "hired_elsewhere"
    assert job.openings == 0 and job.status == JobStatus.CLOSED


@pytest.mark.django_db
def test_openings_go_down_but_the_job_stays_open_while_seats_remain(accepted, users):
    job = accepted.application.job
    assert job.openings == 2
    hire(accepted, users["recruiter"])
    job.refresh_from_db()
    assert job.openings == 1 and job.status == JobStatus.OPEN


@pytest.mark.django_db
def test_buddy_rules(make_employee, hr_locations, team):
    dept = hr_locations["department"]
    joining = date(2026, 12, 1)
    manager = team["boss"]
    recent = make_employee(joined=date(2026, 9, 1), name="Too Recent")  # under six months
    sales = make_employee(
        joined=date(2023, 1, 1), department=hr_locations["department2"], name="Sales Person"
    )
    busy = make_employee(joined=date(2025, 1, 1), name="Busy Buddy")
    free = make_employee(joined=date(2025, 2, 1), name="Free Buddy")
    make_employee(joined=date(2026, 11, 1), name="Joiner One").__class__.objects.filter(
        user__full_name="Joiner One"
    ).update(status=EmployeeStatus.ONBOARDING, buddy=busy)

    exclude = (manager.id,)
    chosen = onboarding.choose_buddy(dept, joining, exclude_ids=exclude)
    assert chosen not in (recent, sales, manager)
    # Fewest current buddies wins over the most recent joiner rule.
    assert chosen != busy
    # Ties on load go to the most recent joiner who qualifies.
    assert chosen == free
    assert onboarding.months_before(joining, 6) == date(2026, 6, 1)


@pytest.mark.django_db
def test_buddy_is_never_the_reporting_manager(accepted, users, team):
    # Only the manager qualifies in the department apart from the team; exclude everyone else.
    Employee.objects.exclude(pk=team["boss"].pk).update(joined_on=date(2030, 1, 1))
    hire(accepted, users["recruiter"])
    employee = Employee.objects.get(user=users["candidate"])
    assert employee.buddy is None or employee.buddy_id != employee.manager_id


@pytest.mark.django_db
def test_leave_is_prorated_from_the_joining_date(make_employee):
    emp = make_employee(joined=date(2026, 7, 20))  # after the 15th: earning starts in August
    today = date(2026, 11, 2)
    engine.credit_entitlements(emp, today)
    sick = LeaveType.objects.get(location=emp.location, code="sick")
    casual = LeaveType.objects.get(location=emp.location, code="casual")
    # Sick is granted for the year: 10 x 5/12 = 4.17 -> 4.0 (half-day rounding).
    assert engine.ledger_total(emp, sick, 2026) == Decimal("4")
    # Casual accrues monthly from August to November: 12/12 x 4 months.
    assert engine.ledger_total(emp, casual, 2026) == Decimal("4")


@pytest.mark.django_db
def test_hired_employee_gets_a_welcome_page_once(accepted, users):
    hire(accepted, users["recruiter"])
    client = as_user(users["candidate"])
    users["candidate"].refresh_from_db()
    data = client.get("/api/onboarding/me").data
    assert data["welcome_pending"] is True
    assert data["buddy"] is None or data["buddy"]["name"]
    assert len(data["first_week"]) == 7
    assert client.post("/api/onboarding/me", {}, format="json").status_code == 200
    assert client.get("/api/onboarding/me").data["welcome_pending"] is False


@pytest.mark.django_db
def test_manager_and_hr_see_progress_peers_do_not(accepted, users, team):
    hire(accepted, users["recruiter"])
    employee = Employee.objects.get(user=users["candidate"])
    assert as_user(users["hiring_manager"]).get(f"/api/onboarding/{employee.id}").status_code == 200
    assert as_user(users["hr_admin"]).get(f"/api/onboarding/{employee.id}").status_code == 200
    peer = team["peers"][1].user
    if employee.buddy is None or employee.buddy.user_id != peer.id:
        assert as_user(peer).get(f"/api/onboarding/{employee.id}").status_code == 404
    names = [row["name"] for row in as_user(users["hiring_manager"]).get("/api/onboarding").data["results"]]
    assert employee.name in names


@pytest.mark.django_db
def test_checklist_tasks_belong_to_their_owner(accepted, users):
    hire(accepted, users["recruiter"])
    employee = Employee.objects.get(user=users["candidate"])
    mine = employee.tasks.filter(owner_kind="employee", kind="acknowledge").first()
    managers = employee.tasks.filter(owner_kind="manager").first()
    hr_task = employee.tasks.filter(owner_kind="hr").first()
    users["candidate"].refresh_from_db()  # now an employee
    joiner = as_user(users["candidate"])

    assert joiner.post(f"/api/onboarding/tasks/{managers.id}/complete", {}, format="json").status_code == 403
    assert joiner.post(f"/api/onboarding/tasks/{hr_task.id}/complete", {}, format="json").status_code == 403
    response = joiner.post(f"/api/onboarding/tasks/{mine.id}/complete", {}, format="json")
    assert response.status_code == 200 and response.data["done"] is True
    assert (
        as_user(users["hr_admin"])
        .post(f"/api/onboarding/tasks/{hr_task.id}/complete", {}, format="json")
        .status_code
        == 200
    )

    upload = employee.tasks.filter(kind="upload").first()
    missing = joiner.post(f"/api/onboarding/tasks/{upload.id}/complete", {}, format="multipart")
    assert missing.status_code == 400 and "document" in missing.data


@pytest.mark.django_db
def test_onboarding_finishes_when_every_task_is_done(accepted, users):
    hire(accepted, users["recruiter"])
    employee = Employee.objects.get(user=users["candidate"])
    employee.tasks.exclude(pk=employee.tasks.first().pk).update(done_at=timezone.now())
    last = employee.tasks.filter(done_at__isnull=True).get()
    if last.kind == "upload":
        last.kind = "task"
        last.save(update_fields=["kind"])
    onboarding.complete(last, users["hr_admin"])
    employee.refresh_from_db()
    assert employee.status == EmployeeStatus.ACTIVE


@pytest.mark.django_db
def test_offer_accepted_tells_hr_the_hire_is_ready(accepted, users):
    from notifications.models import Notification
    from offers.events import offer_accepted

    offer_accepted.send(sender=Offer, offer=accepted)
    assert Notification.objects.filter(user=users["hr_admin"], kind="ready_to_hire").exists()


@pytest.mark.django_db
def test_offer_page_offers_hire_once(accepted, users):
    client = as_user(users["recruiter"])
    data = client.get(f"/api/offers/{accepted.id}").data
    assert data["actions"]["hire"] is True and data["hired"] is None
    assert as_user(users["hiring_manager"]).get(f"/api/offers/{accepted.id}").data["actions"]["hire"] is False
    hire(accepted, users["recruiter"])
    data = client.get(f"/api/offers/{accepted.id}").data
    assert data["actions"]["hire"] is False and data["hired"]["code"].startswith("LW")
