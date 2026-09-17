"""Independent signed-license protocol; never handles camera credentials."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PRODUCT = "tapo_camera_local"
LICENSE_INSTANCE = "license_instance_id"

class LicenseError(Exception):
    """License denied, expired or cannot be securely validated."""

class LicenseUnavailable(LicenseError):
    """Server temporarily unavailable."""

def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")

def decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)

@dataclass(frozen=True)
class LicensePolicy:
    enabled: bool = False
    server_url: str = ""
    public_key: str = ""
    grandfather_existing: bool = True

    def check(self):
        url = urlsplit(self.server_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/") or url.port not in (None, 443):
            raise LicenseError("license_server_configuration")
        try:
            Ed25519PublicKey.from_public_bytes(decode(self.public_key))
        except (ValueError, TypeError) as error:
            raise LicenseError("license_server_configuration") from error

# load_policy moved to license_policy_locked.py for locked releases
def new_identity(instance_id: str | None = None) -> dict:
    key = Ed25519PrivateKey.generate()
    return {"instance_id": instance_id or str(uuid.uuid4()), "private_key": encode(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))}

def make_proof(identity: dict, action: str, license_key: str = "") -> dict:
    key = Ed25519PrivateKey.from_private_bytes(decode(identity["private_key"]))
    public = encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    timestamp = int(time.time())
    nonce = secrets.token_urlsafe(18)
    message = "\n".join(["RD1", action, PRODUCT, identity["instance_id"], public, str(timestamp), nonce, license_key])
    return {"instanceId": identity["instance_id"], "product": PRODUCT, "publicKey": public, "timestamp": timestamp, "nonce": nonce, "licenseKey": license_key, "signature": encode(key.sign(message.encode()))}

def enrollment_url(policy: LicensePolicy, identity: dict) -> str:
    policy.check()
    proof = make_proof(identity, "enroll")
    return policy.server_url.rstrip("/") + "/#pair=" + encode(json.dumps(proof, separators=(",", ":")).encode())

def verify_lease(policy: LicensePolicy, identity: dict, license_key: str, token: str, now: float | None = None) -> dict:
    try:
        if not isinstance(token, str) or len(token) > 4096:
            raise ValueError("Invalid lease")
        body, signature = token.split(".")
        Ed25519PublicKey.from_public_bytes(decode(policy.public_key)).verify(decode(signature), body.encode())
        claim = json.loads(decode(body))
        public = Ed25519PrivateKey.from_private_bytes(decode(identity["private_key"])).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        now = time.time() if now is None else now
        valid = (
            claim["v"] == 1 and claim["status"] == "active" and claim["product"] == PRODUCT
            and claim["instanceId"] == identity["instance_id"]
            and claim["publicKeyHash"] == hashlib.sha256(public).hexdigest()
            and claim["licenseKeyHash"] == hashlib.sha256(license_key.encode()).hexdigest()
            and all(type(claim[field]) is int for field in ("issuedAt", "refreshAfter", "validUntil", "generation"))
            and claim["issuedAt"] <= now + 300
            and claim["issuedAt"] <= claim["refreshAfter"] <= claim["validUntil"]
            and now < claim["validUntil"] <= claim["issuedAt"] + 86400
            and (claim["expiresAt"] is None or type(claim["expiresAt"]) is int and claim["validUntil"] <= claim["expiresAt"])
        )
        if not valid:
            raise ValueError("Invalid lease")
        return claim
    except (InvalidSignature, ValueError, TypeError, KeyError, AttributeError) as error:
        raise LicenseError("license_invalid_or_expired") from error

async def request_lease(session, policy: LicensePolicy, identity: dict, license_key: str, action: str) -> str:
    from aiohttp import ClientError, ClientTimeout

    policy.check()
    try:
        async with session.post(policy.server_url.rstrip("/") + "/api/license/" + action, json=make_proof(identity, action, license_key), timeout=ClientTimeout(total=10), allow_redirects=False) as response:
            if response.status in (400, 401, 403, 409):
                raise LicenseError("license_rejected")
            if response.status != 200:
                raise LicenseUnavailable("license_server_unavailable")
            data = b""
            while chunk := await response.content.read(8193 - len(data)):
                data += chunk
                if len(data) > 8192:
                    raise LicenseUnavailable("license_server_unavailable")
            token = json.loads(data)["lease"]
            verify_lease(policy, identity, license_key, token)
            return token
    except (ClientError, TimeoutError, ValueError, KeyError, TypeError) as error:
        raise LicenseUnavailable("license_server_unavailable") from error
