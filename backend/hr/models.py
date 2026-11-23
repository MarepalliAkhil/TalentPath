"""People operations: employee records, onboarding, leave, holidays, attendance.

Everything a policy decides (leave quotas, notice, sandwich rule, shifts,
clash thresholds) is data per location that hr_admin edits; the code only
applies it. Reasons and uploaded documents are encrypted at rest.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.fields import EncryptedTextField

User = settings.AUTH_USER_MODEL


class EmployeeStatus(models.TextChoices):
    ONBOARDING = "onboarding", "Onboarding"
    ACTIVE = "active", "Active"


class Employee(models.Model):
    """One per person on the payroll-free employee list. Staff of every role can have one;
    the reporting relationship (not the role) decides who approves their leave."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee")
    code = models.CharField(max_length=20, unique=True)
    designation = models.CharField(max_length=120)
    department = models.ForeignKey("org.Department", on_delete=models.PROTECT, related_name="employees")
    location = models.ForeignKey("org.Location", on_delete=models.PROTECT, related_name="employees")
    manager = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports"
    )
    buddy = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="buddy_for"
    )
    joined_on = models.DateField()
    # Week 4A: the employee's job level ("Your next role" looks at higher levels).
    level = models.ForeignKey(
        "org.JobLevel", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=12, choices=EmployeeStatus.choices, default=EmployeeStatus.ACTIVE)
    hired_from = models.ForeignKey(
        "offers.Offer", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    welcome_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__full_name"]

    def __str__(self) -> str:
        return f"{self.code} {self.user.full_name}"

    @property
    def name(self) -> str:
        return self.user.full_name


# ---------------------------------------------------------------- onboarding
class TaskCategory(models.TextChoices):
    DOCUMENTS = "documents", "Documents"
    POLICIES = "policies", "Policies"
    IT = "it", "IT setup"
    BUDDY = "buddy", "Buddy"
    SESSIONS = "sessions", "First-week sessions"


class TaskOwner(models.TextChoices):
    EMPLOYEE = "employee", "New joiner"
    MANAGER = "manager", "Reporting manager"
    HR = "hr", "HR"
    IT = "it", "IT desk"
    BUDDY = "buddy", "Buddy"


class TaskKind(models.TextChoices):
    TASK = "task", "Mark done"
    UPLOAD = "upload", "Upload a document"
    ACKNOWLEDGE = "acknowledge", "Read and acknowledge"


class OnboardingTemplateItem(models.Model):
    """Checklist template. Items with no department apply to everyone; department items add to them
    (matched by department name, so the template can ship before departments exist)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department_name = models.CharField(max_length=100, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=300, blank=True, default="")
    category = models.CharField(max_length=12, choices=TaskCategory.choices)
    owner = models.CharField(max_length=10, choices=TaskOwner.choices)
    kind = models.CharField(max_length=12, choices=TaskKind.choices, default=TaskKind.TASK)
    # Working days relative to the joining date (negative = before day one).
    due_offset_days = models.SmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "title"]


class OnboardingTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="tasks")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=300, blank=True, default="")
    category = models.CharField(max_length=12, choices=TaskCategory.choices)
    owner_kind = models.CharField(max_length=10, choices=TaskOwner.choices)
    # The person responsible; None for HR / IT tasks any hr_admin can complete.
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=12, choices=TaskKind.choices, default=TaskKind.TASK)
    due_on = models.DateField()
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    document = models.ForeignKey(
        "files.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["order", "due_on"]


class FirstWeekSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="sessions")
    day = models.DateField()
    starts = models.TimeField()
    title = models.CharField(max_length=160)
    host = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    host_label = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["day", "starts"]


class HandbookSection(models.Model):
    """Employee handbook text, searched by the HR assistant (BM25) and shown on /hr/policies."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=160)
    keywords = models.CharField(max_length=300, blank=True, default="")
    body = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]


# ---------------------------------------------------------------- leave policy (data)
class LeaveCode(models.TextChoices):
    CASUAL = "casual", "Casual leave"
    SICK = "sick", "Sick leave"
    EARNED = "earned", "Earned leave"
    COMP_OFF = "comp_off", "Comp-off"
    LOSS_OF_PAY = "lop", "Loss of pay"


class LeaveType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey("org.Location", on_delete=models.CASCADE, related_name="leave_types")
    code = models.CharField(max_length=10, choices=LeaveCode.choices)
    name = models.CharField(max_length=60)
    yearly_quota = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("0"))
    # True: quota/12 is credited each month. False: the year's quota is granted on 1 January.
    monthly_accrual = models.BooleanField(default=False)
    prorate_joiners = models.BooleanField(default=True)
    carry_forward_cap = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("0"))
    min_notice_days = models.PositiveSmallIntegerField(default=0)
    backdate_days = models.PositiveSmallIntegerField(default=0)
    max_consecutive_days = models.PositiveSmallIntegerField(null=True, blank=True)
    half_day_allowed = models.BooleanField(default=True)
    document_after_days = models.PositiveSmallIntegerField(null=True, blank=True)
    sandwich_rule = models.BooleanField(default=False)
    # Loss of pay has no balance; every other type cannot go below zero.
    unpaid = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["location", "code"], name="uniq_leave_type_per_location")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.location})"


