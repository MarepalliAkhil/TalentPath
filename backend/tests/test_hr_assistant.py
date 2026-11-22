"""HR assistant inside Ask HIRA: each intent, own data only, the confirmation
card (it never submits), manager pending list and the evaluation set."""

from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from hr import assistant
from hr import leave as engine
from hr.eval_data import QUESTIONS
from hr.models import Holiday, LeaveRequest, LeaveStatus, LeaveType
from interviews.timeutil import today_ist


def ask(user, message):
    client = APIClient()
    client.force_authenticate(user)
    response = client.post("/api/hira/ask", {"message": message}, format="json")
    assert response.status_code == 200, response.data
    return response.data


@pytest.fixture
def staff(team):
    today = today_ist(timezone.now())
    for emp in [team["boss"], team["me"], *team["peers"], team["junior"], team["hr"]]:
        engine.credit_entitlements(emp, today)
    return team


@pytest.mark.django_db
def test_leave_balance_is_the_askers_own(staff):
    data = ask(staff["me"].user, "how many casual leaves do i have left")
    assert data["intent"] == "leave_balance"
    assert data["answer"].startswith("Available now: Casual leave")
    assert data["card"]["kind"] == "balances"
    expected = {r["type"]: r["available"] for r in engine.balances(staff["me"])}
    assert {r["type"]: r["available"] for r in data["card"]["rows"]} == expected


@pytest.mark.django_db
def test_typos_and_hinglish(staff):
    assert ask(staff["me"].user, "mera chutti balance kitna hai")["intent"] == "leave_balance"
    assert ask(staff["me"].user, "levae balanse")["intent"] == "leave_balance"
    assert ask(staff["me"].user, "agle mahine ki chuttiyan")["intent"] == "holidays"


@pytest.mark.django_db
def test_apply_leave_returns_a_confirmation_card_and_never_submits(staff):
    data = ask(staff["me"].user, "apply casual leave next friday")
    assert data["intent"] == "apply_leave"
    card = data["card"]
    assert card["kind"] == "leave_confirm"
    assert card["payload"]["leave_type"] == "casual"
    start = date.fromisoformat(card["payload"]["start"])
    assert start.isoweekday() == 5 and start > today_ist(timezone.now())
    assert "days" in card["check"] and "errors" in card["check"]
    assert not LeaveRequest.objects.exists()  # nothing saved until the employee presses Confirm

    # Confirm = the widget posts the same payload to the normal leave API.
    client = APIClient()
    client.force_authenticate(staff["me"].user)
    if card["check"]["ok"]:
        response = client.post("/api/leave/requests", card["payload"], format="json")
        assert response.status_code == 201
        assert LeaveRequest.objects.get().status == LeaveStatus.PENDING


@pytest.mark.django_db
def test_apply_leave_without_a_date_asks_for_one(staff):
    data = ask(staff["me"].user, "i want to apply for leave")
    assert data["intent"] == "apply_leave" and data["card"] is None
    assert "Which date" in data["answer"]


@pytest.mark.django_db
def test_apply_card_shows_rule_errors(staff):
    data = ask(staff["me"].user, "apply earned leave tomorrow")
    if data["card"]:
        assert data["card"]["check"]["ok"] is False
        assert "notice" in data["answer"] or "cannot be submitted" in data["answer"]


@pytest.mark.django_db
def test_upcoming_holidays(staff):
    me = staff["me"]
    day = today_ist(timezone.now()) + timedelta(days=20)
    Holiday.objects.create(location=me.location, date=day, name="Demo Festival")
    data = ask(me.user, "upcoming holidays")
    assert data["intent"] == "holidays" and "Demo Festival" in data["answer"]
    assert "verify" in data["card"]["note"]


@pytest.mark.django_db
def test_who_is_my_manager_and_buddy(staff):
    me, boss, peer = staff["me"], staff["boss"], staff["peers"][1]
    assert boss.name in ask(me.user, "who is my manager")["answer"]
    assert "do not have an onboarding buddy" in ask(me.user, "who is my buddy")["answer"]
    me.buddy = peer
    me.save(update_fields=["buddy"])
    assert peer.name in ask(me.user, "who is my buddy")["answer"]


