"""Settings for pytest: fixed throwaway keys, fast hashing, local Postgres."""

import os

os.environ.setdefault("DJANGO_LOAD_DOTENV", "0")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-0123456789")
os.environ.setdefault("DATABASE_URL", "postgres://talentpath:talentpath@127.0.0.1:55432/talentpath")
# 32 zero-ish bytes, base64: test-only keys.
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("BLIND_INDEX_KEY", "ZmVkY2JhOTg3NjU0MzIxMGZlZGNiYTk4NzY1NDMyMTA=")
os.environ.setdefault("INTERNAL_TICK_SECRET", "test-internal-secret-0123456789")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("SITE_URL", "https://careers.test")
os.environ.setdefault("DEMO_MODE", "true")

from .settings import *  # noqa: E402,F403

# Argon2 is the production hasher (asserted in tests); MD5 keeps the suite fast.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
COOKIE_SECURE = False
