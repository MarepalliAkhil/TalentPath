import pytest
from django.db import connection

from applications.models import Application
from core.models import AuditLog
from files.storage import read_file
from jobs.models import JobStatus
from notifications.models import EmailOutbox, Notification


def apply(client, job, upload, data, name="resume.pdf", **extra):
    return client.post(
        "/api/applications",
        {"job": job.slug, "resume": upload(data, name=name), **extra},
        format="multipart",
    )


def test_candidate_applies_with_pdf(client_for, open_job, upload, pdf_bytes, users):
    resp = apply(client_for("candidate"), open_job, upload, pdf_bytes, cover_note="Keen to join.")
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == "applied"
    app = Application.objects.get(pk=resp.data["id"])
    assert "Django" in app.resume_text
    assert app.resume_filename == "resume.pdf"
    assert app.events.count() == 1


def test_resume_text_and_file_are_encrypted_at_rest(client_for, open_job, upload, pdf_bytes):
    resp = apply(client_for("candidate"), open_job, upload, pdf_bytes)
    app = Application.objects.get(pk=resp.data["id"])
    with connection.cursor() as cursor:
        cursor.execute("SELECT resume_text FROM applications_application WHERE id = %s", [app.id])
        (raw_text,) = cursor.fetchone()
        cursor.execute("SELECT data FROM files_storedfile WHERE id = %s", [app.resume_file_id])
        (raw_blob,) = cursor.fetchone()
    assert raw_text.startswith("v1:") and "Django" not in raw_text
    raw_blob = bytes(raw_blob)
    assert b"%PDF" not in raw_blob and b"Django" not in raw_blob
    assert read_file(app.resume_file) == pdf_bytes
    assert app.resume_file.size_bytes == len(pdf_bytes)


def test_candidate_applies_with_docx(client_for, open_job, upload, docx_bytes):
    resp = apply(
        client_for("candidate"),
        open_job,
        upload,
        docx_bytes,
        name="cv.docx",
    )
    assert resp.status_code == 201, resp.data
    assert "PostgreSQL" in Application.objects.get(pk=resp.data["id"]).resume_text


def test_duplicate_application_is_blocked(client_for, open_job, upload, pdf_bytes):
    client = client_for("candidate")
    assert apply(client, open_job, upload, pdf_bytes).status_code == 201
    second = apply(client, open_job, upload, pdf_bytes)
    assert second.status_code == 409
    assert Application.objects.count() == 1


@pytest.mark.parametrize(
    "data,name",
    [
        (b"\x89PNG\r\n\x1a\n" + b"0" * 100, "photo.pdf"),  # image renamed to .pdf
        (b"MZ\x90\x00" + b"0" * 100, "resume.pdf"),  # executable renamed to .pdf
        (b"Just some text", "resume.docx"),
        (b"", "resume.pdf"),
    ],
)
def test_resume_type_is_checked_by_content(client_for, open_job, upload, data, name):
    resp = apply(client_for("candidate"), open_job, upload, data, name=name)
    assert resp.status_code == 400
    assert "resume" in resp.data
    assert Application.objects.count() == 0


def test_resume_size_limit(client_for, open_job, upload):
    too_big = b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024)
    resp = apply(client_for("candidate"), open_job, upload, too_big)
    assert resp.status_code in (400, 413)
    assert Application.objects.count() == 0


def test_closed_job_does_not_accept_applications(client_for, make_job, upload, pdf_bytes):
    job = make_job(status=JobStatus.CLOSED, title="Closed Role")
    assert apply(client_for("candidate"), job, upload, pdf_bytes).status_code == 404


def test_application_notifies_candidate_and_recruiter(application, users):
    assert Notification.objects.filter(user=users["candidate"], kind="application_received").count() == 1
    assert Notification.objects.filter(user=users["recruiter"], kind="new_application").count() == 1
    assert EmailOutbox.objects.filter(to_email=users["candidate"].email).count() == 1


def test_candidates_only_see_their_own_applications(client_for, application, make_user, open_job, pdf_bytes):
    from rest_framework.test import APIClient

    from applications.services import apply_to_job

    other = make_user("candidate")
    theirs = apply_to_job(candidate=other, job=open_job, filename="x.pdf", data=pdf_bytes)
    mine = client_for("candidate")
    listed = {a["id"] for a in mine.get("/api/applications").data["results"]}
    assert listed == {str(application.id)}
    assert mine.get(f"/api/applications/{theirs.id}").status_code == 404
    assert mine.get(f"/api/applications/{theirs.id}/resume").status_code == 404
    assert mine.post(f"/api/applications/{theirs.id}/withdraw").status_code == 404
    other_client = APIClient()
    other_client.force_authenticate(other)
    assert {a["id"] for a in other_client.get("/api/applications").data["results"]} == {str(theirs.id)}


def test_candidate_detail_hides_resume_text(client_for, application):
    data = client_for("candidate").get(f"/api/applications/{application.id}").data
    assert "resume_text" not in data and data["events"][0]["to_status"] == "applied"


def test_recruiter_sees_applications_for_own_jobs_only(client_for, application, make_user, make_job):
    client = client_for("recruiter")
    resp = client.get(f"/api/jobs/{application.job_id}/applications")
    assert resp.status_code == 200
    assert [a["id"] for a in resp.data["results"]] == [str(application.id)]
    foreign = make_job(owner=make_user("recruiter"), title="Foreign Job")
    assert client.get(f"/api/jobs/{foreign.id}/applications").status_code == 404


def test_staff_detail_and_resume_download_are_audited(client_for, application, pdf_bytes):
    # Blind screening hides the original file; this test covers a job with blind mode off.
    application.job.blind_screening = False
    application.job.save()
    client = client_for("hiring_manager")
    detail = client.get(f"/api/applications/{application.id}")
    assert detail.status_code == 200 and "Django" in detail.data["resume_text"]
    download = client.get(f"/api/applications/{application.id}/resume")
    assert download.status_code == 200
    assert download.content == pdf_bytes
    assert download["Content-Type"] == "application/pdf"
    assert download["Content-Disposition"].startswith("attachment;")
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"applications.view", "applications.resume_download"} <= actions


def test_status_change_rules_and_notification(client_for, application, users):
    client = client_for("recruiter")
    url = f"/api/applications/{application.id}/status"
    assert client.post(url, {"status": "offer"}, format="json").status_code == 400  # skips steps
    assert client.post(url, {"status": "hired"}, format="json").status_code == 400  # week 3
    moved = client.post(url, {"status": "screening"}, format="json")
    assert moved.status_code == 200 and moved.data["status"] == "screening"
    note = Notification.objects.filter(user=users["candidate"], kind="application_status").get()
    assert "Under review" in note.title  # customer-safe stage words since week 2
    assert client_for("hiring_manager").post(url, {"status": "interview"}, format="json").status_code == 403


def test_withdraw(client_for, application):
    client = client_for("candidate")
    url = f"/api/applications/{application.id}/withdraw"
    resp = client.post(url)
    assert resp.status_code == 200 and resp.data["status"] == "withdrawn"
    assert client.post(url).status_code == 400
    staff = client_for("recruiter")
    moved = staff.post(f"/api/applications/{application.id}/status", {"status": "screening"}, format="json")
    assert moved.status_code == 400


def test_dashboard_summary_counts(client_for, application):
    data = client_for("candidate").get("/api/dashboard/summary").data
    assert data["applications_total"] == 1 and data["applications_by_status"] == {"applied": 1}
    staff = client_for("recruiter").get("/api/dashboard/summary").data
    assert staff["applications_total"] == 1 and staff["jobs_by_status"] == {"open": 1}
