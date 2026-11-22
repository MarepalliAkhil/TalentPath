"""Week 3B demo data: 30 employees with managers and buddies, leave policies and
holiday calendars, leave history in every state, 30 days of attendance, people
mid-onboarding, and one accepted offer ready for the one-click hire demo.

Every person here is fictional. Holiday dates are demo data: verify them
against the official state government list before relying on them.
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.models import Profile, Role, User
from applications.models import Application
from applications.models import ApplicationStatus as S
from applications.services import apply_to_job, move_application
from hr import attendance as att
from hr import leave as engine
from hr import onboarding
from hr.calendar_rules import DayBook, add_working_days, date_range
from hr.defaults import ensure_location_defaults
from hr.models import (
    AttendanceRecord,
    Employee,
    EmployeeStatus,
    Holiday,
    LeaveAction,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    LedgerKind,
    Regularisation,
    WorkMode,
)
from interviews.timeutil import IST, today_ist
from jobs.models import Job
from offers import services as offers
from org.models import Department, Location
from seeding import demo_data as D
from seeding.docgen import make_pdf

VERIFY = "Demo data: verify against the official holiday list"

# key: (department, location, designation, manager key, days since joining; negative = joins in N days)
ORG = {
    "manager": ("Engineering", "Hyderabad", "Head of Engineering", None, 2400),
    "hm_data": ("Data & AI", "Bengaluru", "Head of Data & AI", None, 2000),
    "hm_product": ("Product", "Bengaluru", "Head of Product", None, 1800),
    "hm_gtm": ("Sales", "Hyderabad", "Head of Sales & Marketing", None, 1900),
    "hm_people": ("People & HR", "Hyderabad", "Head of People", None, 2100),
    "admin": ("People & HR", "Hyderabad", "HR Manager", "hm_people", 1500),
    "recruiter": ("People & HR", "Hyderabad", "Senior Recruiter", "admin", 1100),
    "recruiter2": ("People & HR", "Bengaluru", "Recruiter", "admin", 700),
    "recruiter3": ("People & HR", "Hyderabad", "Recruiter", "admin", 420),
    "employee": ("Engineering", "Hyderabad", "Engineering Lead", "manager", 1300),
    "employee2": ("Data & AI", "Bengaluru", "Senior Data Engineer", "hm_data", 900),
    "employee3": ("Design", "Bengaluru", "Product Designer", "hm_product", 800),
    "int_arjun": ("Engineering", "Hyderabad", "Senior Backend Engineer", "employee", 1000),
    "int_ananya": ("Data & AI", "Bengaluru", "ML Engineer", "hm_data", 650),
    "int_imran": ("Sales", "Hyderabad", "Sales Lead", "hm_gtm", 1200),
    "int_meghana": ("People & HR", "Hyderabad", "HR Business Partner", "hm_people", 950),
    "int_naveen": ("Engineering", "Hyderabad", "Backend Engineer", "employee", 500),
    "int_zoya": ("Design", "Bengaluru", "Design Lead", "hm_product", 1400),
    # Week 3B: twelve more people (employee role).
    "rahul": ("Engineering", "Hyderabad", "Backend Engineer", "manager", 600),
    "pooja": ("Engineering", "Bengaluru", "Frontend Engineer", "manager", 450),
    "karthik": ("Engineering", "Hyderabad", "QA Engineer", "manager", 380),
    "aditya": ("Engineering", "Hyderabad", "Backend Engineer", "employee", 6),
    "ritika": ("Data & AI", "Bengaluru", "Data Analyst", "hm_data", 300),
    "varun": ("Platform & Security", "Bengaluru", "DevOps Engineer", "hm_data", 760),
    "nikhil": ("Product", "Bengaluru", "Product Manager", "hm_product", 3),
    "deepa": ("Sales", "Hyderabad", "Account Executive", "int_imran", 540),
    "harish": ("Customer Success", "Bengaluru", "Customer Success Manager", "hm_gtm", 820),
    "anjali": ("Marketing", "Hyderabad", "Marketing Specialist", "hm_gtm", 260),
    "tanvi": ("People & HR", "Hyderabad", "HR Operations Associate", "admin", -6),
    "sameer": ("Finance", "Hyderabad", "Finance Analyst", "hm_people", 980),
}
NEW_PEOPLE = {
    "rahul": ("rahul.verma", "Rahul Verma"),
    "pooja": ("pooja.shah", "Pooja Shah"),
    "karthik": ("karthik.subramanian", "Karthik Subramanian"),
    "aditya": ("aditya.kulkarni", "Aditya Kulkarni"),
    "ritika": ("ritika.bose", "Ritika Bose"),
    "varun": ("varun.mehra", "Varun Mehra"),
    "nikhil": ("nikhil.rao", "Nikhil Rao"),
    "deepa": ("deepa.nair", "Deepa Nair"),
    "harish": ("harish.gowda", "Harish Gowda"),
    "anjali": ("anjali.desai", "Anjali Desai"),
    "tanvi": ("tanvi.kapoor", "Tanvi Kapoor"),
    "sameer": ("sameer.khan", "Sameer Khan"),
}
JOINER = ("joiner", "Ishaan Malhotra")
JOINER_JOB = "Frontend Engineer (React)"

# National holidays (both locations) and state holidays. Moon-based dates can move by a day.
NATIONAL = {
    2026: [
        ("2026-01-26", "Republic Day"),
        ("2026-03-04", "Holi"),
        ("2026-03-21", "Eid-ul-Fitr (moon sighting)"),
        ("2026-04-03", "Good Friday"),
        ("2026-05-27", "Bakrid / Eid-ul-Adha (moon sighting)"),
        ("2026-08-15", "Independence Day"),
        ("2026-09-14", "Ganesh Chaturthi"),
        ("2026-10-02", "Gandhi Jayanti"),
        ("2026-10-20", "Vijayadashami"),
        ("2026-11-08", "Deepavali"),
        ("2026-12-25", "Christmas"),
    ],
    2027: [
        ("2027-01-26", "Republic Day"),
        ("2027-08-16", "Independence Day (observed)"),
        ("2027-10-02", "Gandhi Jayanti"),
        ("2027-12-25", "Christmas"),
    ],
}
STATE = {
    "Hyderabad": {
        2026: [
            ("2026-01-14", "Sankranti / Pongal"),
            ("2026-03-19", "Ugadi"),
            ("2026-03-27", "Sri Rama Navami"),
            ("2026-04-14", "Dr B R Ambedkar Jayanti"),
            ("2026-06-02", "Telangana Formation Day"),
            ("2026-07-27", "Bonalu"),
            ("2026-10-19", "Bathukamma (Saddula)"),
        ],
        2027: [("2027-01-15", "Sankranti / Pongal"), ("2027-06-02", "Telangana Formation Day")],
    },
    "Bengaluru": {
        2026: [
            ("2026-01-15", "Makara Sankranti"),
            ("2026-03-19", "Ugadi"),
            ("2026-05-01", "May Day"),
            ("2026-11-01", "Kannada Rajyotsava"),
        ],
        2027: [("2027-01-15", "Makara Sankranti"), ("2027-05-01", "May Day")],
    },
}


def seed_policies() -> dict:
    for location in Location.objects.all():
        ensure_location_defaults(location)
    made = 0
    for loc_name, years in STATE.items():
        location = Location.objects.filter(name=loc_name).first()
        if location is None:
            continue
        for year, rows in NATIONAL.items():
            for day, name in rows:
                _, created = Holiday.objects.get_or_create(
                    location=location, date=date.fromisoformat(day), defaults={"name": name, "note": VERIFY}
                )
                made += created
            for day, name in years.get(year, []):
                _, created = Holiday.objects.get_or_create(
                    location=location,
                    date=date.fromisoformat(day),
                    defaults={"name": name, "regional": True, "note": VERIFY},
                )
                made += created
    return {"holidays": made}


def _user(email, name, role, password_hash):
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create(email=email, full_name=name, role=role, password=password_hash)
    Profile.objects.get_or_create(user=user)
    return user


def seed_employees(staff: dict, password_hash: str, today: date) -> dict:
    people = dict(staff)
    for key, (local, name) in NEW_PEOPLE.items():
        people[key] = _user(f"{local}@{D.DEMO_DOMAIN}", name, Role.EMPLOYEE, password_hash)
    departments = {d.name: d for d in Department.objects.all()}
    locations = {loc.name: loc for loc in Location.objects.all()}
    employees = {}
    pending_managers = []
    for key, (dept, loc, designation, manager_key, days) in ORG.items():
        user = people[key]
        emp = Employee.objects.filter(user=user).first()
        if emp is None:
            emp = Employee.objects.create(
                user=user,
                code=onboarding.next_code(),
                designation=designation,
                department=departments[dept],
                location=locations[loc],
                joined_on=today - timedelta(days=days),
                status=EmployeeStatus.ONBOARDING if days < 30 else EmployeeStatus.ACTIVE,
            )
        employees[key] = emp
        pending_managers.append((key, manager_key))
    for key, manager_key in pending_managers:
        emp = employees[key]
        if manager_key and emp.manager_id is None:
            emp.manager = employees[manager_key]
            emp.save(update_fields=["manager"])
    # Long-standing employees get a buddy history too: everyone who joined in the last year.
    for emp in employees.values():
        if emp.buddy_id is None and (today - emp.joined_on).days < 365:
            emp.buddy = onboarding.choose_buddy(
                emp.department, emp.joined_on, exclude_ids=(emp.id, emp.manager_id)
            )
            emp.save(update_fields=["buddy"])
    return employees


def seed_onboarding(employees: dict, today: date) -> int:
    count = 0
    for key in ("aditya", "nikhil", "tanvi"):
        emp = employees[key]
        if emp.tasks.exists():
            continue
        onboarding.generate_checklist(emp)
        onboarding.generate_first_week(emp)
        count += 1
        if key == "tanvi":
            continue  # joins next week: nothing done yet except IT prep
        for n, task in enumerate(emp.tasks.order_by("due_on", "order")):
            if task.due_on < today and not (key == "aditya" and n == 3):  # one overdue item stays open
                task.done_at = timezone.now() - timedelta(days=max(1, (today - task.due_on).days))
                task.done_by = task.owner or employees["admin"].user
                task.save(update_fields=["done_at", "done_by"])
    return count


def _working_after(location, start: date, n: int) -> date:
    return add_working_days(location, start, n)


def _make_leave(
    emp,
    code,
    start,
    end=None,
    *,
    status,
    half="",
    reason="",
    note="",
    approver=None,
    assigned_days_ago=0,
    decided_by=None,
):
    lt = LeaveType.objects.get(location=emp.location, code=code)
    end = end or start
    days, _ = engine.count_days(emp, lt, start, end, half)
    if days == 0:
        return None
    now = timezone.now()
    req = LeaveRequest.objects.create(
        employee=emp,
        leave_type=lt,
        start=start,
        end=end,
        half=half,
        days=days,
        reason=reason,
        status=status,
        stage="manager" if status == LeaveStatus.PENDING else "",
        approver=approver if status == LeaveStatus.PENDING else None,
        assigned_at=now - timedelta(days=assigned_days_ago) if status == LeaveStatus.PENDING else None,
        decided_by=decided_by if status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED) else None,
        decided_at=now - timedelta(days=max(assigned_days_ago - 1, 0))
        if status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED)
        else None,
        decision_note=note,
        manager_approved_by=decided_by if status == LeaveStatus.APPROVED else None,
    )
    LeaveAction.objects.create(
        request=req,
        actor=emp.user,
        action="submitted",
        detail=f"{engine.fmt_days(days)} of {lt.name.lower()}",
    )
    if status == LeaveStatus.PENDING:
        LeaveAction.objects.create(
            request=req, action="assigned", detail=f"Waiting for {approver.full_name if approver else 'HR'}"
        )
    elif status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        LeaveAction.objects.create(request=req, actor=decided_by, action=status, detail="")
    elif status == LeaveStatus.CANCELLED:
        LeaveAction.objects.create(request=req, actor=emp.user, action="cancelled", detail="")
    if status == LeaveStatus.APPROVED and not lt.unpaid:
        engine._credit(emp, lt, start.year, LedgerKind.USE, -days, f"use:{req.id}", "Seeded history")
    return req


def seed_leave(employees: dict, today: date) -> dict:
    e = employees
    if LeaveRequest.objects.filter(employee__in=e.values()).exists():
        return {"skipped": True}
    for emp in e.values():
        engine.credit_entitlements(emp, today)
    hyd = e["manager"].location
    admin = e["admin"].user
    # Comp-off for working on a holiday.
    for key in ("rahul", "int_imran", "karthik"):
        lt = LeaveType.objects.get(location=e[key].location, code="comp_off")
        engine.adjust(e[key], lt, Decimal("1"), "Worked on the Deepavali release weekend", admin)

    # The clash demo: three of Vikram Natarajan's reports are off on one day after the joiner starts.
    joining = demo_joining_date(today, hyd)
    clash = _working_after(hyd, joining, 6)
    vikram = e["manager"].user
    _make_leave(
        e["rahul"], "casual", clash, status=LeaveStatus.APPROVED, reason="Family function", decided_by=vikram
    )
    _make_leave(
        e["pooja"],
        "earned",
        clash,
        _working_after(e["pooja"].location, clash, 1),
        status=LeaveStatus.APPROVED,
        reason="Trip home",
        decided_by=vikram,
    )
    _make_leave(
        e["karthik"],
        "comp_off",
        clash,
        status=LeaveStatus.PENDING,
        reason="Comp-off for the release weekend",
        approver=vikram,
    )

    divya = e["employee"].user
    # Divya (Engineering Lead, employee role) is on leave today, so Arjun's request is delegated to Vikram.
    _make_leave(
        e["employee"],
        "earned",
        today - timedelta(days=1),
        today + timedelta(days=1),
        status=LeaveStatus.APPROVED,
        reason="Personal",
        decided_by=vikram,
    )
    _make_leave(
        e["int_arjun"],
        "casual",
        _working_after(hyd, today, 3),
        status=LeaveStatus.PENDING,
        reason="Bank work",
        approver=divya,
    )
    _make_leave(
        e["int_arjun"],
        "sick",
        _working_after(hyd, today - timedelta(days=21), 0),
        status=LeaveStatus.APPROVED,
        reason="Fever",
        decided_by=divya,
    )
    _make_leave(
        e["int_arjun"],
        "casual",
        _working_after(hyd, today, 12),
        status=LeaveStatus.REJECTED,
        reason="Cousin's wedding",
        note="Release week: can we move this by a week?",
        decided_by=divya,
    )
    _make_leave(
        e["int_naveen"],
        "casual",
        _working_after(hyd, today, 8),
        status=LeaveStatus.CANCELLED,
        reason="Plans changed",
    )
    blr = e["hm_data"].location
    # Long leave: needs the manager and then HR.
    _make_leave(
        e["employee2"],
        "earned",
        _working_after(blr, today, 10),
        _working_after(blr, today, 15),
        status=LeaveStatus.PENDING,
        reason="Vacation",
        approver=e["hm_data"].user,
        assigned_days_ago=1,
    )
    # Waiting more than 48 hours: escalated by the tick below.
    _make_leave(
        e["employee3"],
        "casual",
        _working_after(blr, today, 5),
        status=LeaveStatus.PENDING,
        reason="Moving house",
        approver=e["hm_product"].user,
        assigned_days_ago=3,
    )
    _make_leave(
        e["int_imran"],
        "earned",
        _working_after(hyd, today - timedelta(days=35), 0),
        _working_after(hyd, today - timedelta(days=35), 2),
        status=LeaveStatus.APPROVED,
        reason="Vacation",
        decided_by=e["hm_gtm"].user,
    )
    _make_leave(
        e["deepa"],
        "casual",
        _working_after(hyd, today, 4),
        status=LeaveStatus.PENDING,
        reason="Doctor's appointment",
        approver=e["int_imran"].user,
    )
    _make_leave(
        e["int_meghana"],
        "casual",
        _working_after(hyd, today - timedelta(days=9), 0),
        half="first",
        status=LeaveStatus.APPROVED,
        reason="Errand",
        decided_by=e["hm_people"].user,
    )
    _make_leave(
        e["harish"],
        "casual",
        _working_after(blr, today, 2),
        status=LeaveStatus.REJECTED,
        reason="Personal",
        note="Quarterly review with the customer that day.",
        decided_by=e["hm_gtm"].user,
    )
    _make_leave(
        e["varun"],
        "lop",
        _working_after(blr, today - timedelta(days=16), 0),
        status=LeaveStatus.APPROVED,
        reason="Extended trip",
        decided_by=e["hm_data"].user,
    )
    _make_leave(
        e["admin"],
        "casual",
        _working_after(hyd, today, 9),
        status=LeaveStatus.PENDING,
        reason="Personal",
        approver=e["hm_people"].user,
    )
    _make_leave(
        e["ritika"],
        "sick",
        _working_after(blr, today - timedelta(days=4), 0),
        status=LeaveStatus.APPROVED,
        reason="Migraine",
        decided_by=e["hm_data"].user,
    )
    _make_leave(
        e["sameer"],
        "earned",
        _working_after(hyd, today, 14),
        _working_after(hyd, today, 16),
        status=LeaveStatus.APPROVED,
        reason="Vacation",
        decided_by=e["hm_people"].user,
    )

    now = timezone.now()
    delegated = engine.refresh_delegations(now)
    escalated = engine.escalate_due(now)
    return {
        "requests": LeaveRequest.objects.filter(employee__in=e.values()).count(),
        "delegated": delegated,
        "escalated": escalated,
        "clash_date": clash.isoformat(),
    }


def seed_attendance(employees: dict, today: date) -> dict:
    if AttendanceRecord.objects.filter(employee__in=employees.values()).exists():
        return {"skipped": True}
    rng = random.Random("attendance-2026")
    made = missing = 0
    for _key, emp in sorted(employees.items()):
        book = DayBook(emp.location, today - timedelta(days=31), today)
        leave_days = set()
        for req in LeaveRequest.objects.filter(employee=emp, status=LeaveStatus.APPROVED):
            leave_days.update(date_range(req.start, req.end))
        rows = []
        for day in date_range(max(today - timedelta(days=30), emp.joined_on), today - timedelta(days=1)):
            if not book.is_working(day) or day in leave_days or rng.random() < 0.03:
                continue
            start = datetime.combine(day, time(9, 0), tzinfo=IST) + timedelta(minutes=rng.randint(0, 70))
            end = datetime.combine(day, time(17, 50), tzinfo=IST) + timedelta(minutes=rng.randint(0, 95))
            gone = rng.random() < 0.03
            late, early = att.flags(emp, day, start, None if gone else end)
            rows.append(
                AttendanceRecord(
                    employee=emp,
                    date=day,
                    check_in=start,
                    check_out=None if gone else end,
                    mode=WorkMode.REMOTE if rng.random() < 0.3 else WorkMode.OFFICE,
                    late=late,
                    early=early,
                    missing_checkout=gone,
                )
            )
            missing += gone
        AttendanceRecord.objects.bulk_create(rows)
        made += len(rows)
    # One pending and one approved regularisation.
    arjun = employees["int_arjun"]
    day = add_working_days(arjun.location, today - timedelta(days=6), 0)
    AttendanceRecord.objects.update_or_create(
        employee=arjun,
        date=day,
        defaults={
            "check_in": datetime.combine(day, time(9, 40), tzinfo=IST),
            "check_out": None,
            "missing_checkout": True,
            "late": False,
            "early": False,
        },
    )
    att.request_regularisation(
        arjun,
        {
            "date": day.isoformat(),
            "check_in": "09:40",
            "check_out": "18:45",
            "mode": "office",
            "reason": "Forgot to check out after the release call",
        },
    )
    rahul = employees["rahul"]
    day2 = add_working_days(rahul.location, today - timedelta(days=12), 0)
    if not Regularisation.objects.filter(employee=rahul, date=day2).exists():
        reg = att.request_regularisation(
            rahul,
            {
                "date": day2.isoformat(),
                "check_in": "09:30",
                "check_out": "18:40",
                "mode": "remote",
                "reason": "Internet outage at home, worked offline",
            },
        )
        att.decide(reg, employees["manager"].user, True, "Thanks for flagging it.")
    return {"records": made, "missing_checkouts": missing}


def demo_joining_date(today: date, location) -> date:
    return add_working_days(location, today + timedelta(days=7), 0)


def seed_hire_demo(employees: dict, password_hash: str, today: date) -> dict:
    """One accepted offer, ready for the one-click hire walkthrough."""
    from seeding.hiring import pass_all_rounds

    email = f"{JOINER[0]}@{D.DEMO_DOMAIN}"
    if User.objects.filter(email=email).exists():
        return {"skipped": True}
    job = Job.objects.filter(title=JOINER_JOB, created_by__email__endswith=D.DEMO_DOMAIN).first()
    if job is None:
        return {"skipped": True}
    candidate = _user(email, JOINER[1], Role.CANDIDATE, password_hash)
    lines = [
        JOINER[1],
        "Frontend Engineer | Bengaluru",
        "SKILLS",
        "React, TypeScript, JavaScript, CSS, Accessibility, Jest",
        "EXPERIENCE",
        "Frontend Engineer, Brightlane Labs (fictional), 2022 - 2026",
        "Built accessible React screens used by thousands of people every day.",
        "Synthetic resume for the TalentPath demo.",
    ]
    application = apply_to_job(
        candidate=candidate, job=job, filename="ishaan-malhotra.pdf", data=make_pdf(lines), silent=True
    )
    recruiter, manager = job.created_by, job.hiring_manager
    move_application(application, S.SCREENING, recruiter, silent=True)
    move_application(application, S.INTERVIEW, recruiter, silent=True)
    pass_all_rounds(application, start_days_ago=9)
    vikram = employees["manager"].user
    joining = demo_joining_date(today, employees["manager"].location)
    offer = offers.create_draft(
        application,
        recruiter,
        {
            "designation": "Frontend Engineer",
            "reporting_manager_id": str(vikram.id),
            "joining_date": joining.isoformat(),
            "expires_on": (today + timedelta(days=4)).isoformat(),
            "fixed_pay": 1450000,
            "variable_pay": 145000,
            "joining_bonus": 50000,
        },
    )
    offers.submit(offer, recruiter)
    if manager:
        offers.approve(offer, manager)
    offers.approve(offer, employees["admin"].user)
    offers.send(offer, recruiter)
    offers.accept(offer, candidate, candidate.full_name)
    Application.objects.filter(pk=application.pk).update(updated_at=timezone.now())
    return {"joiner": JOINER[1], "email": email, "job": job.title, "joining": joining.isoformat()}


def seed_people(staff: dict, password_hash: str) -> dict:
    today = today_ist(timezone.now())
    out = seed_policies()
    employees = seed_employees(staff, password_hash, today)
    out["employees"] = Employee.objects.filter(user__email__endswith=D.DEMO_DOMAIN).count()
    out["onboarding"] = seed_onboarding(employees, today)
    out["leave"] = seed_leave(employees, today)
    out["attendance"] = seed_attendance(employees, today)
    out["hire_demo"] = seed_hire_demo(employees, password_hash, today)
    return out
