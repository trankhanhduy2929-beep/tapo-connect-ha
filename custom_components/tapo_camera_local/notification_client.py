"""Owner-provisioned signed cloud notification reads, without camera commands."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import ssl
import stat
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import certifi
import requests

from .notification_data import NOTIFICATION_TYPES, notification_time

APP_TYPE = "TP-Link_Tapo_Android"
NOTIFICATION_PATH = "/api/v2/common/getAppNotificationByPage"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class NotificationError(Exception):
    """A sanitized cloud request or profile failure."""


class NotificationAuthError(NotificationError):
    """Session renewal is required; do not retry credentials automatically."""


def cloud_base(value) -> str:
    if not isinstance(value, str) or any(character.isspace() or ord(character) < 32 for character in value):
        raise NotificationError("Invalid cloud destination")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise NotificationError("Invalid cloud destination") from None
    host = parsed.hostname or ""
    if parsed.scheme != "https" or port not in (None, 443) or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or parsed.path not in ("", "/") or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host) or not host.endswith(".tplinkcloud.com"):
        raise NotificationError("Invalid cloud destination")
    return value.rstrip("/")


def validate_profile(profile) -> dict:
    if not isinstance(profile, dict) or profile.get("version") != 1:
        raise NotificationError("Unsupported private cloud profile")
    for key in ("camera_id", "terminal", "access_token", "access_key", "signing_secret"):
        value = profile.get(key)
        if not isinstance(value, str) or not 0 < len(value) <= 4096 or any(ord(character) < 33 or ord(character) > 126 for character in value):
            raise NotificationError("Invalid private cloud profile")
    cloud_base(profile.get("device_base"))
    certificates = profile.get("certificates")
    if not isinstance(certificates, list) or not 1 <= len(certificates) <= 16 or not all(isinstance(certificate, str) and certificate.startswith("-----BEGIN CERTIFICATE-----") and len(certificate) <= 16384 for certificate in certificates):
        raise NotificationError("Invalid cloud certificate bundle")
    return profile


def load_profile(config_dir: str, relative_path: str) -> dict:
    try:
        relative = Path(relative_path)
        if relative.is_absolute() or len(relative.parts) < 2 or relative.parts[0] == "www" or any(part in (".", "..") for part in relative.parts):
            raise NotificationError("Use a relative file inside a private HA config directory")
        path = Path(config_dir)
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise NotificationError("Symlinks are not permitted for cloud profiles")
        parent = path.parent.stat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
            raise NotificationError("Cloud profile directory must be owner-only (700)")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077 or metadata.st_nlink != 1:
                raise NotificationError("Cloud profile must be an owner-only regular file (600)")
            text = handle.read(65537)
        if len(text) > 65536:
            raise NotificationError("Private cloud profile too large")
        return validate_profile(json.loads(text))
    except (OSError, ValueError, TypeError, RecursionError):
        raise NotificationError("Cannot read private cloud profile") from None


def signed_headers(payload: bytes, path: str, access_key: str, secret: str, nonce: str) -> dict:
    checksum = base64.b64encode(hashlib.md5(payload).digest()).decode()
    signed = f"{checksum}\n9999999999\n{nonce}\n{path}".encode()
    signature = hmac.new(secret.encode(), signed, hashlib.sha1).hexdigest()
    return {"Content-Type": "application/json;charset=UTF-8", "Content-MD5": checksum, "X-Authorization": f"Timestamp=9999999999, Nonce={nonce}, AccessKey={access_key}, Signature={signature}"}


class VerifiedAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, context):
        self.context = context
        super().__init__(max_retries=0)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        return super().init_poolmanager(connections, maxsize, block, ssl_context=self.context, **kwargs)


class NotificationClient:
    def __init__(self, profile: dict):
        self.profile = validate_profile(profile)
        self.camera_id = self.profile["camera_id"]
        self.base = cloud_base(self.profile["device_base"])
        self.session = requests.Session()
        self.session.trust_env = False
        self.auth_failed = False
        resumed = profile.get("notification_cursor")
        self._notification_since = resumed if type(resumed) is int and resumed > 0 else None
        self._notification_query = None
        self._initial_sync = True
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            context.load_verify_locations(cadata="\n".join(self.profile["certificates"]))
            self.session.mount("https://", VerifiedAdapter(context))
        except (ValueError, ssl.SSLError, OSError):
            self.session.close()
            raise NotificationError("Cannot initialize verified cloud TLS") from None

    def _page(self, body: dict) -> dict:
        if self.auth_failed:
            raise NotificationAuthError("Cloud session rejected; import a new MFA-verified profile")
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        headers = signed_headers(payload, NOTIFICATION_PATH, self.profile["access_key"], self.profile["signing_secret"], str(uuid.uuid4()))
        params = {"appName": APP_TYPE, "appVer": "3.18.506", "termID": self.profile["terminal"], "locale": "en_US", "token": self.profile["access_token"]}
        try:
            with self.session.post(self.base + NOTIFICATION_PATH, data=payload, headers=headers, params=params, timeout=(8, 20), allow_redirects=False, stream=True) as response:
                if response.status_code in (401, 403):
                    self.auth_failed = True
                    raise NotificationAuthError("Cloud session rejected; import a new MFA-verified profile")
                if response.status_code != 200:
                    raise NotificationError("Cloud notification request failed")
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise NotificationError("Cloud notification response too large")
                data = json.loads(content)
            if not isinstance(data, dict):
                raise NotificationError("Unexpected cloud notification response")
            code = data.get("error_code")
            if type(code) is int and code in (-20651, -20675, -20677):
                self.auth_failed = True
                raise NotificationAuthError("Cloud session rejected; import a new MFA-verified profile")
            if type(code) is not int or code != 0:
                raise NotificationError("Cloud rejected the notification request")
            result = data.get("result")
            if not isinstance(result, dict):
                raise NotificationError("Cloud notification result missing")
            return result
        except (requests.RequestException, ValueError, OSError, RecursionError):
            raise NotificationError("Unable to read cloud notifications; details suppressed") from None

    def fetch(self) -> dict:
        now = time.time()
        minimum = int(now * 1000) - 7 * 86400000
        body = dict(self._notification_query) if self._notification_query else {"index": 0, "indexTime": max(self._notification_since or minimum, minimum), "limit": 50, "locale": "en_US", "direction": "asc", "msgTypes": list(NOTIFICATION_TYPES), "appType": APP_TYPE, "terminalUUID": self.profile["terminal"], "mobileType": "ANDROID", "deviceToken": "", "contentVersion": 3}
        initial_sync = self._initial_sync
        records = []
        more = False
        for _page in range(3):
            result = self._page(body)
            items = result.get("notifications")
            if not isinstance(items, list) or len(items) > 50:
                raise NotificationError("Unexpected notification list")
            records.extend(items)
            more = result.get("hasNextPage") is True
            if more and not items:
                raise NotificationError("Cloud returned a non-advancing notification page")
            body["index"] += len(items)
            if not more:
                break
        if more:
            self._notification_query = body
        else:
            times = [parsed.timestamp() for record in records if isinstance(record, dict) and (parsed := notification_time(record.get("time"), now)) is not None]
            advanced = int((max(times) if times else now) * 1000) - 300000
            self._notification_since = max(self._notification_since or 0, advanced, minimum)
            self._notification_query = None
            self._initial_sync = False
        return {"notifications": records, "truncated": more, "initial_sync": initial_sync}

    @property
    def cursor_ms(self) -> int | None:
        """Persistable watermark; None until the first complete page is read."""
        return self._notification_since

    def close(self):
        self.session.close()


def open_client(config_dir: str, relative_path: str) -> NotificationClient:
    return NotificationClient(load_profile(config_dir, relative_path))


def probe_profile(config_dir: str, relative_path: str) -> str:
    client = open_client(config_dir, relative_path)
    try:
        client.fetch()
        return client.camera_id
    finally:
        client.close()
