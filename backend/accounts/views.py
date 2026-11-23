from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from core.audit import audit
from core.auth import clear_auth_cookies, set_auth_cookies
from core.demo import demo_account_for, demo_config, demo_mode, deny_demo, is_demo_email
from core.utils import paginate
from core.views import PolicyAPIView

from .models import Profile, Role, User
from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    StaffCreateSerializer,
    UserUpdateSerializer,
    user_dict,
)
from .services import create_user, revoke_sessions, send_password_reset, send_staff_invite, set_phone


def _signed_in_response(user: User, status_code: int) -> Response:
    refresh = RefreshToken.for_user(user)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    response = Response({"user": user_dict(user)}, status=status_code)
    set_auth_cookies(response, refresh)
    return response


class CsrfView(PolicyAPIView):
    policy_action = "auth.csrf"

    def get(self, request):
        get_token(request._request)
        return Response({"detail": "CSRF cookie set."})


class RegisterView(PolicyAPIView):
    policy_action = "auth.register"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        data = RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = create_user(
            email=v["email"], full_name=v["full_name"], role=Role.CANDIDATE, password=v["password"]
        )
        audit(request, "auth.register", actor=user, target=user)
        return _signed_in_response(user, status.HTTP_201_CREATED)


class LoginView(PolicyAPIView):
    policy_action = "auth.login"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"].strip().lower()
        lock_key = f"login-fail:{email}"
        failures = cache.get(lock_key, 0)
        if failures >= settings.LOGIN_MAX_FAILURES:
            audit(request, "auth.login_locked", email_domain=email.split("@")[-1])
            return Response(
                {"detail": "Too many failed attempts. Try again in 15 minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        user = authenticate(request._request, username=email, password=data.validated_data["password"])
        if user is None:
            cache.set(lock_key, failures + 1, settings.LOGIN_LOCK_SECONDS)
            audit(request, "auth.login_failed", email_domain=email.split("@")[-1])
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        cache.delete(lock_key)
        audit(request, "auth.login", actor=user, target=user)
        return _signed_in_response(user, status.HTTP_200_OK)


class LogoutView(PolicyAPIView):
    policy_action = "auth.logout"

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        if request.user.is_authenticated:
            audit(request, "auth.logout")
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


class RefreshView(PolicyAPIView):
    policy_action = "auth.refresh"
    authentication_classes = []

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE)
        serializer = TokenRefreshSerializer(data={"refresh": raw or ""})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken, AuthenticationFailed, serializers.ValidationError):
            response = Response({"detail": "Session expired."}, status=401)
            clear_auth_cookies(response)
            return response
        refresh = RefreshToken(serializer.validated_data["refresh"])
        response = Response({"detail": "Refreshed."})
        set_auth_cookies(response, refresh)
        return response


class MeView(PolicyAPIView):
    policy_action = "auth.me"

    def get(self, request):
        return Response({"user": user_dict(request.user)})


