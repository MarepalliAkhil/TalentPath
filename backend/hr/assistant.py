"""Ask HIRA for employees: rule-based HR answers on the same engine as the
candidate assistant (normalise -> spell-correct -> keyword intents -> BM25).

Personal answers only ever read the signed-in person's own records. Applying
for leave returns a confirmation card with the engine's validation; the
employee presses Confirm in the widget, which calls the normal leave API. The
assistant never submits anything by itself.
"""

import difflib
import re
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from hira.engine import BM25, STOPWORDS, _tokens
from interviews.timeutil import today_ist

from . import leave as engine
from .models import Employee, HandbookSection, Holiday, LeaveType

NORMALISE = {
    # Hinglish (English letters) -> English
    "chutti": "leave",
    "chhutti": "leave",
    "chuti": "leave",
    "chhuti": "leave",
    "chuttiyan": "holidays",
    "chhuttiyan": "holidays",
    "chuttiyon": "holidays",
    "chhuttiyon": "holidays",
    "tyohar": "festival",
    "kitni": "how many",
    "kitne": "how many",
    "kitna": "how many",
    "baki": "left",
    "baaki": "left",
    "bachi": "left",
    "bache": "left",
    "bacha": "left",
    "mera": "my",
    "meri": "my",
    "mere": "my",
    "mujhe": "me",
    "muje": "me",
    "kaun": "who",
    "kon": "who",
    "hai": "is",
    "hain": "are",
    "kya": "what",
    "kab": "when",
    "kal": "tomorrow",
    "parso": "dayafter",
    "parson": "dayafter",
    "agle": "next",
    "agla": "next",
    "agli": "next",
    "chahiye": "need",
    "chaiye": "need",
    "lena": "take",
    "leni": "take",
    "lunga": "take",
    "lungi": "take",
    "batao": "tell",
    "bata": "tell",
    "dikhao": "show",
    "hajri": "attendance",
    "haziri": "attendance",
    "hazri": "attendance",
    "manzoor": "approve",
    "manjoor": "approve",
    "bimar": "sick",
    "beemar": "sick",
    "tabiyat": "sick",
    "bukhar": "fever",
    "somvar": "monday",
    "mangalvar": "tuesday",
    "budhvar": "wednesday",
    "guruvar": "thursday",
    "shukravar": "friday",
    "shanivar": "saturday",
    "ravivar": "sunday",
    "ka": "",
    "ki": "",
    "ke": "",
    "ko": "",
    "se": "",
    "mein": "in",
    "liye": "for",
    "hoon": "",
    "hu": "",
    "karo": "",
    "karna": "",
    "karni": "",
    # short forms
    "lv": "leave",
    "leav": "leave",
    "leaves": "leave",
    "hols": "holidays",
    "hol": "holiday",
    "u": "you",
    "r": "are",
    "pls": "please",
    "plz": "please",
    "tmrw": "tomorrow",
    "tmr": "tomorrow",
    "tomo": "tomorrow",
    "tom": "tomorrow",
    "fri": "friday",
    "mon": "monday",
    "tue": "tuesday",
    "tues": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "thurs": "thursday",
    "sat": "saturday",
    "sun": "sunday",
    "cl": "casual",
    "sl": "sick",
    "el": "earned",
    "pl": "earned",
    "wfh": "remote",
    "mgr": "manager",
    "boss": "manager",
}

