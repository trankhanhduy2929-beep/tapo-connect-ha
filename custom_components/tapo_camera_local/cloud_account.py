"""Owner login, email MFA and bounded renewal of Tapo cloud sessions."""

from __future__ import annotations

import base64
import json
import re
import ssl
import time
import uuid
from pathlib import Path

import certifi
import requests

from .notification_client import (
    MAX_RESPONSE_BYTES,
    NotificationAuthError,
    NotificationClient,
    NotificationError,
    VerifiedAdapter,
    cloud_base,
    signed_headers,
)

ACCOUNT_BASE = "https://account-api.i.tplinkcloud.com"
STATUS_PATH = "/api/v2/account/getAccountStatusAndUrl"
LOGIN_PATH = "/api/v2/account/login"
EMAIL_PATH = "/api/v2/account/getEmailVC4TerminalMFA"
VERIFY_PATH = "/api/v2/account/checkMFACodeAndLogin"
DEVICES_PATH = "/api/v2/common/getDeviceList"
AUTH_CODES = {-20651, -20675, -20677}
MFA_MAX_AGE = 600


class CloudAccountError(NotificationError):
    def __init__(self, kind: str):
        self.kind = kind
        super().__init__(kind)


def app_parameters() -> dict:
    try:
        data = json.loads(Path(__file__).with_name("cloud_app.json").read_text())
        if not isinstance(data, dict) or set(data) != {"version", "app_type", "app_version", "certificates", "access_key", "signing_secret"} or data["version"] != 1:
            raise ValueError
        if not all(isinstance(data[key], str) and data[key] and len(data[key]) <= 4096 for key in ("app_type", "app_version", "access_key", "signing_secret")):
            raise ValueError
        if not isinstance(data["certificates"], list) or not data["certificates"] or not all(isinstance(value, str) and value.startswith("-----BEGIN CERTIFICATE-----") for value in data["certificates"]):
            raise ValueError
        return data
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise CloudAccountError("cloud_app_invalid") from None


def secret_text(value) -> str:
    if not isinstance(value, str) or not 0 < len(value) <= 4096 or any(ord(character) < 33 or ord(character) > 126 for character in value):
        raise CloudAccountError("cloud_bad_response")
    return value


def validated_session(value: dict) -> dict:
    if not isinstance(value, dict) or value.get("version") != 1:
        raise NotificationAuthError("Cloud session unavailable; sign in through Home Assistant")
    result = {"version": 1}
    try:
        for key in ("terminal", "access_token"):
            result[key] = secret_text(value.get(key))
        for key in ("login_base", "device_base"):
            result[key] = cloud_base(value.get(key))
        if value.get("refresh_base"):
            result["refresh_base"] = cloud_base(value["refresh_base"])
        if value.get("refresh_token"):
            result["refresh_token"] = secret_text(value["refresh_token"])
        cursor = value.get("notification_cursor")
        if type(cursor) is int and cursor > 0:
            result["notification_cursor"] = cursor
    except NotificationError:
        raise NotificationAuthError("Cloud session invalid; sign in through Home Assistant") from None
    return result


