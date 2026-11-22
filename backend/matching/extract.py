"""Deterministic resume parsing: sections, skills with evidence, experience years.

Standard library only. The skill matcher is built from (slug, name, synonyms)
rows, so it works from the database taxonomy or from org.taxonomy_data.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from .weights import EVIDENCE_STRENGTH

# ----------------------------------------------------------------- sections
SECTION_HEADERS = {
    "skills": [
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "skills and tools",
        "skills & tools",
        "tools",
        "technologies",
        "tech stack",
        "core competencies",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "internships",
        "internship",
        "experience and internships",
    ],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "project work"],
    "education": ["education", "academics", "academic background", "qualifications", "education details"],
    "certifications": ["certifications", "certificates", "licenses", "courses", "certifications and courses"],
    "summary": [
        "summary",
        "profile",
        "about",
        "about me",
        "objective",
        "career objective",
        "professional summary",
    ],
}
_HEADER_LOOKUP = {h: section for section, headers in SECTION_HEADERS.items() for h in headers}


def _header_key(line: str) -> str:
    key = line.strip().strip(":-–—|#*").strip().lower()
    key = re.sub(r"\s+", " ", key)
    return key


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (section, line) pairs. Lines before the first header are 'other'."""
    out: list[tuple[str, str]] = []
    current = "other"
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        key = _header_key(line)
        if len(key) <= 40 and key in _HEADER_LOOKUP:
            current = _HEADER_LOOKUP[key]
            continue
        out.append((current, line))
    return out


# ------------------------------------------------------------- tokenisation
_SPLIT = re.compile(r"[\s,;:()\[\]{}|/\\<>\"'!?•·*]+")


def normalise_token(token: str) -> str:
    token = token.lower().strip()
    token = token.strip("-–—_=~`")
    token = token.rstrip(".")
    if not token:
        return ""
    lead = "." if token.startswith(".") and len(token) > 1 and token[1].isalpha() else ""
    body = token.lstrip(".")
    body = body.replace(".", "").replace("-", "").replace("–", "")
    body = body.replace("&", "and")
    return lead + body


def tokenize(text: str) -> list[str]:
    tokens = []
    for part in _SPLIT.split(text or ""):
        tok = normalise_token(part)
        if tok:
            tokens.append(tok)
    return tokens


# ------------------------------------------------------------- skill matcher
# Aliases that are also everyday words (or one or two letters) only count inside
# a skills section, so "go to market" or a person named Ruby is not a skill.
AMBIGUOUS = {
    "go",
    "r",
    "c",
    "rest",
    "express",
    "spark",
    "swift",
    "dart",
    "ruby",
    "helm",
    "flask",
    "jest",
    "lean",
    "node",
    "next",
    "nest",
    "vue",
    "rails",
    "elastic",
    "torch",
    "shell",
    "sh",
    "ps",
    "pm",
    "pr",
    "ba",
    "er",
    "ta",
    "ia",
    "cv",
    "dl",
    "tf",
    "kt",
    "rn",
    "ml",
    "ts",
    "py",
    "kam",
    "sem",
    "smm",
    "ixd",
    "spring",
    "excel",
    "kafka",
    "airflow",
    "snowflake",
    "tableau",
    "android",
    "ios",
    "linux",
    "git",
    "agile",
    "scrum",
    "kanban",
    "lambda",
    "networking",
    "monitoring",
    "logging",
    "tracing",
    "encryption",
    "training",
    "coaching",
    "empathy",
    "privacy",
    "compliance",
    "contracts",
    "analytics",
    "branding",
    "dashboards",
    "presenting",
    "teamwork",
    "documentation",
    "recruiting",
    "recruitment",
    "prioritisation",
    "prioritization",
    "outbound",
    "prospecting",
    "purchasing",
    "logistics",
    "bookkeeping",
    "stats",
    "hindi",
    "telugu",
    "tamil",
    "kannada",
    "english",
    "net",
    "ux",
    "ui",
    "qa",
    "seo",
    "crm",
    "erp",
    "hr",
}


@dataclass(frozen=True)
class SkillRef:
    slug: str
    name: str


@dataclass
class SkillMatcher:
    index: dict = field(default_factory=dict)  # tuple(tokens) -> (SkillRef, ambiguous)
    max_len: int = 1

    @classmethod
    def build(cls, rows) -> "SkillMatcher":
        """rows: iterable of (slug, name, synonyms)."""
        matcher = cls()
        for slug, name, synonyms in rows:
            ref = SkillRef(slug, name)
            for alias in [name, *(synonyms or [])]:
                key = tuple(tokenize(alias))
                if not key:
                    continue
                ambiguous = len(key) == 1 and (key[0] in AMBIGUOUS or len(key[0]) <= 1)
                current = matcher.index.get(key)
                # Prefer the canonical name's own skill when aliases collide.
                if current is None or alias == name:
                    matcher.index[key] = (ref, ambiguous)
                matcher.max_len = max(matcher.max_len, len(key))
        return matcher

    def find(self, text: str, *, allow_ambiguous: bool) -> list[SkillRef]:
        tokens = tokenize(text)
        found: list[SkillRef] = []
        i = 0
        while i < len(tokens):
            for n in range(min(self.max_len, len(tokens) - i), 0, -1):
                hit = self.index.get(tuple(tokens[i : i + n]))
                if hit and (allow_ambiguous or not hit[1]):
                    found.append(hit[0])
                    i += n
                    break
            else:
                i += 1
        return found


