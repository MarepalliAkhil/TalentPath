"""Skill-gap career map, "Your next role" and internal mobility.

One source of truth for fit: every score here comes from `matching.scoring.score` with
`matching.services.job_requirements`, exactly what recruiters see for an application.
"""

import json
from collections import Counter
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import Role
from applications.models import Application, Source
from applications.resume import CONTENT_TYPES, ResumeError, inspect_resume, safe_filename
from core.audit import audit
from files.storage import read_file, save_file
from jobs.models import Job, JobStatus
from matching.scoring import score
from matching.services import facts_to_input, get_matcher, job_requirements, parse_text
from matching.weights import EXTRACTOR_VERSION
from org.models import JobLevel, Skill

from . import graph
from .models import CareerProfile, ResumeVersion

MAP_LIMIT = 12


# ---------------------------------------------------------------- the person's skills
def _skill_names() -> dict:
    return dict(Skill.objects.values_list("slug", "name"))


def person_facts(user) -> dict:
    """Skills, evidence and experience for the career map. Order of sources: the resume on
    their profile, else their latest application's parsed resume, else (employees) the
    skills HR recorded on their interviewer profile."""
    profile = CareerProfile.objects.filter(user=user).first()
    if profile and profile.resume_text:
        evidence = {e["slug"]: e["snippet"] for e in json.loads(profile.evidence or "[]")}
        years = None if profile.experience_years is None else float(profile.experience_years)
        return {"source": "profile", "skills": profile.skills, "evidence": evidence, "years": years}
    from matching.models import ParsedProfile

    parsed = ParsedProfile.objects.filter(application__candidate=user).order_by("-parsed_at").first()
    if parsed:
        evidence = {e["slug"]: e["snippet"] for e in json.loads(parsed.evidence or "[]")}
        years = None if parsed.experience_years is None else float(parsed.experience_years)
        return {"source": "application", "skills": parsed.skills, "evidence": evidence, "years": years}
    from interviews.models import InterviewerProfile

    interviewer = InterviewerProfile.objects.filter(user=user).prefetch_related("skills").first()
    if interviewer:
        skills = [{"slug": s.slug, "name": s.name, "section": "skills"} for s in interviewer.skills.all()]
        if skills:
            return {"source": "hr_record", "skills": skills, "evidence": {}, "years": None}
    return {"source": "none", "skills": [], "evidence": {}, "years": None}


def save_profile_resume(user, filename: str, data: bytes, request=None) -> CareerProfile:
    try:
        kind, text = inspect_resume(data)
    except ResumeError as exc:
        raise ValidationError({"resume": str(exc)}) from exc
    name = safe_filename(filename, kind)
    parsed = parse_text(text, get_matcher())
    with transaction.atomic():
        profile, _ = CareerProfile.objects.select_for_update().get_or_create(user=user)
        profile.resume_file = save_file(
            owner=user, original_name=name, content_type=CONTENT_TYPES[kind], raw=data
        )
        # D-82: the new resume replaces the current one; earlier versions stay in the history.
        ResumeVersion.objects.filter(user=user, is_current=True).update(is_current=False)
        ResumeVersion.objects.create(user=user, file=profile.resume_file, filename=name, is_current=True)
        profile.resume_filename = name
        profile.resume_text = text
        profile.skills = parsed["skills"]
        profile.evidence = json.dumps(parsed["evidence"])
        years = parsed["experience_years"]
        profile.experience_years = None if years is None else Decimal(str(years))
        profile.extractor_version = EXTRACTOR_VERSION
        profile.save()
    audit(request, "career.resume_uploaded", actor=user, target=profile, skills=len(parsed["skills"]))
    return profile


def delete_profile_resume(user, request=None) -> bool:
    """Deleting removes the current resume and every earlier version (the person's right to delete)."""
    profile = CareerProfile.objects.filter(user=user).first()
    if profile is None:
        return False
    files = {v.file_id for v in ResumeVersion.objects.filter(user=user) if v.file_id}
    if profile.resume_file_id:
        files.add(profile.resume_file_id)
    profile.delete()
    ResumeVersion.objects.filter(user=user).delete()
    from files.models import StoredFile

    StoredFile.objects.filter(pk__in=files).delete()
    audit(request, "career.resume_deleted", actor=user, target=user)
    return True


def profile_dict(user) -> dict:
    profile = CareerProfile.objects.filter(user=user).first()
    facts = person_facts(user)
    return {
        "has_resume": bool(profile and profile.resume_text),
        "filename": profile.resume_filename if profile else "",
        "updated_at": profile.updated_at.isoformat() if profile else None,
        "source": facts["source"],
        "skills": sorted({s["name"] for s in facts["skills"]}),
        "experience_years": facts["years"],
    }


