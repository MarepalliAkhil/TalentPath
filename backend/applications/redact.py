"""Redaction for blind screening. Pure functions, standard library only.

Replaces with [hidden]: the candidate's own known values (name parts, email,
phone, address, city), any email / phone / URL, personal-detail labels
(age, date of birth, gender...), and education-institution names.
"""

import re

HIDDEN = "[hidden]"

INSTITUTION_WORD = re.compile(
    r"\b(university|universities|college|institute|institution|school|academy|vidyalaya|"
    r"vidyapeeth|vidyapith|polytechnic|iit|iiit|nit|iim|bits)\b",
    re.IGNORECASE,
)
KNOWN_INSTITUTIONS = [
    "BITS Pilani",
    "VIT",
    "VIT Vellore",
    "SRM",
    "Manipal",
    "Amity",
    "KL University",
    "KLU",
    "Anna University",
    "Osmania University",
    "JNTU",
    "JNTUH",
    "JNTUK",
    "Andhra University",
    "Delhi University",
    "Jadavpur University",
    "Christ University",
    "Symbiosis",
    "Amrita",
    "Thapar",
    "PSG Tech",
    "LPU",
    "Lovely Professional University",
    "Chandigarh University",
    "Mumbai University",
    "Pune University",
    "Savitribai Phule Pune University",
    "GITAM",
    "CBIT",
    "VNR VJIET",
    "Vasavi",
    "MVGR",
    "IIIT Hyderabad",
    "BHU",
    "AMU",
    "DTU",
    "NSUT",
    "COEP",
    "VJTI",
    "RVCE",
    "BMSCE",
    "PES University",
    "MIT Manipal",
    "SASTRA",
    "NMIMS",
]
_KNOWN_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in sorted(KNOWN_INSTITUTIONS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b(?:linkedin|github|gitlab|behance)\.com/\S*", re.IGNORECASE)
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
PERSONAL_LABEL_RE = re.compile(
    r"\b(age|date of birth|d\.?o\.?b|gender|sex|marital status|nationality|religion|caste|"
    r"father'?s name|mother'?s name|address)\s*[:\-–]\s*[^\n|,]*[^\s|,]",
    re.IGNORECASE,
)
_CAP = r"[A-Z][\w.&'’-]*"
INSTITUTION_PHRASE_RE = re.compile(
    rf"(?:{_CAP}\s+(?:(?:of|and|for|&)\s+)?){{0,5}}"
    r"(?:University|College|Institute|Institution|School|Academy|Vidyalaya|Vidyapeeth|Polytechnic)"
    rf"(?:\s+(?:of|for)(?:\s+(?:and\s+|&\s+)?{_CAP}){{1,5}})?"
    rf"|\b(?:IIT|IIIT|NIT|IIM|BITS)\b(?:[\s,-]+{_CAP})?"
)
_SEGMENT_SPLIT = re.compile(r"(\s*[,|•;]\s*|\s+[-–—]\s+)")


def _phone(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return HIDDEN if len(digits) >= 10 else match.group(0)


def _redact_institutions(line: str) -> str:
    line = _KNOWN_RE.sub(HIDDEN, line)
    line = INSTITUTION_PHRASE_RE.sub(HIDDEN, line)
    if not (INSTITUTION_WORD.search(line) or _KNOWN_RE.search(line)):
        return line
    parts = _SEGMENT_SPLIT.split(line)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 0 and (INSTITUTION_WORD.search(part) or _KNOWN_RE.search(part)):
            out.append(HIDDEN)
        else:
            out.append(part)
    return "".join(out)


def _known_patterns(known: dict) -> list[re.Pattern]:
    values: list[str] = []
    name = (known.get("full_name") or "").strip()
    if name:
        values.append(name)
        values += [p for p in re.split(r"\s+", name) if len(p) >= 2]
    for key in ("email", "city"):
        if known.get(key):
            values.append(known[key].strip())
    address = (known.get("address") or "").strip()
    if address:
        values.append(address)
        values += [p.strip() for p in address.split(",") if len(p.strip()) >= 4]
    patterns = [re.compile(r"(?<!\w)" + re.escape(v) + r"(?!\w)", re.IGNORECASE) for v in values if v]
    phone_digits = re.sub(r"\D", "", known.get("phone") or "")
    if len(phone_digits) >= 7:
        tail = r"[\s().-]*".join(re.escape(d) for d in phone_digits[-10:])
        patterns.append(re.compile(r"(?:\+?\d{1,3}[\s().-]*)?" + tail))
    return sorted(patterns, key=lambda p: len(p.pattern), reverse=True)


def redact(text: str, known: dict | None = None) -> str:
    if not text:
        return ""
    for pattern in _known_patterns(known or {}):
        text = pattern.sub(HIDDEN, text)
    text = EMAIL_RE.sub(HIDDEN, text)
    text = URL_RE.sub(HIDDEN, text)
    text = PHONE_RE.sub(_phone, text)
    text = PERSONAL_LABEL_RE.sub(lambda m: f"{m.group(1)}: {HIDDEN}", text)
    return "\n".join(_redact_institutions(line) for line in text.split("\n"))
