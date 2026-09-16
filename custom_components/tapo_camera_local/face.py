"""Face metadata, not images or biometric embeddings; APK-derived field names."""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

MAX_FACE_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_MAGIC_TYPES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF8", "image/gif"),
    (b"RIFF", "image/webp"),
)


def value_at(data: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def epoch_seconds(value: Any) -> float | None:
    """Accept plausible Unix seconds or milliseconds; never invent a timestamp."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    if 946684800000 <= number < 4102444800000:
        number /= 1000
    return number if 946684800 <= number < 4102444800 else None


def timestamp(value: Any) -> datetime | None:
    seconds = epoch_seconds(value)
    return datetime.fromtimestamp(seconds, UTC) if seconds is not None else None


def face_identifier(value: Any) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str) and len(value) <= 40 and re.fullmatch(r"-?[0-9]+", value):
        return str(int(value))
    return None

def _image_type(data: bytes) -> str | None:
    for magic, content_type in IMAGE_MAGIC_TYPES:
        if data.startswith(magic):
            return content_type
    return None

def _decode_image_string(value: str) -> bytes | None:
    if len(value) > 4 * ((MAX_FACE_IMAGE_BYTES + 2) // 3) + 256:
        return None
    text = value.strip()
    if text.startswith("data:image/"):
        _, separator, text = text.partition(",")
        if not separator:
            return None
    if text.startswith(("http://", "https://")):
        return None
    compact = "".join(text.split())
    if len(compact) < 8:
        return None
    try:
        padding = "=" * (-len(compact) % 4)
        decoded = base64.b64decode(compact + padding, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(decoded) > MAX_FACE_IMAGE_BYTES or _image_type(decoded) is None:
        return None
    return decoded

def _decode_image_value(value: Any, depth: int = 0) -> bytes | None:
    if depth > 3:
        return None
    if isinstance(value, bytes):
        return value if len(value) <= MAX_FACE_IMAGE_BYTES and _image_type(value) else None
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("{", "[")):
            try:
                return _decode_image_value(json.loads(text), depth + 1)
            except (json.JSONDecodeError, TypeError, ValueError):
                return None
        return _decode_image_string(text)
    if isinstance(value, list):
        for item in value:
            if image := _decode_image_value(item, depth + 1):
                return image
        return None
    if isinstance(value, dict):
        for key in ("data", "base64", "content", "image", "face_info", "bytes"):
            if key in value and (image := _decode_image_value(value[key], depth + 1)):
                return image
    return None

def face_image_bytes(data: Any, identifier: str) -> bytes | None:
    """Decode only an actual image returned by the experimental face API."""
    node = value_at(data, "face_detection", "action_face_info_get")
    if node is None:
        node = value_at(data, "action_face_info_get")
    if isinstance(node, list):
        matching = [
            item for item in node
            if isinstance(item, dict) and face_identifier(item.get("face_id")) == identifier
        ]
        node = matching[0] if matching else None
    elif isinstance(node, dict) and "face_id" in node:
        if face_identifier(node.get("face_id")) != identifier:
            return None
    return _decode_image_value(node)


def face_state(data: Any) -> dict[str, Any]:
    config = value_at(data, "config", "face_detection", "detection")
    catalog_result = value_at(data, "catalog", "face_detection", "search_faces_info_result")
    records = value_at(catalog_result, "faces_infos")
    raw_events = value_at(data, "tracking", "tracking_traj_list")
    catalog_valid = isinstance(records, list)
    tracking_valid = isinstance(raw_events, list)
    catalog: dict[str, dict] = {}
    for record in records if catalog_valid else []:
        if not isinstance(record, dict):
            continue
        identifier = face_identifier(record.get("face_id"))
        if identifier is None:
            continue
        name = record.get("name")
        tag = record.get("tag")
        catalog[identifier] = {
            "face_id": identifier,
            "name": name[:255] if isinstance(name, str) and name else None,
            "tag": tag if isinstance(tag, str) and tag in {"familiar", "stranger", ""} else None,
            "fresh_time": timestamp(record.get("fresh_time")),
            "create_time": timestamp(record.get("create_time")),
            "modify_time": timestamp(record.get("modify_time")),
        }
    events = []
    for record in raw_events if tracking_valid else []:
        if not isinstance(record, dict):
            continue
        identifier = face_identifier(record.get("face_id"))
        started = timestamp(record.get("traj_start_time"))
        if identifier is None or started is None:
            continue
        events.append({
            "face_id": identifier,
            "recognized_at": started,
            "ended_at": timestamp(record.get("traj_end_time")),
            "source": "face_tracking",
        })
    events.sort(key=lambda event: (event["recognized_at"], event["face_id"]))
    total = value_at(catalog_result, "total_num")
    return {
        "enabled": as_boolean(value_at(config, "enabled")),
        "catalog_available": catalog_valid,
        "tracking_available": tracking_valid,
        "face_count": len(catalog) if catalog_valid else None,
        "reported_total": total if isinstance(total, int) else None,
        "catalog_complete": catalog_valid and (total is None or total == len(catalog)),
        "catalog": catalog,
        "events": events,
        "history_truncated": bool(value_at(data, "history_truncated")),
    }


def as_boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, int)):
        normalized = str(value).lower()
        if normalized in {"on", "1", "true", "enabled"}:
            return True
        if normalized in {"off", "0", "false", "disabled"}:
            return False
    return None


class FaceHistory:
    """Keep last-seen state and deduplicate polling; do not replay startup history."""

    def __init__(self) -> None:
        self.state = face_state({})
        self.last_event: dict | None = None
        self.last_seen: dict[str, datetime] = {}
        self._seen: OrderedDict[tuple, None] = OrderedDict()
        self._initialized = False

    def update(self, data: dict) -> list[dict]:
        self.state = face_state(data)
        emitted = []
        for event in self.state["events"]:
            identifier, occurred = event["face_id"], event["recognized_at"]
            key = identifier, occurred
            if key in self._seen:
                continue
            self._seen[key] = None
            if len(self._seen) > 4096:
                self._seen.popitem(last=False)
            if self.last_seen.get(identifier, datetime.min.replace(tzinfo=UTC)) >= occurred:
                continue
            self.last_seen[identifier] = occurred
            if self.last_event is None or occurred > self.last_event["recognized_at"]:
                self.last_event = event
            if self._initialized:
                person = self.state["catalog"].get(identifier, {})
                emitted.append({
                    "face_id": identifier, "name": person.get("name"),
                    "tag": person.get("tag"), "recognized_at": occurred.isoformat(),
                    "source": "face_tracking",
                })
        if self.state["tracking_available"]:
            self._initialized = True
        return emitted

    def latest(self) -> dict:
        event = self.last_event or {}
        person = self.state["catalog"].get(event.get("face_id"), {})
        return {
            "last_face_id": event.get("face_id"),
            "last_face_name": person.get("name"),
            "last_face_tag": person.get("tag"),
            "last_recognized_at": event.get("recognized_at"),
        }