# ----------------------------------------------------------------- evidence
SECTION_PRIORITY = ["experience", "projects", "certifications", "skills", "summary", "education", "other"]


@dataclass
class SkillEvidence:
    slug: str
    name: str
    section: str
    snippet: str

    def as_dict(self) -> dict:
        return {"slug": self.slug, "name": self.name, "section": self.section, "snippet": self.snippet}


def extract_skills(text: str, matcher: SkillMatcher) -> dict[str, SkillEvidence]:
    """Strongest evidence per skill slug."""
    best: dict[str, SkillEvidence] = {}
    for section, line in split_sections(text):
        for ref in matcher.find(line, allow_ambiguous=(section == "skills")):
            current = best.get(ref.slug)
            if current is None or SECTION_PRIORITY.index(section) < SECTION_PRIORITY.index(current.section):
                best[ref.slug] = SkillEvidence(ref.slug, ref.name, section, line[:140])
    return best


def evidence_strength(section: str) -> float:
    return EVIDENCE_STRENGTH.get(section, EVIDENCE_STRENGTH["other"])


# ------------------------------------------------------------- experience
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_POINT = rf"(?:{_MONTH}\.?\s+(?:19|20)\d\d|(?:0?[1-9]|1[0-2])\s*/\s*(?:19|20)\d\d|(?:19|20)\d\d)"
_END = rf"(?:{_POINT}|present|current|now|till date|to date|ongoing)"
RANGE_RE = re.compile(rf"({_POINT})\s*(?:-|–|—|to|until|till)\s*({_END})", re.IGNORECASE)
INTERN_RE = re.compile(r"\b(intern|internship|trainee|apprentice)\b", re.IGNORECASE)


def _parse_point(text: str, *, today: date, is_end: bool) -> tuple[int, int] | None:
    t = text.strip().lower().rstrip(".")
    if t in ("present", "current", "now", "till date", "to date", "ongoing"):
        return (today.year, today.month) if is_end else None
    m = re.match(rf"({_MONTH})\.?\s+((?:19|20)\d\d)$", t)
    if m:
        return int(m.group(2)), MONTHS[m.group(1)[:4] if m.group(1).startswith("sept") else m.group(1)[:3]]
    m = re.match(r"(\d{1,2})\s*/\s*((?:19|20)\d\d)$", t)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.match(r"((?:19|20)\d\d)$", t)
    if m:
        return int(m.group(1)), 1
    return None


def _months(start: tuple[int, int], end: tuple[int, int]) -> int:
    return (end[0] - start[0]) * 12 + (end[1] - start[1])


def _merge(intervals: list[tuple[int, int]]) -> int:
    total, last_end = 0, None
    for s, e in sorted(intervals):
        if last_end is None or s >= last_end:
            total += e - s
            last_end = e
        elif e > last_end:
            total += e - last_end
            last_end = e
    return total


@dataclass
class ExperienceEstimate:
    years: float | None  # full-time years; None means unknown (never guessed)
    internship_months: int | None
    ranges_found: int


def estimate_experience(text: str, *, today: date | None = None) -> ExperienceEstimate:
    today = today or date.today()
    full: list[tuple[int, int]] = []
    intern: list[tuple[int, int]] = []
    found = 0
    section, header = "other", ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        key = _header_key(line)
        if len(key) <= 40 and key in _HEADER_LOOKUP:
            section, header = _HEADER_LOOKUP[key], key
            continue
        if section != "experience":
            continue
        for m in RANGE_RE.finditer(line):
            start = _parse_point(m.group(1), today=today, is_end=False)
            end = _parse_point(m.group(2), today=today, is_end=True)
            if not start or not end:
                continue
            months = _months(start, end)
            if months <= 0 or months > 50 * 12 or end > (today.year, today.month):
                continue
            found += 1
            interval = (start[0] * 12 + start[1], end[0] * 12 + end[1])
            is_intern = header.startswith("internship") or INTERN_RE.search(line)
            (intern if is_intern else full).append(interval)
    if not found:
        return ExperienceEstimate(None, None, 0)
    years = round(_merge(full) / 12, 1) if full else 0.0
    return ExperienceEstimate(years, _merge(intern) if intern else 0, found)


def job_mentioned_skills(description: str, matcher: SkillMatcher) -> list[SkillRef]:
    seen, out = set(), []
    for ref in matcher.find(description, allow_ambiguous=False):
        if ref.slug not in seen:
            seen.add(ref.slug)
            out.append(ref)
    return out
