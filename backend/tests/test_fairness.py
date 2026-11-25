"""Fairness proof (runs in CI).

1. Counterfactual: synthetic resumes are rewritten changing ONLY the name,
   gender words and pronouns, college and city. Score, band and explanation
   must be identical for every variant against every demo job.
2. Structural: the scoring module cannot import or reference protected fields,
   and receives a data object that only carries allowed fields.
"""

import ast
import dataclasses
import inspect
import random
from datetime import date
from pathlib import Path

import pytest

from matching import scoring, services
from matching.extract import SkillMatcher
from matching.fairness import VARIANTS, check, make_variant, score_text
from matching.scoring import JobRequirements, ScoringInput
from org.taxonomy_data import SKILLS, skill_slug
from seeding import demo_data as D
from seeding.resumes import resume_lines

TODAY = date(2026, 11, 21)
PROTECTED = {
    "name",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "photo",
    "gender",
    "sex",
    "pronoun",
    "age",
    "birth",
    "dob",
    "address",
    "city",
    "location",
    "college",
    "university",
    "school",
    "institute",
    "religion",
    "caste",
    "marital",
    "nationality",
    "candidate",
    "user",
    "profile",
    "resume_text",
    "cover_note",
    "headline",
    # Prompt 1 application form (D-83): never inputs to the score.
    "ctc",
    "salary",
    "compensation",
    "cgpa",
    "percentage",
    "relocate",
    "notice",
    "form",
    "answers",
    "declarations",
}


@pytest.fixture(scope="module")
def matcher():
    return SkillMatcher.build([(skill_slug(n), n, syn) for n, _, _, syn in SKILLS])


def _requirements():
    by_name = {n: skill_slug(n) for n, _, _, _ in SKILLS}
    ranks = dict(D.LEVELS)
    for spec in D.JOBS:
        title, _, _, _, level, required, nice = spec[:7]
        yield (
            title,
            JobRequirements(
                required=tuple((by_name[n], n) for n in required),
                nice=tuple((by_name[n], n) for n in nice),
                level_rank=ranks[level],
            ),
        )


def _synthetic_resumes(count=24):
    tracks = list(D.TRACKS)
    for n in range(count):
        rng = random.Random(9000 + n)
        track = tracks[n % len(tracks)]
        pool = D.TRACKS[track][1]
        skills = rng.sample(pool, k=min(len(pool), 6))
        name = f"{D.FIRST_NAMES[n % len(D.FIRST_NAMES)]} {D.LAST_NAMES[n % len(D.LAST_NAMES)]}"
        city = D.CITIES[n % len(D.CITIES)]
        known = {"full_name": name, "city": city}
        text = "\n".join(
            resume_lines(
                rng,
                name=name,
                email=f"p{n}@candidates.example",
                phone=f"+91 55501 {n:05d}",
                city=city,
                track=track,
                skills=skills,
                college=D.COLLEGES[n % len(D.COLLEGES)],
                pronoun=D.PRONOUNS[n % 3],
            )
        )
        yield f"resume-{n}", text, known


def test_variants_really_change_the_protected_details():
    name, city = "Meera Iyer", "Pune"
    text = (
        f"{name}\n{city}\nSUMMARY\nShe enjoys Python. Her projects are public.\n"
        "EDUCATION\nB.Tech, Lakeview University"
    )
    variant = make_variant(text, {"full_name": name, "city": city}, VARIANTS[1])
    assert "Meera" not in variant and "Lakeview University" not in variant and "Pune" not in variant
    assert "He enjoys Python" in variant and "His projects" in variant
    assert "Python" in variant  # skills untouched


def test_counterfactual_scores_identical_for_every_variant(matcher):
    jobs = list(_requirements())
    tested = changes = 0
    for label, text, known in _synthetic_resumes():
        for title, req in jobs:
            base = score_text(text, req, matcher, TODAY)
            for variant in VARIANTS:
                other = score_text(make_variant(text, known, variant), req, matcher, TODAY)
                tested += 1
                assert (other.score, other.band, other.explanation) == (
                    base.score,
                    base.band,
                    base.explanation,
                ), f"{label} vs {title}: {variant} changed {base.score} -> {other.score}"
                changes += other.score != base.score
    assert tested == 24 * 25 * len(VARIANTS) and changes == 0


def test_check_helper_counts_variants(matcher):
    req = next(_requirements())[1]
    items = [(label, text, known, req) for label, text, known in _synthetic_resumes(10)]
    result = check(items, matcher, variants_per_item=3, today=TODAY)
    assert (result.applications, result.variants, result.changes) == (10, 30, 0)


# ------------------------------------------------------------------ structural
SCORING_SOURCE = Path(inspect.getfile(scoring)).read_text(encoding="utf-8")


def _code_without_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                node.body = node.body[1:] or [ast.Pass()]
    return tree


def test_scoring_module_imports_only_allowed_modules():
    tree = ast.parse(SCORING_SOURCE)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
    assert imported <= {"dataclasses", ".weights"}, imported


def test_scoring_module_never_references_protected_fields():
    tree = _code_without_docstrings(ast.parse(SCORING_SOURCE))
    words = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            words.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            words.add(node.attr.lower())
        elif isinstance(node, ast.arg):
            words.add(node.arg.lower())
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            words.update(w.lower() for w in node.value.replace("_", " ").split())
    hits = {w for w in words for p in PROTECTED if p == w or w.startswith(p + "_") or w.endswith("_" + p)}
    # "name" only ever appears as the skill's display name inside (slug, name) pairs.
    assert hits <= {"name"}, hits


def test_scoring_input_carries_only_allowed_fields():
    assert {f.name for f in dataclasses.fields(ScoringInput)} == {"skills", "experience_years"}
    assert list(inspect.signature(scoring.score).parameters) == ["facts", "job"]


def test_services_gate_passes_only_skills_and_years():
    tree = ast.parse(inspect.getsource(services.scoring_input))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert attrs <= {"experience_years", "skills"}, attrs


def test_hr_fairness_check_page(client_for, application):
    data = client_for("hr").get("/api/fairness/check").data
    assert data["applications"] == 1 and data["variants"] == 3 and data["changes"] == 0
    assert data["passed"] is True and data["summary"] == "3 variants tested, 0 score changes."


def test_score_ignores_the_application_form(users, make_job, make_user, pdf_bytes):
    """Prompt 1: CTC, date of birth, college, city and the other form fields never change the
    fit score. Two candidates with the same resume and very different forms score the same."""
    import json

    from applications.services import apply_to_job
    from matching.services import score_application

    from .conftest import application_form

    job = make_job(title="Form Fairness Role")
    low = json.loads(application_form())
    high = json.loads(application_form())
    high["personal"].update(
        {"date_of_birth": "1978-02-02", "current_city": "Visakhapatnam", "willing_to_relocate": False}
    )
    high["education"].update(
        {"college": "Northfield College of Engineering", "score": "6.1", "tenth_percentage": "60"}
    )
    high["compensation"].update({"current_ctc_lpa": "48", "expected_ctc_lpa": "90", "notice_period": "90"})
    scores = []
    for form in (low, high):
        person = make_user("candidate")
        app = apply_to_job(
            candidate=person, job=job, filename="cv.pdf", data=pdf_bytes, silent=True, form=form
        )
        fit = score_application(app)
        scores.append((fit.score, fit.band, json.dumps(fit.explanation, sort_keys=True)))
    assert scores[0] == scores[1]


def test_form_module_is_not_imported_by_the_scorer():
    import ast

    for module in (scoring, services):
        tree = ast.parse(inspect.getsource(module))
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any("form" in name.split(".")[-1] for name in imported), imported
