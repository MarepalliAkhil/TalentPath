import re

import pytest

from jobs.models import Job, JobStatus


@pytest.fixture
def payload(org, skills, users):
    return {
        "title": "  Senior   Data Engineer ",
        "department": str(org["department"].id),
        "location": str(org["location"].id),
        "level": str(org["level"].id),
        "work_mode": "hybrid",
        "employment_type": "full_time",
        "description": "Design reliable pipelines that power hiring analytics for our customers.",
        "required_skills": [str(skills["python"].id), str(skills["postgresql"].id)],
        "nice_to_have_skills": [str(skills["kubernetes"].id)],
        "openings": 2,
        "hiring_manager": str(users["hiring_manager"].id),
    }


def test_recruiter_creates_draft_job_with_clean_slug(client_for, payload, users):
    resp = client_for("recruiter").post("/api/jobs", payload, format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == "draft"
    assert resp.data["title"] == "Senior Data Engineer"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", resp.data["slug"])
    assert resp.data["slug"] == "senior-data-engineer-hyderabad"
    assert Job.objects.get(pk=resp.data["id"]).created_by == users["recruiter"]


def test_job_validation_rules(client_for, payload, skills, users):
    client = client_for("recruiter")
    overlap = {**payload, "nice_to_have_skills": [str(skills["python"].id)]}
    assert client.post("/api/jobs", overlap, format="json").status_code == 400
    wrong_manager = {**payload, "hiring_manager": str(users["recruiter"].id)}
    assert client.post("/api/jobs", wrong_manager, format="json").status_code == 400
    short = {**payload, "description": "Too short"}
    assert client.post("/api/jobs", short, format="json").status_code == 400
    zero = {**payload, "openings": 0}
    assert client.post("/api/jobs", zero, format="json").status_code == 400


def test_status_transitions(client_for, make_job, users):
    client = client_for("recruiter")
    job = make_job(status=JobStatus.DRAFT, manager=None)
    url = f"/api/jobs/{job.id}/status"
    blocked = client.post(url, {"status": "open"}, format="json")
    assert blocked.status_code == 400  # needs a hiring manager first
    assert client.post(url, {"status": "closed"}, format="json").status_code == 400  # draft -> closed
    job.hiring_manager = users["hiring_manager"]
    job.save()
    opened = client.post(url, {"status": "open"}, format="json")
    assert opened.status_code == 200 and opened.data["published_at"]
    assert client.post(url, {"status": "draft"}, format="json").status_code == 400
    assert client.post(url, {"status": "closed"}, format="json").status_code == 200
    assert client.patch(f"/api/jobs/{job.id}", {"openings": 3}, format="json").status_code == 400
    assert client.post(url, {"status": "open"}, format="json").status_code == 200  # reopen


def test_open_requires_a_required_skill(client_for, make_job):
    job = make_job(status=JobStatus.DRAFT, required=(), nice=())
    resp = client_for("recruiter").post(f"/api/jobs/{job.id}/status", {"status": "open"}, format="json")
    assert resp.status_code == 400


def test_recruiters_only_see_and_edit_their_own_jobs(client_for, make_job, make_user):
    other = make_user("recruiter")
    theirs = make_job(owner=other, title="Other Team Job")
    client = client_for("recruiter")
    assert client.get(f"/api/jobs/{theirs.id}").status_code == 404
    assert client.patch(f"/api/jobs/{theirs.id}", {"openings": 4}, format="json").status_code == 404
    assert (
        client.post(f"/api/jobs/{theirs.id}/status", {"status": "closed"}, format="json").status_code == 404
    )
    listed = {j["id"] for j in client.get("/api/jobs").data["results"]}
    assert str(theirs.id) not in listed


def test_hiring_manager_sees_assigned_published_jobs_only(client_for, make_job, make_user):
    assigned = make_job(title="Assigned Job")
    draft = make_job(title="Draft Job", status=JobStatus.DRAFT)
    other = make_job(title="Not Mine", manager=make_user("hiring_manager"))
    listed = {j["id"] for j in client_for("hiring_manager").get("/api/jobs").data["results"]}
    assert str(assigned.id) in listed
    assert str(draft.id) not in listed and str(other.id) not in listed


def test_hr_admin_sees_and_manages_all_jobs(client_for, make_job, make_user):
    job = make_job(owner=make_user("recruiter"))
    client = client_for("hr_admin")
    assert client.get(f"/api/jobs/{job.id}").status_code == 200
    assert client.patch(f"/api/jobs/{job.id}", {"openings": 5}, format="json").data["openings"] == 5


def test_delete_rules(client_for, make_job):
    client = client_for("recruiter")
    live = make_job()
    assert client.delete(f"/api/jobs/{live.id}").status_code == 409
    draft = make_job(status=JobStatus.DRAFT, title="Scratch")
    assert client.delete(f"/api/jobs/{draft.id}").status_code == 204
    assert not Job.objects.filter(pk=draft.pk).exists()


def test_patch_updates_skills(client_for, make_job, skills):
    job = make_job()
    resp = client_for("recruiter").patch(
        f"/api/jobs/{job.id}", {"required_skills": [str(skills["react"].id)]}, format="json"
    )
    assert resp.status_code == 200
    assert [s["name"] for s in resp.data["required_skills"]] == ["React"]


def test_hr_admin_can_create_jobs_and_recruiters_stay_scoped(client_for, payload, users):
    created = client_for("hr_admin").post("/api/jobs", payload, format="json")
    assert created.status_code == 201
    job_id = created.data["id"]
    assert client_for("recruiter").get(f"/api/jobs/{job_id}").status_code == 404  # not the recruiter's job
    assert client_for("hr_admin").get(f"/api/jobs/{job_id}").status_code == 200


def test_blind_settings_are_editable(client_for, payload):
    created = client_for("recruiter").post(
        "/api/jobs", {**payload, "blind_screening": False, "reveal_stage": "offer"}, format="json"
    )
    assert created.status_code == 201
    assert created.data["blind_screening"] is False and created.data["reveal_stage"] == "offer"
    default = client_for("recruiter").post("/api/jobs", {**payload, "title": "Second Role"}, format="json")
    assert default.data["blind_screening"] is True and default.data["reveal_stage"] == "interview"
