"""Counterfactual fairness check.

For each resume we build variants that change ONLY the person's name, gendered
words and pronouns, education institution and city, run every variant through
the real extractor and scorer, and require score, band and explanation to be
identical. Variants exist in memory only; nothing about them is stored.

Limits (also in docs/MATCHING.md): this proves the scorer ignores these
details. It does not prove the job's requirements are fair, and it only covers
the kinds of change listed here.
"""

import re
from dataclasses import dataclass
from datetime import date

from applications.redact import _KNOWN_RE, INSTITUTION_PHRASE_RE

from .extract import SkillMatcher, estimate_experience, extract_skills
from .scoring import JobRequirements, ScoringInput, score

VARIANTS = [
    {"name": "Priya Lakshmi", "gender": "female", "college": "IIT Bombay", "city": "Chennai"},
    {"name": "Rahul Verma", "gender": "male", "college": "Osmania University", "city": "Vijayawada"},
    {
        "name": "Alex Fernandes",
        "gender": "neutral",
        "college": "Sunrise Institute of Technology",
        "city": "Pune",
    },
    {"name": "Fatima Shaikh", "gender": "female", "college": "Delhi University", "city": "Hyderabad"},
    {
        "name": "Arjun Naidu",
        "gender": "male",
        "college": "Lakeview College of Engineering",
        "city": "Bengaluru",
    },
]
CITIES = [
    "Hyderabad",
    "Bengaluru",
    "Bangalore",
    "Pune",
    "Chennai",
    "Vijayawada",
    "Visakhapatnam",
    "Kochi",
    "Mumbai",
    "Delhi",
]
GENDER_WORDS = {
    "female": {
        "he": "she",
        "him": "her",
        "his": "her",
        "himself": "herself",
        "mr": "Ms",
        "male": "female",
        "man": "woman",
    },
    "male": {
        "she": "he",
        "her": "his",
        "hers": "his",
        "herself": "himself",
        "ms": "Mr",
        "mrs": "Mr",
        "female": "male",
        "woman": "man",
    },
    "neutral": {
        "he": "they",
        "she": "they",
        "him": "them",
        "her": "their",
        "his": "their",
        "hers": "theirs",
        "himself": "themself",
        "herself": "themself",
        "mr": "Mx",
        "ms": "Mx",
        "mrs": "Mx",
        "male": "non-binary",
        "female": "non-binary",
        "man": "person",
        "woman": "person",
    },
}


def _keep_case(src: str, word: str) -> str:
    return word.capitalize() if src[:1].isupper() else word


def make_variant(text: str, known: dict, variant: dict) -> str:
    out = text
    name = (known.get("full_name") or "").strip()
    if name:
        new_parts = variant["name"].split()
        old_parts = name.split()
        out = re.sub(re.escape(name), variant["name"], out, flags=re.IGNORECASE)
        for i, part in enumerate(old_parts):
            if len(part) >= 2:
                repl = new_parts[min(i, len(new_parts) - 1)]
                out = re.sub(rf"(?<!\w){re.escape(part)}(?!\w)", repl, out, flags=re.IGNORECASE)
    words = GENDER_WORDS[variant["gender"]]
    out = re.sub(
        r"\b(" + "|".join(words) + r")\b",
        lambda m: _keep_case(m.group(0), words[m.group(0).lower()]),
        out,
        flags=re.IGNORECASE,
    )
    out = "\n".join(
        INSTITUTION_PHRASE_RE.sub(variant["college"], _KNOWN_RE.sub(variant["college"], line))
        for line in out.split("\n")
    )
    cities = set(CITIES) | ({known["city"]} if known.get("city") else set())
    for city in sorted(cities, key=len, reverse=True):
        out = re.sub(rf"(?<!\w){re.escape(city)}(?!\w)", variant["city"], out)
    return out


def score_text(text: str, req: JobRequirements, matcher: SkillMatcher, today: date):
    found = extract_skills(text, matcher)
    exp = estimate_experience(text, today=today)
    facts = ScoringInput(
        skills=tuple(sorted((e.slug, e.section) for e in found.values())), experience_years=exp.years
    )
    return score(facts, req)


@dataclass
class CheckResult:
    applications: int
    variants: int
    changes: int
    examples: list


def check(items, matcher: SkillMatcher, variants_per_item: int = 3, today: date | None = None) -> CheckResult:
    """items: iterable of (label, text, known_values, JobRequirements)."""
    today = today or date.today()
    apps = variants = changes = 0
    examples = []
    for index, (label, text, known, req) in enumerate(items):
        apps += 1
        base = score_text(text, req, matcher, today)
        for k in range(variants_per_item):
            variant = VARIANTS[(index + k) % len(VARIANTS)]
            other = score_text(make_variant(text, known, variant), req, matcher, today)
            variants += 1
            if (other.score, other.band, other.explanation) != (base.score, base.band, base.explanation):
                changes += 1
                if len(examples) < 10:
                    examples.append(
                        {
                            "application": label,
                            "variant": variant["gender"],
                            "original": base.score,
                            "variant_score": other.score,
                        }
                    )
    return CheckResult(apps, variants, changes, examples)
