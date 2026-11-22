"""Ask HIRA: a rule-based candidate assistant. Deterministic, standard library only.

Pipeline: normalise (lowercase, Hinglish words, short forms) -> spell-correct
against the vocabulary -> keyword intent scoring -> BM25 over knowledge entries
when no intent is clear. Entities (skill, location, work mode) come from the
skill taxonomy and the location list.
"""

import difflib
import math
import re
from collections import Counter
from dataclasses import dataclass, field

STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "am",
    "i",
    "me",
    "my",
    "to",
    "for",
    "of",
    "in",
    "on",
    "and",
    "or",
    "do",
    "does",
    "did",
    "can",
    "could",
    "you",
    "your",
    "it",
    "this",
    "that",
    "with",
    "be",
    "please",
    "pls",
    "plz",
    "what",
    "how",
    "any",
    "there",
    "at",
    "from",
    "about",
    "have",
    "has",
    "will",
    "would",
    "should",
    "we",
    "us",
    "our",
    "so",
    "if",
    "as",
    "by",
    "up",
    "get",
    "want",
    "need",
}

# Hinglish and chat short forms written in English letters -> English.
NORMALISE = {
    "mera": "my",
    "meri": "my",
    "mere": "my",
    "mujhe": "me",
    "muje": "me",
    "hamara": "my",
    "kya": "what",
    "kyaa": "what",
    "hai": "is",
    "hain": "are",
    "kaha": "where",
    "kahan": "where",
    "kaise": "how",
    "kese": "how",
    "kaisa": "how",
    "kab": "when",
    "kitna": "how much",
    "naukri": "jobs",
    "naukriyan": "jobs",
    "kaam": "job",
    "chahiye": "need",
    "chaiye": "need",
    "batao": "tell",
    "bataiye": "tell",
    "bata": "tell",
    "dikhao": "show",
    "dikha": "show",
    "liye": "for",
    "ke": "",
    "ka": "",
    "ki": "",
    "ko": "",
    "se": "with",
    "mein": "in",
    "me": "me",
    "wapas": "withdraw",
    "baat": "talk",
    "karni": "",
    "karna": "",
    "karo": "",
    "karu": "",
    "kar": "",
    "bhedbhav": "bias",
    "sahi": "fair",
    "theek": "fair",
    "achha": "good",
    "koi": "any",
    "hyd": "hyderabad",
    "blr": "bengaluru",
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "madras": "chennai",
    "wfh": "remote",
    "u": "you",
    "ur": "your",
    "r": "are",
    "pls": "please",
    "plz": "please",
    "thx": "thanks",
    "ty": "thanks",
    "appln": "application",
    "app": "application",
    "applic": "application",
    "stat": "status",
    "sts": "status",
    "recruter": "recruiter",
    "hr": "recruiter",
    "jobz": "jobs",
    "vacancies": "openings",
    "vacancy": "openings",
}

INTENT_KEYWORDS = {
    "greeting": {
        "hi": 3,
        "hello": 3,
        "hey": 3,
        "namaste": 3,
        "hii": 3,
        "thanks": 3,
        "thank": 3,
        "morning": 1,
    },
    "application_status": {
        "status": 3,
        "application": 1.5,
        "applications": 1.5,
        "applied": 1.5,
        "progress": 2,
        "stage": 2,
        "update": 1.5,
        "heard": 1.5,
        "shortlisted": 2.5,
        "selected": 2,
        "result": 1.5,
        "track": 2,
        "where": 0.5,
    },
    "job_search": {
        "jobs": 2,
        "job": 1.5,
        "openings": 2.5,
        "roles": 1.5,
        "role": 1,
        "positions": 2,
        "position": 1.5,
        "hiring": 1.5,
        "find": 1,
        "search": 1.5,
        "show": 1,
        "available": 1,
        "open": 1,
        "list": 1,
    },
    "matching_jobs": {
        "match": 3,
        "matches": 3,
        "matching": 1,
        "suit": 3,
        "suitable": 3,
        "recommend": 3,
        "fit": 1.5,
        "profile": 1,
    },
    "how_matching_works": {
        "matching": 2,
        "score": 2.5,
        "scored": 2.5,
        "ranking": 2.5,
        "ranked": 2.5,
        "algorithm": 3,
        "ai": 1.5,
        "works": 1,
        "work": 0.5,
        "calculated": 2,
        "decide": 1.5,
        "explain": 1,
    },
    "is_screening_fair": {
        "fair": 3.5,
        "fairness": 3.5,
        "bias": 3.5,
        "biased": 3.5,
        "discrimination": 3.5,
        "discriminate": 3.5,
        "blind": 3,
        "anonymous": 2.5,
        "gender": 2,
        "caste": 2,
        "religion": 2,
        "equal": 2,
    },
    "how_withdraw": {"withdraw": 4, "cancel": 3, "retract": 3, "remove": 1.5, "delete": 1.5, "back": 0.5},
    "talk_to_recruiter": {
        "recruiter": 3,
        "talk": 2,
        "speak": 2,
        "contact": 2,
        "human": 2.5,
        "person": 1.5,
        "message": 2,
        "call": 1.5,
        "reach": 1.5,
        "connect": 1.5,
        "chat": 1,
    },
}
PHRASES = {
    "matching_jobs": [
        "my skills",
        "match me",
        "for my profile",
        "suit me",
        "right for me",
        "jobs for me",
        "match my",
    ],
    "how_matching_works": [
        "how does matching",
        "how matching",
        "how is score",
        "how are candidates ranked",
        "why my score",
    ],
    "application_status": ["my application", "what happened", "any update", "hear back"],
    "talk_to_recruiter": ["talk to", "speak to", "real person"],
    "how_withdraw": ["take back", "withdraw my", "cancel my"],
}
WORK_MODES = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite", "office": "onsite"}
INTENT_THRESHOLD = 2.5
FAQ_THRESHOLD = 1.0


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+#.]+", text.lower())