# ---------------------------------------------------------------- scoring with the week 2 scorer
def score_for(facts: dict, job, req=None):
    req = req or job_requirements(job)
    return score(facts_to_input(facts["skills"], facts["years"]), req), req


def visible_jobs_for(user):
    """Candidates: the public career site. Employees: jobs open to internal applicants."""
    base = Job.objects.select_related("department", "location", "level").prefetch_related(
        "required_skills", "nice_to_have_skills"
    )
    if user.role == Role.CANDIDATE:
        return base.public()
    return base.internal()


def _brief(job, result) -> dict:
    return {
        "id": str(job.id),
        "slug": job.slug,
        "title": job.title,
        "department": job.department.name,
        "location": job.location.name,
        "level": job.level.name,
        "audience": job.audience,
        "score": result.score,
        "band": result.band,
        "band_label": result.band_label,
    }


def closest_jobs(user, limit: int = MAP_LIMIT) -> dict:
    facts = person_facts(user)
    rows = []
    if facts["skills"]:
        matcher = get_matcher()
        for job in visible_jobs_for(user):
            result, _ = score_for(facts, job, job_requirements(job, matcher))
            rows.append((result.score, job.title, _brief(job, result)))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return {"source": facts["source"], "jobs": [r[2] for r in rows[:limit]]}


def job_map(user, job) -> dict:
    facts = person_facts(user)
    result, req = score_for(facts, job)
    have = {s["slug"]: s for s in facts["skills"]}
    names = _skill_names()

    def skill_row(slug, name):
        row = {"slug": slug, "name": name, "effort": graph.effort(slug)}
        if slug in have:
            row["section"] = have[slug].get("section", "")
            row["evidence"] = facts["evidence"].get(slug, "")
        return row

    required_have = [skill_row(s, n) for s, n in req.required if s in have]
    nice_have = [skill_row(s, n) for s, n in req.nice if s in have]
    missing_required = [skill_row(s, n) for s, n in req.required if s not in have]
    missing_nice = [skill_row(s, n) for s, n in req.nice if s not in have]
    priority = {r["slug"]: 0 for r in missing_required} | {r["slug"]: 1 for r in missing_nice}
    path = graph.learning_path(
        [r["slug"] for r in missing_required + missing_nice], set(have), priority=priority
    )
    required_slugs = {r["slug"] for r in missing_required}
    nice_slugs = {r["slug"] for r in missing_nice}
    for step in path:
        step["name"] = names.get(step["slug"], step["slug"])
        slug = step["slug"]
        step["kind"] = (
            "required" if slug in required_slugs else "nice" if slug in nice_slugs else "prerequisite"
        )
        step["prerequisites"] = [names.get(p, p) for p in step["prerequisites"]]
        step["unlocks"] = [names.get(u, u) for u in step["unlocks"]]
    applied = Application.objects.filter(job=job, candidate=user).first()
    return {
        "job": _brief(job, result),
        "explanation": result.explanation,
        "source": facts["source"],
        "have": required_have + nice_have,
        "missing_required": missing_required,
        "missing_nice": missing_nice,
        "path": path,
        "applied": bool(applied),
        "can_apply_internally": user.role == Role.EMPLOYEE and job.audience != "external" and not applied,
    }


def map_job_or_404(user, job_id):
    job = visible_jobs_for(user).filter(pk=job_id).first()
    if job is None:
        raise NotFound()
    return job


# ---------------------------------------------------------------- your next role (employees)
def next_role(user) -> dict:
    from hr.models import Employee

    employee = Employee.objects.select_related("department", "level").filter(user=user).first()
    if employee is None:
        raise NotFound("You do not have an employee record yet.")
    facts = person_facts(user)
    have = {s["slug"] for s in facts["skills"]}
    names = _skill_names()
    current = employee.level
    if current is None:
        return {
            "current_level": None,
            "department": employee.department.name,
            "levels": [],
            "source": facts["source"],
        }
    levels = []
    for level in JobLevel.objects.filter(rank__gt=current.rank).order_by("rank")[:3]:
        jobs = list(
            Job.objects.filter(department=employee.department, level=level)
            .exclude(status=JobStatus.DRAFT)
            .prefetch_related("required_skills")
        )
        if not jobs:
            continue
        counts = Counter(s.slug for job in jobs for s in job.required_skills.all())
        needed = [
            {"slug": slug, "name": names.get(slug, slug), "jobs": n, "effort": graph.effort(slug)}
            for slug, n in sorted(counts.items(), key=lambda kv: (-kv[1], names.get(kv[0], kv[0])))
        ]
        missing = [row for row in needed if row["slug"] not in have]
        levels.append(
            {
                "level": level.name,
                "rank": level.rank,
                "titles": sorted({job.title for job in jobs}),
                "skills_needed": needed,
                "have": [row for row in needed if row["slug"] in have],
                "missing": missing,
                "path": [
                    {**step, "name": names.get(step["slug"], step["slug"])}
                    for step in graph.learning_path([m["slug"] for m in missing], have)
                ],
            }
        )
    return {
        "current_level": current.name,
        "department": employee.department.name,
        "designation": employee.designation,
        "levels": levels,
        "source": facts["source"],
    }


