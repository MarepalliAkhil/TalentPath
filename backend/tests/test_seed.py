import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command

from accounts.models import Role, User
from applications.models import Application
from jobs.models import Job

DEMO_LOGINS = {
    "candidate@demo.example": Role.CANDIDATE,
    "recruiter@demo.example": Role.RECRUITER,
    "manager@demo.example": Role.MANAGER,
    "employee@demo.example": Role.EMPLOYEE,
    "hr@demo.example": Role.HR,
    "admin@demo.example": Role.ADMIN,
}


@pytest.mark.django_db
def test_seed_creates_fictional_demo_data_and_is_idempotent():
    call_command("seed")
    counts = (
        Job.objects.public().count(),
        User.objects.filter(role=Role.CANDIDATE).count(),
        Application.objects.count(),
    )
    assert counts[0] == 25
    assert counts[1] == 61  # 60 synthetic candidates + the week 3B joiner ready to hire
    assert counts[2] >= 60
    for email, role in DEMO_LOGINS.items():
        user = authenticate(username=email, password="Demo@Pass2026")
        assert user is not None and user.role == role, email
    assert not User.objects.exclude(email__endswith=".example").exists()
    demo = User.objects.get(email="candidate@demo.example")
    assert demo.applications.count() == 3
    assert demo.notifications.exists()
    assert all(a.resume_text for a in Application.objects.all()[:20])
    call_command("seed")
    assert (
        Job.objects.public().count(),
        User.objects.filter(role=Role.CANDIDATE).count(),
        Application.objects.count(),
    ) == counts


@pytest.mark.django_db
def test_seed_reset_rebuilds():
    call_command("seed")
    call_command("seed", "--reset")
    assert Job.objects.public().count() == 25  # plus 3 internal-only jobs (week 4A)
    assert User.objects.filter(role=Role.CANDIDATE).count() == 61


@pytest.mark.django_db
def test_seed_week2_pipeline_spread():
    from collections import Counter

    from applications.models import ApplicationNote
    from hira.models import KnowledgeEntry
    from matching.models import FitScore

    call_command("seed")
    counts = [job.applications.count() for job in Job.objects.public()]
    assert min(counts) >= 5 and max(counts) <= 15
    statuses = Counter(Application.objects.values_list("status", flat=True))
    assert {"applied", "screening", "interview", "offer", "rejected", "withdrawn"} <= set(statuses)
    assert (
        Application.objects.filter(status="rejected").exclude(rejection_reason="").count()
        == statuses["rejected"]
    )
    bands = set(FitScore.objects.values_list("band", flat=True))
    assert {"strong", "partial", "low"} <= bands
    assert FitScore.objects.count() == Application.objects.count()
    assert Job.objects.open().filter(blind_screening=False).exists()
    assert Application.objects.filter(job__blind_screening=True, identity_revealed_at__isnull=True).exists()
    assert ApplicationNote.objects.filter(kind="vote").exists()
    assert KnowledgeEntry.objects.count() >= 15


@pytest.mark.django_db
def test_seed_week3_interviews_offers_and_hira_history():
    from collections import Counter

    from hira import activity
    from hira.models import HiraActivity
    from interviews.coordinator import final_round_passed
    from interviews.models import Interview, InterviewerProfile, InterviewPlan, Scorecard
    from offers.models import Offer

    call_command("seed")
    assert InterviewPlan.objects.count() == Job.objects.count()
    assert all(plan.rounds.count() == 4 for plan in InterviewPlan.objects.all())
    assert InterviewerProfile.objects.filter(skills__isnull=False).distinct().count() >= 10
    statuses = Counter(Interview.objects.values_list("status", flat=True))
    assert statuses["completed"] and statuses["scheduled"] and statuses["pending"]
    assert Scorecard.objects.exists()
    owed = [
        i
        for i in Interview.objects.filter(status="completed")
        if i.assignments.count() > i.scorecards.count()
    ]
    assert owed, "some scorecards are still missing (overdue)"
    offers = set(Offer.objects.values_list("status", flat=True))
    assert {"draft", "pending_approval", "approved", "sent", "accepted", "declined", "expired"} <= offers
    recruiter = User.objects.get(email="recruiter@demo.example")
    briefing = activity.briefing(recruiter)
    assert briefing["counts"]["interview_scheduled"] > 0 and briefing["needs_you_count"] > 0
    assert HiraActivity.objects.filter(reason_code="seed_history").exists()
    demo = User.objects.get(email="candidate@demo.example")
    assert [final_round_passed(a) for a in demo.applications.filter(status="interview")] == [True]
    employee = User.objects.get(email="employee@demo.example")
    assert (
        Interview.objects.filter(assignments__interviewer=employee, status="completed")
        .exclude(scorecards__interviewer=employee)
        .exists()
    ), "the walkthrough needs a scorecard for employee@demo.example to fill in"


@pytest.mark.django_db
def test_seed_week3b_people_leave_attendance_and_hire_demo():
    from collections import Counter

    from hr.models import (
        AttendanceRecord,
        Employee,
        EmployeeStatus,
        Holiday,
        LeaveRequest,
        OnboardingTask,
        Regularisation,
    )
    from offers.models import Offer, OfferStatus

    call_command("seed")
    assert Employee.objects.count() == 30
    assert Employee.objects.filter(manager__isnull=False).count() >= 25
    assert Employee.objects.filter(buddy__isnull=False).exists()
    statuses = Counter(LeaveRequest.objects.values_list("status", flat=True))
    assert {"pending", "approved", "rejected", "cancelled"} <= set(statuses)
    assert LeaveRequest.objects.filter(escalated=True).exists()
    assert AttendanceRecord.objects.filter(missing_checkout=True).exists()
    assert AttendanceRecord.objects.values("date").distinct().count() >= 15
    assert Regularisation.objects.exists()
    onboarding = Employee.objects.filter(status=EmployeeStatus.ONBOARDING)
    assert onboarding.count() >= 2
    assert OnboardingTask.objects.filter(employee__in=onboarding, done_at__isnull=False).exists()
    telangana = Holiday.objects.filter(location__name="Hyderabad", regional=True)
    assert telangana.filter(name__icontains="Telangana").exists()
    assert all("verify" in h.note for h in Holiday.objects.all())
    demo = Offer.objects.get(application__candidate__email="joiner@demo.example")
    assert demo.status == OfferStatus.ACCEPTED and demo.application.status == "offer"

    # Idempotent: a second run adds no people, leave or attendance.
    def counts():
        return (Employee.objects.count(), LeaveRequest.objects.count(), AttendanceRecord.objects.count())

    before = counts()
    call_command("seed")
    assert counts() == before


@pytest.mark.django_db
def test_seed_week4a_audiences_sources_profiles_and_mobility():
    from collections import Counter

    from analytics import metrics
    from growth.models import CareerProfile
    from hr.models import Employee, InternalMove

    call_command("seed")
    assert Job.objects.open().filter(audience="internal").count() == 3
    assert Job.objects.filter(audience="external").count() == 3
    sources = Counter(Application.objects.values_list("source", flat=True))
    assert {"career_site", "job_board", "referral", "internal"} <= set(sources)
    assert sources["internal"] == 2
    assert not Employee.objects.filter(level__isnull=True).exists()
    assert CareerProfile.objects.filter(user__email="employee@demo.example").exists()
    assert InternalMove.objects.count() == 1
    # The timeline is spread out, so stage times are not all zero.
    stage = metrics.hiring_report(User.objects.get(email="hr@demo.example"), metrics.parse_filters({}))[1]
    assert any(row["median"] for row in stage["rows"])
