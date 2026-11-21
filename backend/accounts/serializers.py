import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.policy import dashboard_for

from .models import STAFF_ROLES, Role, User

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


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120, required=False)
    headline = serializers.CharField(max_length=160, required=False, allow_blank=True)
    location_text = serializers.CharField(max_length=120, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)

    def validate_phone(self, value: str) -> str:
        value = value.strip()
        if value and not PHONE_RE.match(value):
            raise serializers.ValidationError("Use digits, spaces, +, - or brackets (7-20).")
        return value


class StaffCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120)
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=[(r.value, r.label) for r in STAFF_ROLES])

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value


class UserUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120, required=False)
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)
