"""Bounded Thing passthrough using the existing cloud account, never LAN login."""

from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from urllib.parse import quote

import requests

from .cloud_account import AUTH_CODES, CloudGateway
from .notification_client import (
    MAX_RESPONSE_BYTES,
    NotificationAuthError,
    NotificationError,
    cloud_base,
)
from .tapo_proto.client import (
    READ_QUERIES,
    TapoCamera,
    TapoConnectionError,
    TapoProtocolError,
    TapoRequestError,
)
from .tapo_proto.controls import ACTIONS, SETTINGS, SETTINGS_BY_KEY, validate_write

SERVICE_PATH = "/api/v2/common/getWebServiceInfo"
SERVICE_ID = "nbu.iot-app-server.app-v2"
BASIC_QUERY = {"device_info": {"name": ["basic_info"]}}
CLOUD_QUERIES = {"getDeviceInfo": BASIC_QUERY, **{
    method: params for method, params in READ_QUERIES.items()
    if method in {setting.query for setting in SETTINGS} | {"getPresetConfig", "getSdCardStatus", "getAlertConfig"}
}}
CLOUD_ACTIONS = frozenset(ACTIONS) - {"reboot", "ptz_calibrate", "manual_alarm_start", "manual_alarm_stop"}


class CloudCamera:
    def __init__(self, profile: dict):
        self.camera_id = profile["camera_id"]
        self.host = "Tapo cloud"
        self.profile = {"app_type": "TP-Link_Tapo_Android", "app_version": "3.18.506", **profile}
        self.gateway = CloudGateway(self.profile, profile["terminal"])
        self.camera_base = None
        self.camera_path = None
        self._lock = threading.RLock()
        self._results = {}
        self._statuses = {}
        self._retry_at = {}

    def update_profile(self, profile: dict):
        if profile["camera_id"].casefold() != self.camera_id.casefold():
            raise NotificationError("Cloud camera identity changed")
        self.profile.update(profile)

    def _request(self, method: str, base: str, path: str, *, body=None, params=None):
        base = cloud_base(base)
        if (method, path) != ("GET", "/v2/things") and (method != "POST" or path != self.camera_path or base != self.camera_base):
            raise NotificationError("Unrecognized Thing destination")
        headers = {
            "Authorization": "ut|" + self.profile["access_token"],
            "app-cid": f"app:{self.profile.get('app_type', 'TP-Link_Tapo_Android')}:{self.profile['terminal']}",
            "Content-Type": "application/json;charset=UTF-8",
            "x-app-name": self.profile.get("app_type", "TP-Link_Tapo_Android"),
            "x-app-version": self.profile.get("app_version", "3.18.506"),
            "x-term-id": self.profile["terminal"], "x-ospf": "Android 13",
            "x-net-type": "wifi", "x-locale": "en_US", "x-strict": "0",
        }
        try:
            with self.gateway.session.request(method, base + path, headers=headers, json=body, params=params, timeout=(5, 12), allow_redirects=False, stream=True) as response:
                if response.status_code in (401, 403):
                    raise NotificationAuthError("Cloud camera authorization rejected")
                if response.status_code != 200:
                    raise NotificationError("Cloud camera is offline, busy or unreachable")
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise NotificationError("Cloud camera response too large")
                result = json.loads(content)
        except (requests.RequestException, OSError, ValueError, RecursionError):
            raise NotificationError("Cannot read cloud camera; details suppressed") from None
        if not isinstance(result, dict):
            raise NotificationError("Invalid Thing response")
        for key in ("error_code", "errorCode", "errorcode", "code"):
            if key in result:
                code = result[key]
                if type(code) is int and code in AUTH_CODES:
                    raise NotificationAuthError("Cloud camera session rejected")
                if type(code) is not int or code != 0:
                    raise NotificationError("Thing request rejected")
        return result

    def discover(self):
        route = self.gateway.post(self.profile["device_base"], SERVICE_PATH, {"serviceIds": [SERVICE_ID]}, self.profile["access_token"])
        routes = route.get("serviceUrls")
        base = cloud_base(routes.get(SERVICE_ID) if isinstance(routes, dict) else None)
        matches = []
        complete = False
        for page in range(10):
            result = self._request("GET", base, "/v2/things", params={"page": page, "pageSize": 50, "includePcDevice": "true", "includeKasaShareDevices": "false", "includeMatterDevice": "false"})
            items = result.get("data")
            if not isinstance(items, list) or len(items) > 50:
                raise NotificationError("Invalid Thing device list")
            matches.extend(item for item in items if isinstance(item, dict) and any(isinstance(item.get(key), str) and item[key].casefold() == self.camera_id.casefold() for key in ("thingName", "originalThingName")))
            total = result.get("total")
            if len(items) < 50 or type(total) is int and (page + 1) * 50 >= total:
                complete = True
                break
        if not complete or len(matches) != 1:
            raise NotificationError("No unique account-owned camera in the Thing list")
        selected = matches[0]
        identifier = selected.get("thingName")
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 256 or any(ord(character) < 33 for character in identifier) or identifier in {".", ".."}:
            raise NotificationError("Invalid Thing camera identity")
        self.camera_base = cloud_base(selected.get("appServerUrlV2") or selected.get("appServerUrl"))
        self.camera_path = "/v1/things/" + quote(identifier, safe="") + "/services-sync"

    def _batch(self, queries: dict, *, read_only: bool = True) -> dict:
        if not queries or len(queries) > 6:
            raise ValueError("Use one to six camera queries")
        for method, params in queries.items():
            if read_only:
                if method not in CLOUD_QUERIES or params != CLOUD_QUERIES[method]:
                    raise ValueError("Unrecognized cloud camera read")
            else:
                if len(queries) != 1:
                    raise ValueError("Only one explicit write is permitted")
                allowed_methods = {setting.method for setting in SETTINGS} | {ACTIONS[key][0] for key in CLOUD_ACTIONS} | {"motorMoveToPreset"}
                if method not in allowed_methods:
                    raise ValueError("This cloud camera command is not enabled")
                validate_write(method, params)
        if self.camera_path is None:
            self.discover()
        result = self._request("POST", self.camera_base, self.camera_path, body={"serviceId": "passthrough", "inputParams": {"requestData": {"method": "multipleRequest", "params": {"requests": [{"method": method, "params": params} for method, params in queries.items()]}}}})
        output = result.get("outputParams")
        response = output.get("responseData") if isinstance(output, dict) else None
        if not isinstance(response, dict):
            raise TapoProtocolError("Missing Thing camera response")
        TapoCamera._check_error(response, "multipleRequest", allow_missing=True)
        envelope = response.get("result")
        replies = envelope.get("responses") if isinstance(envelope, dict) else None
        if not isinstance(replies, list) or len(replies) != len(queries):
            raise TapoProtocolError("Incomplete Thing camera response")
        methods = [reply.get("method") for reply in replies if isinstance(reply, dict)]
        if len(methods) != len(queries) or not all(isinstance(method, str) for method in methods) or set(methods) != set(queries):
            raise TapoProtocolError("Mismatched Thing camera response")
        parsed = {}
        for reply in replies:
            method = reply["method"]
            try:
                parsed[method] = TapoCamera._method_result({"result": {"responses": [reply]}}, method, compatible=True)
            except TapoRequestError as error:
                parsed[method] = error
        return parsed

    def call(self, method: str, params: dict, *, read_only: bool = False):
        result = self._batch({method: params}, read_only=read_only)[method]
        if isinstance(result, Exception):
            raise result
        return result

    def device_snapshot(self):
        with self._lock:
            now = time.monotonic()
            queries = [(method, params) for method, params in CLOUD_QUERIES.items() if now >= self._retry_at.get(method, 0)]
            for offset in range(0, len(queries), 6):
                for method, result in self._batch(dict(queries[offset:offset + 6])).items():
                    if isinstance(result, TapoRequestError):
                        if method == "getDeviceInfo":
                            raise result
                        self._results.pop(method, None)
                        unsupported = result.code in {-40209, -40106, -40105}
                        self._statuses[method] = {"status": "unsupported" if unsupported else "transient_error", "code": result.code}
                        self._retry_at[method] = now + (900 if unsupported else 60)
                    else:
                        self._results[method] = result
                        self._statuses[method] = {"status": "ok"}
                        self._retry_at.pop(method, None)
            return self.snapshot()

    def snapshot(self):
        snapshot = {}
        for result in self._results.values():
            for module, value in result.items():
                if isinstance(value, dict):
                    snapshot.setdefault(module, {}).update(deepcopy(value))
        snapshot["api_status"] = deepcopy(self._statuses)
        return snapshot

    def set_setting(self, key: str, value):
        setting = SETTINGS_BY_KEY.get(key)
        if setting is None:
            raise ValueError("Unknown camera setting")
        params = setting.payload(value)
        desired = setting.value(params)
        with self._lock:
            current = self.call(setting.query, CLOUD_QUERIES[setting.query], read_only=True)
            if setting.value(current) is None:
                raise TapoConnectionError("Camera does not expose this setting")
            self._results[setting.query] = current
            if setting.value(current) == desired:
                return
            try:
                self.call(setting.method, params)
            except (NotificationError, TapoConnectionError):
                self._results.pop(setting.query, None)
                self._statuses[setting.query] = {"status": "unconfirmed"}
                raise
            self._results.pop(setting.query, None)
            self._statuses[setting.query] = {"status": "unconfirmed"}
            confirmed = self.call(setting.query, CLOUD_QUERIES[setting.query], read_only=True)
            self._results[setting.query] = confirmed
            self._statuses[setting.query] = {"status": "ok"}
            if setting.value(confirmed) != desired:
                raise TapoConnectionError("Camera did not confirm the requested value")

    def invalidate(self):
        self._retry_at.clear()

    def run_action(self, key: str):
        if key not in CLOUD_ACTIONS:
            raise ValueError("This action is not enabled through cloud")
        method, params = ACTIONS[key]
        return self.call(method, deepcopy(params))

    def move_to_preset(self, identifier: int):
        preset = self.snapshot().get("preset", {}).get("preset", {})
        if str(identifier) not in {str(item) for item in preset.get("id", [])}:
            raise ValueError("Unknown camera preset")
        return self.call("motorMoveToPreset", {"preset": {"goto_preset": {"id": str(identifier)}}})

    def close(self):
        with self._lock:
            self.gateway.session.close()
