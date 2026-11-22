"""Leave engine rules on a fixed calendar (Monday 2 March 2026, IST).

March 2026: Sat 7 / Sun 8, Sat 14 / Sun 15 and Sat 21 / Sun 22 are weekly offs.
Default rules (hr.defaults): casual 12/yr monthly, 1 day notice, max 3, half days;
sick 10/yr granted, backdate 7 days, document after 2 days; earned 18/yr monthly,
7 days notice, max 15, no half days, sandwich on, carry up to 15; LOP unpaid.
"""

from datetime import date
from decimal import Decimal

import pytest

from hr import leave as engine
from hr.models import Holiday, LeaveLedger, LeaveRequest, LeaveStatus, LeaveType

TODAY = date(2026, 3, 2)


@pytest.fixture
def emp(make_employee):
    employee = make_employee(joined=date(2024, 1, 15))
    engine.credit_entitlements(employee, TODAY)
    return employee


def check(employee, **data):
    has_document = data.pop("has_document", False)
    return engine.check(employee, data, today=TODAY, has_document=has_document)


def lt(employee, code):
    return LeaveType.objects.get(location=employee.location, code=code)


@pytest.mark.django_db
def test_weekly_offs_and_holidays_are_not_counted(emp):
    Holiday.objects.create(location=emp.location, date=date(2026, 3, 18), name="Demo holiday")
    result = check(emp, leave_type="casual", start="2026-03-17", end="2026-03-19")
    assert result.errors == {}
    assert result.days == Decimal("2")
    kinds = {r["date"].isoformat(): r["kind"] for r in result.breakdown}
    assert kinds["2026-03-18"] == "holiday"

    weekend = check(emp, leave_type="casual", start="2026-03-07", end="2026-03-08")
    assert "nothing to apply for" in weekend.errors["start"]


@pytest.mark.django_db
def test_sandwich_rule_on_counts_the_weekend_between_leave_days(emp):
    result = check(emp, leave_type="earned", start="2026-03-13", end="2026-03-16")
    assert result.errors == {}, result.errors
    assert result.days == Decimal("4")  # Fri + Sat + Sun + Mon
    assert [r["kind"] for r in result.breakdown].count("sandwich") == 2


@pytest.mark.django_db
def test_sandwich_rule_off_skips_the_weekend(emp):
    LeaveType.objects.filter(location=emp.location, code="earned").update(sandwich_rule=False)
    result = check(emp, leave_type="earned", start="2026-03-13", end="2026-03-16")
    assert result.days == Decimal("2")


@pytest.mark.django_db
def test_sandwich_joins_with_an_existing_request(emp):
    LeaveRequest.objects.create(
        employee=emp,
        leave_type=lt(emp, "earned"),
        start=date(2026, 3, 13),
        end=date(2026, 3, 13),
        days=1,
        status=LeaveStatus.APPROVED,
    )
    result = check(emp, leave_type="earned", start="2026-03-16", end="2026-03-16")
    assert result.days == Decimal("3")  # Mon plus the weekend between the two leaves


@pytest.mark.django_db
def test_minimum_notice(emp):
    result = check(emp, leave_type="earned", start="2026-03-05", end="2026-03-05")
    assert "7 days' notice" in result.errors["start"]
    assert "Mon 9 Mar 2026" in result.errors["start"]
    assert check(emp, leave_type="earned", start="2026-03-09", end="2026-03-09").errors == {}


@pytest.mark.django_db
def test_past_dates_only_where_backdating_is_allowed(emp):
    assert check(emp, leave_type="sick", start="2026-02-26", end="2026-02-26").errors == {}
    late = check(emp, leave_type="sick", start="2026-02-20", end="2026-02-20")
    assert "up to 7 days after" in late.errors["start"]
    assert "past" in check(emp, leave_type="casual", start="2026-02-27", end="2026-02-27").errors["start"]


@pytest.mark.django_db
def test_maximum_consecutive_days(emp):
    result = check(emp, leave_type="casual", start="2026-03-09", end="2026-03-12")
    assert "at most 3 days" in result.errors["end"]


