from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
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
from core.demo import check_demo_upload, demo_account_for, demo_config, demo_mode, deny_demo, is_demo_email
from core.utils import paginate
from core.views import PolicyAPIView
from files.storage import read_file, save_file

from . import people
from .models import Profile, Role, User
from .serializers import (
    LoginSerializer,
    NotificationPrefsSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    StaffCreateSerializer,
    UserUpdateSerializer,
    user_dict,
)
from .services import create_user, revoke_sessions, send_password_reset, send_registration_email, set_phone


class PostOnlyUploadThrottle(ScopedRateThrottle):
    def allow_request(self, request, view):
        return request.method != "POST" or super().allow_request(request, view)


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
    """Candidate registration (D-81): a resume is required. It is checked like an
    application resume, parsed at once and used to pre-fill the profile for review."""

    policy_action = "auth.register"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        from growth.services import save_profile_resume

        from .prefill import dumps, prefill_from_resume

        data = RegisterSerializer(data=request.data)
        errors = {} if data.is_valid() else dict(data.errors)
        upload = request.FILES.get("resume")
        if upload is None:
            errors["resume"] = ["Attach your resume (PDF or DOCX). We use it to fill in your profile."]
        elif upload.size > settings.RESUME_MAX_BYTES:
            errors["resume"] = ["Resumes must be 5 MB or smaller."]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        raw = upload.read(settings.RESUME_MAX_BYTES + 1)
        check_demo_upload(None, len(raw))
        v = data.validated_data
        from applications.resume import ResumeError, inspect_resume

        try:
            inspect_resume(raw)  # refuse a bad file before any account exists
        except ResumeError as exc:
            return Response({"resume": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user = create_user(
                email=v["email"], full_name=v["full_name"], role=Role.CANDIDATE, password=v["password"]
            )
            career = save_profile_resume(user, upload.name, raw, request=request)
            fill = prefill_from_resume(career.resume_text, career.skills)
            profile = user.profile
            set_phone(profile, fill["phone"])
            profile.linkedin_url = fill["linkedin_url"]
            profile.github_url = fill["github_url"]
            profile.portfolio_url = fill["portfolio_url"]
            profile.skills = fill["skills"]
            profile.education = dumps(fill["education"])
            profile.experience = dumps(fill["experience"])
            profile.save()
        audit(
            request,
            "auth.register",
            actor=user,
            target=user,
            prefilled=sorted(k for k, val in fill.items() if val),
        )
        send_registration_email(user)
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


class ProfileView(PolicyAPIView):
    """Every role: read and edit your own details (locked fields refused, D-81)."""

    policy_actions = {"GET": "profile.read", "PATCH": "profile.update"}

    def get(self, request):
        return Response(people.profile_dict(request.user))

    def patch(self, request):
        locked = sorted(set(request.data) & {"email", "full_name", "role", "employee_code", "joined_on"})
        if locked:
            return Response(
                {field: ["This field is locked. Ask an admin to change it."] for field in locked},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = ProfileUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        people.update_own_profile(request, data.validated_data)
        return Response(people.profile_dict(request.user))


class PasswordChangeView(PolicyAPIView):
    policy_action = "profile.password"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        deny_demo(request.user, "change the password")
        data = PasswordChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(data.validated_data["current_password"]):
            return Response({"current_password": ["That is not your current password."]}, status=400)
        try:
            validate_password(data.validated_data["new_password"], user=user)
        except DjangoValidationError as exc:
            return Response({"new_password": list(exc.messages)}, status=400)
        user.set_password(data.validated_data["new_password"])
        user.save(update_fields=["password"])
        revoke_sessions(user)  # sign out every other device; this one gets fresh cookies below
        audit(request, "profile.password_changed", target=user)
        from notifications.services import notify

        notify(
            user,
            kind="password_changed",
            title="Your password was changed",
            body="Your password was just changed. If this was not you, reset it from the sign-in page now.",
            link="/profile",
        )
        return _signed_in_response(user, status.HTTP_200_OK)


class ProfilePhotoView(PolicyAPIView):
    """Your own profile photo. Never used for screening and never shown on applications."""

    policy_action = "profile.photo"
    throttle_classes = [PostOnlyUploadThrottle]
    throttle_scope = "upload"

    def get(self, request):
        profile = Profile.objects.filter(user=request.user).select_related("photo").first()
        if profile is None or profile.photo is None:
            return Response({"detail": "No photo."}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(read_file(profile.photo), content_type=profile.photo.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def post(self, request):
        upload = request.FILES.get("photo")
        if upload is None:
            return Response({"photo": ["Choose a PNG, JPEG or WebP image."]}, status=400)
        if upload.size > people.PHOTO_MAX_BYTES:
            return Response({"photo": ["Photos must be 2 MB or smaller."]}, status=400)
        raw = upload.read(people.PHOTO_MAX_BYTES + 1)
        ctype = people.photo_type(raw)
        if not ctype:
            return Response({"photo": ["Choose a PNG, JPEG or WebP image."]}, status=400)
        check_demo_upload(request.user, len(raw), field="photo")
        profile, _ = Profile.objects.get_or_create(user=request.user)
        old = profile.photo
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[ctype]
        profile.photo = save_file(
            owner=request.user, original_name=f"photo.{ext}", content_type=ctype, raw=raw
        )
        profile.save(update_fields=["photo", "updated_at"])
        if old is not None:
            old.delete()
        audit(request, "profile.photo_uploaded", target=profile)
        return Response(people.profile_dict(request.user), status=status.HTTP_201_CREATED)

    def delete(self, request):
        profile = Profile.objects.filter(user=request.user).select_related("photo").first()
        if profile and profile.photo:
            old = profile.photo
            profile.photo = None
            profile.save(update_fields=["photo", "updated_at"])
            old.delete()
            audit(request, "profile.photo_deleted", target=profile)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationPrefsView(PolicyAPIView):
    policy_action = "profile.notifications"

    def put(self, request):
        data = NotificationPrefsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.notification_prefs = {**(profile.notification_prefs or {}), **data.validated_data["prefs"]}
        profile.save(update_fields=["notification_prefs", "updated_at"])
        audit(request, "profile.notifications", target=profile, prefs=profile.notification_prefs)
        return Response(people.profile_dict(request.user))


def admin_user_dict(user: User) -> dict:
    emp = getattr(user, "employee", None) if hasattr(user, "employee") else None
    return {
        **user_dict(user),
        "created_at": user.created_at.isoformat(),
        "employee": people.employee_dict(emp),
    }


class UserListCreateView(PolicyAPIView):
    """Admin: every account. Never a delete: people with history are deactivated (D-80)."""

    policy_actions = {"GET": "users.list", "POST": "users.create"}

    def get(self, request):
        qs = User.objects.select_related(
            "employee__manager__user", "employee__company", "employee__department", "employee__location"
        ).order_by("role", "full_name")
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role__in=role.split(","))
        active = request.query_params.get("active")
        if active in ("0", "1"):
            qs = qs.filter(is_active=active == "1")
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q))
        if request.query_params.get("has_employee") == "1":
            qs = qs.filter(employee__isnull=False)
        # Up to 200 per page, so the reporting-manager picker can list everyone in one call.
        return paginate(self, request, qs, admin_user_dict, max_page_size=200)

    def post(self, request):
        deny_demo(request.user, "invite staff")
        data = StaffCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = people.create_staff(request, data.validated_data)
        return Response(admin_user_dict(user), status=status.HTTP_201_CREATED)


class UserDetailView(PolicyAPIView):
    policy_actions = {"GET": "users.read", "PATCH": "users.update"}

    def _user(self, pk):
        return get_object_or_404(
            User.objects.select_related("employee__manager__user", "employee__company", "profile"), pk=pk
        )

    def get(self, request, pk):
        user = self._user(pk)
        data = admin_user_dict(user)
        # Staff identity fields the admin may need to correct. Candidates' personal data and
        # documents are not part of the admin's view (D-80).
        profile = getattr(user, "profile", None)
        data["date_of_birth"] = (
            (profile.date_of_birth or None) if profile and user.role != Role.CANDIDATE else None
        )
        return Response(data)

    def patch(self, request, pk):
        deny_demo(request.user, "change staff accounts")
        user = self._user(pk)
        data = UserUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        people.admin_update(request, user, data.validated_data)
        user.refresh_from_db()
        return Response(admin_user_dict(user))


class HiringManagerListView(PolicyAPIView):
    """Minimal directory so recruiters can assign a hiring manager to a job."""

    policy_action = "users.hiring_managers"

    def get(self, request):
        qs = User.objects.filter(role=Role.MANAGER, is_active=True).order_by("full_name")
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
