from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import Role, User
from applications.blind import is_blind
from applications.models import ApplicationStatus as S
from applications.services import staff_visible_applications
from core.audit import audit
from core.utils import IgnoreClientContentNegotiation
from core.views import PolicyAPIView
from jobs.services import editable_jobs, visible_jobs
from org.models import Skill

from . import coordinator, rules, scorecards, tokens
from .models import (
    AssignmentStatus,
    BlockedTime,
    Interview,
    InterviewerProfile,
    InterviewRound,
    InterviewStatus,
    Mode,
    SlotStatus,
)
from .plans import clean_block, clean_working_hours, parse_moment, update_plan
from .slots import interview_counts
from .timeutil import fmt, week_bounds


# ------------------------------------------------------------------ serialisers
def person(user) -> dict:
    return {"id": str(user.id), "name": user.full_name, "role": user.role}


def round_dict(round_, with_pool: bool = True) -> dict:
    data = {
        "id": str(round_.id),
        "order": round_.order,
        "name": round_.name,
        "duration_minutes": round_.duration_minutes,
        "mode": round_.mode,
        "mode_label": Mode(round_.mode).label,
        "interviewers_needed": round_.interviewers_needed,
    }
    if with_pool:
        data["pool"] = [person(u) for u in round_.pool.order_by("full_name")]
    return data


def slot_dict(slot) -> dict:
    return {
        "id": str(slot.id),
        "starts_at": slot.starts_at.isoformat(),
        "ends_at": slot.ends_at.isoformat(),
        "label": fmt(slot.starts_at),
        "status": slot.status,
        "held_until": slot.held_until.isoformat() if slot.held_until else None,
    }


def interview_dict(interview, viewer=None, *, candidate_view: bool = False, now=None) -> dict:
    now = now or timezone.now()
    application = interview.application
    location, note = coordinator.meeting_details(interview) if interview.starts_at else ("", "")
    data = {
        "id": str(interview.id),
        "application": str(application.id),
        "job": {"id": str(application.job_id), "title": application.job.title},
        "round": round_dict(interview.round, with_pool=False),
        "status": interview.status,
        "status_label": InterviewStatus(interview.status).label,
        "starts_at": interview.starts_at.isoformat() if interview.starts_at else None,
        "ends_at": interview.ends_at.isoformat() if interview.ends_at else None,
        "when": fmt(interview.starts_at),
        "mode": interview.mode,
        "mode_label": Mode(interview.mode).label,
        "meeting_link": interview.meeting_link,
        "location": location,
        "meeting_note": note,
        "simulated": True,
        "reschedule_count": interview.reschedule_count,
        "interviewers": [
            {"id": str(a.interviewer_id), "name": a.interviewer.full_name, "status": a.status}
            for a in interview.assignments.select_related("interviewer")
            if not candidate_view or a.status == AssignmentStatus.ASSIGNED
        ],
        "slots": [slot_dict(s) for s in interview.slots.filter(status__in=[SlotStatus.OPEN, SlotStatus.HELD])]
        if interview.status == InterviewStatus.PENDING
        else [],
    }
    if candidate_view:
        data["reschedules_left"] = max(0, rules.RESCHEDULE_LIMIT - interview.reschedule_count)
        data["can_reschedule"] = (
            interview.status == InterviewStatus.SCHEDULED
            and interview.starts_at - now >= rules.RESCHEDULE_CUTOFF
            and interview.reschedule_count < rules.RESCHEDULE_LIMIT
        )
        return data
    blind = is_blind(application)
    data["candidate"] = {
        "code": application.candidate_code,
        "full_name": None if blind else application.candidate.full_name,
    }
    data["attention"] = interview.attention
    data["attention_label"] = interview.get_attention_display() if interview.attention else ""
    data["scheduled_by"] = interview.scheduled_by
    data["scorecard_due_at"] = interview.scorecard_due_at.isoformat() if interview.scorecard_due_at else None
    if viewer is not None:
        mine = interview.assignments.filter(interviewer=viewer).first()
        data["my_assignment"] = mine.status if mine else None
        data["my_scorecard_submitted"] = scorecards.has_submitted(interview, viewer)
        data["can_decline"] = bool(
            mine
            and mine.status == AssignmentStatus.ASSIGNED
            and interview.status == InterviewStatus.SCHEDULED
            and interview.starts_at > now
        )
        data["can_mark_no_show"] = bool(
            mine
            and mine.status == AssignmentStatus.ASSIGNED
            and interview.status in (InterviewStatus.SCHEDULED, InterviewStatus.COMPLETED)
            and interview.starts_at <= now
            and not interview.scorecards.exists()
        )
        data["can_submit_scorecard"] = bool(
            mine
            and mine.status == AssignmentStatus.ASSIGNED
            and interview.status in (InterviewStatus.SCHEDULED, InterviewStatus.COMPLETED)
            and interview.starts_at <= now
            and not data["my_scorecard_submitted"]
        )
    return data


