import pytest
from cryptography.exceptions import InvalidTag

from core.crypto import blind_index, decrypt_bytes, decrypt_text, encrypt_bytes, encrypt_text


def test_round_trip_and_random_nonce():
    a, b = encrypt_text("+91 98765 43210"), encrypt_text("+91 98765 43210")
    assert a != b and a.startswith("v1:")
    assert decrypt_text(a) == decrypt_text(b) == "+91 98765 43210"


def test_tampering_is_detected():
    blob = bytearray(encrypt_bytes(b"secret resume"))
    blob[-1] ^= 1
    with pytest.raises(InvalidTag):
        decrypt_bytes(bytes(blob))


def test_associated_data_binds_ciphertext():
    blob = encrypt_bytes(b"file", aad=b"storedfile:1")
    with pytest.raises(InvalidTag):
        decrypt_bytes(blob, aad=b"storedfile:2")


def test_blind_index_is_deterministic_normalised_and_purpose_bound():
    assert blind_index("+91 98765-43210", "phone") == blind_index("+919876543210", "phone")
    assert blind_index("+919876543210", "phone") != blind_index("+919876543210", "email")
    assert blind_index("", "phone") == ""
    assert len(blind_index("x", "phone")) == 64
