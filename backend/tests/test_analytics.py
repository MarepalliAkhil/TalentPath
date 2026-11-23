"""Analytics on a small fixture with known answers: medians, percentiles, conversion,
sources, leave utilisation, role scoping, department filter and CSV export."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from analytics import metrics
from analytics.views import _safe
from applications.models import Application, ApplicationEvent
from applications.models import ApplicationStatus as S

PATHS = {
    # name: (source, [(status, day)]) — day 0 is the application day
    "a1": ("referral", [(S.SCREENING, 2), (S.INTERVIEW, 5), (S.OFFER, 10), (S.HIRED, 12)]),
    "a2": ("job_board", [(S.SCREENING, 4), (S.INTERVIEW, 10)]),
    "a3": ("career_site", [(S.SCREENING, 6), (S.REJECTED, 7)]),
    "a4": ("career_site", []),
    "a5": ("referral", [(S.SCREENING, 2), (S.INTERVIEW, 4), (S.OFFER, 8), (S.HIRED, 16)]),
}


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_app(job, candidate, source, steps, base):
    last = steps[-1][0] if steps else S.APPLIED
    app = Application.objects.create(job=job, candidate=candidate, source=source, status=last)
    Application.objects.filter(pk=app.pk).update(created_at=base)
    applied = ApplicationEvent.objects.create(application=app, to_status=S.APPLIED)
    ApplicationEvent.objects.filter(pk=applied.pk).update(created_at=base)
    prev = S.APPLIED
    for status, day in steps:
        event = ApplicationEvent.objects.create(application=app, from_status=prev, to_status=status)
        ApplicationEvent.objects.filter(pk=event.pk).update(created_at=base + timedelta(days=day))
        prev = status
    return app


@pytest.fixture
def hiring(users, make_job, make_user, org):
    base = timezone.now() - timedelta(days=30)
    other_recruiter = make_user(Role.RECRUITER)
    other_hm = make_user(Role.HIRING_MANAGER)
    mine = make_job(title="Backend Engineer")
    theirs = make_job(
        title="Sales Lead", owner=other_recruiter, manager=other_hm, department=org["department2"]
    )
    for name, (source, steps) in PATHS.items():
        make_app(mine, make_user(Role.CANDIDATE, name=f"Cand {name}"), source, steps, base)
    for n in range(3):
        make_app(theirs, make_user(Role.CANDIDATE, name=f"Other {n}"), "job_board", [(S.SCREENING, 1)], base)
    return {"mine": mine, "theirs": theirs, "other_recruiter": other_recruiter, "other_hm": other_hm}


def sections(client, report="hiring", **params):
    response = client.get(f"/api/analytics/{report}", params)
    assert response.status_code == 200, response.data
    return {s["key"]: s for s in response.data["sections"]}


# ---------------------------------------------------------------- the statistics
def test_percentile_and_median():
    assert metrics.median([]) is None
    assert metrics.median([7]) == 7
    assert metrics.median([1, 3]) == 2
    assert metrics.median([5, 1, 3]) == 3
    assert metrics.percentile([12, 16], 0.8) == 15.2  # 12 + (16 - 12) * 0.8
    assert metrics.percentile([1, 2, 3, 6], 0.8) == 4.2  # rank 2.4 -> 3 + (6 - 3) * 0.4
    assert metrics.rate(1, 3) == 33.3 and metrics.rate(0, 0) is None


@pytest.mark.django_db
def test_time_to_hire_and_time_in_stage(hiring, users):
    data = sections(as_user(users["recruiter"]))
    tth = {r["measure"]: r["days"] for r in data["time_to_hire"]["rows"]}
    assert tth == {"Median": 14.0, "80th percentile": 15.2, "Hires": 2}
    assert "Median time to hire is 14 days" in data["time_to_hire"]["summary"]
    screening = next(r for r in data["time_in_stage"]["rows"] if r["stage"] == "Screening")
    assert screening == {"stage": "Screening", "median": 2.5, "p80": 4.2, "count": 4}


@pytest.mark.django_db
def test_funnel_conversion(hiring, users):
    rows = {r["stage"]: r for r in sections(as_user(users["recruiter"]))["funnel"]["rows"]}
    assert [rows[s]["reached"] for s in ("Applied", "Screening", "Interview", "Offer", "Hired")] == [
        5,
        4,
        3,
        2,
        2,
    ]
    assert rows["Applied"]["conversion"] is None
    assert rows["Screening"]["conversion"] == 80.0 and rows["Interview"]["conversion"] == 75.0
    assert rows["Offer"]["conversion"] == 66.7 and rows["Hired"]["conversion"] == 100.0


@pytest.mark.django_db
def test_source_effectiveness(hiring, users):
    rows = {r["source"]: r for r in sections(as_user(users["recruiter"]))["sources"]["rows"]}
    assert rows["Referral"] == {
        "source": "Referral",
        "applications": 2,
        "interview_rate": 100.0,
        "hire_rate": 100.0,
    }
    assert rows["Job board"]["applications"] == 1 and rows["Job board"]["hire_rate"] == 0.0
    assert rows["Career site"]["interview_rate"] == 0.0
    assert rows["Internal"]["applications"] == 0 and rows["Internal"]["interview_rate"] is None


# ---------------------------------------------------------------- scope
@pytest.mark.django_db
def test_recruiters_see_only_their_own_jobs(hiring, users):
    mine = sections(as_user(users["recruiter"]))["funnel"]["rows"][0]["reached"]
    theirs = sections(as_user(hiring["other_recruiter"]))["funnel"]["rows"][0]["reached"]
    everyone = sections(as_user(users["hr_admin"]))["funnel"]["rows"][0]["reached"]
    assert (mine, theirs, everyone) == (5, 3, 8)


@pytest.mark.django_db
def test_hiring_managers_see_only_assigned_jobs(hiring, users):
    assert sections(as_user(users["hiring_manager"]))["funnel"]["rows"][0]["reached"] == 5
    assert sections(as_user(hiring["other_hm"]))["funnel"]["rows"][0]["reached"] == 3


@pytest.mark.django_db
def test_employees_and_candidates_see_nothing(hiring, users):
    for role in ("employee", "candidate"):
        assert as_user(users[role]).get("/api/analytics/hiring").status_code == 403
    assert APIClient().get("/api/analytics/hiring").status_code == 401


@pytest.mark.django_db
def test_people_analytics_are_hr_only(users):
    assert as_user(users["recruiter"]).get("/api/analytics/people").status_code == 403
    assert as_user(users["hiring_manager"]).get("/api/analytics/people").status_code == 403
    assert as_user(users["hr_admin"]).get("/api/analytics/people").status_code == 200
    assert as_user(users["hr_admin"]).get("/api/analytics/unknown").status_code == 404


@pytest.mark.django_db
def test_department_and_date_filters(hiring, users, org):
    admin = as_user(users["hr_admin"])
    eng = sections(admin, department=str(org["department"].id))["funnel"]["rows"][0]["reached"]
    sales = sections(admin, department=str(org["department2"].id))["funnel"]["rows"][0]["reached"]
    assert (eng, sales) == (5, 3)
    today = date.today()
    none = sections(admin, **{"from": (today - timedelta(days=5)).isoformat(), "to": today.isoformat()})
    assert none["funnel"]["rows"][0]["reached"] == 0
    assert admin.get("/api/analytics/hiring", {"from": "2026-12-01", "to": "2026-01-01"}).status_code == 400
    assert admin.get("/api/analytics/hiring", {"from": "yesterday"}).status_code == 400


# ---------------------------------------------------------------- CSV
@pytest.mark.django_db
def test_csv_export_matches_the_table_and_scope(hiring, users):
    response = as_user(users["recruiter"]).get("/api/analytics/hiring/funnel.csv")
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    lines = response.content.decode().strip().splitlines()
    assert lines[0] == "Stage,Applications reaching it,% of previous stage"
    assert lines[1] == "Applied,5," and lines[2] == "Screening,4,80.0"
    other = as_user(hiring["other_recruiter"]).get("/api/analytics/hiring/funnel.csv").content.decode()
    assert other.splitlines()[1] == "Applied,3,"
    assert as_user(users["recruiter"]).get("/api/analytics/hiring/nope.csv").status_code == 404
    assert as_user(users["recruiter"]).get("/api/analytics/people/onboarding.csv").status_code == 403


def test_csv_cells_cannot_start_formulas():
    assert _safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert _safe("+1") == "'+1" and _safe("@x") == "'@x"
    assert _safe(-3) == "-3" and _safe("Backend") == "Backend"


# ---------------------------------------------------------------- people
@pytest.mark.django_db
def test_leave_utilisation(make_employee, users):
    from hr.models import LeaveLedger, LeaveRequest, LeaveStatus, LeaveType

    emp = make_employee()
    casual = LeaveType.objects.get(location=emp.location, code="casual")
    year = date.today().year
    LeaveLedger.objects.create(
        employee=emp, leave_type=casual, year=year, kind="grant", days=Decimal("12"), key="t1"
    )
    LeaveRequest.objects.create(
        employee=emp,
        leave_type=casual,
        start=date(year, 1, 5),
        end=date(year, 1, 7),
        days=3,
        status=LeaveStatus.APPROVED,
    )
    LeaveRequest.objects.create(
        employee=emp, leave_type=casual, start=date(year, 1, 12), end=date(year, 1, 12), days=1
    )
    rows = {r["type"]: r for r in sections(as_user(users["hr_admin"]), "people")["leave_utilisation"]["rows"]}
    assert rows["Casual leave"] == {
        "type": "Casual leave",
        "credited": 12.0,
        "taken": 3.0,
        "utilisation": 25.0,
    }


@pytest.mark.django_db
def test_onboarding_and_mobility_counts(make_employee, users):
    from hr.models import InternalMove, OnboardingTask

    done, open_ = make_employee(name="Done Joiner"), make_employee(name="Busy Joiner")
    for emp, finished in ((done, True), (open_, False)):
        OnboardingTask.objects.create(
            employee=emp,
            title="Read policy",
            category="policies",
            owner_kind="employee",
            kind="task",
            due_on=date(2020, 1, 1),
            done_at=timezone.now() if finished else None,
        )
    InternalMove.objects.create(
        employee=done,
        from_department="Sales",
        to_department="Engineering",
        from_designation="SDR",
        to_designation="Engineer",
        moved_on=date.today() - timedelta(days=3),
    )
    data = sections(as_user(users["hr_admin"]), "people")
    onboarding = {r["measure"]: r["value"] for r in data["onboarding"]["rows"]}
    assert onboarding["Joiners with a checklist"] == 2 and onboarding["Checklists complete"] == 1
    assert onboarding["Completion rate (%)"] == 50.0 and onboarding["Tasks overdue"] == 1
    assert data["mobility"]["rows"][0]["to"] == "Engineer, Engineering"


@pytest.mark.django_db
def test_every_section_has_a_summary_and_a_table(hiring, users):
    for report in ("hiring", "people"):
        for sec in sections(as_user(users["hr_admin"]), report).values():
            assert sec["summary"] and sec["columns"]
            if sec["chart"]:
                keys = {c["key"] for c in sec["columns"]}
                assert sec["chart"]["x"] in keys
                assert all(s["key"] in keys for s in sec["chart"]["series"])


# ---------------------------------------------------------------- more metrics on known fixtures
@pytest.mark.django_db
def test_offer_acceptance_rate_and_decline_reasons(hiring, users):
    from offers.models import Offer, OfferStatus

    apps = list(Application.objects.filter(job=hiring["mine"]).order_by("created_at"))
    outcomes = [
        (OfferStatus.ACCEPTED, ""),
        (OfferStatus.ACCEPTED, ""),
        (OfferStatus.DECLINED, "Chose another offer"),
        (OfferStatus.EXPIRED, ""),
        (OfferStatus.DRAFT, ""),  # drafts are not offers yet
    ]
    for app, (status, reason) in zip(apps, outcomes, strict=True):
        offer = Offer(
            application=app,
            status=status,
            expires_on=date.today(),
            created_by=users["recruiter"],
            decline_reason=reason,
        )
        offer.data = {"designation": "Engineer", "fixed_pay": 100}
        offer.save()
    sec = sections(as_user(users["recruiter"]))["offers"]
    assert "50%" in sec["summary"] or "50.0%" in sec["summary"]  # 2 / (2 + 1 + 1)
    rows = {r["outcome"]: r["offers"] for r in sec["rows"]}
    assert rows["Declined: Chose another offer"] == 1
    assert "Draft" not in rows


@pytest.mark.django_db
def test_match_score_versus_outcome(hiring, users):
    from matching.models import FitScore

    bands = {"a1": "strong", "a5": "strong", "a2": "good", "a3": "low", "a4": "low"}
    for app in Application.objects.filter(job=hiring["mine"]).select_related("candidate"):
        key = app.candidate.full_name.split()[-1]
        FitScore.objects.create(application=app, score=50, band=bands[key], version=1, requirements_hash="x")
    rows = {r["band"]: r for r in sections(as_user(users["recruiter"]))["match_vs_outcome"]["rows"]}
    strong = next(r for name, r in rows.items() if name.lower().startswith("strong"))
    low = next(r for name, r in rows.items() if name.lower().startswith("low"))
    assert (
        strong["applications"] == 2
        and strong["reached_interview"] == 100.0
        and strong["reached_offer"] == 100.0
    )
    assert low["applications"] == 2 and low["reached_interview"] == 0.0


@pytest.mark.django_db
def test_hira_automation_counts_only_jobs_in_scope(hiring, users):
    from hira.models import HiraAction, HiraActivity

    for _ in range(3):
        HiraActivity.objects.create(action=HiraAction.INTERVIEW_SCHEDULED, job=hiring["mine"])
    HiraActivity.objects.create(action=HiraAction.SCORECARD_CHASED, job=hiring["mine"], needs_you=True)
    HiraActivity.objects.create(action=HiraAction.INTERVIEW_SCHEDULED, job=hiring["theirs"])
    mine = {r["action"]: r["count"] for r in sections(as_user(users["recruiter"]))["hira"]["rows"]}
    assert (
        mine["Interviews scheduled"] == 3
        and mine["Feedback chased"] == 1
        and mine["Needs-you items raised"] == 1
    )
    everyone = {r["action"]: r["count"] for r in sections(as_user(users["hr_admin"]))["hira"]["rows"]}
    assert everyone["Interviews scheduled"] == 4


@pytest.mark.django_db
def test_absenteeism_and_late_trend(make_employee, users):
    from datetime import datetime, time

    from hr.models import AttendanceRecord, LeaveRequest, LeaveStatus, LeaveType
    from interviews.timeutil import IST

    emp = make_employee()
    today = date.today()
    monday = today - timedelta(days=today.weekday() + 14)  # a full working week, two weeks ago
    # Mon on time, Tue late, Wed nothing (absent), Thu approved leave (not counted), Fri on time.
    for offset, late in ((0, False), (1, True), (4, False)):
        day = monday + timedelta(days=offset)
        AttendanceRecord.objects.create(
            employee=emp,
            date=day,
            check_in=datetime.combine(day, time(9, 30), tzinfo=IST),
            check_out=datetime.combine(day, time(18, 30), tzinfo=IST),
            late=late,
        )
    thursday = monday + timedelta(days=3)
    LeaveRequest.objects.create(
        employee=emp,
        leave_type=LeaveType.objects.get(location=emp.location, code="casual"),
        start=thursday,
        end=thursday,
        days=1,
        status=LeaveStatus.APPROVED,
    )
    data = sections(
        as_user(users["hr_admin"]),
        "people",
        **{"from": monday.isoformat(), "to": (monday + timedelta(days=4)).isoformat()},
    )
    week = data["absenteeism"]["rows"][0]
    assert week == {"week": monday.isoformat(), "absence_rate": 25.0, "absent_days": 1, "working_days": 4}
    late = data["late_trend"]["rows"][0]
    assert late["late"] == 1 and late["check_ins"] == 3 and late["late_rate"] == round(100 / 3, 1)