INTENT_KEYWORDS = {
    "greeting": {"hi": 3, "hello": 3, "hey": 3, "namaste": 3, "thanks": 3, "thank": 3},
    "leave_balance": {
        "balance": 3.5,
        "left": 2.5,
        "remaining": 3,
        "many": 1,
        "leave": 1,
        "available": 1.5,
        "quota": 2,
        "entitled": 2,
    },
    "apply_leave": {
        "apply": 3,
        "take": 2,
        "book": 2,
        "request": 2,
        "need": 1,
        "want": 1,
        "off": 1.5,
        "leave": 1,
        "sick": 1,
        "fever": 1,
        "half": 1.5,
    },
    "holidays": {
        "holiday": 3.5,
        "holidays": 3.5,
        "festival": 3,
        "public": 1.5,
        "calendar": 1,
        "diwali": 2,
        "christmas": 2,
    },
    "my_buddy": {"buddy": 4.5, "mentor": 2.5},
    "my_manager": {"manager": 3.5, "report": 2, "reporting": 2.5, "lead": 1.5, "supervisor": 3},
    "onboarding_status": {
        "onboarding": 4,
        "checklist": 4,
        "tasks": 2.5,
        "task": 2.5,
        "joining": 1.5,
        "pending": 0.5,
        "documents": 1.5,
        "plan": 1,
        "first": 0.5,
        "week": 0.5,
    },
    "attendance_month": {
        "attendance": 4,
        "present": 2.5,
        "late": 2,
        "checkin": 2,
        "checked": 1.5,
        "absent": 2,
        "month": 0.5,
        "days": 0.5,
    },
    "pending_for_me": {
        "approve": 3,
        "approvals": 3.5,
        "approval": 3,
        "pending": 1.5,
        "requests": 1.5,
        "team": 1,
        "waiting": 1.5,
        "inbox": 2,
    },
}
PHRASES = {
    "leave_balance": ["how many leave", "leave left", "leave balance", "how many days"],
    "apply_leave": [
        "apply leave",
        "apply for leave",
        "take leave",
        "need leave",
        "leave on",
        "leave for",
        "day off",
    ],
    "holidays": ["next holiday", "holiday list", "upcoming holiday"],
    "my_manager": ["who is my manager", "report to", "who do i report"],
    "onboarding_status": ["my checklist", "onboarding status", "joining tasks"],
    "attendance_month": ["my attendance", "this month attendance", "check in", "days present"],
    "pending_for_me": [
        "pending for me",
        "waiting for me",
        "my approvals",
        "to approve",
        "what's pending",
        "whats pending",
    ],
}
POLICY_WORDS = {
    "policy",
    "rule",
    "rules",
    "sandwich",
    "carry",
    "forward",
    "notice",
    "document",
    "certificate",
    "maternity",
    "paternity",
    "handbook",
    "allowed",
    "encash",
    "probation",
    "dress",
    "code",
    "shift",
    "timings",
    "regularise",
    "regularisation",
    "regularize",
    "harassment",
    "posh",
    "laptop",
    "remote",
    "hybrid",
    "loss",
    "pay",
    "lop",
    "comp",
    "reimbursement",
    "expenses",
    "insurance",
}
INTENT_THRESHOLD = 2.5
POLICY_THRESHOLD = 1.2
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
TYPE_WORDS = {
    "casual": "casual",
    "sick": "sick",
    "fever": "sick",
    "unwell": "sick",
    "earned": "earned",
    "privilege": "earned",
    "vacation": "earned",
    "comp": "comp_off",
    "compoff": "comp_off",
    "lop": "lop",
    "unpaid": "lop",
}
CHIPS = [
    "How many leaves do I have left?",
    "Apply leave next Friday",
    "Upcoming holidays",
    "Who is my buddy?",
    "My attendance this month",
]
MANAGER_CHIP = "What's pending for me?"


@dataclass
class Parsed:
    intent: str
    text: str
    tokens: list
    start: date | None
    end: date | None
    half: str
    leave_type: str | None
    policy_hit: dict | None
    scores: dict


# ---------------------------------------------------------------- understanding
def _vocab():
    vocab = set(NORMALISE.values()) | set(WEEKDAYS) | set(MONTHS) | set(TYPE_WORDS) | POLICY_WORDS
    for weights in INTENT_KEYWORDS.values():
        vocab.update(weights)
    for phrases in PHRASES.values():
        for p in phrases:
            vocab.update(p.split())
    vocab.update({"tomorrow", "today", "next", "this", "week", "from", "till", "until", "dayafter"})
    return {v for v in vocab if v and v.isalpha() and len(v) >= 3}


VOCAB = _vocab()


def normalise(message: str) -> tuple[str, list]:
    raw = message.lower().replace("comp-off", "compoff").replace("comp off", "compoff")
    raw = raw.replace("check-in", "checkin").replace("check in", "checkin").replace("day after", "dayafter")
    raw = raw.replace("half-day", "half day").replace("what's", "whats")
    words = []
    for tok in re.findall(r"[a-z0-9/\-]+", raw):
        mapped = NORMALISE.get(tok, tok)
        words.extend(mapped.split())
    out = []
    for tok in words:
        if tok in VOCAB or tok in STOPWORDS or len(tok) < 4 or not tok.isalpha():
            out.append(tok)
            continue
        close = difflib.get_close_matches(tok, VOCAB, n=1, cutoff=0.8 if len(tok) < 7 else 0.75)
        out.append(close[0] if close else tok)
    return " ".join(out), out


