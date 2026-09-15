"""Request shapes recovered from com.tplink.libtapocameranetwork.model."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

MODULE = {
    "device_info": "device_info",
    "led": "led",
    "lens_mask": "lens_mask",
    "motor": "motor",
    "preset": "preset",
    "video": "video",
    "audio_config": "audio_config",
    "sd_security": "sd_security",
    "ptz": "ptz",
    "person_detection": "PERSON_DETECTION",
    "vehicle_detection": "vehicle_detection",
    "package_detection": "package_detection",
    "privacy_zone": "cover",
    "third_party": "third_party_compatibility",
    "stream": "video",
}

SECTION = {
    "basic_info": "basic_info",
    "name": "name",
    "config": "config",
    "capability": "capability",
    "state": "state",
    "control": "control",
    "status": "status",
    "presets": "presets",
    "third_party_setting": "third_party_setting",
}

METHOD = {
    "login": "login",
    "logout": "logout",
    "get_device_info": "getDeviceInfo",
    "get_led_status": "getLedStatus",
    "set_led_status": "setLedStatus",
    "get_led_capability": "getLedCapability",
    "get_lens_mask": "getLensMaskConfig",
    "set_lens_mask": "setLensMaskConfig",
    "get_presets": "getPresetConfig",
    "move_to_preset": "motorMoveToPreset",
    "motor_move": "motorMove",
    "stop_move": "stopMove",
    "get_video_qualities": "getVideoQualities",
    "get_stream_capability": "getStreamCapability",
    "request_rtsp_url": "request_rtsp_url",
    "get_sd_card_status": "getSdCardStatus",
    "reboot": "rebootDevice",
    "get_connection_type": "getConnectionType",
    "set_third_party_compatibility": "setThirdPartyCompatibility",
    "get_third_party_compatibility": "getThirdPartyCompatibility",
    "multiple_request": "multipleRequest",
}


def wrapper(
    module: str,
    section: str,
    data: Any = None,
) -> dict[str, Any]:
    return {MODULE[module]: {SECTION[section]: {} if data is None else data}}


def request(method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"method": METHOD.get(method, method)}
    if params is not None:
        payload["params"] = dict(params)
    return payload


def multiple(requests: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "method": METHOD["multiple_request"],
        "params": {"requests": [dict(item) for item in requests]},
    }


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    model: str
    name: str
    mac: str
    firmware: str
    hardware: str
    led: str | None
    rtsp_unrestricted: bool

    @classmethod
    def from_basic_info(cls, data: Mapping[str, Any]) -> DeviceInfo:
        return cls(
            device_id=str(data.get("dev_id", data.get("device_id", ""))),
            model=str(data.get("device_model", "")),
            name=str(data.get("device_name", data.get("device_alias", ""))),
            mac=str(data.get("mac", "")),
            firmware=str(data.get("sw_version", data.get("fw_ver", ""))),
            hardware=str(data.get("hw_version", data.get("hw_ver", data.get("hardware_version", "")))),
            led=data.get("led_status"),
            rtsp_unrestricted=bool(int(data.get("no_rtsp_constrain", 0))),
        )
