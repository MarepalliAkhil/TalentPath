"""Week 4A demo data: job audiences (internal, external, both), application sources, employee
levels, profile resumes for a few employees, internal applications in progress and one past
internal move. Everything is fictional and idempotent (safe to run twice).
"""

import hashlib
from datetime import timedelta

from django.utils import timezone

from accounts.models import Role, User
from applications.models import Application
from applications.models import ApplicationStatus as S
from applications.services import move_application
from core.brand import get_brand
from growth.models import CareerProfile
from growth.services import apply_internally, save_profile_resume
from hr.models import Employee, InternalMove
from interviews.models import InterviewPlan
from interviews.timeutil import today_ist
from jobs.models import Audience, Job, JobStatus
from jobs.services import unique_job_slug
from org.models import Department, JobLevel, Location, Skill
from seeding import demo_data as D
from seeding.docgen import make_pdf

# title, department, location, level, required, nice, summary
INTERNAL_JOBS = [
    (
        "Engineering Manager, Platform Services",
        "Engineering",
        "Hyderabad",
        "Manager",
        ["System Design", "Microservices", "Kubernetes", "Mentoring", "Leadership"],
        ["Stakeholder Management", "AWS"],
        "Lead the team that runs our shared platform services. Internal applicants only.",
    ),
    (
        "Staff Backend Engineer (internal transfer)",
        "Engineering",
        "Hyderabad",
        "Lead",
        ["Python", "Django", "PostgreSQL", "System Design", "Kubernetes"],
        ["Apache Kafka", "Mentoring"],
        "Shape the architecture of the hiring platform. Open to current employees only.",
    ),
    (
        "Analytics Engineer",
        "Data & AI",
        "Bengaluru",
        "Mid-level",
        ["SQL", "dbt", "Python", "Data Visualization"],
        ["Snowflake", "Apache Airflow"],
        "Turn raw product data into trusted models and dashboards. Internal applicants only.",
    ),
]
EXTERNAL_ONLY = ["Software Engineering Intern", "Inside Sales Representative", "HR Operations Specialist"]

# Profile resumes (synthetic) for employees who use the career map and internal mobility.
PROFILES = {
    "employee@demo.example": [
        "SKILLS",
        "Python, Django, PostgreSQL, REST API Design, Docker, Git, Linux, Agile, Mentoring, Leadership",
        "EXPERIENCE",
        "Engineering Lead, Lumina Works (fictional), 2022 - Present",
        "Lead a team of five building Django services on PostgreSQL; mentored two engineers.",
        "Backend Engineer, Northwind Labs (fictional), 2019 - 2022",
        "Built REST APIs in Python and Docker-based deployments.",
    ],
    "rahul.verma@demo.example": [
        "SKILLS",
        "Python, Django, PostgreSQL, Redis, Docker, Git, Linux",
        "EXPERIENCE",
        "Backend Engineer, Lumina Works (fictional), 2024 - Present",
        "Built Django and PostgreSQL services for job search; added Redis caching.",
        "PROJECTS",
        "Event pipeline prototype with Docker on Linux.",
    ],
    "ritika.bose@demo.example": [
        "SKILLS",
        "SQL, Python, Excel, Data Analysis, Data Visualization, Power BI",
        "EXPERIENCE",
        "Data Analyst, Lumina Works (fictional), 2025 - Present",
        "Built Power BI dashboards on SQL models; Python notebooks for data analysis.",
    ],
}

# (email, internal job title, stage to move to)
INTERNAL_APPLICATIONS = [
    ("rahul.verma@demo.example", "Staff Backend Engineer (internal transfer)", S.SCREENING),
    ("ritika.bose@demo.example", "Analytics Engineer", S.INTERVIEW),
]


def level_for(designation: str) -> str:
    d = designation.lower()
    if d.startswith("head of"):
        return "Manager"
    if "lead" in d or "manager" in d:
        return "Lead"
    if "senior" in d:
        return "Senior"
    if "associate" in d or "intern" in d:
        return "Associate"
    return "Mid-level"