def _next_weekday(today: date, index: int, *, strictly_next_week=False) -> date:
    ahead = (index - today.weekday()) % 7 or 7
    day = today + timedelta(days=ahead)
    if (
        strictly_next_week
        and day - today < timedelta(days=7)
        and day.isocalendar()[1] == today.isocalendar()[1]
    ):
        day += timedelta(days=7)
    return day


def _date_at(tokens: list, i: int, today: date) -> tuple[date | None, int]:
    """Try to read a date starting at tokens[i]. Returns (date, tokens consumed)."""
    tok = tokens[i]
    nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
    if tok == "today":
        return today, 1
    if tok == "tomorrow":
        return today + timedelta(days=1), 1
    if tok == "dayafter":
        return today + timedelta(days=2), 1 + (nxt == "tomorrow")
    if tok in ("next", "this", "coming") and nxt in WEEKDAYS:
        return _next_weekday(today, WEEKDAYS.index(nxt)), 2
    if tok == "next" and nxt == "week":
        return _next_weekday(today, 0), 2
    if tok in WEEKDAYS:
        return _next_weekday(today, WEEKDAYS.index(tok)), 1
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", tok)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])), 1
        except ValueError:
            return None, 1
    m = re.fullmatch(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", tok)
    if m:
        year = int(m[3]) if m[3] else today.year
        year += 2000 if year < 100 else 0
        try:
            day = date(year, int(m[2]), int(m[1]))
        except ValueError:
            return None, 1
        if not m[3] and day < today:
            day = date(year + 1, day.month, day.day)
        return day, 1
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", tok)
    if m and nxt in MONTHS:
        return _month_day(today, MONTHS[nxt], int(m[1])), 2
    if tok in MONTHS and re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)?", nxt or "x"):
        return _month_day(today, MONTHS[tok], int(re.match(r"\d+", nxt)[0])), 2
    return None, 0


def _month_day(today: date, month: int, day: int) -> date | None:
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if candidate >= today - timedelta(days=7):
            return candidate
    return None


def parse_dates(tokens: list, today: date) -> tuple[date | None, date | None]:
    found = []
    i = 0
    while i < len(tokens):
        day, used = _date_at(tokens, i, today)
        if day is not None:
            found.append(day)
            i += used
        else:
            i += max(used, 1)
    if not found:
        return None, None
    start = found[0]
    end = found[1] if len(found) > 1 and found[1] >= start else start
    text = " ".join(tokens)
    m = re.search(r"for (\d{1,2}) days?", text)
    if m and len(found) == 1:
        end = start + timedelta(days=int(m[1]) - 1)
    return start, end


def understand(message: str, today: date, policy_docs: list) -> Parsed:
    text, tokens = normalise(message)
    scores = {intent: 0.0 for intent in INTENT_KEYWORDS}
    for intent, weights in INTENT_KEYWORDS.items():
        scores[intent] += sum(weights.get(t, 0) for t in tokens)
    for intent, phrases in PHRASES.items():
        scores[intent] += sum(3 for p in phrases if p in text)
    start, end = parse_dates(tokens, today)
    half = "first" if "half" in tokens else ""
    leave_type = next((TYPE_WORDS[t] for t in tokens if t in TYPE_WORDS), None)
    leavey = "leave" in tokens or "off" in tokens or leave_type is not None or half
    if start and leavey:
        scores["apply_leave"] += 3
        scores["leave_balance"] -= 1
    if start and not leavey and scores["holidays"] == 0:
        scores["apply_leave"] += 1
    if "pending" in tokens and ("me" in tokens or "approve" in tokens or "team" in tokens):
        scores["pending_for_me"] += 1.5
    if any(t in tokens for t in ("late", "present", "absent", "checkin", "checked")):
        scores["attendance_month"] += 2  # "how many days was I late" is about attendance, not balance
    if "left" in tokens and leavey:
        scores["leave_balance"] += 1.5
    policy_signal = sum(1 for t in tokens if t in POLICY_WORDS)
    best = max(scores, key=lambda k: scores[k])
    policy_hit = None
    if policy_signal and policy_docs:
        hit, score = best_policy(tokens, policy_docs)
        strong_policy = (
            policy_signal >= 1
            and score >= POLICY_THRESHOLD
            and (
                scores[best] < INTENT_THRESHOLD + 2
                or policy_signal >= 2
                or "policy" in tokens
                or "rule" in tokens
            )
        )
        if strong_policy and not (best == "apply_leave" and start):
            best, policy_hit = "policy", hit
    if best != "policy" and scores[best] < INTENT_THRESHOLD:
        hit, score = best_policy(tokens, policy_docs) if policy_docs else (None, 0)
        if hit and score >= POLICY_THRESHOLD:
            best, policy_hit = "policy", hit
        else:
            best = "fallback"
    return Parsed(best, text, tokens, start, end, half, leave_type, policy_hit, scores)


