import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command

from accounts.models import Role, User
from applications.models import Application
from jobs.models import Job

DEMO_LOGINS = {
    "candidate@demo.example": Role.CANDIDATE,
    "recruiter@demo.example": Role.RECRUITER,
    "manager@demo.example": Role.HIRING_MANAGER,
    "employee@demo.example": Role.EMPLOYEE,
    "admin@demo.example": Role.HR_ADMIN,
}


@pytest.mark.django_db
def test_seed_creates_fictional_demo_data_and_is_idempotent():
    call_command("seed")
    counts = (
        Job.objects.open().count(),
        User.objects.filter(role=Role.CANDIDATE).count(),
        Application.objects.count(),
    )
    assert counts[0] == 25
    assert counts[1] == 60
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
        Job.objects.open().count(),
        User.objects.filter(role=Role.CANDIDATE).count(),
        Application.objects.count(),
    ) == counts


@pytest.mark.django_db
def test_seed_reset_rebuilds():
    call_command("seed")
    call_command("seed", "--reset")
    assert Job.objects.open().count() == 25
    assert User.objects.filter(role=Role.CANDIDATE).count() == 60
