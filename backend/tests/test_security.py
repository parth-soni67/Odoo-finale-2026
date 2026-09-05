from datetime import timedelta
import pytest
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    """Verifies that password hashing and verification function correctly."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_decoding():
    """Verifies JWT token encoding and decoding."""
    subject = "42"
    claims = {"role": "ADMIN", "email": "test@example.com"}
    token = create_access_token(subject=subject, claims=claims)

    decoded = decode_access_token(token)
    assert decoded["sub"] == subject
    assert decoded["role"] == "ADMIN"
    assert decoded["email"] == "test@example.com"
    assert "exp" in decoded


def test_jwt_token_expired():
    """Verifies that expired JWT tokens raise a decoding error."""
    subject = "42"
    token = create_access_token(
        subject=subject,
        expires_delta=timedelta(seconds=-10)
    )

    with pytest.raises(Exception):
        decode_access_token(token)