def best_policy(tokens, docs) -> tuple[dict | None, float]:
    bm25 = BM25(
        [_content(d["title"] + " " + d["title"] + " " + d["keywords"] + " " + d["body"]) for d in docs]
    )
    query = [t for t in tokens if t not in STOPWORDS]
    scores = bm25.scores(query)
    if not scores:
        return None, 0
    top = max(scores)
    return docs[scores.index(top)], top


def _content(text: str) -> list:
    return [t for t in _tokens(text) if t not in STOPWORDS]


# ---------------------------------------------------------------- sources
def policy_docs(employee) -> list[dict]:
    docs = [
        {
            "slug": s.slug,
            "title": s.title,
            "keywords": s.keywords,
            "body": s.body,
            "link": f"/hr/policies#{s.slug}",
        }
        for s in HandbookSection.objects.all()
    ]
    if employee is not None:
        for lt in LeaveType.objects.filter(location=employee.location, active=True):
            docs.append(
                {
                    "slug": f"leave-{lt.code}",
                    "title": f"{lt.name} policy ({employee.location.name})",
                    "keywords": f"{lt.name} {lt.code} leave policy rules",
                    "body": describe_leave_type(lt),
                    "link": f"/hr/policies#leave-{lt.code}",
                }
            )
    return docs


def describe_leave_type(lt) -> str:
    parts = []
    if lt.unpaid:
        parts.append(f"{lt.name} is unpaid and has no balance.")
    elif lt.yearly_quota:
        how = "credited monthly" if lt.monthly_accrual else "granted on 1 January"
        parts.append(f"{lt.name}: {engine.fmt_days(lt.yearly_quota)} a year, {how}.")
        if lt.prorate_joiners:
            parts.append("Joiners get a prorated share from their joining month.")
        if lt.carry_forward_cap:
            parts.append(
                f"Up to {engine.fmt_days(lt.carry_forward_cap)} carry forward to next year; the rest lapses."
            )
        else:
            parts.append("Unused days do not carry forward.")
    else:
        parts.append(f"{lt.name} is credited by HR when earned.")
    parts.append(f"Notice: {lt.min_notice_days} days." if lt.min_notice_days else "No advance notice needed.")
    if lt.backdate_days:
        parts.append(f"Can be applied up to {lt.backdate_days} days after it was taken.")
    if lt.max_consecutive_days:
        parts.append(f"At most {engine.fmt_days(lt.max_consecutive_days)} in one request.")
    parts.append("Half days allowed." if lt.half_day_allowed else "Full days only.")
    if lt.document_after_days is not None:
        parts.append(f"A document is required for more than {engine.fmt_days(lt.document_after_days)}.")
    parts.append(
        "Sandwich rule on: weekends and holidays between leave days are counted."
        if lt.sandwich_rule
        else "Sandwich rule off: weekends and holidays inside the leave are not counted."
    )
    return " ".join(parts)


# ---------------------------------------------------------------- answers
def _reply(intent: str, answer: str, user, **extra) -> dict:
    from .leave import approvals_for

    chips = list(CHIPS)
    if approvals_for(user).exists() or Employee.objects.filter(manager__user=user).exists():
        chips.insert(1, MANAGER_CHIP)
    data = {
        "intent": intent,
        "answer": answer,
        "chips": chips[:6],
        "jobs": [],
        "applications": [],
        "action": None,
        "link": None,
        "needs_sign_in": False,
        "card": None,
    }
    data.update(extra)
    return data


