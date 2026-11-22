"""Fit score: deterministic, explainable, versioned.

FAIRNESS CONTRACT (enforced by tests/test_fairness.py):
- This module may import only the standard library pieces below and .weights.
- It receives a ScoringInput, which carries ONLY skill slugs with the section
  they were evidenced in, and years of experience. It never sees a name,
  contact detail, demographic, location, education institution or free text.
"""

from dataclasses import dataclass

from .weights import (
    BANDS,
    EVIDENCE_STRENGTH,
    LEVEL_MIN_YEARS,
    SCORER_VERSION,
    STRONG_SECTIONS,
    UNKNOWN_EXPERIENCE_CREDIT,
    WEIGHTS,
)


@dataclass(frozen=True)
class ScoringInput:
    """The only facts the scorer is allowed to read."""

    skills: tuple[tuple[str, str], ...]  # (skill slug, strongest section)
    experience_years: float | None  # None = unknown


@dataclass(frozen=True)
class JobRequirements:
    required: tuple[tuple[str, str], ...]  # (slug, display name)
    nice: tuple[tuple[str, str], ...]  # nice-to-have plus skills mentioned in the description
    level_rank: int


@dataclass(frozen=True)
class ScoreResult:
    score: int
    band: str
    band_label: str
    explanation: dict
    version: int = SCORER_VERSION


def _band(score: int) -> tuple[str, str]:
    for minimum, key, label in BANDS:
        if score >= minimum:
            return key, label
    return BANDS[-1][1], BANDS[-1][2]


def _section_label(section: str) -> str:
    return {"experience": "experience", "projects": "projects", "certifications": "certification"}.get(
        section, ""
    )


def score(facts: ScoringInput, job: JobRequirements) -> ScoreResult:
    have = dict(facts.skills)
    chips: list[dict] = []
    components: dict[str, float] = {}

    matched_required = [(slug, name) for slug, name in job.required if slug in have]
    missing_required = [(slug, name) for slug, name in job.required if slug not in have]
    matched_nice = [(slug, name) for slug, name in job.nice if slug in have]

    if job.required:
        components["required"] = len(matched_required) / len(job.required)
    if job.nice:
        components["nice"] = len(matched_nice) / len(job.nice)

    matched = matched_required + matched_nice
    if matched:
        components["evidence"] = sum(
            EVIDENCE_STRENGTH.get(have[slug], EVIDENCE_STRENGTH["other"]) for slug, _ in matched
        ) / len(matched)
    elif job.required or job.nice:
        components["evidence"] = 0.0

    min_years = LEVEL_MIN_YEARS.get(job.level_rank, 0)
    years = facts.experience_years
    if min_years == 0:
        components["experience"] = 1.0
        exp_chip = {"kind": "info", "label": "Entry-level role: experience not required"}
    elif years is None:
        components["experience"] = UNKNOWN_EXPERIENCE_CREDIT
        exp_chip = {"kind": "info", "label": "Experience not stated (neutral)"}
    elif years >= min_years:
        components["experience"] = 1.0
        exp_chip = {"kind": "positive", "label": f"{years:g} yrs experience (needs {min_years}+)"}
    else:
        components["experience"] = years / min_years
        exp_chip = {"kind": "gap", "label": f"{years:g} yrs experience (needs {min_years}+)"}

    total_weight = sum(WEIGHTS[k] for k in components)
    raw = sum(WEIGHTS[k] * v for k, v in components.items()) / total_weight if total_weight else 0.0
    value = int(round(raw * 100))
    band, band_label = _band(value)

    for slug, name in matched_required:
        where = _section_label(have[slug])
        chips.append({"kind": "positive", "label": f"Has {name} ({where})" if where else f"Has {name}"})
    for _, name in missing_required:
        chips.append({"kind": "gap", "label": f"Missing required: {name}"})
    for _, name in matched_nice:
        chips.append({"kind": "bonus", "label": f"Nice to have: {name}"})
    chips.append(exp_chip)

    breakdown = [
        {"component": key, "weight": WEIGHTS[key], "points": round(WEIGHTS[key] * v * 100 / total_weight, 1)}
        for key, v in components.items()
    ]
    explanation = {
        "chips": chips,
        "raise_score": [f"Add evidence of {name}" for _, name in missing_required],
        "breakdown": breakdown,
        "matched_required": len(matched_required),
        "required_total": len(job.required),
        "matched_nice": len(matched_nice),
        "nice_total": len(job.nice),
        "strong_evidence": sum(1 for slug, _ in matched if have[slug] in STRONG_SECTIONS),
        "experience_years": years,
        "min_years": min_years,
    }
    return ScoreResult(value, band, band_label, explanation)
