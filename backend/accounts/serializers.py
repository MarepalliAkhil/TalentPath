import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.policy import dashboard_for

from .models import STAFF_ROLES, User

PHONE_RE = re.compile(r"^[+0-9 ()\-]{7,20}$")


def user_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": user.get_role_display(),
        "dashboard": dashboard_for(user.role),
        "is_active": user.is_active,
    }


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    accept_terms = serializers.BooleanField(required=False, default=False)

    def validate_accept_terms(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("Accept the Terms and the Privacy Policy to create an account.")
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        probe = User(email=attrs["email"], full_name=attrs["full_name"])
        validate_password(attrs["password"], user=probe)
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=200)
    token = serializers.CharField(max_length=200)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


URL_RE = re.compile(r"^https://[^\s]{3,190}$")
LOCKED_FIELDS = ("email", "full_name", "date_of_birth", "role", "employee_code", "joined_on")


def _https_url(value: str) -> str:
    value = (value or "").strip()
    if value and not value.startswith(("http://", "https://")):
        value = "https://" + value
    if value.startswith("http://"):
        value = "https://" + value[len("http://") :]
    if value and not URL_RE.match(value):
        raise serializers.ValidationError("Use a full web address, for example https://github.com/you.")
    return value


class EducationRow(serializers.Serializer):
    qualification = serializers.CharField(max_length=120)
    college = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    branch = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    year = serializers.CharField(max_length=4, required=False, allow_blank=True, default="")
    score = serializers.CharField(max_length=12, required=False, allow_blank=True, default="")


class ExperienceRow(serializers.Serializer):
    company = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    title = serializers.CharField(max_length=120)
    start = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    end = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    responsibilities = serializers.CharField(max_length=1500, required=False, allow_blank=True, default="")


class ProfileUpdateSerializer(serializers.Serializer):
    """What a person may change about themselves. Locked fields are refused (D-81)."""

    headline = serializers.CharField(max_length=160, required=False, allow_blank=True)
    location_text = serializers.CharField(max_length=120, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    linkedin_url = serializers.CharField(max_length=200, required=False, allow_blank=True)
    github_url = serializers.CharField(max_length=200, required=False, allow_blank=True)
    portfolio_url = serializers.CharField(max_length=200, required=False, allow_blank=True)
    skills = serializers.ListField(
        child=serializers.CharField(max_length=80), required=False, max_length=60, allow_empty=True
    )
    education = EducationRow(many=True, required=False, max_length=8)
    experience = ExperienceRow(many=True, required=False, max_length=12)
    # Allowed only while empty; afterwards it is locked like the other identity fields.
    date_of_birth = serializers.DateField(required=False)

    def validate_phone(self, value: str) -> str:
        value = value.strip()
        if value and not PHONE_RE.match(value):
            raise serializers.ValidationError("Use digits, spaces, +, - or brackets (7-20).")
        return value

    def validate_linkedin_url(self, value):
        return _https_url(value)

    def validate_github_url(self, value):
        return _https_url(value)

    def validate_portfolio_url(self, value):
        return _https_url(value)

    def validate_skills(self, value):
        seen, out = set(), []
        for name in value:
            name = name.strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append(name)
        return out

    def validate_date_of_birth(self, value):
        from datetime import date

        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 16 or age > 80:
            raise serializers.ValidationError("Enter a date of birth for someone aged 16 to 80.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class NotificationPrefsSerializer(serializers.Serializer):
    prefs = serializers.DictField(child=serializers.BooleanField())

    def validate_prefs(self, value):
        from notifications.templates import CATEGORIES

        unknown = set(value) - set(CATEGORIES)
        if unknown:
            raise serializers.ValidationError(f"Unknown categories: {', '.join(sorted(unknown))}.")
        return value


class StaffEmployeeSerializer(serializers.Serializer):
    """Optional employee record created together with a staff account."""

    department = serializers.UUIDField()
    location = serializers.UUIDField()
    designation = serializers.CharField(min_length=2, max_length=120)
    joined_on = serializers.DateField()
    manager = serializers.UUIDField(required=False, allow_null=True)
    company = serializers.UUIDField(required=False, allow_null=True)


class StaffCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120)
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=[(r.value, r.label) for r in STAFF_ROLES])
    employee = StaffEmployeeSerializer(required=False, allow_null=True)

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value


class UserUpdateSerializer(serializers.Serializer):
    """Admin changes (D-80, D-81). Locked fields need a reason, and every change is audited."""

    role = serializers.ChoiceField(choices=[(r.value, r.label) for r in STAFF_ROLES], required=False)
    is_active = serializers.BooleanField(required=False)
    full_name = serializers.CharField(min_length=2, max_length=120, required=False)
    email = serializers.EmailField(max_length=254, required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    employee_code = serializers.RegexField(r"^[A-Z]{2,4}\d{3,6}$", required=False)
    joined_on = serializers.DateField(required=False)
    manager = serializers.UUIDField(required=False, allow_null=True)
    company = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        locked = [f for f in LOCKED_FIELDS if f in attrs]
        if locked and len(attrs.get("reason", "").strip()) < 10:
            raise serializers.ValidationError(
                {"reason": "Give a reason of at least 10 characters for changing locked fields."}
            )
        return attrs