def plan_dict(plan) -> dict:
    return {
        "job": {"id": str(plan.job_id), "title": plan.job.title},
        "hira_enabled": plan.hira_enabled,
        "rounds": [round_dict(r) for r in plan.rounds.prefetch_related("pool")],
    }


def profile_dict(profile, week_load: dict | None = None) -> dict:
    user = profile.user
    return {
        **person(user),
        "skills": [
            {"id": str(s.id), "name": s.name, "slug": s.slug} for s in profile.skills.order_by("name")
        ],
        "working_hours": profile.working_hours,
        "active": profile.active,
        "interviews_this_week": (week_load or {}).get(str(user.id), 0),
    }


def _staff_interview(request, pk):
    interview = get_object_or_404(
        Interview.objects.select_related(
            "round", "application", "application__job", "application__candidate"
        ),
        pk=pk,
    )
    if not coordinator.staff_can_see(request.user, interview):
        raise Http404()
    return interview


def _candidate_interview(request, pk):
    return get_object_or_404(coordinator.candidate_interviews(request.user), pk=pk)


# ------------------------------------------------------------------------ plans
class InterviewPlanView(PolicyAPIView):
    policy_actions = {"GET": "interviews.plan_read", "PUT": "interviews.plan_update"}

    def get(self, request, pk):
        job = get_object_or_404(visible_jobs(request.user, with_counts=False), pk=pk)
        return Response(plan_dict(coordinator.get_plan(job)))

    def put(self, request, pk):
        job = get_object_or_404(editable_jobs(request.user), pk=pk)
        plan = update_plan(coordinator.get_plan(job), request.data if isinstance(request.data, dict) else {})
        audit(request, "interviews.plan_updated", target=job, hira_enabled=plan.hira_enabled)
        return Response(plan_dict(plan))


class InterviewerListView(PolicyAPIView):
    policy_action = "interviewers.list"

    def get(self, request):
        profiles = (
            InterviewerProfile.objects.select_related("user")
            .filter(user__is_active=True)
            .order_by("user__full_name")
        )
        skill = request.query_params.get("skill")
        if skill:
            profiles = profiles.filter(skills__slug=skill)
        start, end = week_bounds(timezone.now())
        load = interview_counts([p.user_id for p in profiles], start, end)
        return Response({"results": [profile_dict(p, load) for p in profiles.prefetch_related("skills")]})


class InterviewerUpdateView(PolicyAPIView):
    policy_action = "interviewers.update"

    def patch(self, request, pk):
        user = get_object_or_404(User.objects.exclude(role=Role.CANDIDATE), pk=pk)
        profile, _ = InterviewerProfile.objects.get_or_create(user=user)
        data = request.data if isinstance(request.data, dict) else {}
        if "working_hours" in data:
            profile.working_hours = clean_working_hours(data["working_hours"])
        if "active" in data:
            profile.active = bool(data["active"])
        profile.save()
        if "skills" in data:
            ids = [str(s) for s in data.get("skills") or []]
            skills = list(Skill.objects.filter(id__in=ids))
            if len(skills) != len(set(ids)):
                raise ValidationError({"skills": "Unknown skill."})
            profile.skills.set(skills)
        audit(request, "interviewers.updated", target=user)
        return Response(profile_dict(profile))


