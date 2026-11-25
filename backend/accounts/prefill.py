"""Pre-fill a new candidate's profile from the resume they registered with (D-81).

Deterministic and standard library only: the same extractor as applications finds skills;
simple patterns find a phone number and profile links; the education and experience
sections become editable rows. Nothing here is guessed silently: the candidate reviews
every field on their profile before it is used anywhere.
"""

import json
import re

from matching.extract import split_sections

PHONE_RE = re.compile(r"(?:\+91[\s-]?)?(?:\(?0?\)?[\s-]?)?[6-9]\d{4}[\s-]?\d{5}")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})(/[^\s,;)]*)?", re.IGNORECASE)
DATE_RANGE_RE = re.compile(
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})"
    r"\s*(?:-|–|—|to)\s*"
    r"(present|current|now|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})",
    re.IGNORECASE,
)
SCORE_RE = re.compile(
    r"(\d{1,2}(?:\.\d{1,2})?)\s*(?:/\s*10|cgpa|gpa)|(\d{2}(?:\.\d{1,2})?)\s*%", re.IGNORECASE
)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
DEGREE_WORDS = (
    "b.tech",
    "btech",
    "b.e",
    "m.tech",
    "mtech",
    "bsc",
    "b.sc",
    "msc",
    "m.sc",
    "mba",
    "bca",
    "mca",
    "b.com",
    "bcom",
    "bachelor",
    "master",
    "diploma",
    "phd",
    "class xii",
    "class x",
    "12th",
    "10th",
)


def _clean_url(match: re.Match) -> str:
    host, path = match.group(1).lower(), (match.group(2) or "").rstrip(".")
    return f"https://{host}{path}"


def find_links(text: str) -> dict:
    links = {"linkedin_url": "", "github_url": "", "portfolio_url": ""}
    for match in URL_RE.finditer(text or ""):
        url = _clean_url(match)
        host = match.group(1).lower()
        if "@" in text[max(0, match.start() - 1) : match.start()]:
            continue  # part of an email address
        if host.endswith("linkedin.com") and "/in/" in url and not links["linkedin_url"]:
            links["linkedin_url"] = url
        elif host.endswith("github.com") and match.group(2) and not links["github_url"]:
            links["github_url"] = url
        elif (
            not links["portfolio_url"]
            and match.group(2) is not None
            and not host.endswith(("linkedin.com", "github.com"))
            and "." in host
        ):
            links["portfolio_url"] = url
    return links


def find_phone(text: str) -> str:
    match = PHONE_RE.search(text or "")
    if not match:
        return ""
    digits = re.sub(r"\D", "", match.group(0))[-10:]
    return f"+91 {digits[:5]} {digits[5:]}" if len(digits) == 10 else ""


def education_rows(lines: list[str]) -> list[dict]:
    rows = []
    for line in lines:
        lowered = line.lower()
        if not any(word in lowered for word in DEGREE_WORDS) and not YEAR_RE.search(line):
            continue
        score = SCORE_RE.search(line)
        year = YEAR_RE.findall(line)
        parts = [p.strip() for p in re.split(r"[,|–—-]", line) if p.strip()]
        rows.append(
            {
                "qualification": parts[0][:120] if parts else line[:120],
                "college": parts[1][:120] if len(parts) > 1 else "",
                "branch": "",
                "year": year[-1] if year else "",
                "score": (score.group(1) or score.group(2)) if score else "",
            }
        )
    return rows[:6]


def experience_rows(lines: list[str]) -> list[dict]:
    rows: list[dict] = []
    for line in lines:
        dates = DATE_RANGE_RE.search(line)
        if dates:
            head = line[: dates.start()].strip(" ,|–—-")
            parts = [p.strip() for p in re.split(r",| at | \| ", head) if p.strip()]
            rows.append(
                {
                    "title": parts[0][:120] if parts else head[:120],
                    "company": parts[1][:120] if len(parts) > 1 else "",
                    "start": dates.group(1),
                    "end": dates.group(2),
                    "responsibilities": "",
                }
            )
        elif rows and len(rows[-1]["responsibilities"]) < 600:
            bullet = line.lstrip("-•*· ").strip()
            rows[-1]["responsibilities"] = (rows[-1]["responsibilities"] + "\n" + bullet).strip()
    return rows[:8]


def prefill_from_resume(text: str, skills: list[dict]) -> dict:
    """Profile fields to pre-fill. `skills` are the extractor's [{slug, name, section}]."""
    sections = split_sections(text or "")
    edu = [line for section, line in sections if section == "education"]
    exp = [line for section, line in sections if section == "experience"]
    return {
        "phone": find_phone(text),
        **find_links(text),
        "skills": sorted({s["name"] for s in skills})[:60],
        "education": education_rows(edu),
        "experience": experience_rows(exp),
    }


def dumps(rows) -> str:
    return json.dumps(rows or [], ensure_ascii=False)


def loads(raw: str) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []
