"""Interview scorecards: a template from the job, independent feedback, summaries.

Independence: an interviewer cannot read other scorecards for an interview until
they have submitted their own (reduces anchoring). The recruiter who owns the
job, its hiring manager and HR read every submitted scorecard, except for
an interview where they are themselves an interviewer who has not submitted yet.
"""

import json
from collections import Counter, defaultdict

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Role

from .models import AssignmentStatus, InterviewStatus, Recommendation, Scorecard

GENERAL = [
    {"key": "communication", "label": "Communication", "kind": "general"},
    {"key": "problem_solving", "label": "Problem solving", "kind": "general"},
]
COMMENT_REQUIRED_FOR = {1, 2, 5}


def template(job) -> list[dict]:
    skills = [
        {"key": f"skill:{s.slug}", "label": s.name, "kind": "skill"}
        for s in job.required_skills.order_by("name")
    ]
    return [*skills, *GENERAL]


def _is_interviewer(interview, user) -> bool:
    return interview.assignments.filter(interviewer=user).exists()


def has_submitted(interview, user) -> bool:
    return interview.scorecards.filter(interviewer=user).exists()


def can_read_others(interview, user) -> bool:
    if _is_interviewer(interview, user) and not has_submitted(interview, user):
        return False
    job = interview.application.job
    if user.role == Role.HR or job.created_by_id == user.id or job.hiring_manager_id == user.id:
        return True
    return _is_interviewer(interview, user)


def card_dict(card: Scorecard) -> dict:
    try:
        comments = json.loads(card.comments or "{}")
    except ValueError:
        comments = {}
    return {
        "id": str(card.id),
        "interviewer": {"id": str(card.interviewer_id), "name": card.interviewer.full_name},
        "criteria": [
            {**c, "rating": card.ratings.get(c["key"]), "comment": comments.get(c["key"], "")}
            for c in card.criteria
        ],
        "recommendation": card.recommendation,
        "recommendation_label": Recommendation(card.recommendation).label,
        "summary": card.summary,
        "submitted_at": card.submitted_at.isoformat(),
    }


def visible_cards(interview, user) -> tuple[list[Scorecard], bool]:
    """(cards the user may read, whether others are hidden from them)."""
    cards = list(interview.scorecards.select_related("interviewer"))
    if can_read_others(interview, user):
        return cards, False
    return [c for c in cards if c.interviewer_id == user.id], True


def submit(
    interview, interviewer, *, ratings: dict, comments: dict, recommendation: str, summary: str = "", now=None
):
    now = now or timezone.now()
    if not interview.assignments.filter(interviewer=interviewer, status=AssignmentStatus.ASSIGNED).exists():
        raise ValidationError({"interview": "Only interviewers on this interview can submit a scorecard."})
    if (
        interview.status not in (InterviewStatus.SCHEDULED, InterviewStatus.COMPLETED)
        or interview.starts_at > now
    ):
        raise ValidationError({"interview": "You can submit feedback once the interview has started."})
    criteria = template(interview.application.job)
    errors: dict = {}
    clean_ratings, clean_comments = {}, {}
    ratings = ratings if isinstance(ratings, dict) else {}
    comments = comments if isinstance(comments, dict) else {}
    for c in criteria:
        key = c["key"]
        try:
            value = int(ratings.get(key))
        except (TypeError, ValueError):
            value = None
        if value not in (1, 2, 3, 4, 5):
            errors[f"ratings.{key}"] = f"Rate {c['label']} from 1 to 5."
            continue
        text = str(comments.get(key) or "").strip()[:1000]
        if value in COMMENT_REQUIRED_FOR and not text:
            errors[f"comments.{key}"] = f"Explain a rating of {value} for {c['label']}."
        clean_ratings[key] = value
        if text:
            clean_comments[key] = text
    if recommendation not in Recommendation.values:
        errors["recommendation"] = "Choose an overall recommendation."
    if errors:
        raise ValidationError(errors)
    try:
        with transaction.atomic():
            card = Scorecard.objects.create(
                interview=interview,
                interviewer=interviewer,
                ratings=clean_ratings,
                criteria=criteria,
                comments=json.dumps(clean_comments),
                summary=(summary or "").strip()[:2000],
                recommendation=recommendation,
            )
    except IntegrityError as exc:
        raise ValidationError(
            {"interview": "You have already submitted a scorecard for this interview."}
        ) from exc
    if interview.status == InterviewStatus.SCHEDULED and interview.ends_at <= now:
        type(interview).objects.filter(pk=interview.pk).update(
            status=InterviewStatus.COMPLETED, completed_at=now
        )
        interview.status = InterviewStatus.COMPLETED
    return card


def summary(interview, user) -> dict:
    """Average per criterion and recommendation counts, from the cards this user may read."""
    cards, hidden = visible_cards(interview, user)
    if hidden:
        cards = []
    totals: dict = defaultdict(list)
    labels: dict = {}
    for card in cards:
        for c in card.criteria:
            labels[c["key"]] = c["label"]
            if card.ratings.get(c["key"]) is not None:
                totals[c["key"]].append(card.ratings[c["key"]])
    recs = Counter(card.recommendation for card in cards)
    expected = interview.assignments.filter(status=AssignmentStatus.ASSIGNED).count()
    return {
        "submitted": len(interview.scorecards.all()),
        "expected": expected,
        "hidden": hidden,
        "criteria": [
            {"key": k, "label": labels[k], "average": round(sum(v) / len(v), 1), "count": len(v)}
            for k, v in totals.items()
        ],
        "recommendations": {r.value: recs.get(r.value, 0) for r in Recommendation},
    }
