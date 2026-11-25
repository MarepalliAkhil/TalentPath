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


def application_form(answers=None, **sections):
    """A valid application form (D-83) for API tests; override any section."""
    import json
    from datetime import date, timedelta

    form = {
        "personal": {
            "phone": "+91 90000 12345",
            "current_city": "Hyderabad",
            "willing_to_relocate": True,
            "date_of_birth": "1999-04-12",
        },
        "education": {
            "highest_qualification": "Bachelor's degree",
            "college": "Lakeview University",
            "branch": "Computer Science",
            "graduation_year": 2021,
            "score_type": "cgpa",
            "score": "8.4",
            "tenth_percentage": "91",
            "twelfth_percentage": "88.5",
        },
        "experience": {"status": "fresher", "roles": [], "total_years": "0"},
        "compensation": {
            "current_ctc_lpa": "0",
            "expected_ctc_lpa": "6.5",
            "notice_period": "immediate",
            "earliest_joining": (date.today() + timedelta(days=20)).isoformat(),
        },
        "links": {"github_url": "github.com/test-candidate"},
        "answers": answers or {},
        "cover_letter": "",
        "declarations": {"info_true": True, "accept_terms": True},
    }
    form.update(sections)
    return json.dumps(form)


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
            hiring_manager=users["manager"] if manager is _DEFAULT else manager,
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


# ----------------------------------------------------------------- week 3A helpers
@pytest.fixture
def interviewers(make_user, skills):
    """Four employee interviewers tagged with Python and Django, default hours (Mon-Fri 10-18 IST)."""
    from interviews.models import InterviewerProfile

    people = []
    for n in range(4):
        user = make_user(Role.EMPLOYEE, name=f"Interviewer {n}")
        profile = InterviewerProfile.objects.create(user=user)
        profile.skills.set([skills["python"], skills["django"]])
        people.append(user)
    return people


@pytest.fixture
def plan_job(make_job, interviewers):
    """An open job with a two-round plan: Technical (1 interviewer) and Panel (2)."""
    from interviews.models import InterviewPlan, InterviewRound

    job = make_job(title="Platform Engineer")
    plan = InterviewPlan.objects.create(job=job)
    tech = InterviewRound.objects.create(
        plan=plan, order=1, name="Technical", duration_minutes=60, interviewers_needed=1
    )
    tech.pool.set(interviewers)
    panel = InterviewRound.objects.create(
        plan=plan, order=2, name="Panel", duration_minutes=60, interviewers_needed=2
    )
    panel.pool.set(interviewers)
    return job


@pytest.fixture
def to_interview(users):
    """Move an application Applied -> Screening -> Interview (HIRA proposes slots on arrival)."""
    from applications.services import move_application

    def _move(application, actor=None):
        actor = actor or application.job.created_by
        move_application(application, "screening", actor, silent=True)
        move_application(application, "interview", actor)
        application.refresh_from_db()
        return application

    return _move


@pytest.fixture
def apply_as(pdf_bytes):
    def _apply(candidate, job):
        return apply_to_job(candidate=candidate, job=job, filename="cv.pdf", data=pdf_bytes, silent=True)

    return _apply


@pytest.fixture
def run_round():
    """Create a finished interview for `round_` with `people`, each submitting a scorecard."""
    from datetime import timedelta

    from interviews import scorecards
    from interviews.models import Interview, InterviewAssignment, InterviewStatus

    def _run(application, round_, people, recommendation="yes", rating=4, submit=True, hours_ago=2):
        start = timezone.now() - timedelta(hours=hours_ago)
        interview = Interview.objects.create(
            application=application,
            round=round_,
            status=InterviewStatus.COMPLETED,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            scorecard_due_at=start + timedelta(hours=25),
            completed_at=start + timedelta(hours=1),
        )
        for person in people:
            InterviewAssignment.objects.create(interview=interview, interviewer=person)
        if submit:
            keys = [c["key"] for c in scorecards.template(application.job)]
            for person in people:
                comments = {k: "Clear evidence in the exercise." for k in keys} if rating in (1, 2, 5) else {}
                scorecards.submit(
                    interview,
                    person,
                    ratings={k: rating for k in keys},
                    comments=comments,
                    recommendation=recommendation,
                )
        return interview

    return _run


# ----------------------------------------------------------------- week 3B helpers
@pytest.fixture
def hr_locations(org):
    """Default leave types and work policy (09:30-18:30, Sat/Sun off) for both test locations."""
    from hr.defaults import ensure_location_defaults

    ensure_location_defaults(org["location"])
    ensure_location_defaults(org["location2"])
    return org


@pytest.fixture
def make_employee(hr_locations, make_user):
    from datetime import date

    from hr.models import Employee
    from hr.onboarding import next_code

    def _make(
        user=None,
        *,
        manager=None,
        joined=date(2024, 1, 15),
        department=None,
        location=None,
        designation="Engineer",
        role=Role.EMPLOYEE,
        name=None,
    ):
        user = user or make_user(role, name=name)
        return Employee.objects.create(
            user=user,
            code=next_code(),
            designation=designation,
            department=department or hr_locations["department"],
            location=location or hr_locations["location"],
            manager=manager,
            joined_on=joined,
        )

    return _make


@pytest.fixture
def team(users, make_employee):
    """Hiring manager -> four reports (the employee user is one of them); hr reports to nobody.

    The reporting line, not the role, decides approvals: `lead` is an employee-role user who manages `junior`.
    """
    boss = make_employee(users["manager"], designation="Head of Engineering")
    me = make_employee(users["employee"], manager=boss)
    peers = [make_employee(manager=boss, name=f"Peer {n}") for n in range(3)]
    lead = peers[0]
    junior = make_employee(manager=lead, name="Junior")
    hr = make_employee(users["hr"], designation="HR Manager")
    recruiter = make_employee(users["recruiter"], manager=hr, designation="Recruiter")
    return {
        "boss": boss,
        "me": me,
        "peers": peers,
        "lead": lead,
        "junior": junior,
        "hr": hr,
        "recruiter": recruiter,
    }
