"""Bounded local queries with strict, sanitized response handling."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import threading
import time
from copy import deepcopy
from typing import Any

from .controls import ACTIONS, SETTINGS_BY_KEY
from .models import DeviceInfo

SLOW_QUERIES = frozenset({"getAppComponentList", "getSdCardStatus", "getClockStatus"})


class TapoConnectionError(Exception):
    """A sanitized network or protocol failure."""


class TapoAuthError(TapoConnectionError):
    """Authentication failed or the camera temporarily blocked login."""


class TapoSecureTransportRequired(TapoConnectionError):
    """The selected transport is not implemented."""


class TapoProtocolError(TapoConnectionError):
    """A response arrived but did not match the expected camera schema."""


class TapoRequestError(TapoConnectionError):
    """A camera rejected a request without exposing its raw response."""

    def __init__(self, method: str, code: int) -> None:
        self.code = code
        super().__init__(f"{method}: camera error {code}")


READ_QUERIES = {
    "getAppComponentList": {"app_component": {"name": "app_component_list"}},
    "getLedStatus": {"led": {"name": ["config"]}},
    "getLensMaskConfig": {"lens_mask": {"name": ["lens_mask_info"]}},
    "getSdCardStatus": {"harddisk_manage": {"table": ["hd_info"]}},
    "getClockStatus": {"system": {"name": "clock_status"}},
    "getLastAlarmInfo": {"system": {"name": "last_alarm_info"}},
    "getPresetConfig": {"preset": {"name": ["preset"]}},
    "getDetectionConfig": {"motion_detection": {"name": ["motion_det"]}},
    "getPersonDetectionConfig": {"people_detection": {"name": ["detection"]}},
    "getPetDetectionConfig": {"pet_detection": {"name": ["detection"]}},
    "getVehicleDetectionConfig": {"vehicle_detection": {"name": ["detection"]}},
    "getBarkDetectionConfig": {"bark_detection": {"name": ["detection"]}},
    "getMeowDetectionConfig": {"meow_detection": {"name": ["detection"]}},
    "getGlassDetectionConfig": {"glass_detection": {"name": ["detection"]}},
    "getTamperDetectionConfig": {"tamper_detection": {"name": ["tamper_det"]}},
    "getBCDConfig": {"sound_detection": {"name": ["bcd"]}},
    "getLinecrossingDetectionConfig": {"linecrossing_detection": {"name": ["detection"]}},
    "getIntrusionDetectionConfig": {"intrusion_detection": {"name": ["detection"]}},
    "getFaceDetectionConfig": {"face_detection": {"name": ["detection"]}},
    "getRecordPlan": {"record_plan": {"name": ["chn1_channel"]}},
    "getCircularRecordingConfig": {"harddisk_manage": {"name": "harddisk"}},
    "getAudioConfig": {"audio_config": {"name": ["speaker", "microphone", "record_audio"]}},
    "getDayNightModeConfig": {"image": {"name": "common"}},
    "getRotationStatus": {"image": {"name": ["switch"]}},
    "getTargetTrackConfig": {"target_track": {"name": ["target_track_info"]}},
    "getSmartTrackConfig": {"smart_track": {"name": "smart_track_info"}},
    "getPatrolAction": {"patrol": {"get_patrol_action": {}}},
    "getCoverConfig": {"cover": {"name": ["cover"]}},
    "getMsgPushConfig": {"msg_push": {"name": ["chn1_msg_push_info"]}},
    "getAlertConfig": {"msg_alarm": {"name": ["chn1_msg_alarm_info"]}},
}

class TapoCamera:
    """Synchronous facade; HA calls it in an executor, not on its event loop."""

    def __init__(
        self, host: str, password: str, username: str = "admin", *,
        port: int = 443, use_https: bool = True, verify_ssl: bool = False,
        timeout: float = 10, transport_factory=None,
    ) -> None:
        host = host.strip()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
                raise ValueError("Enter an IP address or hostname, not a URL") from None
        if not use_https:
            raise TapoSecureTransportRequired("The local camera client requires HTTPS")
        if not 1 <= port <= 65535 or not 2 <= timeout <= 60:
            raise ValueError("Invalid port or timeout")
        self.host = host
        self.username = username
        self.password = password
        self._username = username
        self._port = port
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._factory = transport_factory
        self._transport = None
        self._runner = None
        self._lock = threading.RLock()
        self._results: dict[str, dict] = {}
        self._statuses: dict[str, dict] = {}
        self._retry_at: dict[str, float] = {}
        self._last_config_poll = float("-inf")
        self._last_catalog_poll = float("-inf")

    async def _send(self, body: dict, read_only: bool) -> dict:
        if self._transport is None:
            self._transport = self._build_transport()
        method = body["params"]["requests"][0]["method"]
        for attempt in range(2):
            try:
                response = await self._transport.send(json.dumps(body, separators=(",", ":")))
                return self._method_result(response, method)
            except TapoProtocolError:
                raise
            except Exception as error:  # noqa: BLE001
                if self._is_auth_error(error):
                    raise TapoAuthError("Camera rejected or temporarily blocked login") from None
                code = error.code if isinstance(error, TapoRequestError) else getattr(error, "error_code", None)
                if read_only and attempt == 0 and code in {-40401, 9999}:
                    await self._transport.reset()
                    continue
                if code is not None:
                    raise TapoRequestError(method, int(code)) from None
                await self._transport.reset()
                raise TapoConnectionError("Camera network/TLS request failed") from None
        raise TapoConnectionError("Camera session could not be renewed")

    def _build_transport(self):
        if self._factory is not None:
            return self._factory(self.host, self._port, self._username, self.password)
        raise TapoSecureTransportRequired("Use the native PytapoCamera client")

    @staticmethod
    def _is_auth_error(error: Exception) -> bool:
        name = error.__class__.__name__.lower()
        code = getattr(error, "error_code", None)
        if "auth" in name or code in {
            -40404,
            -40411,
            -40412,
            -1501,
            1111,
            -1005,
            1100,
            1003,
        }:
            return True
        message = str(error).lower()
        return any(
            marker in message
            for marker in (
                "invalid authentication",
                "invalid credentials",
                "authentication data",
                "login failed",
                "unknown credentials",
                "handshake failed",
            )
        )

    def call(self, method: str, params: dict | None = None, *, read_only: bool = False) -> dict:
        with self._lock:
            if self._runner is None:
                self._runner = asyncio.Runner()
            body = {
                "method": "multipleRequest",
                "params": {"requests": [{"method": method, "params": params or {}}]},
            }
            result = self._runner.run(self._send(body, read_only))
            if not read_only:
                self._last_config_poll = float("-inf")
            return result

    @classmethod
    def _method_result(cls, response: Any, method: str, *, compatible: bool = False) -> dict:
        if not isinstance(response, dict):
            raise TapoProtocolError("Invalid camera response type")
        cls._check_error(response, method, allow_missing=compatible)
        envelope = response.get("result")
        if not isinstance(envelope, dict):
            raise TapoProtocolError("Missing camera response envelope")
        replies = envelope.get("responses")
        if not isinstance(replies, list) or len(replies) != 1 or not isinstance(replies[0], dict):
            raise TapoProtocolError("Missing camera method response")
        reply = replies[0]
        if reply.get("method", method) != method:
            raise TapoProtocolError("Unexpected camera method response")
        cls._check_error(reply, method, allow_missing=compatible)
        if compatible and "result" not in reply:
            result = {key: value for key, value in reply.items() if key not in {"method", "error_code"}}
        else:
            result = reply.get("result", {})
        if not isinstance(result, dict):
            raise TapoProtocolError("Missing camera method result")
        return result

    @staticmethod
    def _check_error(response: dict, method: str, *, allow_missing: bool = False) -> None:
        if allow_missing and "error_code" not in response:
            return
        code = response.get("error_code")
        if not isinstance(code, int) or isinstance(code, bool):
            raise TapoProtocolError("Missing or invalid camera error code")
        if code in {
            -40404,
            -40411,
            -40412,
            -1501,
            1111,
            -1005,
            1100,
            1003,
        }:
            raise TapoAuthError("Camera rejected or temporarily blocked authentication")
        if code:
            raise TapoRequestError(method, code)

    def _optional(self, method: str, params: dict) -> dict | None:
        if self._retry_at.get(method, 0) > time.monotonic():
            return None
        try:
            result = self.call(method, params, read_only=True)
        except TapoRequestError as error:
            status = "unsupported" if error.code == -40106 else "rejected"
            self._statuses[method] = {"status": status, "error_code": error.code}
            self._retry_at[method] = time.monotonic() + (3600 if status == "unsupported" else 300)
            self._results.pop(method, None)
            return None
        except TapoAuthError:
            raise
        except TapoConnectionError:
            self._statuses[method] = {"status": "transient_error"}
            self._retry_at[method] = time.monotonic() + 30
            self._results.pop(method, None)
            return None
        self._statuses[method] = {"status": "ok"}
        self._retry_at.pop(method, None)
        self._results[method] = result
        return result

    def basic_info(self) -> DeviceInfo:
        with self._lock:
            result = self.call("getDeviceInfo", {"device_info": {"name": ["basic_info"]}}, read_only=True)
            section = result.get("device_info")
            basic = section.get("basic_info") if isinstance(section, dict) else None
            if not isinstance(basic, dict) or not basic.get("device_model"):
                raise TapoProtocolError("Camera did not return basic_info")
            self._results["getDeviceInfo"] = result
            return DeviceInfo.from_basic_info(basic)

    def login(self) -> None:
        self.basic_info()

    def _optional_many(self, queries: dict) -> None:
        for method, params in queries.items():
            self._optional(method, params)

    def invalidate(self) -> None:
        with self._lock:
            self._last_config_poll = float("-inf")
            self._last_catalog_poll = float("-inf")

    def set_setting(self, key: str, value: Any) -> None:
        setting = SETTINGS_BY_KEY.get(key)
        if setting is None:
            raise ValueError("Unknown camera setting")
        params = setting.payload(value)
        requested_value = setting.value(params)
        with self._lock:
            current = self.call(setting.query, READ_QUERIES[setting.query], read_only=True)
            current_value = setting.value(current)
            if current_value is None:
                raise TapoConnectionError("Camera does not expose this setting with a known schema")
            if current_value == requested_value:
                self._results[setting.query] = current
                return
            self.call(setting.method, params)
            try:
                confirmed = self.call(setting.query, READ_QUERIES[setting.query], read_only=True)
            except TapoConnectionError:
                self._results.pop(setting.query, None)
                raise TapoConnectionError("Command sent but camera state could not be confirmed") from None
            self._results[setting.query] = confirmed
            self._statuses[setting.query] = {"status": "ok"}
            if setting.value(confirmed) != requested_value:
                raise TapoConnectionError("Camera did not confirm the requested value; refresh to see its actual state")

    def run_action(self, key: str) -> dict:
        method, params = ACTIONS[key]
        return self.call(method, deepcopy(params))

    def device_snapshot(self) -> dict:
        with self._lock:
            self.basic_info()
            now = time.monotonic()
            self._optional_many({method: params for method, params in READ_QUERIES.items() if method not in SLOW_QUERIES})
            if now - self._last_config_poll >= 60:
                self._optional_many({method: params for method, params in READ_QUERIES.items() if method in SLOW_QUERIES})
                self._last_config_poll = now
            if now - self._last_catalog_poll >= 60:
                self._optional("searchFacesInfo", {
                    "face_detection": {"search_faces_info": {
                        "update_time": 0, "strategy": "select", "face_id": [], "tag": []
                    }}
                })
                self._last_catalog_poll = now
            face = self._face_snapshot()
            snapshot: dict[str, Any] = {}
            for method, result in self._results.items():
                if method in {"searchFacesInfo", "doSearchFaceTrackingList", "doFaceInfoGet"}:
                    continue
                for module, value in result.items():
                    if isinstance(value, dict):
                        snapshot.setdefault(module, {}).update(deepcopy(value))
            snapshot["face_data"] = face
            snapshot["api_status"] = deepcopy(self._statuses)
            return snapshot

    def face_image(self, face_id: str | int) -> bytes | None:
        with self._lock:
            return self._face_image(face_id)

    def _face_image(self, face_id: str | int) -> bytes | None:
        """Fetch a profile image when the camera exposes the legacy JSON API."""
        try:
            identifier = int(face_id)
        except (TypeError, ValueError):
            return None
        if identifier < 0:
            return None
        response = self._optional("doFaceInfoGet", {
            "face_detection": {"action_face_info_get": {"face_id": [identifier]}}
        })
        self._results.pop("doFaceInfoGet", None)
        if response is None:
            return None
        try:
            from ..face import face_image_bytes
        except ImportError:
            from face import face_image_bytes

        image = face_image_bytes(response, str(identifier))
        if image is None:
            self._statuses["doFaceInfoGet"] = {"status": "invalid_image"}
        else:
            self._statuses["doFaceInfoGet"] = {"status": "ok", "image": "available"}
        return image

    def _face_snapshot(self) -> dict:
        config = self._results.get("getFaceDetectionConfig", {})
        catalog = self._results.get("searchFacesInfo", {})
        result = {
            "config": deepcopy(config), "catalog": deepcopy(catalog),
            "tracking": {}, "history_truncated": False,
        }
        if not config and not catalog:
            return result
        now = int(time.time())
        records: list[dict] = []
        for page in range(5):
            response = self._optional("doSearchFaceTrackingList", {
                "face_detection": {"action_search_face_tracking_list": {
                    "start_time": now - 3600, "end_time": now,
                    "start_index": page * 100, "end_index": page * 100 + 99,
                    "tag": [], "face_id": [], "mode": "brief", "order": "reverse",
                }}
            })
            if response is None:
                return result
            page_result: Any = response
            for section in ("face_detection", "action_search_face_tracking_list", "search_face_tracking_list_result"):
                page_result = page_result.get(section) if isinstance(page_result, dict) else None
            if not isinstance(page_result, dict) or not isinstance(page_result.get("tracking_traj_list"), list):
                self._statuses["doSearchFaceTrackingList"] = {"status": "invalid_response"}
                return result
            page_records = page_result["tracking_traj_list"]
            records.extend(page_records)
            total = page_result.get("traj_cnt")
            if len(page_records) < 100 or isinstance(total, int) and len(records) >= total:
                break
        else:
            result["history_truncated"] = True
        result["tracking"] = {"tracking_traj_list": records}
        return result

    def presets(self) -> list[dict]:
        preset = self._results.get("getPresetConfig", {}).get("preset", {}).get("preset", {})
        names, identifiers = preset.get("name", []), preset.get("id", [])
        if not isinstance(names, list) or not isinstance(identifiers, list):
            return []
        return [{"name": str(name), "index": str(identifier)} for identifier, name in zip(identifiers, names)]

    def set_led(self, enabled: bool) -> dict:
        return self.call("setLedStatus", {"led": {"config": {"enabled": "on" if enabled else "off"}}})

    def set_privacy(self, enabled: bool) -> dict:
        return self.call("setLensMaskConfig", {"lens_mask": {"lens_mask_info": {"enabled": "on" if enabled else "off"}}})

    def move_to_preset(self, index: int) -> dict:
        return self.call("motorMoveToPreset", {"preset": {"goto_preset": {"id": str(index)}}})

    def ptz_stop(self) -> dict:
        return self.call("stopMove", {"motor": {"stop": ""}})

    def reboot(self) -> dict:
        return self.call("rebootDevice", {"system": {"reboot": "null"}})

    def close(self) -> None:
        with self._lock:
            if self._runner is not None:
                try:
                    if self._transport is not None:
                        self._runner.run(self._transport.close())
                finally:
                    self._runner.close()
                    self._runner = None
                    self._transport = None
