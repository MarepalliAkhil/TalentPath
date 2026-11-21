import itertools

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from accounts.services import create_user
from applications.services import apply_to_job
from jobs.models import Job, JobStatus
from jobs.services import unique_job_slug
from org.models import Department, JobLevel, Location, Skill
from seeding.docgen import make_docx, make_pdf

PASSWORD = "Correct-Horse-42!"
ROLES = [r.value for r in Role]
PRINCIPALS = [*ROLES, "anonymous"]
RESUME_LINES = [
    "Test Candidate",
    "Backend Engineer | Hyderabad",
    "SKILLS",
    "Python, Django, PostgreSQL",
    "Synthetic resume for tests.",
]
_DEFAULT = object()


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user(db):
    counter = itertools.count()

    def _make(role=Role.CANDIDATE, email=None, password=PASSWORD, name=None):
        n = next(counter)
        return create_user(
            email=email or f"{role}{n}@test.example",
            full_name=name or f"Test {role} {n}",
            role=role,
            password=password,
        )

    return _make


@pytest.fixture
def users(make_user):
    return {role: make_user(role) for role in ROLES}


@pytest.fixture
def client_for(users):
    def _client(principal):
        client = APIClient()
        if principal != "anonymous":
            client.force_authenticate(users[principal])
        return client

    return _client


@pytest.fixture
def org(db):
    return {
        "department": Department.objects.create(name="Engineering"),
        "department2": Department.objects.create(name="Sales"),
        "location": Location.objects.create(name="Hyderabad"),
        "location2": Location.objects.create(name="Remote (India)"),
        "level": JobLevel.objects.create(name="Senior", rank=40),
    }


@pytest.fixture
def skills(db):
    slugs = ["python", "django", "postgresql", "javascript", "react", "kubernetes"]
    return {slug: Skill.objects.get(slug=slug) for slug in slugs}


@pytest.fixture
def make_job(org, skills, users):
    def _make(
        *,
        owner=None,
        manager=_DEFAULT,
        status=JobStatus.OPEN,
        title="Backend Engineer",
        work_mode="hybrid",
        department=None,
        location=None,
        required=("python", "django"),
        nice=("postgresql",),
    ):
        location = location or org["location"]
        job = Job.objects.create(
            slug=unique_job_slug(title, location.name),
            title=title,
            department=department or org["department"],
            location=location,
            level=org["level"],
            work_mode=work_mode,
            description="Build and run the services behind our hiring platform. " * 3,
            openings=2,
            status=status,
            created_by=owner or users["recruiter"],
            hiring_manager=users["hiring_manager"] if manager is _DEFAULT else manager,
            published_at=None if status == JobStatus.DRAFT else timezone.now(),
        )
        job.required_skills.set([skills[s] for s in required])
        job.nice_to_have_skills.set([skills[s] for s in nice])
        return job

    return _make


@pytest.fixture
def pdf_bytes():
    return make_pdf(RESUME_LINES)


@pytest.fixture
def docx_bytes():
    return make_docx(RESUME_LINES)


@pytest.fixture
def upload():
    def _upload(data, name="resume.pdf", content_type="application/pdf"):
        return SimpleUploadedFile(name, data, content_type=content_type)

    return _upload


@pytest.fixture
def open_job(make_job):
    return make_job()


@pytest.fixture
def application(users, open_job, pdf_bytes):
    return apply_to_job(candidate=users["candidate"], job=open_job, filename="cv.pdf", data=pdf_bytes)
