"""Skill-gap career map: prerequisites, curated links only, the same score as the recruiter
view, profile resume limits and deletion, and what candidates and employees may see."""

import json

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from applications.services import apply_to_job
from core.models import AuditLog
from files.models import StoredFile
from growth import graph
from growth.models import CareerProfile
from jobs.models import Audience
from org.models import JobLevel, Skill
from org.taxonomy_data import SKILLS, skill_slug
from seeding.docgen import make_pdf

RESUME = [
    "Asha Verma",
    "SKILLS",
    "Python, Django, Git",
    "EXPERIENCE",
    "Backend Engineer, Example Labs (fictional), 2021 - 2025",
    "Built Django services in Python.",
]


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def upload(client, lines=RESUME, name="cv.pdf"):
    data = make_pdf(lines)
    return client.post(
        "/api/career/profile",
        {"resume": SimpleUploadedFile(name, data, "application/pdf")},
        format="multipart",
    )


# ---------------------------------------------------------------- the data files
def test_graph_and_links_only_use_known_skills():
    known = {skill_slug(s[0]) for s in SKILLS}
    g = graph.skill_graph()
    for slug, node in g.items():
        assert slug in known
        assert node["effort"] in ("small", "medium", "large")
        assert set(node["prerequisites"]) <= known and set(node["related"]) <= known
    with open(settings.LEARNING_LINKS_PATH, encoding="utf-8") as fh:
        links = json.load(fh)["links"]
    for slug, entry in links.items():
        assert slug in known
        assert entry["url"].startswith("https://")


def test_graph_has_no_cycles():
    g = graph.skill_graph()

    def reach(start, seen=()):
        for pre in g.get(start, {}).get("prerequisites", []):
            assert pre != start and pre not in seen, f"cycle through {pre}"
            reach(pre, seen + (start,))

    for slug in g:
        reach(slug)


def test_learning_path_respects_prerequisites():
    path = graph.learning_path(["kubernetes", "django"], have=set(), priority={"kubernetes": 0, "django": 1})
    order = [step["slug"] for step in path]
    assert order.index("linux") < order.index("docker") < order.index("kubernetes")
    assert order.index("python") < order.index("django")
    for i, step in enumerate(path):
        for pre in graph.prerequisites(step["slug"]):
            if pre in order:
                assert order.index(pre) < i


def test_learning_path_skips_what_you_have():
    order = [s["slug"] for s in graph.learning_path(["kubernetes"], have={"linux", "docker"})]
    assert order == ["kubernetes"]


def test_only_curated_links_appear():
    with open(settings.LEARNING_LINKS_PATH, encoding="utf-8") as fh:
        curated = {slug: e["url"] for slug, e in json.load(fh)["links"].items()}
    path = graph.learning_path(["kubernetes", "stakeholder-management", "system-design"], have=set())
    for step in path:
        if step["slug"] in curated:
            assert step["link"]["url"] == curated[step["slug"]]
        else:
            assert step["link"] is None  # text only, never an invented URL


# ---------------------------------------------------------------- same scorer as recruiters
@pytest.mark.django_db
def test_map_uses_the_same_score_as_the_recruiter_view(users, open_job):
    client = as_user(users["candidate"])
    data = make_pdf(RESUME)
    assert upload(client).status_code == 201
    application = apply_to_job(
        candidate=users["candidate"], job=open_job, filename="cv.pdf", data=data, silent=True
    )
    recruiter_view = as_user(users["recruiter"]).get(f"/api/applications/{application.id}").data
    mine = client.get(f"/api/career/map/{open_job.id}").data
    assert mine["job"]["score"] == application.fit_score.score == recruiter_view["fit"]["score"]
    assert mine["job"]["band"] == application.fit_score.band
    listed = {j["id"]: j["score"] for j in client.get("/api/career/map").data["jobs"]}
    assert listed[str(open_job.id)] == application.fit_score.score


@pytest.mark.django_db
def test_job_map_lists_have_missing_and_a_path(users, make_job):
    job = make_job(title="Platform Engineer", required=("python", "kubernetes"), nice=("postgresql",))
    client = as_user(users["candidate"])
    upload(client)
    data = client.get(f"/api/career/map/{job.id}").data
    assert [s["slug"] for s in data["have"]] == ["python"]
    assert data["have"][0]["evidence"]  # the resume line that shows it
    assert [s["slug"] for s in data["missing_required"]] == ["kubernetes"]
    assert [s["slug"] for s in data["missing_nice"]] == ["postgresql"]
    order = [s["slug"] for s in data["path"]]
    assert order.index("linux") < order.index("docker") < order.index("kubernetes")
    kinds = {s["slug"]: s["kind"] for s in data["path"]}
    assert (
        kinds["kubernetes"] == "required"
        and kinds["docker"] == "prerequisite"
        and kinds["postgresql"] == "nice"
    )


@pytest.mark.django_db
def test_without_a_resume_the_map_is_empty_not_invented(users, open_job):
    data = as_user(users["candidate"]).get("/api/career/map").data
    assert data == {"source": "none", "jobs": []}