def source_for(email: str, slug: str) -> str:
    """Deterministic, roughly realistic mix: half career site, 30% job boards, 20% referrals."""
    bucket = int(hashlib.sha256(f"{email}|{slug}".encode()).hexdigest(), 16) % 10
    return "career_site" if bucket < 5 else "job_board" if bucket < 8 else "referral"


def seed_audiences(staff) -> int:
    Job.objects.filter(title__in=EXTERNAL_ONLY, created_by__email__endswith=D.DEMO_DOMAIN).update(
        audience=Audience.EXTERNAL
    )
    made = 0
    employer = get_brand()["employerName"]
    for title, dept, loc, level, required, nice, summary in INTERNAL_JOBS:
        location = Location.objects.get(name=loc)
        if Job.objects.filter(title=title, location=location).exists():
            continue
        department = Department.objects.get(name=dept)
        manager = staff[D.DEPARTMENT_MANAGER[dept]]
        job = Job.objects.create(
            slug=unique_job_slug(title, location.name),
            title=title,
            department=department,
            location=location,
            level=JobLevel.objects.get(name=level),
            work_mode="hybrid",
            description=(
                f"{summary}\n\nAbout the role\n{summary}\n\n{employer} is a fictional company in this demo."
            ),
            openings=1,
            status=JobStatus.OPEN,
            created_by=staff["recruiter"],
            hiring_manager=manager,
            audience=Audience.INTERNAL,
            published_at=timezone.now() - timedelta(days=12),
        )
        job.required_skills.set(Skill.objects.filter(name__in=required))
        job.nice_to_have_skills.set(Skill.objects.filter(name__in=nice))
        from interviews.coordinator import get_plan

        get_plan(job)
        made += 1
    return made


def seed_sources() -> int:
    changed = 0
    for app in Application.objects.filter(
        candidate__email__endswith=".example", source="career_site", candidate__role=Role.CANDIDATE
    ).select_related("candidate", "job"):
        source = source_for(app.candidate.email, app.job.slug)
        if source != "career_site":
            Application.objects.filter(pk=app.pk).update(source=source)
            changed += 1
    return changed


def seed_levels() -> int:
    levels = {lvl.name: lvl for lvl in JobLevel.objects.all()}
    changed = 0
    for emp in Employee.objects.filter(level__isnull=True, user__email__endswith=D.DEMO_DOMAIN):
        emp.level = levels.get(level_for(emp.designation))
        emp.save(update_fields=["level"])
        changed += 1
    return changed


def seed_profiles() -> int:
    made = 0
    for email, lines in PROFILES.items():
        user = User.objects.filter(email=email).first()
        if user is None or CareerProfile.objects.filter(user=user).exists():
            continue
        name = user.full_name
        save_profile_resume(user, f"{name.lower().replace(' ', '-')}-resume.pdf", make_pdf([name, *lines]))
        made += 1
    return made


def seed_internal_applications() -> int:
    made = 0
    for email, title, stage in INTERNAL_APPLICATIONS:
        user = User.objects.filter(email=email).first()
        job = Job.objects.filter(title=title).first()
        if user is None or job is None or Application.objects.filter(candidate=user, job=job).exists():
            continue
        InterviewPlan.objects.filter(job=job).update(hira_enabled=True)
        application = apply_internally(user, job.id)
        recruiter = job.created_by
        move_application(application, S.SCREENING, recruiter, silent=True)
        if stage == S.INTERVIEW:
            move_application(application, S.INTERVIEW, recruiter, silent=True)
        made += 1
    return made


