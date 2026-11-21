"""File storage. Free mode ("db") keeps files compressed and encrypted in PostgreSQL,
because Render's free disk is ephemeral. An object-storage backend can be added
later behind the same two functions."""

import hashlib
import zlib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.crypto import decrypt_bytes, encrypt_bytes

from .models import StoredFile


def _aad(file_id) -> bytes:
    return f"storedfile:{file_id}".encode()


def save_file(*, owner, original_name: str, content_type: str, raw: bytes) -> StoredFile:
    if settings.FILE_STORAGE_MODE != "db":
        raise ImproperlyConfigured(f"Unsupported FILE_STORAGE_MODE {settings.FILE_STORAGE_MODE!r}")
    stored = StoredFile(
        owner=owner,
        original_name=original_name[:255],
        content_type=content_type,
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    stored.data = encrypt_bytes(zlib.compress(raw, 6), aad=_aad(stored.id))
    stored.save()
    return stored


def read_file(stored: StoredFile) -> bytes:
    blob = bytes(stored.data)
    return zlib.decompress(decrypt_bytes(blob, aad=_aad(stored.id)))