# ---------------------------------------------------------------- internal mobility
NOTICE_TEXT = {
    "interview": "Your reporting manager is told only if your application reaches the Interview stage. "
    "Nobody is told when you apply, and your application is screened like any other.",
    "offer": "Your reporting manager is told only if you receive an offer. "
    "Nobody is told when you apply or interview, and your application is screened like any other.",
}


def notice_rule(employee) -> dict:
    from hr.calendar_rules import policy_for

    stage = policy_for(employee.location).internal_manager_notice
    return {
        "stage": stage,
        "text": NOTICE_TEXT.get(stage, NOTICE_TEXT["interview"]),
        "manager": employee.manager.name if employee.manager else None,
    }


def employee_or_404(user):
    from hr.models import Employee

    employee = (
        Employee.objects.select_related("location", "manager__user", "department").filter(user=user).first()
    )
    if employee is None:
        raise NotFound("You do not have an employee record yet.")
    return employee


def internal_jobs(user) -> dict:
    employee = employee_or_404(user)
    facts = person_facts(user)
    profile = CareerProfile.objects.filter(user=user).first()
    applied = {a.job_id: a for a in Application.objects.filter(candidate=user).select_related("job")}
    matcher = get_matcher()
    rows = []
    for job in visible_jobs_for(user):
        result, _ = score_for(facts, job, job_requirements(job, matcher))
        row = _brief(job, result) | {
            "applied": job.id in applied,
            "own_department": job.department_id == employee.department_id,
        }
        rows.append(row)
    rows.sort(key=lambda r: (-r["score"], r["title"]))
    from applications.services import CANDIDATE_STATUS_WORDS

    mine = [
        {
            "id": str(a.id),
            "job": a.job.title,
            "status": a.status,
            "status_label": CANDIDATE_STATUS_WORDS.get(a.status, a.get_status_display()),
            "applied_at": a.created_at.isoformat(),
        }
        for a in sorted(applied.values(), key=lambda a: a.created_at, reverse=True)
        if a.source == Source.INTERNAL
    ]
    return {
        "jobs": rows,
        "applications": mine,
        "rule": notice_rule(employee),
        "has_resume": bool(profile and profile.resume_file_id),
    }


def apply_internally(user, job_id, request=None) -> Application:
    from applications.services import apply_to_job

    employee_or_404(user)  # only people with an employee record can apply internally
    job = Job.objects.internal().filter(pk=job_id).first()
    if job is None:
        raise NotFound()
    profile = CareerProfile.objects.filter(user=user).select_related("resume_file").first()
    if profile is None or profile.resume_file is None:
        raise ValidationError(
            {"resume": "Add your resume on your profile first; internal applications use it."}
        )
    data = read_file(profile.resume_file)
    application = apply_to_job(
        candidate=user,
        job=job,
        filename=profile.resume_filename or "resume.pdf",
        data=data,
        source=Source.INTERNAL,
    )
    audit(request, "internal.applied", actor=user, target=application, job=str(job.id))
    return application


def internal_stage_notice(application, new_status: str) -> bool:
    """Tell the internal applicant's reporting manager at the configured stage (never at application)."""
    from hr.models import Employee
    from notifications.services import notify

    if application.source != Source.INTERNAL:
        return False
    employee = (
        Employee.objects.select_related("manager__user", "location")
        .filter(user=application.candidate)
        .first()
    )
    if employee is None or employee.manager is None:
        return False
    if notice_rule(employee)["stage"] != new_status:
        return False
    notify(
        employee.manager.user,
        kind="internal_mobility",
        title=f"{employee.name} is interviewing for an internal role"
        if new_status == "interview"
        else f"{employee.name} has an internal offer",
        body=f"{employee.name} applied internally for {application.job.title} and has reached the "
        f"{'Interview' if new_status == 'interview' else 'Offer'} stage. You are told under the internal "
        "mobility rule; please keep it confidential.",
        link="/team-calendar",
    )
    audit(
        None,
        "internal.manager_informed",
        target=application,
        stage=new_status,
        manager=str(employee.manager.user_id),
    )
    return True