@dataclass
class Context:
    skill_matcher: object  # matching.extract.SkillMatcher
    locations: dict  # lowercase name or alias -> slug
    knowledge: list  # [{"key","question","keywords","answer","link"}]
    vocabulary: set = field(default_factory=set)
    _bm25: object = None

    def __post_init__(self):
        vocab = set(NORMALISE.values()) | set(WORK_MODES)
        for weights in INTENT_KEYWORDS.values():
            vocab.update(weights)
        for phrases in PHRASES.values():
            for p in phrases:
                vocab.update(p.split())
        vocab.update(t for name in self.locations for t in _tokens(name))
        for key in self.skill_matcher.index:
            vocab.update(k for k in key if len(k) >= 4)
        for entry in self.knowledge:
            vocab.update(_tokens(entry["question"] + " " + entry["keywords"]))
        self.vocabulary = {v for v in vocab if v}
        self._bm25 = BM25(
            [
                _content(
                    entry["question"]
                    + " "
                    + entry["question"]
                    + " "
                    + entry["keywords"]
                    + " "
                    + entry["keywords"]
                    + " "
                    + entry["answer"]
                )
                for entry in self.knowledge
            ]
        )


def _content(text: str) -> list[str]:
    return [t for t in _tokens(text) if t not in STOPWORDS]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avgdl = (sum(len(d) for d in docs) / len(docs)) if docs else 0
        self.tf = [Counter(d) for d in docs]
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for tf, doc in zip(self.tf, self.docs, strict=True):
            s = 0.0
            for q in query:
                if q in tf:
                    f = tf[q]
                    s += (
                        self.idf[q]
                        * f
                        * (self.k1 + 1)
                        / (f + self.k1 * (1 - self.b + self.b * len(doc) / self.avgdl))
                    )
            out.append(s)
        return out


def normalise(text: str, ctx: Context) -> tuple[str, list[str]]:
    words = []
    for tok in _tokens(text):
        mapped = NORMALISE.get(tok, tok)
        words.extend(mapped.split())
    corrected = []
    for tok in words:
        if tok in ctx.vocabulary or tok in STOPWORDS or len(tok) < 4 or not tok.isalpha():
            corrected.append(tok)
            continue
        cutoff = 0.8 if len(tok) < 7 else 0.75
        close = difflib.get_close_matches(tok, ctx.vocabulary, n=1, cutoff=cutoff)
        corrected.append(close[0] if close else tok)
    return " ".join(corrected), corrected


@dataclass
class Understanding:
    intent: str
    text: str
    skills: list  # [(slug, name)]
    location: str | None
    work_mode: str | None
    faq_key: str | None
    scores: dict


def understand(message: str, ctx: Context) -> Understanding:
    text, tokens = normalise(message, ctx)
    scores = {intent: 0.0 for intent in INTENT_KEYWORDS}
    for intent, weights in INTENT_KEYWORDS.items():
        scores[intent] += sum(weights.get(t, 0) for t in tokens)
    for intent, phrases in PHRASES.items():
        scores[intent] += sum(3 for p in phrases if p in text)

    skills, seen = [], set()
    for ref in ctx.skill_matcher.find(text, allow_ambiguous=False):
        if ref.slug not in seen:
            seen.add(ref.slug)
            skills.append((ref.slug, ref.name))
    location = None
    padded = f" {text} "
    for name in sorted(ctx.locations, key=len, reverse=True):
        if f" {name} " in padded:
            location = ctx.locations[name]
            break
    work_mode = next((WORK_MODES[t] for t in tokens if t in WORK_MODES), None)
    if skills or location or work_mode:
        scores["job_search"] += 2.5
    if scores["matching_jobs"] >= 3:
        scores["job_search"] -= 1  # "jobs that match my skills" is about the candidate's profile
    if scores["how_matching_works"] and ("score" in tokens or "ranked" in tokens or "ranking" in tokens):
        scores["matching_jobs"] -= 1

    best = max(scores, key=lambda k: scores[k])
    faq_key = None
    if scores[best] < INTENT_THRESHOLD:
        ranked = ctx._bm25.scores([t for t in tokens if t not in STOPWORDS]) if ctx.knowledge else []
        if ranked and max(ranked) >= FAQ_THRESHOLD:
            faq_key = ctx.knowledge[ranked.index(max(ranked))]["key"]
            best = "faq"
        else:
            best = "fallback"
    return Understanding(best, text, skills, location, work_mode, faq_key, scores)
