"""Bounded single-channel settings recovered from pytapo and the APK models."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Setting:
    key: str
    kind: str
    query: str
    method: str
    module: str
    section: str
    field: str
    minimum: int = 0
    maximum: int = 100
    choices: tuple[str, ...] = ()
    on_value: str = "on"
    off_value: str = "off"

    def value(self, snapshot: dict) -> Any:
        module = snapshot.get(self.module)
        if not isinstance(module, dict):
            return None
        section = module.get(self.section)
        if not isinstance(section, dict):
            return None
        raw = section.get(self.field)
        try:
            if self.kind == "switch":
                return {self.on_value: True, self.off_value: False}.get(raw)
            if self.kind == "number":
                number = float(raw)
                return int(number) if not isinstance(raw, bool) and number.is_integer() and self.minimum <= number <= self.maximum else None
            if self.kind == "select":
                return raw if raw in self.choices else None
            if self.kind == "text":
                return schedule(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        return None

    def payload(self, value: Any) -> dict:
        if self.kind == "switch":
            if not isinstance(value, bool):
                raise ValueError("A boolean is required")
            encoded = self.on_value if value else self.off_value
        elif self.kind == "number":
            number = float(value)
            if isinstance(value, bool) or not math.isfinite(number) or not number.is_integer() or not self.minimum <= number <= self.maximum:
                raise ValueError("Number is outside the supported range")
            encoded = str(int(number)) if "detection" in self.module else int(number)
        elif self.kind == "select":
            if value not in self.choices:
                raise ValueError("Unsupported option")
            encoded = value
        else:
            encoded = schedule(value)
        params = {self.module: {self.section: {self.field: encoded}}}
        if self.method in {"setSpeakerVolume", "setMicrophoneVolume"}:
            params["method"] = "set"
        return params


def schedule(value: Any) -> str:
    """Validate a single day without altering the other six days or enabled flag."""
    if not isinstance(value, str) or len(value) > 255:
        raise ValueError("Use a JSON list of at most ten recording periods")
    periods = json.loads(value)
    if not isinstance(periods, list) or len(periods) > 10:
        raise ValueError("Use at most ten recording periods")
    previous_end = 0
    for period in periods:
        match = re.fullmatch(r"(\d{2})(\d{2})-(\d{2})(\d{2}):([12])", period) if isinstance(period, str) else None
        if match is None:
            raise ValueError("Expected HHMM-HHMM:1 or HHMM-HHMM:2")
        start_hour, start_minute, end_hour, end_minute = map(int, match.groups()[:4])
        start = start_hour * 60 + start_minute
        end = end_hour * 60 + end_minute
        if start_hour > 23 or end_hour > 24 or start_minute > 59 or end_minute > 59 or end > 1440 or not previous_end <= start < end:
            raise ValueError("Periods must be ordered, non-overlapping and within one day")
        previous_end = end
    return json.dumps(periods, separators=(",", ":"))


DETECTION_SCHEMAS = (
    ("motion_detection", "motion_det", "Detection"),
    ("people_detection", "detection", "PersonDetection"),
    ("pet_detection", "detection", "PetDetection"),
    ("vehicle_detection", "detection", "VehicleDetection"),
    ("bark_detection", "detection", "BarkDetection"),
    ("meow_detection", "detection", "MeowDetection"),
    ("glass_detection", "detection", "GlassDetection"),
    ("tamper_detection", "tamper_det", "TamperDetection"),
    ("sound_detection", "bcd", "BCD"),
    ("linecrossing_detection", "detection", "LinecrossingDetection"),
    ("intrusion_detection", "detection", "IntrusionDetection"),
    ("face_detection", "detection", "FaceDetection"),
)

SETTINGS = [
    Setting("led", "switch", "getLedStatus", "setLedStatus", "led", "config", "enabled"),
    Setting("privacy", "switch", "getLensMaskConfig", "setLensMaskConfig", "lens_mask", "lens_mask_info", "enabled"),
    Setting("recording", "switch", "getRecordPlan", "setRecordPlan", "record_plan", "chn1_channel", "enabled"),
    Setting("recording_loop", "switch", "getCircularRecordingConfig", "setCircularRecordingConfig", "harddisk_manage", "harddisk", "loop"),
    Setting("record_audio", "switch", "getAudioConfig", "setRecordAudio", "audio_config", "record_audio", "enabled"),
    Setting("microphone_mute", "switch", "getAudioConfig", "setMicrophoneVolume", "audio_config", "microphone", "mute"),
    Setting("noise_cancelling", "switch", "getAudioConfig", "setMicrophoneVolume", "audio_config", "microphone", "noise_cancelling"),
    Setting("speaker_volume", "number", "getAudioConfig", "setSpeakerVolume", "audio_config", "speaker", "volume"),
    Setting("microphone_volume", "number", "getAudioConfig", "setMicrophoneVolume", "audio_config", "microphone", "volume"),
    Setting("day_night_mode", "select", "getDayNightModeConfig", "setDayNightModeConfig", "image", "common", "inf_type", choices=("auto", "on", "off")),
    Setting("light_frequency", "select", "getDayNightModeConfig", "setLightFrequencyInfo", "image", "common", "light_freq_mode", choices=("auto", "50", "60")),
    Setting("image_flip", "switch", "getRotationStatus", "setRotationStatus", "image", "switch", "flip_type", on_value="center"),
    Setting("lens_correction", "switch", "getRotationStatus", "setLdc", "image", "switch", "ldc"),
    Setting("white_lamp", "switch", "getRotationStatus", "setLdc", "image", "switch", "force_wtl_state"),
    Setting("auto_tracking", "switch", "getTargetTrackConfig", "setTargetTrackConfig", "target_track", "target_track_info", "enabled"),
    Setting("privacy_zones", "switch", "getCoverConfig", "setCoverConfig", "cover", "cover", "enabled"),
    Setting("notifications", "switch", "getMsgPushConfig", "setMsgPushConfig", "msg_push", "chn1_msg_push_info", "notification_enabled"),
    Setting("rich_notifications", "switch", "getMsgPushConfig", "setMsgPushConfig", "msg_push", "chn1_msg_push_info", "rich_notification_enabled"),
]

for module, section, stem in DETECTION_SCHEMAS:
    query, method = f"get{stem}Config", f"set{stem}Config"
    SETTINGS.append(Setting(f"{module}_enabled", "switch", query, method, module, section, "enabled"))
    if module in {"tamper_detection", "sound_detection"}:
        SETTINGS.append(Setting(f"{module}_sensitivity", "select", query, method, module, section, "sensitivity", choices=("low", "medium", "high")))
    elif module not in {"linecrossing_detection", "intrusion_detection", "face_detection"}:
        field = "digital_sensitivity" if module == "motion_detection" else "sensitivity"
        SETTINGS.append(Setting(f"{module}_{field}", "number", query, method, module, section, field, minimum=1))

for target in ("people", "pet", "vehicle", "baby"):
    SETTINGS.append(Setting(f"smart_tracking_{target}", "switch", "getSmartTrackConfig", "setSmartTrackConfig", "smart_track", "smart_track_info", f"{target}_enabled"))

for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
    SETTINGS.append(Setting(f"recording_{day}", "text", "getRecordPlan", "setRecordPlan", "record_plan", "chn1_channel", day))

SETTINGS = tuple(SETTINGS)
SETTINGS_BY_KEY = {setting.key: setting for setting in SETTINGS}

ACTIONS = {
    "reboot": ("rebootDevice", {"system": {"reboot": "null"}}),
    "ptz_stop": ("stopMove", {"motor": {"stop": "null"}}),
    "ptz_left": ("singalMove", {"motor": {"movestep": {"direction": "180"}}}),
    "ptz_right": ("singalMove", {"motor": {"movestep": {"direction": "0"}}}),
    "ptz_up": ("singalMove", {"motor": {"movestep": {"direction": "90"}}}),
    "ptz_down": ("singalMove", {"motor": {"movestep": {"direction": "270"}}}),
    "ptz_calibrate": ("manualCalibrate", {"motor": {"manual_cali": {"cal_to_resume": "0"}}}),
    "cruise_horizontal": ("cruiseMove", {"motor": {"cruise": {"coord": "x"}}}),
    "cruise_vertical": ("cruiseMove", {"motor": {"cruise": {"coord": "y"}}}),
    "cruise_stop": ("cruiseStop", {"motor": {"cruise_stop": "null"}}),
    "manual_alarm_start": ("do", {"msg_alarm": {"manual_msg_alarm": {"action": "start"}}}),
    "manual_alarm_stop": ("do", {"msg_alarm": {"manual_msg_alarm": {"action": "stop"}}}),
}


def validate_write(method: str, params: dict) -> None:
    for setting in SETTINGS:
        if method != setting.method:
            continue
        try:
            raw = params[setting.module][setting.section][setting.field]
            value = {setting.on_value: True, setting.off_value: False}.get(raw) if setting.kind == "switch" else raw
            if setting.payload(value) == params:
                return
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if any(method == action_method and params == body for action_method, body in ACTIONS.values()):
        return
    if method == "motorMoveToPreset":
        try:
            identifier = params["preset"]["goto_preset"]["id"]
            if isinstance(identifier, str) and re.fullmatch(r"[0-9]{1,6}", identifier) and params == {"preset": {"goto_preset": {"id": identifier}}}:
                return
        except (KeyError, TypeError):
            pass
    raise ValueError("Unrecognized camera command or payload")