class CloudGateway:
    def __init__(self, material: dict, terminal: str):
        self.material = material
        self.terminal = terminal
        self.session = requests.Session()
        self.session.trust_env = False
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            context.load_verify_locations(cadata="\n".join(material["certificates"]))
            self.session.mount("https://", VerifiedAdapter(context))
        except (OSError, ValueError, ssl.SSLError):
            self.session.close()
            raise CloudAccountError("cloud_app_invalid") from None

    def __enter__(self):
        return self

    def __exit__(self, *_arguments):
        self.session.close()

    def post(self, base: str, path: str, body: dict, token: str | None = None) -> dict:
        if path not in {STATUS_PATH, LOGIN_PATH, EMAIL_PATH, VERIFY_PATH, DEVICES_PATH, "/api/v2/common/getWebServiceInfo", "/"} or path == "/" and (set(body) != {"method", "params"} or body["method"] != "refreshToken"):
            raise CloudAccountError("cloud_bad_request")
        if path == "/api/v2/common/getWebServiceInfo" and body != {"serviceIds": ["nbu.iot-app-server.app-v2"]}:
            raise CloudAccountError("cloud_bad_request")
        base = cloud_base(base)
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        headers = signed_headers(payload, path, self.material["access_key"], self.material["signing_secret"], str(uuid.uuid4()))
        params = {"appName": self.material["app_type"], "appVer": self.material["app_version"], "termID": self.terminal, "locale": "en_US"}
        if token:
            params["token"] = token
        try:
            with self.session.post(base + path, data=payload, headers=headers, params=params, timeout=(8, 20), allow_redirects=False, stream=True) as response:
                if response.status_code in (401, 403):
                    raise NotificationAuthError("Cloud authorization rejected")
                if response.status_code == 429:
                    raise CloudAccountError("cloud_locked")
                if response.status_code != 200:
                    raise CloudAccountError("cloud_cannot_connect")
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise CloudAccountError("cloud_bad_response")
                data = json.loads(content)
        except (requests.RequestException, OSError, ValueError, RecursionError):
            raise CloudAccountError("cloud_cannot_connect") from None
        if not isinstance(data, dict) or type(data.get("error_code")) is not int:
            raise CloudAccountError("cloud_bad_response")
        if code := data["error_code"]:
            if code in AUTH_CODES:
                raise NotificationAuthError("Cloud session rejected")
            message = data.get("msg", data.get("message", ""))
            if isinstance(message, str) and re.search(r"locked|too many|rate.?limit", message, re.IGNORECASE):
                raise CloudAccountError("cloud_locked")
            if path == VERIFY_PATH:
                raise CloudAccountError("cloud_invalid_code")
            if path == LOGIN_PATH:
                raise CloudAccountError("cloud_invalid_auth")
            if path == "/":
                raise NotificationAuthError("Cloud renewal rejected; sign in through Home Assistant")
            raise CloudAccountError("cloud_bad_response")
        result = data.get("result")
        if result is None and path == EMAIL_PATH:
            return {}
        if not isinstance(result, dict):
            raise CloudAccountError("cloud_bad_response")
        return result


