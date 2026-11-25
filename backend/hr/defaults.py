"""Starting configuration. HR can change all of it on the HR settings page.

`DEFAULT_LEAVE_TYPES` and `DEFAULT_WORK_POLICY` are applied per location by the
seed (and by tests); the checklist template and handbook ship as a data
migration so every environment has them.
"""

from datetime import time
from decimal import Decimal

DEFAULT_LEAVE_TYPES = [
    {
        "code": "casual",
        "name": "Casual leave",
        "yearly_quota": Decimal("12"),
        "monthly_accrual": True,
        "carry_forward_cap": Decimal("0"),
        "min_notice_days": 1,
        "max_consecutive_days": 3,
        "half_day_allowed": True,
        "sandwich_rule": False,
    },
    {
        "code": "sick",
        "name": "Sick leave",
        "yearly_quota": Decimal("10"),
        "monthly_accrual": False,
        "carry_forward_cap": Decimal("0"),
        "min_notice_days": 0,
        "backdate_days": 7,
        "half_day_allowed": True,
        "document_after_days": 2,
        "sandwich_rule": False,
    },
    {
        "code": "earned",
        "name": "Earned leave",
        "yearly_quota": Decimal("18"),
        "monthly_accrual": True,
        "carry_forward_cap": Decimal("15"),
        "min_notice_days": 7,
        "max_consecutive_days": 15,
        "half_day_allowed": False,
        "sandwich_rule": True,
    },
    {
        "code": "comp_off",
        "name": "Comp-off",
        "yearly_quota": Decimal("0"),
        "monthly_accrual": False,
        "carry_forward_cap": Decimal("0"),
        "min_notice_days": 1,
        "max_consecutive_days": 2,
        "half_day_allowed": True,
        "sandwich_rule": False,
    },
    {
        "code": "lop",
        "name": "Loss of pay",
        "yearly_quota": Decimal("0"),
        "monthly_accrual": False,
        "carry_forward_cap": Decimal("0"),
        "min_notice_days": 3,
        "max_consecutive_days": 30,
        "half_day_allowed": True,
        "sandwich_rule": True,
        "unpaid": True,
    },
]

DEFAULT_WORK_POLICY = {
    "shift_start": time(9, 30),
    "shift_end": time(18, 30),
    "late_grace_minutes": 15,
    "early_grace_minutes": 15,
    "weekly_off": [6, 7],
    "hr_approval_over_days": Decimal("5"),
    "min_team_available_pct": 50,
    "escalate_after_hours": 48,
}


def ensure_location_defaults(location, *, overrides: dict | None = None) -> None:
    """Create the default leave types and work policy for a location if missing (never overwrites)."""
    from .models import LeaveType, WorkPolicy

    for spec in DEFAULT_LEAVE_TYPES:
        values = {**spec, **((overrides or {}).get(spec["code"], {}))}
        code = values.pop("code")
        LeaveType.objects.get_or_create(location=location, code=code, defaults=values)
    WorkPolicy.objects.get_or_create(location=location, defaults=dict(DEFAULT_WORK_POLICY))


# (department name or None, order, title, description, category, owner, kind, working-day offset)
CHECKLIST_TEMPLATE = [
    (
        None,
        10,
        "Upload ID and address proof",
        "PAN or Aadhaar and a recent address proof (synthetic in this demo).",
        "documents",
        "employee",
        "upload",
        -2,
    ),
    (
        None,
        20,
        "Upload education certificates",
        "Your highest qualification certificate.",
        "documents",
        "employee",
        "upload",
        2,
    ),
    (
        None,
        30,
        "Read and acknowledge the code of conduct",
        "Covers conduct, POSH and data privacy.",
        "policies",
        "employee",
        "acknowledge",
        1,
    ),
    (
        None,
        40,
        "Read and acknowledge the leave and attendance policy",
        "Leave types, notice, sandwich rule, shifts and regularisation.",
        "policies",
        "employee",
        "acknowledge",
        2,
    ),
    (
        None,
        50,
        "Prepare laptop and accounts",
        "Laptop, email, single sign-on and VPN ready before day one.",
        "it",
        "it",
        "task",
        -1,
    ),
    (None, 60, "Add to team channels and calendars", "", "it", "manager", "task", 0),
    (None, 70, "Meet your buddy", "Lunch with your buddy on day two.", "buddy", "buddy", "task", 1),
    (None, 80, "Set 30-day goals with your manager", "", "sessions", "manager", "task", 4),
    (
        None,
        90,
        "Attend the HR induction",
        "Policies, leave and attendance in TalentPath.",
        "sessions",
        "employee",
        "task",
        3,
    ),
    (None, 100, "Verify documents", "HR checks the uploaded documents.", "documents", "hr", "task", 4),
    (
        "Engineering",
        55,
        "Set up the development environment",
        "Repository access, local build and the first pull request.",
        "it",
        "employee",
        "task",
        2,
    ),
    ("Engineering", 85, "Pair on a starter ticket", "", "sessions", "buddy", "task", 4),
    (
        "Data & AI",
        55,
        "Get data platform access",
        "Warehouse, notebooks and data-access training.",
        "it",
        "it",
        "task",
        1,
    ),
    (
        "Platform & Security",
        55,
        "Complete security onboarding",
        "Secrets handling, on-call basics and access reviews.",
        "policies",
        "employee",
        "acknowledge",
        3,
    ),
    ("Sales", 55, "CRM access and territory briefing", "", "it", "manager", "task", 2),
    ("Customer Success", 55, "Shadow two customer calls", "", "sessions", "buddy", "task", 4),
    ("Design", 55, "Design tools and design-system walkthrough", "", "it", "buddy", "task", 2),
    ("Product", 55, "Product roadmap walkthrough", "", "sessions", "manager", "task", 3),
]

