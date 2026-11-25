"""Django settings.

Every secret comes from the environment. The process refuses to start when a
required variable is missing, so a misconfigured deploy fails loudly instead of
running with weak defaults.
"""

import base64
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader (standard library only). Real env vars win."""
    if os.environ.get("DJANGO_LOAD_DOTENV", "1") == "0":
        return
    path = BASE_DIR / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = env(name)
    return int(value) if value else default


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


REQUIRED_ENV = (
    "SECRET_KEY",
    "DATABASE_URL",
    "FIELD_ENCRYPTION_KEY",
    "BLIND_INDEX_KEY",
    "INTERNAL_TICK_SECRET",
)
_missing = [name for name in REQUIRED_ENV if not env(name)]
if _missing:
    raise ImproperlyConfigured(
        "Missing required environment variables: "
        + ", ".join(_missing)
        + ". Copy backend/.env.example to backend/.env and fill them in."
    )

DEBUG = env_bool("DEBUG", False)
SECRET_KEY = env("SECRET_KEY")
if len(SECRET_KEY) < 32:
    raise ImproperlyConfigured("SECRET_KEY must be at least 32 characters long.")


def _key_bytes(name: str) -> bytes:
    raw = env(name)
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:  # binascii.Error, ValueError
        raise ImproperlyConfigured(f"{name} must be URL-safe base64.") from exc
    if len(key) != 32:
        raise ImproperlyConfigured(f"{name} must decode to exactly 32 bytes.")
    return key


FIELD_ENCRYPTION_KEY_BYTES = _key_bytes("FIELD_ENCRYPTION_KEY")
BLIND_INDEX_KEY_BYTES = _key_bytes("BLIND_INDEX_KEY")
if FIELD_ENCRYPTION_KEY_BYTES == BLIND_INDEX_KEY_BYTES:
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY and BLIND_INDEX_KEY must differ.")
INTERNAL_TICK_SECRET = env("INTERNAL_TICK_SECRET")
if len(INTERNAL_TICK_SECRET) < 24:
    raise ImproperlyConfigured("INTERNAL_TICK_SECRET must be at least 24 characters long.")


# --- Production (Render) -------------------------------------------------------
# Render sets RENDER=true on every service. PRODUCTION=true applies the same rules anywhere else.
PRODUCTION = env_bool("PRODUCTION", env_bool("RENDER", False))
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME")
FRONTEND_DOMAIN = env("FRONTEND_DOMAIN").removeprefix("https://").removeprefix("http://").strip("/")
if PRODUCTION:
    _prod_missing = [name for name in ("FRONTEND_DOMAIN",) if not env(name)]
    if _prod_missing:
        raise ImproperlyConfigured(
            "Missing required production environment variables: " + ", ".join(_prod_missing) + "."
        )
    if DEBUG:
        raise ImproperlyConfigured("DEBUG must be off in production.")


def _database(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must be a postgres:// URL.")
    allowed_options = {"sslmode", "connect_timeout", "channel_binding"}
    options = {k: v[0] for k, v in parse_qs(parsed.query).items() if k in allowed_options}
    if PRODUCTION:
        options.setdefault("sslmode", "require")  # Neon needs TLS; never connect in clear text
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 0),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": options,
    }


DATABASES = {"default": _database(env("DATABASE_URL"))}

if PRODUCTION:
    _frontend = f"https://{FRONTEND_DOMAIN}"
    ALLOWED_HOSTS = list(
        dict.fromkeys(h for h in [RENDER_EXTERNAL_HOSTNAME, FRONTEND_DOMAIN, *env_list("ALLOWED_HOSTS")] if h)
    )
    SITE_URL = (env("SITE_URL") or _frontend).rstrip("/")
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([_frontend, *env_list("CSRF_TRUSTED_ORIGINS")]))
    WS_ALLOWED_ORIGINS = list(dict.fromkeys([_frontend, *env_list("WS_ALLOWED_ORIGINS")]))
else:
    ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
    SITE_URL = env("SITE_URL", "http://localhost:5173").rstrip("/")
    CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", SITE_URL)
    WS_ALLOWED_ORIGINS = env_list("WS_ALLOWED_ORIGINS", SITE_URL)
DEMO_MODE = env_bool("DEMO_MODE", False)

SHARED_DIR = Path(env("SHARED_DIR") or (BASE_DIR.parent / "shared"))
POLICY_PATH = SHARED_DIR / "policy.json"
BRAND_PATH = SHARED_DIR / "brand.json"
SKILL_GRAPH_PATH = SHARED_DIR / "skill_graph.json"
LEARNING_LINKS_PATH = SHARED_DIR / "learning_links.json"

INSTALLED_APPS = [
    "daphne",  # makes `runserver` serve WebSockets too (ASGI)
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "channels",
    "core",
    "accounts",
    "org",
    "jobs",
    "files",
    "applications",
    "notifications",
    "matching",
    "hira",
    "interviews",
    "offers",
    "hr",
    "growth",
    "analytics",
    "seeding",
]

MIDDLEWARE = [
    # First: lets the platform's health check reach /api/ping whatever Host it sends (core/middleware.py).
    "core.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
TEMPLATES = []
APPEND_SLASH = False

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 60 * 60

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# In-memory cache on one free instance; Redis only when REDIS_URL is set (several instances).
if env("REDIS_URL"):
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Cookies, CSRF and security headers ---------------------------------------
COOKIE_SECURE = True if PRODUCTION else env_bool("COOKIE_SECURE", not DEBUG)
ACCESS_COOKIE = "tp_access"
REFRESH_COOKIE = "tp_refresh"
REFRESH_COOKIE_PATH = "/api/auth"
CSRF_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it and echoes it in X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000 if PRODUCTION else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = PRODUCTION
SECURE_SSL_REDIRECT = PRODUCTION
# Render's health check calls /api/ping over the internal network without TLS.
SECURE_REDIRECT_EXEMPT = [r"^api/ping$"]
# HSTS preload needs control of the parent domain (onrender.com belongs to Render), so it stays off.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# --- Uploads -----------------------------------------------------------------
RESUME_MAX_BYTES = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = RESUME_MAX_BYTES + 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_STORAGE_MODE = env("FILE_STORAGE_MODE", "db")  # "db" = compressed in PostgreSQL

# --- DRF / JWT -----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.auth.CookieJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.PolicyPermission"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": env("THROTTLE_LOGIN", "10/min"),
        "register": env("THROTTLE_REGISTER", "10/hour"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", "5/hour"),
        "upload": env("THROTTLE_UPLOAD", "20/hour"),
        "demo_inbox": "30/min",
        "hira": env("THROTTLE_HIRA", "30/min"),
        "schedule_link": env("THROTTLE_SCHEDULE_LINK", "30/min"),
    },
    "NUM_PROXIES": env_int("NUM_PROXIES", 0),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "SIGNING_KEY": SECRET_KEY,
    "ALGORITHM": "HS256",
}

# --- Channels ------------------------------------------------------------------
REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
WS_TICKET_TTL_SECONDS = 30

# --- Email delivery (D-86) -------------------------------------------------------
# "console" logs one line per email and sends nothing (default; tests). "smtp" sends with
# Gmail and an App Password (local use). "api" uses Brevo or Resend over HTTPS (Render's free
# plan blocks SMTP ports). Credentials come only from the environment, never from code.
EMAIL_PROVIDER = (env("EMAIL_PROVIDER") or "console").strip().lower()
if EMAIL_PROVIDER not in ("console", "smtp", "api"):
    raise ImproperlyConfigured("EMAIL_PROVIDER must be console, smtp or api.")
DEFAULT_FROM_EMAIL = env("EMAIL_FROM") or env("EMAIL_HOST_USER") or "no-reply@talentpath.example"
EMAIL_FROM_NAME = env("EMAIL_FROM_NAME") or "TalentPath"
EMAIL_HOST = env("EMAIL_HOST") or "smtp.gmail.com"
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True) if env("EMAIL_USE_TLS") else True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_API_PROVIDER = env("EMAIL_API_PROVIDER", "").strip().lower()
EMAIL_API_KEY = env("EMAIL_API_KEY", "")
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 15)
# Comma-separated addresses or @domains. When set, real emails go only there; the rest stay
# in the outbox as "held" (handy for demos with real inboxes).
EMAIL_ALLOWLIST = env("EMAIL_ALLOWLIST", "")
EMAIL_MAX_PER_RECIPIENT_PER_HOUR = env_int("EMAIL_MAX_PER_RECIPIENT_PER_HOUR", 10)
EMAIL_MAX_PER_HOUR = env_int("EMAIL_MAX_PER_HOUR", 60)
EMAIL_DAILY_CAP = env_int("EMAIL_DAILY_CAP", 250)
EMAIL_MAX_ATTEMPTS = env_int("EMAIL_MAX_ATTEMPTS", 5)
if EMAIL_PROVIDER == "smtp" and not (EMAIL_HOST_USER and EMAIL_HOST_PASSWORD):
    raise ImproperlyConfigured("EMAIL_PROVIDER=smtp needs EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.")
if EMAIL_PROVIDER == "api" and (EMAIL_API_PROVIDER not in ("brevo", "resend") or not EMAIL_API_KEY):
    raise ImproperlyConfigured(
        "EMAIL_PROVIDER=api needs EMAIL_API_PROVIDER (brevo or resend) and EMAIL_API_KEY."
    )
# Django's own mail helpers never send by themselves; everything goes through notifications.delivery.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    # Email logs carry the masked recipient and kind only (never bodies or credentials).
    "loggers": {"talentpath.email": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