# ---------------------------------------------------------------- profile resume
@pytest.mark.django_db
def test_profile_resume_is_parsed_encrypted_and_deletable(users):
    from django.db import connection

    client = as_user(users["candidate"])
    response = upload(client)
    assert response.status_code == 201 and response.data["has_resume"] is True
    assert "Python" in response.data["skills"]
    profile = CareerProfile.objects.get(user=users["candidate"])
    with connection.cursor() as cur:
        cur.execute(
            "SELECT resume_text, evidence FROM growth_careerprofile WHERE id = %s",
            [profile.id.hex if connection.vendor == "sqlite" else profile.id],
        )
        text, evidence = cur.fetchone()
    assert text.startswith("v1:") and evidence.startswith("v1:")
    assert "Django" not in text and "Django" not in evidence  # stored encrypted
    file_id = profile.resume_file_id
    assert client.delete("/api/career/profile").status_code == 204
    assert not CareerProfile.objects.filter(user=users["candidate"]).exists()
    assert not StoredFile.objects.filter(pk=file_id).exists()
    assert client.get("/api/career/profile").data["has_resume"] is False
    assert AuditLog.objects.filter(action="career.resume_deleted").exists()


@pytest.mark.django_db
def test_replacing_the_resume_keeps_the_old_version_in_history(users):
    """Prompt 1 (D-82): a new resume replaces the current one; the old version is kept until
    the person deletes their resume, which removes every version."""
    from growth.models import ResumeVersion

    client = as_user(users["candidate"])
    upload(client)
    first = CareerProfile.objects.get(user=users["candidate"]).resume_file_id
    upload(client, RESUME + ["PROJECTS", "React dashboard."])
    current = CareerProfile.objects.get(user=users["candidate"]).resume_file_id
    assert current != first and StoredFile.objects.filter(pk=first).exists()
    versions = ResumeVersion.objects.filter(user=users["candidate"])
    assert versions.count() == 2 and versions.get(is_current=True).file_id == current
    assert client.delete("/api/career/profile").status_code == 204
    assert not ResumeVersion.objects.filter(user=users["candidate"]).exists()
    assert not StoredFile.objects.filter(owner=users["candidate"]).exists()


@pytest.mark.django_db
def test_profile_resume_limits(users):
    client = as_user(users["candidate"])
    fake = SimpleUploadedFile("cv.pdf", b"not a resume", "application/pdf")
    assert client.post("/api/career/profile", {"resume": fake}, format="multipart").status_code == 400
    big = SimpleUploadedFile("cv.pdf", b"%PDF-1.4" + b"0" * (5 * 1024 * 1024 + 10), "application/pdf")
    assert client.post("/api/career/profile", {"resume": big}, format="multipart").status_code in (400, 413)
    assert client.post("/api/career/profile", {}, format="multipart").status_code == 400


@pytest.mark.django_db
def test_people_only_see_their_own_profile(users):
    upload(as_user(users["candidate"]))
    other = as_user(users["employee"]).get("/api/career/profile").data
    assert other["has_resume"] is False and other["skills"] == []


# ---------------------------------------------------------------- what each person may see
@pytest.mark.django_db
def test_candidates_never_see_internal_jobs(users, make_job):
    internal = make_job(title="Internal Platform Lead")
    internal.audience = Audience.INTERNAL
    internal.save()
    client = as_user(users["candidate"])
    upload(client)
    assert client.get(f"/api/career/map/{internal.id}").status_code == 404
    assert str(internal.id) not in {j["id"] for j in client.get("/api/career/map").data["jobs"]}
    assert APIClient().get(f"/api/public/jobs/{internal.slug}").status_code == 404
    slugs = {j["slug"] for j in APIClient().get("/api/public/jobs").data["results"]}
    assert internal.slug not in slugs


@pytest.mark.django_db
def test_employees_do_not_see_external_only_jobs(team, make_job):
    external = make_job(title="Campus Intern")
    external.audience = Audience.EXTERNAL
    external.save()
    client = as_user(team["me"].user)
    upload(client)
    assert client.get(f"/api/career/map/{external.id}").status_code == 404


@pytest.mark.django_db
def test_next_role_shows_higher_levels_in_my_department(team, make_job, org):
    me = team["me"]
    me.level = JobLevel.objects.get(name="Senior")
    me.save()
    lead = JobLevel.objects.create(name="Lead", rank=50)
    job = make_job(title="Lead Backend Engineer", required=("python", "kubernetes"))
    job.level = lead
    job.save()
    other_dept = make_job(title="Sales Lead", department=org["department2"], required=("python",))
    other_dept.level = lead
    other_dept.save()
    client = as_user(me.user)
    upload(client)
    data = client.get("/api/career/next-role").data
    assert data["current_level"] == "Senior"
    level = data["levels"][0]
    assert level["level"] == "Lead" and level["titles"] == ["Lead Backend Engineer"]
    assert [m["slug"] for m in level["missing"]] == ["kubernetes"]
    assert [s["slug"] for s in level["path"]][-1] == "kubernetes"


@pytest.mark.django_db
def test_next_role_needs_an_employee_record(users):
    assert as_user(users["employee"]).get("/api/career/next-role").status_code == 404


def test_skill_names_in_graph_exist_in_db_migration(db):
    assert Skill.objects.filter(slug="kubernetes").exists() and Skill.objects.filter(slug="docker").exists()