@pytest.mark.django_db
def test_half_days(emp):
    half = check(emp, leave_type="casual", start="2026-03-10", end="2026-03-10", half="first")
    assert half.errors == {} and half.days == Decimal("0.5")
    assert (
        "cannot be taken as a half day"
        in check(emp, leave_type="earned", start="2026-03-10", end="2026-03-10", half="first").errors["half"]
    )
    assert (
        "same date"
        in check(emp, leave_type="casual", start="2026-03-10", end="2026-03-11", half="second").errors["half"]
    )


@pytest.mark.django_db
def test_other_half_of_the_same_day_is_allowed(emp):
    LeaveRequest.objects.create(
        employee=emp,
        leave_type=lt(emp, "casual"),
        start=date(2026, 3, 10),
        end=date(2026, 3, 10),
        half="first",
        days=Decimal("0.5"),
    )
    assert check(emp, leave_type="casual", start="2026-03-10", end="2026-03-10", half="second").errors == {}
    clash = check(emp, leave_type="casual", start="2026-03-10", end="2026-03-10", half="first")
    assert "already have" in clash.errors["start"]


@pytest.mark.django_db
def test_documents_required_for_long_sick_leave(emp):
    result = check(emp, leave_type="sick", start="2026-03-03", end="2026-03-05")
    assert result.needs_document and "Attach a document" in result.errors["document"]
    assert check(emp, leave_type="sick", start="2026-03-03", end="2026-03-05", has_document=True).errors == {}
    assert check(emp, leave_type="sick", start="2026-03-03", end="2026-03-04").needs_document is False


@pytest.mark.django_db
def test_balance_cannot_go_negative_and_pending_is_reserved(emp):
    # Casual accrues 1 a month: 3 days by March.
    LeaveRequest.objects.create(
        employee=emp,
        leave_type=lt(emp, "casual"),
        start=date(2026, 3, 4),
        end=date(2026, 3, 5),
        days=2,
    )
    result = check(emp, leave_type="casual", start="2026-03-10", end="2026-03-11")
    assert "1 day of casual leave available" in result.errors["leave_type"]


@pytest.mark.django_db
def test_loss_of_pay_has_no_balance(emp):
    result = check(emp, leave_type="lop", start="2026-03-09", end="2026-03-13")
    assert result.errors == {} and result.available is None


@pytest.mark.django_db
def test_requests_cannot_cross_the_year_or_start_before_joining(make_employee):
    joiner = make_employee(joined=date(2026, 3, 16))
    engine.credit_entitlements(joiner, TODAY)
    before = engine.check(
        joiner, {"leave_type": "lop", "start": "2026-03-10", "end": "2026-03-10"}, today=TODAY
    )
    assert "joining date" in before.errors["start"]
    across = engine.check(
        joiner, {"leave_type": "lop", "start": "2026-12-30", "end": "2027-01-04"}, today=TODAY
    )
    assert "31 December" in across.errors["end"]


@pytest.mark.django_db
def test_hr_approval_needed_above_the_threshold(emp):
    assert check(emp, leave_type="lop", start="2026-03-09", end="2026-03-13").needs_hr is False  # 5 days
    assert (
        check(emp, leave_type="lop", start="2026-03-09", end="2026-03-16").needs_hr is True
    )  # 8 with sandwich


@pytest.mark.django_db
def test_monthly_accrual_is_idempotent(emp):
    casual = lt(emp, "casual")
    before = engine.ledger_total(emp, casual, 2026)
    assert before == Decimal("3")
    assert engine.credit_entitlements(emp, TODAY) == 0
    engine.run_accruals(TODAY)
    assert engine.ledger_total(emp, casual, 2026) == before
    # April arrives: exactly one more month.
    engine.run_accruals(date(2026, 4, 1))
    engine.run_accruals(date(2026, 4, 1))
    assert engine.ledger_total(emp, casual, 2026) == Decimal("4")


