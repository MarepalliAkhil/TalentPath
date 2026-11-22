import json
from datetime import date

import pytest
from django.core.management import call_command
from django.db import connection

from matching.extract import SkillMatcher, estimate_experience, extract_skills, split_sections
from matching.models import ParsedProfile
from matching.services import job_requirements, parse_text
from matching.weights import EXTRACTOR_VERSION
from org.taxonomy_data import SKILLS, skill_slug

TODAY = date(2026, 11, 21)


@pytest.fixture(scope="module")
def matcher():
    return SkillMatcher.build([(skill_slug(n), n, syn) for n, _, _, syn in SKILLS])


RESUME = """Asha Rao
Backend developer
SUMMARY
Ready to go to market quickly.
TECHNICAL SKILLS:
JS, React.js, Node.js, k8s, C#, Go, Postgres
Work Experience
Software Engineer - Kestrel (Jan 2024 - Present)
Built RESTful APIs in Django and PostgreSQL, shipped with Docker.
Engineering Intern - Brightleaf (06/2023 - 12/2023)
Developer - Orchid 2021-2023
Projects
Chat app with WebSockets and Redis
Education
B.Tech, Lakeview University, 2017 - 2021
Certifications
Online course: Terraform fundamentals
"""


def test_sections_are_detected():
    sections = {s for s, _ in split_sections(RESUME)}
    assert sections == {"other", "summary", "skills", "experience", "projects", "education", "certifications"}


@pytest.mark.parametrize(
    "alias,slug",
    [
        ("JS", "javascript"),
        ("React.js", "react"),
        ("Node.js", "nodejs"),
        ("k8s", "kubernetes"),
        ("C#", "csharp"),
        ("Postgres", "postgresql"),
        ("ReactJS", "react"),
        ("CI/CD", "cicd"),
    ],
)
def test_synonyms_case_and_punctuation_insensitive(matcher, alias, slug):
    found = extract_skills(f"SKILLS\n{alias}, {alias.lower()}", matcher)
    assert set(found) == {slug}


def test_evidence_uses_strongest_section(matcher):
    found = extract_skills(RESUME, matcher)
    assert found["postgresql"].section == "experience"  # listed in skills, used in experience
    assert found["django"].section == "experience"
    assert found["redis"].section == "projects"
    assert found["terraform"].section == "certifications"
    assert found["javascript"].section == "skills"
    assert "Django" in found["django"].snippet


def test_ambiguous_words_only_count_in_skills_section(matcher):
    found = extract_skills(RESUME, matcher)
    assert found["go"].section == "skills"  # "Go" listed as a skill
    prose = extract_skills("SUMMARY\nReady to go to market. Ruby is my colleague.", matcher)
    assert "go" not in prose and "ruby" not in prose


def test_experience_years_full_time_and_internship_separate():
    exp = estimate_experience(RESUME, today=TODAY)
    # Jan 2024 - Nov 2026 = 34 months, 2021-2023 = 24 months -> 58 months = 4.8 years
    assert exp.years == 4.8
    assert exp.internship_months == 6


@pytest.mark.parametrize(
    "text,years",
    [
        ("EXPERIENCE\nAnalyst, Acme (2023-2025)", 2.0),
        ("EXPERIENCE\nAnalyst, Acme, March 2020 to February 2022", 1.9),
        ("EXPERIENCE\nIntern, Acme (2025 - present)\nINTERNSHIPS\nTrainee (2024 - 2025)", 0.0),
    ],
)
def test_experience_formats(text, years):
    assert estimate_experience(text, today=TODAY).years == years


@pytest.mark.parametrize(
    "text",
    [
        "EXPERIENCE\nWorked at Acme for a while",
        "No headings at all, 2019 - 2022",
        "EDUCATION\nB.Tech 2019 - 2023",
        "",
    ],
)
def test_experience_unknown_is_never_guessed(text):
    exp = estimate_experience(text, today=TODAY)
    assert exp.years is None and exp.internship_months is None


def test_parsed_profile_is_versioned_and_evidence_encrypted(application):
    profile = ParsedProfile.objects.get(application=application)
    assert profile.version == EXTRACTOR_VERSION
    assert {s["slug"] for s in profile.skills} >= {"python", "django", "postgresql"}
    with connection.cursor() as cursor:
        cursor.execute("SELECT evidence FROM matching_parsedprofile")
        (raw,) = cursor.fetchone()
    assert raw.startswith("v1:") and "Django" not in raw
    assert any(row["slug"] == "django" for row in json.loads(profile.evidence))


def test_reparse_command_updates_old_versions(application):
    ParsedProfile.objects.filter(application=application).update(version=0, skills=[])
    call_command("reparse_profiles")
    profile = ParsedProfile.objects.get(application=application)
    assert profile.version == EXTRACTOR_VERSION and profile.skills


def test_job_requirements_include_description_mentions(make_job):
    job = make_job(required=("python",), nice=())
    job.description = "Build services in Python and Kubernetes. " * 3
    job.save()
    req = job_requirements(job)
    assert [s for s, _ in req.required] == ["python"]
    assert "kubernetes" in [s for s, _ in req.nice]


def test_parse_text_reports_sections(matcher):
    data = parse_text(RESUME, matcher)
    assert "projects" in data["sections_found"] and data["experience_years"] is not None