@pytest.mark.django_db
def test_onboarding_status(staff):
    me = staff["me"]
    assert "no onboarding checklist" in ask(me.user, "onboarding checklist status")["answer"]
    from hr.onboarding import generate_checklist

    generate_checklist(me)
    data = ask(me.user, "what is left in my onboarding")
    assert data["intent"] == "onboarding_status" and "0%" in data["answer"]


@pytest.mark.django_db
def test_attendance_this_month(staff):
    data = ask(staff["me"].user, "my attendance this month")
    assert data["intent"] == "attendance_month" and data["card"]["kind"] == "attendance"


@pytest.mark.django_db
def test_policy_questions_cite_the_source(staff):
    data = ask(staff["me"].user, "what is the sandwich rule")
    assert data["intent"] == "policy"
    assert data["card"]["kind"] == "source" and data["card"]["link"].startswith("/hr/policies")


@pytest.mark.django_db
def test_manager_pending_list(staff):
    me, boss = staff["me"], staff["boss"]
    start = today_ist(timezone.now()) + timedelta(days=21)
    while start.isoweekday() > 5:
        start += timedelta(days=1)
    engine.apply(me, me.user, {"leave_type": "lop", "start": start.isoformat(), "reason": "Moving house"})
    data = ask(boss.user, "what's pending for me")
    assert data["intent"] == "pending_for_me"
    assert data["card"]["rows"][0]["name"] == me.name
    assert "Moving house" not in str(data)  # reasons stay on the approval page
    assert ask(me.user, "what's pending for me")["answer"] == "Nothing is waiting for you right now."


@pytest.mark.django_db
def test_never_reveals_other_peoples_leave(staff):
    me, peer = staff["me"], staff["peers"][1]
    LeaveRequest.objects.create(
        employee=peer,
        leave_type=LeaveType.objects.get(location=peer.location, code="sick"),
        start=today_ist(timezone.now()),
        end=today_ist(timezone.now()),
        days=1,
        reason="Migraine",
        status=LeaveStatus.APPROVED,
    )
    first = peer.name.split()[0]  # "Peer"
    data = ask(me.user, f"how much leave does {peer.name.split()[-1]} {first} have")
    assert "Migraine" not in str(data)
    data = ask(me.user, f"leave balance of {peer.user.full_name.lower()}")
    assert data["intent"] in ("privacy", "leave_balance")
    if data["intent"] == "leave_balance":
        assert {r["type"]: r["available"] for r in data["card"]["rows"]} == {
            r["type"]: r["available"] for r in engine.balances(me)
        }


@pytest.mark.django_db
def test_candidates_keep_the_candidate_assistant(users):
    data = ask(users["candidate"], "leave balance")
    assert data.get("card") in (None, {}) or data["card"].get("kind") != "balances"


@pytest.mark.django_db
def test_understand_parses_dates_deterministically():
    monday = date(2026, 3, 2)
    parsed = assistant.understand("apply sick leave tomorrow", monday, [])
    assert parsed.intent == "apply_leave" and parsed.leave_type == "sick" and parsed.start == date(2026, 3, 3)
    friday = assistant.understand("casual leave next friday", monday, [])
    assert friday.start.isoweekday() == 5 and friday.start > monday


def test_evaluation_set_is_large_and_split():
    assert len(QUESTIONS) >= 60
    tune_q = {q for split, q, _ in QUESTIONS if split == "tune"}
    hold_q = {q for split, q, _ in QUESTIONS if split == "holdout"}
    assert len(tune_q) >= 30 and len(hold_q) >= 30
    assert not tune_q & hold_q
    hinglish = [
        q
        for q in tune_q | hold_q
        if any(w in q.split() for w in ("chutti", "kitni", "mera", "mere", "kya", "hai"))
    ]
    assert len(hinglish) >= 6