class CloudAccount:
    def __init__(self):
        self.material = app_parameters()
        self.terminal = str(uuid.uuid4())
        self.email = ""
        self.phase = "new"
        self.login_base = None
        self.refresh_base = None
        self.process_id = None
        self.email_sent_at = None
        self.session_data = None
        self.devices = {}

    def discard(self):
        if self.session_data is not None:
            self.session_data.clear()
        self.devices = {}

    def _accept(self, result: dict):
        if result.get("MFAProcessId"):
            raise CloudAccountError("cloud_mfa_unsupported")
        session = {"version": 1, "terminal": self.terminal, "login_base": self.login_base, "device_base": result.get("appServerUrlV2") or self.login_base, "access_token": result.get("token")}
        if self.refresh_base:
            session["refresh_base"] = self.refresh_base
        if result.get("refreshToken"):
            session["refresh_token"] = result["refreshToken"]
        self.session_data = validated_session(session)
        self.process_id = None
        self.phase = "authenticated"

    def begin(self, email: str, password: str, region: str = "") -> bool:
        if self.phase != "new":
            raise CloudAccountError("cloud_restart_login")
        if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or not isinstance(password, str) or not 0 < len(password) <= 1024 or not isinstance(region, str) or region and not re.fullmatch(r"[A-Za-z]{2}", region):
            raise CloudAccountError("cloud_invalid_input")
        self.email = email
        self.phase = "login_started"
        with CloudGateway(self.material, self.terminal) as gateway:
            status = gateway.post(ACCOUNT_BASE, STATUS_PATH, {"appType": self.material["app_type"], "cloudUserName": email, "regionCode": region.upper()})
            if status.get("lockedMinutes") not in (None, "", "0", 0):
                raise CloudAccountError("cloud_locked")
            if type(status.get("status")) is not int or status["status"] != 1:
                raise CloudAccountError("cloud_invalid_auth")
            self.login_base = cloud_base(status.get("appServerUrlV2"))
            if status.get("appServerUrl"):
                self.refresh_base = cloud_base(status["appServerUrl"])
            result = gateway.post(self.login_base, LOGIN_PATH, {"appType": self.material["app_type"], "appVersion": self.material["app_version"], "cloudUserName": email, "cloudPassword": password, "platform": "Android", "refreshTokenNeeded": True, "terminalUUID": self.terminal, "terminalName": "Home Assistant", "terminalMeta": "Tapo Camera Local", "supportBindAccount": False})
            if not result.get("MFAProcessId"):
                self._accept(result)
                return True
            self.process_id = secret_text(result["MFAProcessId"])
            methods = result.get("supportedMFATypes")
            if isinstance(methods, list) and not any(type(method) is int and method == 2 for method in methods):
                raise CloudAccountError("cloud_mfa_unsupported")
            self.phase = "email_started"
            gateway.post(self.login_base, EMAIL_PATH, {"cloudUserName": email, "cloudPassword": password, "appType": self.material["app_type"], "terminalUUID": self.terminal, "locale": "en_US"})
            self.email_sent_at = time.monotonic()
            self.phase = "waiting_code"
            return False

    def verify(self, code: str):
        if self.phase != "waiting_code" or self.email_sent_at is None:
            raise CloudAccountError("cloud_restart_login")
        if not 0 <= time.monotonic() - self.email_sent_at <= MFA_MAX_AGE:
            self.phase = "expired"
            self.process_id = None
            raise CloudAccountError("cloud_mfa_expired")
        if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
            raise CloudAccountError("cloud_invalid_code")
        self.phase = "verification_started"
        try:
            with CloudGateway(self.material, self.terminal) as gateway:
                result = gateway.post(self.login_base, VERIFY_PATH, {"cloudUserName": self.email, "appType": self.material["app_type"], "MFAProcessId": self.process_id, "MFAType": 2, "code": code, "terminalBindEnabled": False, "supportBindAccount": False})
            self._accept(result)
        finally:
            self.process_id = None

    def cameras(self) -> dict:
        if self.phase != "authenticated":
            raise CloudAccountError("cloud_restart_login")
        with CloudGateway(self.material, self.terminal) as gateway:
            result = gateway.post(self.session_data["device_base"], DEVICES_PATH, {}, self.session_data["access_token"])
        records = result.get("deviceList")
        if not isinstance(records, list) or len(records) > 2000:
            raise CloudAccountError("cloud_bad_response")
        devices = {}
        for record in records:
            if not isinstance(record, dict) or not re.fullmatch(r"C260(?:\([^)]*\))?", str(record.get("deviceModel", "")), re.IGNORECASE):
                continue
            identifier = secret_text(record.get("deviceId"))
            name = record.get("alias") or "Tapo C260"
            if not isinstance(name, str) or not 0 < len(name) <= 256:
                name = "Tapo C260"
            try:
                decoded = base64.b64decode(name, validate=True).decode("utf-8")
                if decoded:
                    name = decoded
            except (ValueError, UnicodeError):
                pass
            name = "".join(character for character in name if ord(character) >= 32)[:80] or "Tapo C260"
            devices[identifier] = f"{name} · C260 · {identifier[-6:]}"
        self.devices = devices
        return dict(devices)

    def check_camera(self, camera_id: str):
        if camera_id not in self.devices:
            raise CloudAccountError("cloud_invalid_device")
        client = ManagedNotificationClient(self.session_data, camera_id, self.material)
        try:
            client.fetch()
        finally:
            client.close()


class ManagedNotificationClient(NotificationClient):
    def __init__(self, session: dict, camera_id: str, material: dict | None = None):
        self.session_data = validated_session(session)
        self.material = material or app_parameters()
        self.renewal_attempted = False
        super().__init__({**self.material, **self.session_data, "camera_id": camera_id})

    def renew(self):
        if self.renewal_attempted or not self.session_data.get("refresh_token"):
            raise NotificationAuthError("Sign in again through Home Assistant")
        self.renewal_attempted = True
        with CloudGateway(self.material, self.session_data["terminal"]) as gateway:
            result = gateway.post(self.session_data.get("refresh_base", self.session_data["login_base"]), "/", {"method": "refreshToken", "params": {"refreshToken": self.session_data["refresh_token"], "appType": self.material["app_type"], "terminalUUID": self.session_data["terminal"]}}, self.session_data["access_token"])
        renewed = dict(self.session_data)
        renewed["access_token"] = secret_text(result.get("token"))
        if result.get("refreshToken"):
            renewed["refresh_token"] = secret_text(result["refreshToken"])
        if result.get("appServerUrlV2"):
            renewed["device_base"] = cloud_base(result["appServerUrlV2"])
        self.session_data = validated_session(renewed)
        self.profile.update(self.session_data)
        self.base = self.session_data["device_base"]
        self.auth_failed = False

    def fetch(self):
        result = super().fetch()
        self.renewal_attempted = False
        return result


def open_managed_client(session: dict, camera_id: str) -> ManagedNotificationClient:
    return ManagedNotificationClient(session, camera_id)
