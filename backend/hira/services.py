"""Ask HIRA answers. Personal intents only ever read the signed-in candidate's own data."""

from django.db.models import Q

from accounts.models import Role
from applications.models import Application
from applications.models import ApplicationStatus as S
from applications.services import CANDIDATE_STATUS_WORDS
from core.brand import get_brand
from jobs.models import Job
from jobs.serializers import public_job_dict
from matching.services import get_matcher, profile_skill_slugs
from org.models import Location

from .engine import Context, Understanding, understand
from .models import KnowledgeEntry

LOCATION_ALIASES = {"bangalore": "bengaluru", "remote india": "remote-india", "wfh": "remote-india"}
ACTIVE = {S.APPLIED, S.SCREENING, S.INTERVIEW, S.OFFER}

PUBLIC_CHIPS = [
    "Find React jobs in Hyderabad",
    "Remote jobs",
    "How does matching work?",
    "Is the screening fair?",
    "What is the interview process?",
]
CANDIDATE_CHIPS = [
    "What is my application status?",
    "Jobs that match my skills",
    "Find React jobs in Hyderabad",
    "Is the screening fair?",
    "Talk to a recruiter",
]


def build_context() -> Context:
    locations = {}
    for loc in Location.objects.all():
        locations[loc.name.lower()] = loc.slug
        locations[loc.slug.replace("-", " ")] = loc.slug
    for alias, slug in LOCATION_ALIASES.items():
        if slug in locations.values():
            locations[alias] = slug
    knowledge = list(
        KnowledgeEntry.objects.filter(active=True).values("key", "question", "keywords", "answer", "link")
    )
    return Context(skill_matcher=get_matcher(), locations=locations, knowledge=knowledge)


def _is_candidate(user) -> bool:
    return bool(user and user.is_authenticated and user.role == Role.CANDIDATE)


def _reply(u: Understanding, answer: str, user, **extra) -> dict:
    chips = CANDIDATE_CHIPS if _is_candidate(user) else PUBLIC_CHIPS
    data = {
        "intent": u.intent,
        "answer": answer,
        "chips": chips,
        "jobs": [],
        "applications": [],
        "action": None,
        "link": None,
        "needs_sign_in": False,
    }
    data.update(extra)
    return data


def _sign_in(u: Understanding, user, what: str) -> dict:
    if user and user.is_authenticated:
        return _reply(
            u,
            "Ask HIRA answers personal questions for candidate accounts only. "
            "Staff can find this on their dashboards.",
            user,
        )
    return _reply(u, f"Please sign in as a candidate to {what}.", user, needs_sign_in=True, link="/login")


def _search_jobs(u: Understanding, limit: int = 5):
    qs = (
        Job.objects.public()
        .select_related("department", "location", "level")
        .prefetch_related("required_skills", "nice_to_have_skills")
    )
    if u.skills:
        slugs = [slug for slug, _ in u.skills]
        qs = qs.filter(Q(required_skills__slug__in=slugs) | Q(nice_to_have_skills__slug__in=slugs)).distinct()
    if u.location:
        qs = qs.filter(location__slug=u.location)
    if u.work_mode:
        qs = qs.filter(work_mode=u.work_mode)
    jobs = list(qs.order_by("-published_at")[:limit])
    return jobs, qs.count()


def _describe_filters(u: Understanding, ctx: Context) -> str:
    parts = []
    if u.skills:
        parts.append(" / ".join(name for _, name in u.skills))
    if u.work_mode:
        parts.append(u.work_mode.replace("onsite", "on-site"))
    if u.location:
        label = next((name.title() for name, slug in ctx.locations.items() if slug == u.location), u.location)
        parts.append(f"in {label}")
    return " ".join(parts)