# ------------------------------------------------------------------ availability
def availability_dict(user) -> dict:
    profile, _ = InterviewerProfile.objects.get_or_create(user=user)
    now = timezone.now()
    return {
        "timezone": "Asia/Kolkata",
        "working_hours": profile.working_hours,
        "skills": [s.name for s in profile.skills.order_by("name")],
        "blocked": [
            {
                "id": str(b.id),
                "starts_at": b.starts_at.isoformat(),
                "ends_at": b.ends_at.isoformat(),
                "label": f"{fmt(b.starts_at)} to {fmt(b.ends_at)}",
                "reason": b.reason,
            }
            for b in BlockedTime.objects.filter(user=user, ends_at__gt=now)
        ],
    }


class AvailabilityView(PolicyAPIView):
    policy_actions = {"GET": "availability.manage", "PUT": "availability.manage"}

    def get(self, request):
        return Response(availability_dict(request.user))

    def put(self, request):
        profile, _ = InterviewerProfile.objects.get_or_create(user=request.user)
        profile.working_hours = clean_working_hours((request.data or {}).get("working_hours"))
        profile.save(update_fields=["working_hours", "updated_at"])
        return Response(availability_dict(request.user))


class BlockedTimeView(PolicyAPIView):
    policy_actions = {"POST": "availability.manage"}

    def post(self, request):
        start, end, reason = clean_block(request.data or {}, timezone.now())
        BlockedTime.objects.create(user=request.user, starts_at=start, ends_at=end, reason=reason)
        return Response(availability_dict(request.user), status=status.HTTP_201_CREATED)


