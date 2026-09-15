"""Only known, non-secret scalar fields become entities."""

from __future__ import annotations

import math
from typing import Any

try:
    from .face import as_boolean, timestamp, value_at
except ImportError:
    from face import as_boolean, timestamp, value_at

DETECTIONS = {
    "motion_detection": ("motion_det", "motion_detection"),
    "people_detection": ("detection", "person_detection"),
    "pet_detection": ("detection", "pet_detection"),
    "vehicle_detection": ("detection", "vehicle_detection"),
    "bark_detection": ("detection", "bark_detection"),
    "meow_detection": ("detection", "meow_detection"),
    "glass_detection": ("detection", "glass_detection"),
    "tamper_detection": ("tamper_det", "tamper_detection"),
    "sound_detection": ("bcd", "baby_cry_detection"),
    "linecrossing_detection": ("detection", "linecrossing_detection"),
    "intrusion_detection": ("detection", "intrusion_detection"),
    "face_detection": ("detection", "face_detection"),
}

SETTING_SWITCH_KEYS = frozenset({
    *(f"{module}_enabled" for module in DETECTIONS),
    "led",
    "lens_cover",
    "recording_loop",
    "record_audio",
    "microphone_mute",
    "image_flip",
    "auto_tracking",
    "smart_tracking_people",
    "smart_tracking_pet",
    "smart_tracking_vehicle",
    "smart_tracking_baby",
})


def observations(data: dict) -> dict[str, dict[str, Any]]:
    result = {}

    def add(key, name, value, *, kind="sensor", device_class=None, unit=None, translation_key=None, placeholders=None):
        if isinstance(value, (dict, list, tuple)):
            return
        if isinstance(value, str) and len(value) > 255:
            return
        result[key] = {
            "name": name, "value": value, "kind": kind,
            "device_class": device_class, "unit": unit,
            "translation_key": translation_key or key, "placeholders": placeholders or {},
        }

    basic = value_at(data, "device_info", "basic_info") or {}
    for field, key, name in (
        ("device_model", "model", "Model"), ("sw_version", "firmware", "Firmware"),
        ("fw_ver", "firmware", "Firmware"), ("hw_version", "hardware", "Hardware"),
        ("hw_ver", "hardware", "Hardware"), ("dev_id", "device_id", "Device ID"),
        ("device_id", "device_id", "Device ID"),
        ("mac", "mac", "MAC address"), ("local_ip", "ip_address", "IP address"),
        ("connection_type", "connection_type", "Connection type"),
        ("signal_level", "signal_level", "Wi-Fi signal level"),
    ):
        if field in basic:
            add(key, name, basic[field])
    if "rssi" in basic:
        try:
            rssi = int(basic["rssi"])
        except (TypeError, ValueError):
            rssi = None
        add("wifi_signal", "Wi-Fi signal", rssi, device_class="signal_strength", unit="dBm")
    for module, (section, title) in DETECTIONS.items():
        settings = value_at(data, module, section)
        if not isinstance(settings, dict):
            continue
        for field in ("enabled", "sensitivity", "digital_sensitivity"):
            if field in settings:
                value = as_boolean(settings[field]) if field == "enabled" else settings[field]
                add(f"{module}_{field}", title, value,
                    kind="setting" if field == "enabled" else "sensor")
    for module, section, key, title in (
        ("led", "config", "led", "Status LED"),
        ("lens_mask", "lens_mask_info", "lens_cover", "Privacy mode"),
    ):
        setting = value_at(data, module, section)
        if module == "lens_mask" and not isinstance(setting, dict):
            setting = value_at(data, module, "config")
        if isinstance(setting, dict) and "enabled" in setting:
            add(key, title, as_boolean(setting["enabled"]), kind="setting")

    audio = value_at(data, "audio_config") or {}
    speaker = audio.get("speaker") if isinstance(audio, dict) else None
    microphone = audio.get("microphone") if isinstance(audio, dict) else None
    record_audio = audio.get("record_audio") if isinstance(audio, dict) else None
    if isinstance(speaker, dict) and "volume" in speaker:
        add("speaker_volume", "speaker_volume", _number(speaker["volume"]), unit="%")
    if isinstance(microphone, dict):
        if "volume" in microphone:
            add("microphone_volume", "microphone_volume", _number(microphone["volume"]), unit="%")
        if "mute" in microphone:
            add("microphone_mute", "microphone_mute", as_boolean(microphone["mute"]), kind="setting")
    if isinstance(record_audio, dict) and "enabled" in record_audio:
        add("record_audio", "record_audio", as_boolean(record_audio["enabled"]), kind="setting")

    image = data.get("image") or {}
    common = image.get("common") if isinstance(image, dict) else None
    switch = image.get("switch") if isinstance(image, dict) else None
    if isinstance(common, dict) and common.get("inf_type") is not None:
        add("day_night_mode", "day_night_mode", str(common["inf_type"]), kind="select")
    if isinstance(switch, dict) and switch.get("flip_type") is not None:
        add("image_flip", "image_flip", {"center": True, "off": False}.get(str(switch["flip_type"]).lower()), kind="setting")

    harddisk = value_at(data, "harddisk_manage", "harddisk")
    if isinstance(harddisk, dict) and "loop" in harddisk:
        add("recording_loop", "recording_loop", as_boolean(harddisk["loop"]), kind="setting")

    target_track = value_at(data, "target_track", "target_track_info")
    if isinstance(target_track, dict) and "enabled" in target_track:
        add("auto_tracking", "auto_tracking", as_boolean(target_track["enabled"]), kind="setting")
    smart_track = value_at(data, "smart_track", "smart_track_info")
    if isinstance(smart_track, dict):
        for field, key in (
            ("people_enabled", "smart_tracking_people"),
            ("pet_enabled", "smart_tracking_pet"),
            ("vehicle_enabled", "smart_tracking_vehicle"),
            ("baby_enabled", "smart_tracking_baby"),
        ):
            if field in smart_track:
                add(key, key, as_boolean(smart_track[field]), kind="setting")
    alarm = value_at(data, "system", "last_alarm_info")
    if isinstance(alarm, dict):
        if "last_alarm_type" in alarm:
            add("last_alarm_type", "Last alarm type (camera code)", alarm["last_alarm_type"])
        if "last_alarm_time" in alarm:
            add("last_alarm_at", "Last alarm time", timestamp(alarm["last_alarm_time"]), device_class="timestamp")
    sd = value_at(data, "harddisk_manage", "hd_info")
    for path, record in storage_records(sd):
        for field in ("status", "capacity", "free", "used", "total", "percent", "free_space", "total_space"):
            if field in record:
                add(f"sd_{path}_{field}", f"SD {path} {field.replace('_', ' ')}", record[field], translation_key=f"sd_{field}", placeholders={"card": path})
    return result

def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return (int(number) if number.is_integer() else number) if math.isfinite(number) else None


def storage_records(value: Any, path: str = "card", depth: int = 0):
    if depth > 4:
        return
    if isinstance(value, dict):
        if "status" in value or "capacity" in value:
            yield path, value
        else:
            for key, child in value.items():
                if str(key).isalnum():
                    yield from storage_records(child, str(key), depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from storage_records(child, str(index + 1), depth + 1)
