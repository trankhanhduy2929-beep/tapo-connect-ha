"""Camera notifications; history is not physical presence or a tracking clock."""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from datetime import UTC, datetime

FACE_NOTIFICATION_TYPES = {"familiarFaceDetected": "familiar", "unfamiliarFaceDetected": "stranger"}
NOTIFICATION_TYPES = {
    **FACE_NOTIFICATION_TYPES,
    "Motion": "motion", "Audio": "audio", "BabyCry": "baby_cry",
    "PersonDetected": "person", "PersonEnhanced": "person",
    "PetDetected": "pet", "VehicleDetected": "vehicle",
    "tapoCameraAreaIntrusionDetection": "intrusion",
    "tapoCameraLinecrossingDetection": "line_crossing",
    "tapoCameraCameraTampering": "tampering",
    "tapoGlassBreakingDetected": "glass_break",
    "tapoSmokeAlarmDetected": "smoke_alarm",
    "tapoMeowDetected": "meow", "tapoBarkDetected": "bark",
    "Tapo.LoiteringDetected": "loitering",
    "deliverPackageDetected": "package_delivered",
    "pickUpPackageDetected": "package_removed",
    "antiTheft": "anti_theft", "ringEvent": "doorbell", "missRingEvent": "missed_doorbell",
    "tapoCameraSDNeedInitialization": "sd_uninitialized",
    "tapoCameraSDInsufficientStorage": "sd_full",
    "hardDiskNotInitialized": "disk_uninitialized",
    "hardDiskInsufficientStorage": "disk_full",
    "Tapo.CamSDCardEncryptionDisabled": "sd_encryption_disabled",
    "Tapo.CamSDCardAutomaticDecryptionFailed": "sd_decryption_failed",
    "CameraLowBattery": "low_battery", "BatteryEmpty": "battery_empty",
    "BatteryFullyCharged": "battery_charged",
    "tapoDeviceOverheat": "overheat", "tapoDeviceOverheatRelieve": "overheat_cleared",
    "tapoNewFirmware": "new_firmware", "Tapo.multipleTypeDetect": "multiple_detection",
}
CORE_CATEGORIES = (
    "familiar", "stranger", "person", "pet", "vehicle", "motion", "audio",
    "baby_cry", "bark", "meow", "glass_break", "smoke_alarm", "tampering",
    "intrusion", "line_crossing",
)
NOTIFICATION_CATEGORIES = tuple(dict.fromkeys(NOTIFICATION_TYPES.values()))
RECENT_SECONDS = 60


def notification_time(value, now: float) -> datetime | None:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{10,13}", value):
        value = int(value)
    if type(value) is not int:
        return None
    seconds = value / 1000 if value >= 1000000000000 else value
    if not 946684800 <= seconds <= now + 300:
        return None
    return datetime.fromtimestamp(seconds, UTC)


def safe_text(value, limit: int = 255) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(character) < 32 for character in value):
        return None
    return value


def parse_notification(record, camera_id: str, now: float) -> dict | None:
    if not isinstance(record, dict):
        return None
    message_type = record.get("msgType")
    tag = NOTIFICATION_TYPES.get(message_type) if isinstance(message_type, str) else None
    if tag is None:
        return None
    attachment = record.get("attachments")
    if isinstance(attachment, str) and len(attachment) <= 65536:
        try:
            attachment = json.loads(attachment)
        except (ValueError, RecursionError):
            return None
    if not isinstance(attachment, dict):
        return None
    identifier = attachment.get("deviceId")
    if not isinstance(identifier, str) or identifier.casefold() != camera_id.casefold():
        return None
    message_id = safe_text(record.get("msgId"))
    occurred = notification_time(record.get("time"), now)
    if message_id is None or occurred is None:
        return None
    name = safe_text(attachment.get("personName")) if tag == "familiar" else None
    face_id = attachment.get("faceId")
    if type(face_id) is int:
        face_id = str(face_id)
    face_id = safe_text(face_id, 128)
    return {
        "message_id": message_id, "name": name, "tag": tag, "face_id": face_id,
        "message_type": message_type,
        "notified_at": occurred, "time_source": "notification.time",
        "source": "tapo_cloud_notification",
    }


class NotificationHistory:
    def __init__(self):
        self.latest = None
        self.latest_notification = None
        self.categories = {}
        self.people = {}
        self.seen = OrderedDict()
        self.initialized = False
        self.count = 0
        self.truncated = False

    def update(self, records: list, camera_id: str, now: float, *, truncated: bool = False) -> list:
        events = [event for record in records if (event := parse_notification(record, camera_id, now)) is not None]
        events.sort(key=lambda event: (event["notified_at"], event["message_id"]))
        self.count = len({event["message_id"] for event in events})
        self.truncated = truncated
        emitted = []
        for event in events:
            if event["tag"] in {"familiar", "stranger"} and (self.latest is None or event["notified_at"] > self.latest["notified_at"]):
                self.latest = event
            if self.latest_notification is None or event["notified_at"] > self.latest_notification["notified_at"]:
                self.latest_notification = event
            previous_category = self.categories.get(event["tag"])
            if previous_category is None or event["notified_at"] > previous_category["notified_at"]:
                self.categories[event["tag"]] = event
            if event["name"]:
                person_key = hashlib.sha256(event["name"].encode()).hexdigest()[:24]
                previous = self.people.get(person_key)
                if (previous is None or event["notified_at"] > previous["notified_at"]) and (previous is not None or len(self.people) < 200):
                    self.people[person_key] = event
            if event["message_id"] not in self.seen:
                if self.initialized and event["notified_at"].timestamp() >= now - 120:
                    emitted.append(event)
                self.seen[event["message_id"]] = None
        while len(self.seen) > 2000:
            self.seen.popitem(last=False)
        self.initialized = True
        return emitted

    def dump(self, camera_id: str) -> dict:
        events = {event["message_id"]: event for event in [*self.categories.values(), *self.people.values()]}
        return {"version": 1, "camera_id": camera_id, "notifications": [
            {"msgId": event["message_id"], "msgType": event["message_type"], "time": int(event["notified_at"].timestamp() * 1000),
             "attachments": {"deviceId": camera_id, "personName": event["name"], "faceId": event["face_id"]}}
            for event in events.values()
        ]}

    def restore(self, data, camera_id: str, now: float):
        if not isinstance(data, dict) or data.get("version") != 1 or data.get("camera_id") != camera_id:
            return False
        records = data.get("notifications")
        if not isinstance(records, list) or len(records) > 200 + len(NOTIFICATION_CATEGORIES):
            return False
        self.update(records, camera_id, now)
        self.initialized = False
        return True