def answer(message: str, user, ctx: Context | None = None) -> dict:
    staff = bool(user and user.is_authenticated and user.role != Role.CANDIDATE)
    if staff:
        from hr import assistant as hr_assistant

        hr_reply = hr_assistant.answer(message, user)
        if hr_reply is not None:
            return hr_reply
    ctx = ctx or build_context()
    u = understand(message, ctx)
    candidate_only = (
        "fallback",
        "greeting",
        "application_status",
        "matching_jobs",
        "talk_to_recruiter",
        "how_withdraw",
    )
    if staff and u.intent in candidate_only:
        from hr import assistant as hr_assistant
        from hr.models import Employee

        if Employee.objects.filter(user=user).exists():
            return hr_assistant.fallback_reply(user)
    knowledge = {e["key"]: e for e in ctx.knowledge}
    assistant = get_brand()["assistant"]["name"]

    if u.intent == "greeting":
        return _reply(
            u,
            f"Hi, I am {assistant}. I can find jobs, explain how matching works"
            + (" and check your applications." if _is_candidate(user) else "."),
            user,
        )

    if u.intent == "application_status":
        if not _is_candidate(user):
            return _sign_in(u, user, "check your applications")
        apps = list(
            Application.objects.filter(candidate=user).select_related("job").order_by("-created_at")[:10]
        )
        if not apps:
            return _reply(u, "You have not applied to any jobs yet. Want me to find some?", user)
        rows = [
            {
                "id": str(a.id),
                "title": a.job.title,
                "status": a.status,
                "status_label": CANDIDATE_STATUS_WORDS.get(a.status, a.status),
            }
            for a in apps
        ]
        lines = "; ".join(f"{r['title']}: {r['status_label']}" for r in rows[:5])
        return _reply(
            u, f"Here is where your applications stand. {lines}.", user, applications=rows, link="/candidate"
        )

    if u.intent == "job_search":
        jobs, total = _search_jobs(u)
        what = _describe_filters(u, ctx)
        if not jobs:
            where = f" for {what}" if what else ""
            text = f"I could not find open jobs{where}. Try a related skill or another city."
            return _reply(u, text, user, link="/jobs")
        head = (
            f"I found {total} open {'job' if total == 1 else 'jobs'}" + (f" for {what}" if what else "") + "."
        )
        return _reply(u, head, user, jobs=[public_job_dict(j) for j in jobs], link="/jobs")

    if u.intent == "matching_jobs":
        if not _is_candidate(user):
            return _sign_in(u, user, "see jobs that match the skills on your resume")
        skills = profile_skill_slugs(user)
        if not skills:
            return _reply(
                u,
                "I need a resume first. Apply to a job and I will match future roles to your skills.",
                user,
                link="/jobs",
            )
        applied = Application.objects.filter(candidate=user).values("job_id")
        ranked = []
        for job in (
            Job.objects.public()
            .exclude(pk__in=applied)
            .select_related("department", "location", "level")
            .prefetch_related("required_skills", "nice_to_have_skills")
        ):
            req = {s.slug for s in job.required_skills.all()}
            overlap = len(skills & req)
            if overlap:
                ranked.append((overlap / max(len(req), 1), overlap, job))
        ranked.sort(key=lambda r: (-r[0], -r[1], r[2].title))
        if not ranked:
            return _reply(
                u,
                "No open roles match the skills on your resume right now. New roles are posted every week.",
                user,
                link="/jobs",
            )
        jobs = [r[2] for r in ranked[:5]]
        return _reply(
            u, "These open roles match skills on your resume.", user, jobs=[public_job_dict(j) for j in jobs]
        )

    if u.intent in ("how_matching_works", "is_screening_fair", "how_withdraw"):
        key = {
            "how_matching_works": "how-matching-works",
            "is_screening_fair": "is-screening-fair",
            "how_withdraw": "how-withdraw",
        }[u.intent]
        entry = knowledge.get(key)
        text = entry["answer"] if entry else "Please check the help pages."
        extra = {}
        if u.intent == "how_withdraw" and _is_candidate(user):
            extra["applications"] = [
                {
                    "id": str(a.id),
                    "title": a.job.title,
                    "status": a.status,
                    "status_label": CANDIDATE_STATUS_WORDS[a.status],
                }
                for a in Application.objects.filter(candidate=user, status__in=ACTIVE).select_related("job")
            ]
            extra["link"] = "/candidate"
        return _reply(u, text, user, **extra)

    if u.intent == "talk_to_recruiter":
        if not _is_candidate(user):
            return _sign_in(u, user, "message the recruiter for one of your applications")
        apps = list(Application.objects.filter(candidate=user, status__in=ACTIVE).select_related("job"))
        if not apps:
            return _reply(
                u, "You do not have an active application, so there is no recruiter to message yet.", user
            )
        rows = [
            {
                "id": str(a.id),
                "title": a.job.title,
                "status": a.status,
                "status_label": CANDIDATE_STATUS_WORDS[a.status],
            }
            for a in apps
        ]
        return _reply(
            u,
            "Choose the application and write your message. The recruiter for that role will see it.",
            user,
            applications=rows,
            action={"type": "message_recruiter"},
        )

    if u.intent == "faq" and u.faq_key in knowledge:
        entry = knowledge[u.faq_key]
        return _reply(u, entry["answer"], user, link=entry["link"] or None)

    return _reply(
        u,
        "I am not sure I understood. I can find jobs, explain matching and fairness"
        + (
            ", check your applications or message a recruiter."
            if _is_candidate(user)
            else ", and answer hiring questions."
        ),
        user,
    )
