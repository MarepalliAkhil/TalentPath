"""Every number the fit score uses lives here. Documented in docs/MATCHING.md.

Bump SCORER_VERSION whenever a weight, band or rule changes, and
EXTRACTOR_VERSION whenever extraction changes: stored results with an older
version are recomputed (lazily, or with `manage.py reparse_profiles` / `rescore`).
"""

EXTRACTOR_VERSION = 1
SCORER_VERSION = 1

# Component weights (points out of 100 when every component applies).
# A component that does not apply to a job (for example, no nice-to-have
# skills) is dropped and the remaining weights are scaled back up to 100.
WEIGHTS = {
    "required": 50,  # share of the job's required skills the resume shows
    "nice": 15,  # share of nice-to-have (and description-mentioned) skills shown
    "evidence": 20,  # matched skills backed by experience or projects, not just listed
    "experience": 15,  # years of full-time experience against the job level
}

# Evidence strength of the strongest section a skill was found in.
EVIDENCE_STRENGTH = {
    "experience": 1.0,
    "projects": 1.0,
    "certifications": 0.75,
    "skills": 0.5,
    "summary": 0.5,
    "education": 0.5,
    "other": 0.5,
}
STRONG_SECTIONS = ("experience", "projects")

# Minimum years of full-time experience expected per job level rank
# (org.JobLevel.rank). Internships are reported separately and not counted.
LEVEL_MIN_YEARS = {10: 0, 20: 0, 30: 2, 40: 5, 50: 7, 60: 6}
UNKNOWN_EXPERIENCE_CREDIT = 0.5  # never guess: unknown gets neutral half credit

# Bands: (minimum score, key, label), highest first.
BANDS = [
    (80, "strong", "Strong"),
    (60, "good", "Good"),
    (40, "partial", "Partial"),
    (0, "low", "Low"),
]
