"""Encryption for members' own LLM API keys stored in the database."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet(secret: str) -> Fernet:
    if not secret:
        raise ValueError("No encryption secret configured")
    digest = hashlib.sha256(b"gnosis-user-llm-keys:" + secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(secret: str, plaintext: str) -> str:
    return _fernet(secret).encrypt(plaintext.encode()).decode()


def decrypt(secret: str, token: str) -> str | None:
    """None when the secret changed since encryption: the member must re-enter the key."""
    try:
        return _fernet(secret).decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