@pytest.mark.django_db
def test_accrual_adds_up_to_the_yearly_quota():
    quota = Decimal("18")
    assert sum(engine.accrual_for_month(quota, m) for m in range(1, 13)) == quota
    assert sum(engine.accrual_for_month(Decimal("10"), m) for m in range(1, 13)) == Decimal("10")


@pytest.mark.django_db
def test_year_end_carry_forward_is_capped_and_idempotent(make_employee):
    employee = make_employee(joined=date(2024, 1, 15))
    engine.credit_entitlements(employee, date(2025, 12, 31))  # 2025: earned 18, casual 12, sick 10
    first = engine.run_year_end(date(2026, 1, 1))
    second = engine.run_year_end(date(2026, 1, 1))
    assert first["carried"] > 0 and second == {"carried": 0, "lapsed": 0}
    earned, casual = lt(employee, "earned"), lt(employee, "casual")
    carry = LeaveLedger.objects.get(employee=employee, leave_type=earned, kind="carry")
    assert carry.year == 2026 and carry.days == Decimal("15")  # capped at 15 of 18
    assert engine.ledger_total(employee, earned, 2025) == Decimal("15")  # 3 lapsed in 2025
    assert not LeaveLedger.objects.filter(employee=employee, leave_type=casual, kind="carry").exists()


@pytest.mark.django_db
def test_future_year_balance_is_projected(emp):
    result = check(emp, leave_type="sick", start="2027-01-05", end="2027-01-05")
    assert result.errors == {}
    assert result.available is not None and result.available >= Decimal("1")


@pytest.mark.django_db
def test_rules_come_from_data_not_code(emp):
    LeaveType.objects.filter(location=emp.location, code="casual").update(
        max_consecutive_days=5, min_notice_days=0
    )
    assert "end" not in check(emp, leave_type="casual", start="2026-03-02", end="2026-03-04").errors


@pytest.mark.django_db
def test_hr_adjustment_needs_a_note_and_is_audited(emp, users):
    from core.models import AuditLog

    comp = lt(emp, "comp_off")
    from rest_framework.exceptions import ValidationError

    with pytest.raises(ValidationError):
        engine.adjust(emp, comp, 1, "", users["hr_admin"])
    engine.adjust(emp, comp, Decimal("1"), "Worked on the release Saturday", users["hr_admin"])
    assert LeaveLedger.objects.get(employee=emp, leave_type=comp, kind="adjust").days == Decimal("1")
    assert AuditLog.objects.filter(action="leave.adjusted").exists()


@pytest.mark.django_db
def test_leave_later_this_year_counts_accruals_still_to_come(make_employee):
    # Joined on 20 February (after the 15th): casual accrues from March, one day a month.
    joiner = make_employee(joined=date(2026, 2, 20))
    engine.credit_entitlements(joiner, TODAY)  # March: 1 day credited so far (February does not count)
    casual = lt(joiner, "casual")
    assert engine.ledger_total(joiner, casual, 2026) == Decimal("1")
    in_may = engine.check(joiner, {"leave_type": "casual", "start": "2026-05-12"}, today=TODAY)
    assert in_may.available == Decimal("3")  # March + April + May
    assert in_may.errors == {}
    two_days_now = engine.check(
        joiner, {"leave_type": "casual", "start": "2026-03-10", "end": "2026-03-11"}, today=TODAY
    )
    assert "1 day of casual leave available" in two_days_now.errors["leave_type"]


@pytest.mark.django_db
def test_balance_never_shows_negative_when_booked_ahead(make_employee):
    joiner = make_employee(joined=date(2026, 2, 20))
    engine.credit_entitlements(joiner, TODAY)
    LeaveRequest.objects.create(
        employee=joiner,
        leave_type=lt(joiner, "casual"),
        start=date(2026, 5, 11),
        end=date(2026, 5, 12),
        days=2,
    )
    casual = next(r for r in engine.balances(joiner, today=TODAY) if r["type"] == "casual")
    assert casual["available"] == 0.0 and casual["booked_ahead"] == 1.0
