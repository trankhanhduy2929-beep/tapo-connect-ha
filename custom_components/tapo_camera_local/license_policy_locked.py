"""License policy locked at build time - do not edit."""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Locked policy - values are baked into the release
_LOCKED_ENABLED = True
_LOCKED_SERVER = "https://tapo-connect-license.vercel.app"
_LOCKED_KEY = "mkmmpFPP730mpNYkVaYGBrP42DFL8w2opNVYYaFyzIE"
_LOCKED_GRANDFATHER = False

def _decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)

def _check(policy):
    url = urlsplit(policy.server_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/") or url.port not in (None, 443):
        raise ValueError("license_server_configuration")
    try:
        Ed25519PublicKey.from_public_bytes(_decode(policy.public_key))
    except (ValueError, TypeError) as error:
        raise ValueError("license_server_configuration") from error

class _Policy:
    enabled = _LOCKED_ENABLED
    server_url = _LOCKED_SERVER
    public_key = _LOCKED_KEY
    grandfather_existing = _LOCKED_GRANDFATHER
    def check(self): _check(self)

def load_policy() -> _Policy:
    """Load locked policy - ignores external license_policy.json."""
    p = _Policy()
    p.check()
    return p
