"""Glue between the database and the pure extractor / scorer."""

import hashlib
import json
from decimal import Decimal
from functools import lru_cache

from django.db import transaction

from org.models import Skill

from .extract import SkillMatcher, estimate_experience, extract_skills, job_mentioned_skills, split_sections
from .models import FitScore, ParsedProfile
from .scoring import JobRequirements, ScoringInput, score
from .weights import BANDS, EXTRACTOR_VERSION, SCORER_VERSION

BAND_LABELS = {key: label for _, key, label in BANDS}


def _taxonomy_rows():
    return tuple(
        (s.slug, s.name, tuple(s.synonyms or ())) for s in Skill.objects.only("slug", "name", "synonyms")
    )


@lru_cache(maxsize=4)
def _matcher_for(rows) -> SkillMatcher:
    return SkillMatcher.build(rows)


def get_matcher() -> SkillMatcher:
    """Rebuilt automatically when hr_admin edits the taxonomy (rows are the cache key)."""
    return _matcher_for(_taxonomy_rows())


# ------------------------------------------------------------------ parsing
def parse_text(text: str, matcher: SkillMatcher | None = None) -> dict:
    matcher = matcher or get_matcher()
    found = extract_skills(text, matcher)
    experience = estimate_experience(text)
    return {
        "skills": [{"slug": e.slug, "name": e.name, "section": e.section} for e in found.values()],
        "evidence": [{"slug": e.slug, "snippet": e.snippet} for e in found.values()],
        "sections_found": sorted({section for section, _ in split_sections(text)} - {"other"}),
        "experience_years": experience.years,
        "internship_months": experience.internship_months,
    }


def parse_application(application, matcher: SkillMatcher | None = None) -> ParsedProfile:
    data = parse_text(application.resume_text or "", matcher)
    years = data["experience_years"]
    profile, _ = ParsedProfile.objects.update_or_create(
        application=application,
        defaults={
            "version": EXTRACTOR_VERSION,
            "skills": data["skills"],
            "evidence": json.dumps(data["evidence"]),
            "sections_found": data["sections_found"],
            "experience_years": None if years is None else Decimal(str(years)),
            "internship_months": data["internship_months"],
        },
    )
    return profile


# ------------------------------------------------------------------ scoring
def job_requirements(job, matcher: SkillMatcher | None = None) -> JobRequirements:
    matcher = matcher or get_matcher()
    required = tuple((s.slug, s.name) for s in job.required_skills.all().order_by("name"))
    nice = [(s.slug, s.name) for s in job.nice_to_have_skills.all().order_by("name")]
    taken = {slug for slug, _ in required} | {slug for slug, _ in nice}
    for ref in job_mentioned_skills(job.description or "", matcher):
        if ref.slug not in taken:
            nice.append((ref.slug, ref.name))
            taken.add(ref.slug)
    return JobRequirements(required=required, nice=tuple(nice), level_rank=job.level.rank)


def requirements_hash(req: JobRequirements) -> str:
    raw = json.dumps([req.required, req.nice, req.level_rank, SCORER_VERSION])
    return hashlib.sha256(raw.encode()).hexdigest()


def scoring_input(profile: ParsedProfile) -> ScoringInput:
    """The structural fairness gate: only skills, sections and years pass through."""
    years = None if profile.experience_years is None else float(profile.experience_years)
    skills = tuple(sorted((s["slug"], s["section"]) for s in profile.skills))
    return ScoringInput(skills=skills, experience_years=years)


def score_application(application, req: JobRequirements | None = None) -> FitScore:
    profile = application.parsed_profile if hasattr(application, "parsed_profile") else None
    if profile is None or profile.version != EXTRACTOR_VERSION:
        profile = parse_application(application)
    req = req or job_requirements(application.job)
    result = score(scoring_input(profile), req)
    fit, _ = FitScore.objects.update_or_create(
        application=application,
        defaults={
            "score": result.score,
            "band": result.band,
            "explanation": result.explanation,
            "version": result.version,
            "requirements_hash": requirements_hash(req),
        },
    )
    return fit


def process_application(application) -> FitScore:
    """Called when an application arrives."""
    with transaction.atomic():
        parse_application(application)
        return score_application(application)


def rescore_job(job) -> int:
    """Called when a job's skills, description or level change."""
    req = job_requirements(job)
    count = 0
    for application in job.applications.select_related("job__level", "parsed_profile"):
        score_application(application, req)
        count += 1
    return count


def ensure_fresh(applications) -> None:
    """Recompute stale results (older extractor or scorer version, or changed job)."""
    cache: dict = {}
    for app in applications:
        req = cache.get(app.job_id)
        if req is None:
            req = cache[app.job_id] = job_requirements(app.job)
        fit = app.fit_score if hasattr(app, "fit_score") else None
        profile = app.parsed_profile if hasattr(app, "parsed_profile") else None
        stale = (
            fit is None
            or profile is None
            or profile.version != EXTRACTOR_VERSION
            or fit.version != SCORER_VERSION
            or fit.requirements_hash != requirements_hash(req)
        )
        if stale:
            if profile is None or profile.version != EXTRACTOR_VERSION:
                app.parsed_profile = parse_application(app)
            app.fit_score = score_application(app, req)


def fit_dict(app) -> dict | None:
    fit = app.fit_score if hasattr(app, "fit_score") else None
    if fit is None:
        return None
    return {
        "score": fit.score,
        "band": fit.band,
        "band_label": BAND_LABELS.get(fit.band, fit.band),
        "explanation": fit.explanation,
        "version": fit.version,
        "computed_at": fit.computed_at.isoformat(),
    }


def profile_skill_slugs(candidate) -> set[str]:
    """Skills from the candidate's latest parsed profile (used by Ask HIRA and rejections)."""
    profile = ParsedProfile.objects.filter(application__candidate=candidate).order_by("-parsed_at").first()
    return {s["slug"] for s in (profile.skills if profile else [])}
