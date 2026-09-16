"""Digest helpers recovered from com.tplink.libtapocameranetwork.util."""

import base64
import hashlib
import os


def md5_upper(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest().upper()


def sha256_upper(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest().upper()


def login_hash(password: str) -> str:
    """Value sent as Account.password when Account.hashed is true."""
    return md5_upper(password)


def sha1_password_hash(password: str) -> str:
    """Variant used while synchronising legacy SHA-1 device accounts."""
    return sha256_upper(md5_upper(password) + password)


def sha256_user_password_digest(username: str, password: str) -> str:
    """Unverified fallback digest for firmware expecting username-bound hashes."""
    return sha256_upper(username + md5_upper(password))


def random_cnonce(size: int = 32) -> str:
    return base64.b64encode(os.urandom(size)).decode()


def random_nonce(size: int = 32) -> str:
    return base64.b64encode(os.urandom(size)).decode()