def _mentions_colleague(tokens, employee) -> str | None:
    names = set()
    for full in Employee.objects.exclude(pk=employee.pk).values_list("user__full_name", flat=True):
        for part in full.lower().split():
            if len(part) >= 4:
                names.add(part)
    own = set(employee.name.lower().split())
    hit = next((t for t in tokens if t in names and t not in own), None)
    return hit


def answer(message: str, user, *, today: date | None = None) -> dict:
    today = today or today_ist(timezone.now())
    employee = (
        Employee.objects.select_related(
            "user", "manager__user", "buddy__user", "department", "location", "buddy__department"
        )
        .filter(user=user)
        .first()
    )
    if employee is None:
        return None
    docs = policy_docs(employee)
    p = understand(message, today, docs)
    first = user.full_name.split()[0]

    colleague = _mentions_colleague(p.tokens, employee)
    if colleague and p.intent in ("leave_balance", "attendance_month", "apply_leave", "fallback"):
        return _reply(
            "privacy",
            "I can only share your own leave and attendance. "
            "Managers can see their team on the team calendar.",
            user,
            link="/team-calendar",
        )

    if p.intent == "greeting":
        return _reply(
            p.intent, f"Hi {first}, I am HIRA. Ask me about leave, holidays, attendance or onboarding.", user
        )

    if p.intent == "leave_balance":
        rows = engine.balances(employee, today=today)
        wanted = [r for r in rows if p.leave_type and r["type"] == p.leave_type]
        shown = wanted or [r for r in rows if not r["unpaid"]]
        text = (
            "; ".join(f"{r['name']}: {engine.fmt_days(r['available'])}" for r in shown)
            or "No leave types are set up for your location yet."
        )
        return _reply(
            p.intent,
            f"Available now: {text}." if shown else text,
            user,
            card={"kind": "balances", "rows": rows},
            link="/leave",
        )

    if p.intent == "apply_leave":
        if p.start is None:
            return _reply(
                p.intent,
                "Which date? Try “apply casual leave next Friday” or “sick leave tomorrow”.",
                user,
                link="/leave",
            )
        payload = {
            "leave_type": p.leave_type or "casual",
            "start": p.start.isoformat(),
            "end": (p.end or p.start).isoformat(),
            "half": p.half if p.half and p.start == (p.end or p.start) else "",
            "reason": "",
        }
        result = engine.check(employee, payload, today=today)
        lt = LeaveType.objects.filter(location=employee.location, code=payload["leave_type"]).first()
        name = lt.name.lower() if lt else payload["leave_type"]
        when = engine.nice_date(p.start) + (
            f" to {engine.nice_date(p.end)}" if p.end and p.end != p.start else ""
        )
        if result.errors:
            text = f"I checked {name} for {when}, but it cannot be submitted as it is: " + " ".join(
                result.errors.values()
            )
        else:
            text = (
                f"Here is {name} for {when}: {engine.fmt_days(result.days)}. "
                "Press Confirm to send it to your manager."
            )
        return _reply(
            p.intent,
            text,
            user,
            card={
                "kind": "leave_confirm",
                "payload": payload,
                "check": result.as_dict(),
                "type_name": lt.name if lt else "",
            },
        )

    if p.intent == "holidays":
        upcoming = list(
            Holiday.objects.filter(location=employee.location, date__gte=today).order_by("date")[:6]
        )
        if not upcoming:
            return _reply(
                p.intent, f"No more holidays are listed for {employee.location.name} this year.", user
            )
        rows = [{"date": h.date.isoformat(), "name": h.name, "regional": h.regional} for h in upcoming]
        nxt = upcoming[0]
        return _reply(
            p.intent,
            f"Next holiday in {employee.location.name}: {nxt.name} on {engine.nice_date(nxt.date)}.",
            user,
            card={
                "kind": "holidays",
                "rows": rows,
                "note": "Demo holiday calendar: verify dates before relying on them.",
            },
            link="/hr/policies#holidays",
        )

    if p.intent == "my_buddy":
        if employee.buddy is None:
            return _reply(p.intent, "You do not have an onboarding buddy assigned. HR can set one up.", user)
        b = employee.buddy
        return _reply(
            p.intent,
            f"Your buddy is {b.name}, {b.designation} in {b.department.name}. "
            "Lunch with them is on your first-week plan.",
            user,
            card={
                "kind": "person",
                "name": b.name,
                "designation": b.designation,
                "role": "Buddy",
                "email": b.user.email,
            },
            link="/welcome",
        )

    if p.intent == "my_manager":
        if employee.manager is None:
            return _reply(
                p.intent, "You do not report to anyone in TalentPath. HR approves your leave.", user
            )
        m = employee.manager
        return _reply(
            p.intent,
            f"You report to {m.name}, {m.designation}. They approve your leave and attendance corrections.",
            user,
            card={
                "kind": "person",
                "name": m.name,
                "designation": m.designation,
                "role": "Reporting manager",
                "email": m.user.email,
            },
        )

    if p.intent == "onboarding_status":
        from .onboarding import progress

        tasks = list(employee.tasks.all())
        if not tasks:
            return _reply(
                p.intent, "You have no onboarding checklist. It is created when someone is hired.", user
            )
        prog = progress(employee)
        pending = [t for t in tasks if not t.done_at]
        names = ", ".join(t.title for t in pending[:3])
        text = f"Onboarding is {prog['percent']}% done ({prog['done']} of {prog['total']})." + (
            f" Next: {names}." if pending else " All done."
        )
        return _reply(
            p.intent,
            text,
            user,
            card={
                "kind": "checklist",
                "progress": prog,
                "rows": [
                    {
                        "title": t.title,
                        "due_on": t.due_on.isoformat(),
                        "done": bool(t.done_at),
                        "owner": t.get_owner_kind_display(),
                    }
                    for t in pending[:5]
                ],
            },
            link="/welcome",
        )

    if p.intent == "attendance_month":
        from .attendance import summary

        data = summary(employee, today.replace(day=1), today=today)
        c = data["counts"]
        text = (
            f"This month: {c['present']} days present ({c['office']} office, {c['remote']} remote), "
            f"{c['late']} late, {c['on_leave']} on leave, {c['missing_checkout']} missing check-outs."
        )
        return _reply(
            p.intent,
            text,
            user,
            card={"kind": "attendance", "counts": c, "month": data["month"]},
            link="/attendance",
        )

    if p.intent == "pending_for_me":
        from .attendance import regularisations_for
        from .leave import approvals_for

        leaves = list(approvals_for(user)[:5])
        regs = list(regularisations_for(user)[:5])
        if not leaves and not regs:
            return _reply(p.intent, "Nothing is waiting for you right now.", user, link="/leave/approvals")
        rows = [
            {
                "kind": "leave",
                "name": lv.employee.name,
                "detail": f"{engine.fmt_days(lv.days)} from {engine.nice_date(lv.start)}",
                "escalated": lv.escalated,
            }
            for lv in leaves
        ] + [
            {
                "kind": "attendance",
                "name": r.employee.name,
                "detail": f"Attendance correction for {engine.nice_date(r.date)}",
                "escalated": False,
            }
            for r in regs
        ]
        return _reply(
            p.intent,
            f"Waiting for you: {len(leaves)} leave request{'s' if len(leaves) != 1 else ''} and "
            f"{len(regs)} attendance correction{'s' if len(regs) != 1 else ''}.",
            user,
            card={"kind": "pending", "rows": rows},
            link="/leave/approvals",
        )

    if p.intent == "policy" and p.policy_hit:
        hit = p.policy_hit
        sentences = re.split(r"(?<=[.!?])\s+", hit["body"].strip())
        return _reply(
            p.intent,
            " ".join(sentences[:3]),
            user,
            card={"kind": "source", "title": hit["title"], "link": hit["link"]},
            link=hit["link"],
        )

    return None  # let the general assistant try (job search, FAQs)


def fallback_reply(user) -> dict:
    return _reply(
        "fallback",
        "I did not catch that. I can show your leave balance, apply for leave, list holidays, "
        "check attendance and onboarding, or answer policy questions.",
        user,
        link="/hr/policies",
    )
