"""AES-GCM field encryption and HMAC blind indexes.

Ciphertext format (text): "v1:" + urlsafe-base64(nonce[12] + ciphertext+tag).
The "v1" prefix leaves room for key rotation later.
"""

import base64
import hashlib
import hmac
import os
import unicodedata

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

PREFIX = "v1:"
NONCE_BYTES = 12


def _aead() -> AESGCM:
    return AESGCM(settings.FIELD_ENCRYPTION_KEY_BYTES)


def encrypt_bytes(data: bytes, aad: bytes = b"") -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return nonce + _aead().encrypt(nonce, data, aad or None)


def decrypt_bytes(blob: bytes, aad: bytes = b"") -> bytes:
    nonce, ciphertext = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    return _aead().decrypt(nonce, ciphertext, aad or None)


def encrypt_text(value: str) -> str:
    token = base64.urlsafe_b64encode(encrypt_bytes(value.encode("utf-8"))).decode("ascii")
    return PREFIX + token


def decrypt_text(value: str) -> str:
    if not value.startswith(PREFIX):
        raise ValueError("Value is not encrypted with a known key version.")
    blob = base64.urlsafe_b64decode(value[len(PREFIX) :].encode("ascii"))
    return decrypt_bytes(blob).decode("utf-8")


def normalize_for_index(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").strip().lower()
    return "".join(ch for ch in value if not ch.isspace() and ch not in "-().")


def blind_index(value: str, purpose: str) -> str:
    """Deterministic keyed hash so encrypted values can still be looked up."""
    normalized = normalize_for_index(value)
    if not normalized:
        return ""
    message = f"{purpose}:{normalized}".encode()
    return hmac.new(settings.BLIND_INDEX_KEY_BYTES, message, hashlib.sha256).hexdigest()
