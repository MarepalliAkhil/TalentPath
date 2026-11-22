import pytest

from applications.models import ApplicationNote
from applications.services import apply_to_job, move_application
from core.models import AuditLog
from notifications.models import EmailOutbox, Notification


@pytest.fixture
def pushes(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "applications.services.push_realtime", lambda user_id, payload: sent.append((str(user_id), payload))
    )
    return sent


def status(client, app, to, **extra):
    return client.post(f"/api/applications/{app.id}/status", {"status": to, **extra}, format="json")


def test_allowed_and_forbidden_transitions(client_for, application):
    client = client_for("recruiter")
    assert status(client, application, "offer").status_code == 400  # no skipping
    assert status(client, application, "interview").status_code == 400
    assert status(client, application, "hired").status_code == 400  # reserved for week 3
    assert status(client, application, "withdrawn").status_code == 400  # candidate only
    assert status(client, application, "screening").status_code == 200
    assert status(client, application, "applied").status_code == 400  # no going back
    assert status(client, application, "interview").status_code == 200


def test_reject_needs_a_reason_and_the_reason_stays_internal(client_for, application, users):
    client = client_for("recruiter")
    assert status(client, application, "rejected").status_code == 400
    assert status(client, application, "rejected", reason="bad").status_code == 400
    ok = status(client, application, "rejected", reason="skills_gap", note="Needs more SQL depth")
    assert ok.status_code == 200 and ok.data["rejection_reason"] == "Required skills not shown"
    application.refresh_from_db()
    assert application.rejection_note == "Needs more SQL depth"
    candidate_view = client_for("candidate").get(f"/api/applications/{application.id}").data
    assert "skills_gap" not in str(candidate_view) and "SQL depth" not in str(candidate_view)
    assert candidate_view["status_label"] == "Not progressing"


def test_rejection_message_is_kind_short_and_suggests_jobs(application, users, make_job):
    other = make_job(title="Platform Engineer", required=("python",), nice=())
    move_application(application, "rejected", users["recruiter"], reason="stronger_fit")
    note = Notification.objects.filter(user=users["candidate"], kind="application_status").latest(
        "created_at"
    )
    assert "Thank you for applying" in note.body and other.title in note.body
    for word in ("score", "fit", "band", "reason", "stronger", "skills_gap", "%"):
        assert word not in note.body.lower()
    assert len(note.body) < 400
    assert EmailOutbox.objects.filter(to_email=users["candidate"].email, subject=note.title).exists()


def test_only_the_candidate_can_withdraw(client_for, application):
    assert client_for("recruiter").post(f"/api/applications/{application.id}/withdraw").status_code == 403
    assert client_for("candidate").post(f"/api/applications/{application.id}/withdraw").status_code == 200


def test_role_scoping_on_board_and_moves(client_for, application, make_user, make_job, pdf_bytes):
    foreign = make_job(owner=make_user("recruiter"), manager=make_user("hiring_manager"), title="Elsewhere")
    foreign_app = apply_to_job(
        candidate=make_user("candidate"), job=foreign, filename="c.pdf", data=pdf_bytes
    )
    recruiter, manager, admin = client_for("recruiter"), client_for("hiring_manager"), client_for("hr_admin")
    assert recruiter.get(f"/api/jobs/{application.job_id}/board").status_code == 200
    assert recruiter.get(f"/api/jobs/{foreign.id}/board").status_code == 404
    assert status(recruiter, foreign_app, "screening").status_code == 404
    assert manager.get(f"/api/jobs/{application.job_id}/board").status_code == 200
    assert manager.get(f"/api/jobs/{foreign.id}/board").status_code == 404
    assert status(manager, application, "screening").status_code == 403  # policy: managers do not move
    assert admin.get(f"/api/jobs/{foreign.id}/board").status_code == 200
    assert status(admin, foreign_app, "screening").status_code == 200


def test_board_shape(client_for, application):
    board = client_for("recruiter").get(f"/api/jobs/{application.job_id}/board").data
    assert [c["status"] for c in board["columns"]] == [
        "applied",
        "screening",
        "interview",
        "offer",
        "hired",
        "rejected",
        "withdrawn",
    ]
    targets = {c["status"]: c["drop_target"] for c in board["columns"]}
    assert targets["hired"] is False and targets["withdrawn"] is False and targets["screening"] is True
    assert board["can_move"] is True and board["transitions"]["applied"] == ["rejected", "screening"]
    assert {r["value"] for r in board["rejection_reasons"]} >= {"skills_gap", "other"}
    manager_board = client_for("hiring_manager").get(f"/api/jobs/{application.job_id}/board").data
    assert (
        manager_board["can_move"] is False
        and manager_board["columns"][0]["cards"][0]["allowed_transitions"] == []
    )