def seed_past_move(today) -> int:
    emp = (
        Employee.objects.filter(user__email="varun.mehra@demo.example")
        .select_related("department", "manager__user")
        .first()
    )
    if emp is None or InternalMove.objects.filter(employee=emp).exists():
        return 0
    InternalMove.objects.create(
        employee=emp,
        from_department="Data & AI",
        to_department=emp.department.name,
        from_designation="Data Platform Engineer",
        to_designation=emp.designation,
        from_manager=getattr(Employee.objects.filter(designation="Head of Data & AI").first(), "name", ""),
        to_manager=emp.manager.name if emp.manager else "",
        moved_on=today - timedelta(days=75),
    )
    return 1


def seed_growth(staff) -> dict:
    today = today_ist(timezone.now())
    return {
        "internal_jobs": seed_audiences(staff),
        "sources": seed_sources(),
        "levels": seed_levels(),
        "profiles": seed_profiles(),
        "internal_applications": seed_internal_applications(),
        "past_moves": seed_past_move(today),
        "timeline": seed_timeline(timezone.now()),
        "scorecards_timed": seed_scorecard_times(timezone.now()),
    }


# ---------------------------------------------------------------- timeline (analytics need real gaps)
# Days between entering one stage and the next (min, max); picked per application from a hash.
STAGE_GAPS = {
    S.SCREENING: (1, 5),
    S.INTERVIEW: (2, 8),
    S.OFFER: (5, 12),
    S.HIRED: (2, 6),
    S.REJECTED: (1, 9),
    S.WITHDRAWN: (1, 10),
}


def _hash(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def seed_timeline(now) -> int:
    """The seed creates every application and stage change at once. Spread them back in time
    (deterministically, within each job's posting window) so stage times and time to hire mean
    something. Applications already in the past are left alone, so a second run changes nothing."""
    from applications.models import ApplicationEvent

    fresh = now - timedelta(minutes=30)
    moved = 0
    for app in Application.objects.filter(
        candidate__email__endswith=".example", created_at__gte=fresh
    ).select_related("job", "candidate"):
        events = list(ApplicationEvent.objects.filter(application=app).order_by("created_at"))
        h = _hash(f"{app.candidate.email}|{app.job.slug}")
        gaps = []
        for i, event in enumerate(e for e in events if e.to_status != S.APPLIED):
            lo, hi = STAGE_GAPS.get(event.to_status, (1, 5))
            gaps.append(lo + (h >> (8 * i)) % (hi - lo + 1) + ((h >> (8 * i + 4)) % 20) / 24)
        total = sum(gaps)
        published = app.job.published_at or now - timedelta(days=30)
        earliest = min(published, now - timedelta(days=2))
        window = max((now - timedelta(days=1) - earliest).total_seconds() / 86400, 1.0)
        scale = min(1.0, (window * 0.85) / total) if total else 1.0
        gaps = [g * scale for g in gaps]
        slack = max(window - sum(gaps), 0.0)
        start = earliest + timedelta(days=slack * ((h % 1000) / 1000))
        Application.objects.filter(pk=app.pk).update(created_at=start)
        t, k = start, 0
        for event in events:
            if event.to_status != S.APPLIED:
                t = t + timedelta(days=gaps[k])
                k += 1
            ApplicationEvent.objects.filter(pk=event.pk).update(
                created_at=t if event.to_status != S.APPLIED else start
            )
        moved += 1
    return moved


def seed_scorecard_times(now) -> int:
    """Scorecards are stamped at seed time; place them a few hours after their interview
    (about half within the 24-hour target) so timeliness figures are meaningful."""
    from interviews.models import Scorecard

    fixed = 0
    for card in Scorecard.objects.filter(submitted_at__gte=now - timedelta(minutes=30)).select_related(
        "interview", "interviewer"
    ):
        ends = card.interview.ends_at
        if ends is None or ends >= now:
            continue
        hours = 2 + _hash(f"{card.interview_id}|{card.interviewer.email}") % 44
        Scorecard.objects.filter(pk=card.pk).update(submitted_at=min(ends + timedelta(hours=hours), now))
        fixed += 1
    return fixed
