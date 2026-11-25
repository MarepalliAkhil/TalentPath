from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from core.brand import get_brand
from core.crypto import blind_index
from notifications.services import queue_email

from .models import Profile, Role, User


@transaction.atomic
def create_user(*, email: str, full_name: str, role: str = Role.CANDIDATE, password=None) -> User:
    user = User.objects.create_user(email=email, password=password, full_name=full_name.strip(), role=role)
    Profile.objects.create(user=user)
    return user


def set_phone(profile: Profile, phone: str) -> None:
    profile.phone = phone or ""
    profile.phone_bidx = blind_index(phone, "phone") if phone else ""


def reset_link(user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
    token = default_token_generator.make_token(user)
    return f"{settings.SITE_URL}/reset-password?uid={uid}&token={token}"


def send_password_reset(user: User) -> None:
    product = get_brand()["name"]
    queue_email(
        to_email=user.email,
        user=user,
        kind="password_reset",
        subject=f"Reset your {product} password",
        body=(
            f"Hi {user.full_name},\n\nUse this link within 1 hour to choose a new password:\n"
            f"{reset_link(user)}\n\nIf you did not ask for this, you can ignore this email."
        ),
    )


def send_registration_email(user: User) -> None:
    product = get_brand()["name"]
    queue_email(
        to_email=user.email,
        user=user,
        kind="registration",
        subject=f"Welcome to {product}",
        body=(
            f"Hi {user.full_name},\n\nYour account is ready. We read your resume and filled in "
            "your profile: please check your phone, links, skills, education and experience "
            f"before you apply.\n\n{settings.SITE_URL}/profile"
        ),
    )


def send_staff_invite(user: User, invited_by: User) -> None:
    product = get_brand()["name"]
    queue_email(
        to_email=user.email,
        user=user,
        kind="staff_invite",
        subject=f"You have been invited to {product}",
        body=(
            f"Hi {user.full_name},\n\n{invited_by.full_name} created a {user.get_role_display()} "
            f"account for you. Set your password within 1 hour:\n{reset_link(user)}\n"
        ),
    )


def revoke_sessions(user: User) -> int:
    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        count += int(created)
    return count