def test_every_move_is_audited_and_pushed_live(client_for, application, users, pushes):
    status(client_for("recruiter"), application, "screening")
    entry = AuditLog.objects.get(action="applications.status", target_id=str(application.id))
    assert entry.meta == {"old": "applied", "new": "screening"}
    recipients = {uid for uid, _ in pushes}
    assert {
        str(users["recruiter"].id),
        str(users["hiring_manager"].id),
        str(users["hr_admin"].id),
    } <= recipients
    assert str(users["candidate"].id) not in recipients
    assert pushes[0][1] == {
        "type": "board",
        "event": "moved",
        "job": str(application.job_id),
        "application": str(application.id),
        "status": "screening",
    }


def test_hiring_manager_notes_and_votes_only_at_screening_and_interview(client_for, application):
    manager = client_for("hiring_manager")
    url = f"/api/applications/{application.id}/notes"
    assert manager.post(url, {"body": "Looks good"}, format="json").status_code == 400  # still Applied
    move_application(application, "screening", application.job.created_by)
    up = manager.post(url, {"body": "Strong projects", "vote": "up"}, format="json")
    assert up.status_code == 201 and up.data["vote"] == "up" and up.data["author_role"] == "hiring_manager"
    assert manager.post(url, {"vote": "sideways"}, format="json").status_code == 400
    assert manager.post(url, {}, format="json").status_code == 400
    recruiter = client_for("recruiter")
    assert recruiter.post(url, {"vote": "up"}, format="json").status_code == 400  # votes are the manager's
    assert recruiter.post(url, {"body": "Call scheduled"}, format="json").status_code == 201
    notes = recruiter.get(url).data
    assert [n["body"] for n in notes] == ["Strong projects", "Call scheduled"]
    assert AuditLog.objects.filter(action="applications.note").count() == 2
    assert client_for("candidate").get(url).status_code == 403


def test_bulk_moves_with_confirmation_rules(client_for, open_job, make_user, pdf_bytes):
    apps = [
        apply_to_job(candidate=make_user("candidate"), job=open_job, filename="x.pdf", data=pdf_bytes)
        for _ in range(3)
    ]
    url = f"/api/jobs/{open_job.id}/applications/bulk-status"
    client = client_for("recruiter")
    ids = [str(a.id) for a in apps]
    assert client.post(url, {"ids": ids, "status": "interview"}, format="json").status_code == 400
    assert client.post(url, {"ids": ids, "status": "rejected"}, format="json").status_code == 400  # reason
    ok = client.post(url, {"ids": ids[:2], "status": "screening"}, format="json")
    assert ok.status_code == 200 and ok.data["moved"] == 2
    # all or nothing: one of these is already in Screening, so moving all to Screening fails as a whole
    assert client.post(url, {"ids": ids, "status": "screening"}, format="json").status_code == 400
    apps[2].refresh_from_db()
    assert apps[2].status == "applied"
    rejected = client.post(url, {"ids": ids, "status": "rejected", "reason": "role_filled"}, format="json")
    assert rejected.status_code == 200 and rejected.data["moved"] == 3
    assert AuditLog.objects.filter(action="applications.status").count() == 5


def test_bulk_rejects_foreign_ids(client_for, open_job, application, make_job, make_user, pdf_bytes):
    other_job = make_job(title="Another Role")
    stranger = apply_to_job(candidate=make_user("candidate"), job=other_job, filename="y.pdf", data=pdf_bytes)
    url = f"/api/jobs/{open_job.id}/applications/bulk-status"
    resp = client_for("recruiter").post(
        url, {"ids": [str(application.id), str(stranger.id)], "status": "screening"}, format="json"
    )
    assert resp.status_code == 400
    assert (
        client_for("hiring_manager")
        .post(url, {"ids": [str(application.id)], "status": "screening"}, format="json")
        .status_code
        == 403
    )


def test_candidate_message_visible_to_recruiter_only(client_for, application, users):
    resp = client_for("candidate").post(
        "/api/hira/message",
        {"application": str(application.id), "message": "Is the role hybrid?"},
        format="json",
    )
    assert resp.status_code == 201
    note = ApplicationNote.objects.get(application=application)
    assert note.kind == "candidate_message"
    notes = client_for("recruiter").get(f"/api/applications/{application.id}/notes").data
    assert notes[0]["body"] == "Is the role hybrid?" and notes[0]["author_role"] == "candidate"
    assert notes[0]["author"].startswith("Candidate #")  # blind: no name
    alert = Notification.objects.get(user=users["recruiter"], kind="candidate_message")
    assert "Is the role hybrid?" not in alert.body