class Holiday(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey("org.Location", on_delete=models.CASCADE, related_name="holidays")
    date = models.DateField()
    name = models.CharField(max_length=120)
    regional = models.BooleanField(default=False)
    note = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["location", "date"], name="uniq_holiday_per_day")]


class WorkPolicy(models.Model):
    """Per-location rules: shift, attendance grace, leave approval threshold, team clash threshold."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.OneToOneField("org.Location", on_delete=models.CASCADE, related_name="work_policy")
    shift_start = models.TimeField()
    shift_end = models.TimeField()
    late_grace_minutes = models.PositiveSmallIntegerField(default=15)
    early_grace_minutes = models.PositiveSmallIntegerField(default=15)
    # ISO weekdays that are off (6 = Saturday, 7 = Sunday).
    weekly_off = models.JSONField(default=list)
    # Leaves longer than this many days also need hr_admin.
    hr_approval_over_days = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("5"))
    # Warn when fewer than this share of a team would be available on a day.
    min_team_available_pct = models.PositiveSmallIntegerField(default=50)
    escalate_after_hours = models.PositiveSmallIntegerField(default=48)
    # Week 4A: when an internal applicant's reporting manager is told (never at application time).
    internal_manager_notice = models.CharField(
        max_length=10, choices=[("interview", "At Interview"), ("offer", "At Offer")], default="interview"
    )


# ---------------------------------------------------------------- leave
class LedgerKind(models.TextChoices):
    GRANT = "grant", "Yearly grant"
    ACCRUAL = "accrual", "Monthly accrual"
    CARRY = "carry", "Carried forward"
    LAPSE = "lapse", "Lapsed at year end"
    USE = "use", "Leave taken"
    REVERSAL = "reversal", "Leave cancelled"
    ADJUST = "adjust", "Adjustment by HR"


class LeaveLedger(models.Model):
    """Every change to a balance. `key` makes accrual, carry-forward and usage idempotent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="ledger")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="+")
    year = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=10, choices=LedgerKind.choices)
    days = models.DecimalField(max_digits=5, decimal_places=1)
    key = models.CharField(max_length=160, unique=True)
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class LeaveStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class ApprovalStage(models.TextChoices):
    NONE = "", "None"
    MANAGER = "manager", "Reporting manager"
    HR = "hr", "HR"


class HalfDay(models.TextChoices):
    NONE = "", "Full day"
    FIRST = "first", "First half"
    SECOND = "second", "Second half"


class LeaveRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="+")
    start = models.DateField()
    end = models.DateField()
    half = models.CharField(max_length=6, choices=HalfDay.choices, blank=True, default="")
    days = models.DecimalField(max_digits=5, decimal_places=1)
    reason = EncryptedTextField(blank=True, default="")
    document = models.ForeignKey(
        "files.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(
        max_length=10, choices=LeaveStatus.choices, default=LeaveStatus.PENDING, db_index=True
    )
    stage = models.CharField(max_length=8, choices=ApprovalStage.choices, blank=True, default="")
    # Who must act now. None at the HR stage means any hr_admin.
    approver = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    assigned_at = models.DateTimeField(null=True, blank=True)
    delegated = models.BooleanField(default=False)
    escalated = models.BooleanField(default=False)
    manager_approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = EncryptedTextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start", "-created_at"]


class LeaveAction(models.Model):
    """Timeline of a request (submitted, delegated, escalated, approved...). Append-only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name="actions")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=20)
    detail = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


# ---------------------------------------------------------------- attendance
class WorkMode(models.TextChoices):
    OFFICE = "office", "Office"
    REMOTE = "remote", "Remote"


class AttendanceRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()  # IST calendar day
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=8, choices=WorkMode.choices, default=WorkMode.OFFICE)
    late = models.BooleanField(default=False)
    early = models.BooleanField(default=False)
    missing_checkout = models.BooleanField(default=False)
    regularised = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="uniq_attendance_per_day")]


class RegularisationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Regularisation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="regularisations")
    date = models.DateField()
    check_in = models.TimeField()
    check_out = models.TimeField()
    mode = models.CharField(max_length=8, choices=WorkMode.choices, default=WorkMode.OFFICE)
    reason = EncryptedTextField()
    status = models.CharField(
        max_length=10, choices=RegularisationStatus.choices, default=RegularisationStatus.PENDING
    )
    approver = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = EncryptedTextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


# ---------------------------------------------------------------- internal mobility (week 4A)
class InternalMove(models.Model):
    """An employee moved to another role through an internal application. Append-only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="moves")
    application = models.ForeignKey(
        "applications.Application", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    from_department = models.CharField(max_length=100)
    to_department = models.CharField(max_length=100)
    from_designation = models.CharField(max_length=120)
    to_designation = models.CharField(max_length=120)
    from_manager = models.CharField(max_length=120, blank=True, default="")
    to_manager = models.CharField(max_length=120, blank=True, default="")
    moved_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-moved_on"]
