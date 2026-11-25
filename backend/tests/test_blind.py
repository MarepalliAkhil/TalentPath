import pytest

from accounts.services import set_phone
from applications.services import apply_to_job, move_application
from core.models import AuditLog
from notifications.models import Notification
from seeding.docgen import make_docx

PERSONAL = [
    "Meera",
    "Krishnan",
    "meera.k@candidates.example",
    "98765",
    "Lakeview University",
    "Vijayawada",
    "linkedin.com",
]


@pytest.fixture
def meera(make_user):
    user = make_user("candidate", email="meera.k@candidates.example", name="Meera Krishnan")
    profile = user.profile
    set_phone(profile, "+91 98765 43210")
    profile.location_text = "Vijayawada"
    profile.headline = "Backend developer"
    profile.save()
    return user


@pytest.fixture
def blind_app(meera, open_job):
    lines = [
        "Meera Krishnan",
        "Backend developer | Vijayawada",
        "Email: meera.k@candidates.example | Phone: +91 98765 43210 | linkedin.com/in/meerak",
        "Age: 26 | Gender: Female",
        "SKILLS",
        "Python, Django, PostgreSQL",
        "EXPERIENCE",
        "Engineer - Kestrel (2021 - present)",
        "Built Django and PostgreSQL services",
        "EDUCATION",
        "B.Tech, Lakeview University, 2016 - 2020",
    ]
    return apply_to_job(
        candidate=meera,
        job=open_job,
        filename="cv.docx",
        data=make_docx(lines),
        cover_note="Meera here, happy to talk.",
    )


def _assert_no_personal_data(blob: str):
    for value in PERSONAL:
        assert value not in blob, value


@pytest.mark.parametrize("role", ["recruiter", "manager", "hr"])
def test_blind_list_board_and_detail_hide_identity(role, client_for, blind_app):
    client = client_for(role)
    rows = client.get(f"/api/jobs/{blind_app.job_id}/applications").data["results"]
    board = client.get(f"/api/jobs/{blind_app.job_id}/board").data
    detail = client.get(f"/api/applications/{blind_app.id}").data
    for payload in (rows[0], board["columns"][0]["cards"][0], detail):
        assert payload["blind"] is True
        assert payload["candidate"]["full_name"] is None and payload["candidate"]["email"] is None
        assert payload["candidate"]["code"].startswith("Candidate #")
    _assert_no_personal_data(str(rows) + str(board) + str(detail))
    assert "[hidden]" in detail["resume_text"] and "Django" in detail["resume_text"]


def test_original_file_is_not_sent_while_blind(client_for, blind_app):
    resp = client_for("recruiter").get(f"/api/applications/{blind_app.id}/resume")
    assert resp.status_code == 409 and resp.data["code"] == "identity_hidden"
    own = client_for("candidate")  # unrelated candidate: not theirs
    assert own.get(f"/api/applications/{blind_app.id}/resume").status_code == 404


def test_new_application_notification_uses_the_code_while_blind(blind_app):
    note = Notification.objects.get(user=blind_app.job.created_by, kind="new_application")
    assert "Meera" not in note.body and blind_app.candidate_code in note.body


def test_identity_revealed_automatically_at_interview(client_for, blind_app):
    recruiter = blind_app.job.created_by
    move_application(blind_app, "screening", recruiter)
    assert client_for("recruiter").get(f"/api/applications/{blind_app.id}").data["blind"] is True
    move_application(blind_app, "interview", recruiter)
    detail = client_for("recruiter").get(f"/api/applications/{blind_app.id}").data
    assert detail["blind"] is False and detail["candidate"]["full_name"] == "Meera Krishnan"
    assert "Lakeview University" in detail["resume_text"]
    entry = AuditLog.objects.get(action="applications.identity_revealed", target_id=str(blind_app.id))
    assert entry.meta["automatic"] is True and entry.meta["stage"] == "interview"
    assert client_for("recruiter").get(f"/api/applications/{blind_app.id}/resume").status_code == 200


def test_reveal_stage_offer_keeps_interview_blind(client_for, blind_app):
    job = blind_app.job
    job.reveal_stage = "offer"
    job.save()
    for stage in ("screening", "interview"):
        move_application(blind_app, stage, job.created_by)
    assert client_for("recruiter").get(f"/api/applications/{blind_app.id}").data["blind"] is True
    move_application(blind_app, "offer", job.created_by)
    assert client_for("recruiter").get(f"/api/applications/{blind_app.id}").data["blind"] is False


def test_manual_reveal_only_hr_with_reason_and_audited(client_for, blind_app):
    url = f"/api/applications/{blind_app.id}/reveal"
    assert (
        client_for("recruiter").post(url, {"reason": "I really want to know"}, format="json").status_code
        == 403
    )
    assert (
        client_for("manager").post(url, {"reason": "I really want to know"}, format="json").status_code == 403
    )
    admin = client_for("hr")
    assert admin.post(url, {"reason": "short"}, format="json").status_code == 400
    ok = admin.post(url, {"reason": "Candidate asked for an accessibility adjustment"}, format="json")
    assert ok.status_code == 200 and ok.data["blind"] is False
    entry = AuditLog.objects.get(action="applications.identity_revealed")
    assert entry.meta["automatic"] is False and "accessibility" in entry.meta["reason"]
    assert (
        admin.post(url, {"reason": "Candidate asked again for something"}, format="json").status_code == 409
    )


def test_blind_off_shows_identity(client_for, blind_app):
    blind_app.job.blind_screening = False
    blind_app.job.save()
    detail = client_for("recruiter").get(f"/api/applications/{blind_app.id}").data
    assert detail["blind"] is False and detail["candidate"]["email"] == "meera.k@candidates.example"


def test_candidate_never_sees_blind_internals(client_for, blind_app, meera):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(meera)
    data = client.get(f"/api/applications/{blind_app.id}").data
    assert "fit" not in data and "notes" not in data and "resume_text" not in data and "blind" not in data