class BlockedTimeDetailView(PolicyAPIView):
    policy_actions = {"DELETE": "availability.manage"}

    def delete(self, request, pk):
        get_object_or_404(BlockedTime, pk=pk, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------- listings
class MyInterviewsView(PolicyAPIView):
    policy_action = "interviews.mine"

    def get(self, request):
        now = timezone.now()
        rows = [
            interview_dict(i, candidate_view=True, now=now)
            for i in coordinator.candidate_interviews(request.user)
        ]
        return Response({"results": rows})


class AssignedInterviewsView(PolicyAPIView):
    policy_action = "interviews.assigned"

    def get(self, request):
        now = timezone.now()
        rows = [
            interview_dict(i, request.user, now=now) for i in coordinator.assigned_interviews(request.user)
        ]
        upcoming = [
            r for r in rows if r["status"] == "scheduled" and r["ends_at"] and r["ends_at"] > now.isoformat()
        ]
        feedback = [r for r in rows if r["can_submit_scorecard"]]
        past = [r for r in rows if r not in upcoming and r not in feedback]
        return Response({"upcoming": upcoming, "needs_feedback": feedback, "past": past[-20:]})


class ApplicationInterviewsView(PolicyAPIView):
    policy_action = "interviews.for_application"

    def get(self, request, pk):
        application = get_object_or_404(staff_visible_applications(request.user), pk=pk)
        plan = coordinator.get_plan(application.job)
        rounds = []
        for row in coordinator.round_status(application):
            interview = row["interview"]
            rounds.append(
                {
                    "round": round_dict(row["round"]),
                    "interview": interview_dict(interview, request.user) if interview else None,
                    "outcome": row["outcome"],
                    "summary": scorecards.summary(interview, request.user) if interview else None,
                }
            )
        from offers.views import offer_brief

        offer = application.offers.order_by("-created_at").first()
        return Response(
            {
                "application": str(application.id),
                "status": application.status,
                "hira_enabled": plan.hira_enabled,
                "rounds": rounds,
                "final_round_passed": coordinator.final_round_passed(application),
                "can_schedule": request.user.role in (Role.RECRUITER, Role.HR_ADMIN)
                and application.status == S.INTERVIEW,
                "offer": offer_brief(offer) if offer else None,
            }
        )


def _editable_application(request, pk):
    qs = staff_visible_applications(request.user)
    if request.user.role == Role.RECRUITER:
        qs = qs.filter(job__created_by=request.user)
    application = get_object_or_404(qs, pk=pk)
    if application.status != S.INTERVIEW:
        raise ValidationError({"application": "Interviews are scheduled at the Interview stage."})
    return application


class ProposeView(PolicyAPIView):
    policy_action = "interviews.propose"

    def post(self, request, pk):
        application = _editable_application(request, pk)
        pending = application.interviews.filter(status=InterviewStatus.PENDING).first()
        if pending is not None:
            coordinator.propose(pending, reason="recruiter_request")
        elif application.interviews.filter(status=InterviewStatus.SCHEDULED).exists():
            raise ValidationError({"application": "An interview is already scheduled for this candidate."})
        else:
            round_ = coordinator.next_round(application)
            if round_ is None:
                raise ValidationError({"application": "There is no next round to schedule."})
            coordinator._start_round(application, round_, silent=False)
        audit(request, "interviews.propose_requested", target=application)
        return Response({"ok": True})


class ManualScheduleView(PolicyAPIView):
    policy_action = "interviews.schedule_manual"

    def post(self, request, pk):
        application = _editable_application(request, pk)
        data = request.data if isinstance(request.data, dict) else {}
        plan = coordinator.get_plan(application.job)
        round_ = (
            InterviewRound.objects.filter(plan=plan, pk=data.get("round_id")).first()
            if data.get("round_id")
            else None
        )
        if round_ is None:
            raise ValidationError({"round_id": "Choose a round from this job's plan."})
        start = parse_moment(data.get("starts_at"), "starts_at")
        interview = coordinator.schedule_manually(
            application, round_, start, data.get("interviewer_ids") or [], request.user
        )
        return Response(interview_dict(interview, request.user), status=status.HTTP_201_CREATED)


# ------------------------------------------------------------ candidate actions
def _slot_id(request):
    slot = (request.data or {}).get("slot") if isinstance(request.data, dict) else None
    if not slot:
        raise ValidationError({"slot": "Choose a slot."})
    return slot


class HoldView(PolicyAPIView):
    policy_action = "interviews.hold"

    def post(self, request, pk):
        interview = _candidate_interview(request, pk)
        slot = coordinator.hold(interview, _slot_id(request))
        return Response({"slot": slot_dict(slot), "held_minutes": rules.HOLD_MINUTES})


class ConfirmView(PolicyAPIView):
    policy_action = "interviews.confirm"

    def post(self, request, pk):
        interview = coordinator.confirm(_candidate_interview(request, pk), _slot_id(request))
        return Response(interview_dict(interview, candidate_view=True))


class RescheduleView(PolicyAPIView):
    policy_action = "interviews.reschedule"

    def post(self, request, pk):
        interview = _candidate_interview(request, pk)
        coordinator.reschedule(interview)
        interview.refresh_from_db()
        return Response(interview_dict(interview, candidate_view=True))


# ---------------------------------------------------------- interviewer actions
def _my_interview(request, pk):
    return get_object_or_404(
        Interview.objects.filter(assignments__interviewer=request.user)
        .distinct()
        .select_related("round", "application", "application__job", "application__candidate"),
        pk=pk,
    )


class DeclineView(PolicyAPIView):
    policy_action = "interviews.decline"

    def post(self, request, pk):
        interview = _my_interview(request, pk)
        result = coordinator.decline(
            interview, request.user, reason=str((request.data or {}).get("reason") or "")
        )
        return Response(result)


class NoShowView(PolicyAPIView):
    policy_action = "interviews.no_show"

    def post(self, request, pk):
        interview = coordinator.mark_no_show(_my_interview(request, pk), request.user)
        return Response(interview_dict(interview, request.user))


class CalendarView(PolicyAPIView):
    policy_action = "interviews.calendar"
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, pk):
        if request.user.role == Role.CANDIDATE:
            interview = _candidate_interview(request, pk)
            audience = "candidate"
        else:
            interview = _staff_interview(request, pk)
            audience = "interviewer"
        if interview.status != InterviewStatus.SCHEDULED:
            return Response({"detail": "This interview is not scheduled."}, status=status.HTTP_409_CONFLICT)
        name, ctype, text = coordinator._ics(interview, audience)
        response = HttpResponse(text, content_type=f"{ctype}; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        response["Cache-Control"] = "no-store"
        return response


# ------------------------------------------------------------- email link flow
class LinkThrottle(ScopedRateThrottle):
    scope = "schedule_link"


def _link_payload(row) -> dict:
    interview = row.interview
    return {
        "job": {"title": interview.application.job.title},
        "round": round_dict(interview.round, with_pool=False),
        "status": interview.status,
        "slots": [slot_dict(s) for s in interview.slots.filter(status__in=[SlotStatus.OPEN, SlotStatus.HELD])]
        if interview.status == InterviewStatus.PENDING
        else [],
        "expires_at": row.expires_at.isoformat(),
        "hold_minutes": rules.HOLD_MINUTES,
        "simulated": True,
    }


class ScheduleLinkView(PolicyAPIView):
    """Pick a slot from the email link without signing in (single use, expires)."""

    policy_actions = {"GET": "schedule.link", "POST": "schedule.link"}
    throttle_classes = [LinkThrottle]
    authentication_classes = []

    def get(self, request, token, action=None):
        if action is not None:
            raise Http404()
        return Response(_link_payload(tokens.resolve(token)))

    def post(self, request, token, action=None):
        if action not in ("hold", "confirm"):
            raise Http404()
        row = tokens.resolve(token)
        if action == "hold":
            slot = coordinator.hold(row.interview, _slot_id(request))
            return Response({"slot": slot_dict(slot), "held_minutes": rules.HOLD_MINUTES})
        interview = coordinator.confirm(row.interview, _slot_id(request), link=row)
        return Response(
            {"status": interview.status, "when": fmt(interview.starts_at), "mode": Mode(interview.mode).label}
        )


# ------------------------------------------------------------------ scorecards
class ScorecardView(PolicyAPIView):
    policy_actions = {"GET": "scorecards.read", "POST": "scorecards.submit"}

    def get(self, request, pk):
        interview = _staff_interview(request, pk)
        cards, hidden = scorecards.visible_cards(interview, request.user)
        mine = next((c for c in cards if c.interviewer_id == request.user.id), None)
        return Response(
            {
                "interview": interview_dict(interview, request.user),
                "template": scorecards.template(interview.application.job),
                "comment_required_for": sorted(scorecards.COMMENT_REQUIRED_FOR),
                "mine": scorecards.card_dict(mine) if mine else None,
                "others": [scorecards.card_dict(c) for c in cards if c.interviewer_id != request.user.id],
                "others_hidden": hidden,
                "summary": scorecards.summary(interview, request.user),
            }
        )

    def post(self, request, pk):
        interview = _staff_interview(request, pk)
        data = request.data if isinstance(request.data, dict) else {}
        card = scorecards.submit(
            interview,
            request.user,
            ratings=data.get("ratings"),
            comments=data.get("comments"),
            recommendation=data.get("recommendation"),
            summary=data.get("summary") or "",
        )
        audit(request, "scorecards.submitted", target=interview)
        interview.refresh_from_db()
        coordinator.after_scorecard(interview)
        return Response(scorecards.card_dict(card), status=status.HTTP_201_CREATED)
