"""SimpleJWT tokens carried in HttpOnly cookies, with Django's CSRF check."""

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class _CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request) -> None:
    check = _CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """Reads the access token from the HttpOnly cookie.

    An expired or invalid cookie is treated as anonymous, so protected
    endpoints answer 401 and the SPA can call /api/auth/refresh.
    CSRF is enforced for every unsafe method in core.views.PolicyAPIView.
    """

    def authenticate(self, request):
        raw = request.COOKIES.get(settings.ACCESS_COOKIE)
        if not raw:
            return None
        try:
            token = self.get_validated_token(raw)
            user = self.get_user(token)
        except (InvalidToken, TokenError, exceptions.AuthenticationFailed):
            return None
        return user, token


def _seconds(key: str) -> int:
    return int(settings.SIMPLE_JWT[key].total_seconds())


def set_auth_cookies(response, refresh: RefreshToken) -> None:
    common = {"httponly": True, "secure": settings.COOKIE_SECURE, "samesite": "Lax"}
    response.set_cookie(
        settings.ACCESS_COOKIE,
        str(refresh.access_token),
        max_age=_seconds("ACCESS_TOKEN_LIFETIME"),
        path="/",
        **common,
    )
    response.set_cookie(
        settings.REFRESH_COOKIE,
        str(refresh),
        max_age=_seconds("REFRESH_TOKEN_LIFETIME"),
        path=settings.REFRESH_COOKIE_PATH,
        **common,
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie(settings.ACCESS_COOKIE, path="/", samesite="Lax")
    response.delete_cookie(settings.REFRESH_COOKIE, path=settings.REFRESH_COOKIE_PATH, samesite="Lax")