HANDBOOK = [
    (
        "leave-overview",
        "Leave at Lumina Works",
        "leave types casual sick earned comp off loss of pay quota balance",
        "Every location sets its own leave types, quotas and rules; your leave page shows the ones that apply to you. "
        "Casual and earned leave are credited every month, sick leave is granted on 1 January, and joiners get a "
        "prorated share from their joining month (the joining month counts if you join by the 15th). Comp-off is "
        "credited by HR when you work on a holiday. Loss of pay is unpaid and has no balance.",
    ),
    (
        "applying",
        "Applying for leave",
        "apply notice approval manager hr approve reject cancel",
        "Apply on the leave page or ask HIRA; you always see the days counted and any rule that is not met before "
        "you submit. Your reporting manager approves; leave longer than the location's threshold also needs HR. "
        "If your manager is on leave, the request goes to their manager. Requests waiting more than 48 hours are "
        "escalated one level up. You can cancel before the start date, and approved days return to your balance.",
    ),
    (
        "sandwich-rule",
        "Sandwich rule",
        "sandwich weekend holiday between leave counted",
        "When the sandwich rule is on for a leave type, weekends and holidays that fall between two leave days are "
        "counted as leave, including when the leave days are in two separate requests. When it is off, only "
        "working days are counted. Earned leave and loss of pay use the sandwich rule by default.",
    ),
    (
        "carry-forward",
        "Carry forward and lapse",
        "carry forward lapse year end unused encash",
        "At the start of each year, unused days carry forward up to the cap set for that leave type, and anything "
        "above the cap lapses. Earned leave carries up to 15 days by default; casual and sick leave do not carry "
        "forward. Leave encashment is not part of this demo.",
    ),
    (
        "sick-documents",
        "Sick leave and medical certificates",
        "sick medical certificate document doctor fever",
        "Sick leave needs no advance notice and can be applied up to 7 days after you were unwell. For sick leave "
        "longer than 2 days, attach a medical certificate (PDF or image). Documents are encrypted and only you, "
        "your approver and HR can open them.",
    ),
    (
        "attendance",
        "Attendance and shifts",
        "attendance check in check out shift timings late early office remote",
        "Check in and check out on the attendance page and choose office or remote; no location is tracked. The "
        "general shift is 09:30 to 18:30 with 15 minutes' grace, so a check-in after 09:45 is marked late and a "
        "check-out before 18:15 early. Each location can set its own shift.",
    ),
    (
        "regularisation",
        "Regularising attendance",
        "regularise regularisation regularize missed check out correction",
        "If you forgot to check out, or worked without checking in, request a regularisation for that day with your "
        "actual times and a reason within 30 days. Your reporting manager approves it.",
    ),
    (
        "hybrid-work",
        "Hybrid and remote work",
        "remote hybrid work from home wfh office days",
        "Most teams work hybrid: agree office days with your manager and record remote days when you check in. "
        "Remote (India) roles work fully remote.",
    ),
    (
        "probation",
        "Probation",
        "probation confirmation review notice period",
        "New joiners are on probation for six months, with check-ins at 30, 60 and 90 days. Your manager confirms you at the end of probation.",
    ),
    (
        "conduct",
        "Code of conduct and POSH",
        "conduct posh harassment complaint ethics respect",
        "Treat everyone with respect. Harassment of any kind is not tolerated; raise concerns with HR or the "
        "internal committee under the POSH policy, confidentially. This is a demo handbook for a fictional company.",
    ),
    (
        "it-equipment",
        "Laptop and IT",
        "laptop it equipment vpn email password security",
        "You get a laptop and accounts before day one. Keep the laptop encrypted and locked, never share passwords, "
        "and report a lost device to the IT desk the same day.",
    ),
    (
        "parental-leave",
        "Maternity and paternity leave",
        "maternity paternity parental adoption baby",
        "Maternity leave follows the Maternity Benefit Act (26 weeks for the first two children); paternity leave is "
        "10 working days. HR records these directly; they are not part of the self-service leave types in this demo.",
    ),
]