class PasswordResetRequestView(PolicyAPIView):
    policy_action = "auth.password_reset"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        data = PasswordResetRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=data.validated_data["email"].strip(), is_active=True).first()
        # Demo accounts cannot change their password in demo mode (same answer, so nothing leaks).
        if user is not None and not (demo_mode() and is_demo_email(user.email)):
            send_password_reset(user)
            audit(request, "auth.password_reset_requested", actor=user, target=user)
        return Response(
            {"detail": "If an account exists for that email, a reset link is on its way."},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(PolicyAPIView):
    policy_action = "auth.password_reset_confirm"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        data = PasswordResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = None
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(v["uid"])))
        except (ValueError, TypeError, OverflowError, DjangoValidationError, User.DoesNotExist):
            user = None
        if user is None or not user.is_active or not default_token_generator.check_token(user, v["token"]):
            return Response(
                {"detail": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if demo_mode() and is_demo_email(user.email):
            return Response({"detail": "Demo accounts cannot change their password."}, status=403)
        try:
            validate_password(v["password"], user=user)
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=400)
        user.set_password(v["password"])
        user.save(update_fields=["password"])
        revoke_sessions(user)
        audit(request, "auth.password_reset_completed", actor=user, target=user)
        return Response({"detail": "Password updated. You can sign in now."})


def profile_dict(user: User, profile: Profile) -> dict:
    return {
        **user_dict(user),
        "headline": profile.headline,
        "location_text": profile.location_text,
        "phone": profile.phone,
        "address": profile.address,
    }


class ProfileView(PolicyAPIView):
    policy_actions = {"GET": "profile.read", "PATCH": "profile.update"}

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        return Response(profile_dict(request.user, profile))

    def patch(self, request):
        data = ProfileUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = request.user
        profile, _ = Profile.objects.get_or_create(user=user)
        if "full_name" in v:
            user.full_name = v["full_name"].strip()
            user.save(update_fields=["full_name"])
        for field in ("headline", "location_text", "address"):
            if field in v:
                setattr(profile, field, v[field].strip())
        if "phone" in v:
            set_phone(profile, v["phone"])
        profile.save()
        audit(request, "profile.update", target=profile, fields=sorted(v.keys()))
        return Response(profile_dict(user, profile))


class UserListCreateView(PolicyAPIView):
    policy_actions = {"GET": "users.list", "POST": "users.create"}

    def get(self, request):
        qs = User.objects.all().order_by("role", "full_name")
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q))
        return paginate(self, request, qs, user_dict)

    def post(self, request):
        deny_demo(request.user, "invite staff")
        data = StaffCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = create_user(email=v["email"], full_name=v["full_name"], role=v["role"])
        send_staff_invite(user, invited_by=request.user)
        audit(request, "users.create", target=user, role=user.role)
        return Response(user_dict(user), status=status.HTTP_201_CREATED)


class UserDetailView(PolicyAPIView):
    policy_actions = {"PATCH": "users.update"}

    def patch(self, request, pk):
        deny_demo(request.user, "change staff accounts")
        user = get_object_or_404(User, pk=pk)
        data = UserUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        if user == request.user and (v.get("is_active") is False or v.get("role", user.role) != user.role):
            return Response({"detail": "You cannot deactivate or demote your own account."}, status=400)
        changed = []
        for field in ("full_name", "role", "is_active"):
            if field in v and getattr(user, field) != v[field]:
                setattr(user, field, v[field])
                changed.append(field)
        if changed:
            user.save(update_fields=changed)
            if "role" in changed or "is_active" in changed:
                revoke_sessions(user)
            audit(request, "users.update", target=user, fields=changed)
        return Response(user_dict(user))


class HiringManagerListView(PolicyAPIView):
    """Minimal directory so recruiters can assign a hiring manager to a job."""

    policy_action = "users.hiring_managers"

    def get(self, request):
        qs = User.objects.filter(role=Role.HIRING_MANAGER, is_active=True).order_by("full_name")
        return Response([{"id": str(u.id), "full_name": u.full_name} for u in qs])


# ---------------------------------------------------------------- demo mode (week 4A)
class DemoConfigView(PolicyAPIView):
    """Whether demo mode is on, the banner text and which "Try as" buttons to show."""

    policy_action = "demo.config"

    def get(self, request):
        return Response(demo_config())


class DemoLoginView(PolicyAPIView):
    """Sign in to a seeded demo account by role. Only works when DEMO_MODE is on."""

    policy_action = "auth.demo_login"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        if not demo_mode():
            return Response({"detail": "Demo sign-in is switched off."}, status=status.HTTP_404_NOT_FOUND)
        user = demo_account_for(str(request.data.get("role") or ""))
        if user is None:
            return Response({"role": "Choose one of the demo roles (run the seed first)."}, status=400)
        audit(request, "auth.demo_login", actor=user, target=user, role=user.role)
        return _signed_in_response(user, status.HTTP_200_OK)
