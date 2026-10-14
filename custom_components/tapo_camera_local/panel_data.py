"""Plain aggregation for the Tapo Connect panel; no frontend dependency here.

Every function takes plain values so the panel payloads can be unit-checked
without a running Home Assistant or a real camera.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from .const import CONF_CONNECTION_MODE, MODE_CLOUD_NOTIFICATIONS

CONTROL_DOMAINS = ("switch", "number", "select", "text", "button")
OBSERVATION_DOMAINS = ("sensor", "binary_sensor", "image")
CONTROL_SERVICES = {
    "switch": "turn_on",
    "number": "set_value",
    "select": "select_option",
    "text": "set_value",
    "button": "press",
}
HISTORY_LIMIT_DEFAULT = 100
HISTORY_LIMIT_MAX = 200


def runtime_for(data: dict, entry_id: str) -> dict:
    return (data or {}).get(entry_id) or {}


def is_cloud(entry) -> bool:
    return entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS


def camera_summary(entry, runtime: dict) -> dict:
    """One selectable camera for the panel header."""
    cloud = is_cloud(entry)
    notifications = runtime.get("notification_coordinator")
    coordinator = runtime.get("coordinator")
    if cloud and notifications is not None:
        name = notifications.device_name
        model = notifications.device_model
        device_id = notifications.device_id
        available = bool(notifications.last_update_success)
        settings_ready = bool(getattr(coordinator, "last_update_success", False))
    else:
        info = getattr(coordinator, "device_info", None)
        name = getattr(coordinator, "device_name", None) or entry.title
        model = getattr(info, "model", "") or ""
        device_id = getattr(coordinator, "device_id", None) or entry.entry_id
        available = bool(getattr(coordinator, "last_update_success", False))
        settings_ready = available
    return {
        "entry_id": entry.entry_id,
        "name": name,
        "model": model,
        "device_id": device_id,
        "mode": "cloud" if cloud else "local",
        "available": available,
        "settings_ready": settings_ready,
    }


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def control_item(registry_entry, state) -> dict | None:
    """Describe one writable entity for the settings tab."""
    domain = getattr(registry_entry, "domain", None)
    if domain not in CONTROL_DOMAINS or state is None:
        return None
    entity_id = registry_entry.entity_id
    attributes = state.attributes or {}
    item = {
        "entity_id": entity_id,
        "domain": domain,
        "service": CONTROL_SERVICES[domain],
        "name": attributes.get("friendly_name") or getattr(registry_entry, "name", None) or getattr(registry_entry, "original_name", None) or entity_id,
        "category": str(getattr(registry_entry, "entity_category", "") or "") or None,
        "available": state.state not in ("unavailable", "unknown"),
        "value": state.state,
    }
    if domain == "select":
        options = attributes.get("options")
        item["options"] = [option for option in options if isinstance(option, str)] if isinstance(options, list) else []
    if domain == "number":
        item["min"] = _number(attributes.get("min"))
        item["max"] = _number(attributes.get("max"))
        item["step"] = _number(attributes.get("step")) or 1
        item["unit"] = attributes.get("unit_of_measurement")
    if domain == "text":
        item["max_length"] = attributes.get("max")
    if domain == "button":
        item["value"] = None
    return item


def settings_items(registry_entries: Iterable, states) -> list[dict]:
    items = []
    for registry_entry in registry_entries:
        item = control_item(registry_entry, states.get(registry_entry.entity_id))
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: (item["category"] or "", item["name"].casefold(), item["entity_id"]))
    return items


def observation_item(registry_entry, state) -> dict | None:
    domain = getattr(registry_entry, "domain", None)
    if domain not in OBSERVATION_DOMAINS or state is None:
        return None
    attributes = state.attributes or {}
    return {
        "entity_id": registry_entry.entity_id,
        "domain": domain,
        "name": attributes.get("friendly_name") or getattr(registry_entry, "name", None) or registry_entry.entity_id,
        "value": state.state,
        "unit": attributes.get("unit_of_measurement"),
    }


def observation_items(registry_entries: Iterable, states) -> list[dict]:
    items = []
    for registry_entry in registry_entries:
        item = observation_item(registry_entry, states.get(registry_entry.entity_id))
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: (item["name"].casefold(), item["entity_id"]))
    return items


def _moment(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, UTC).isoformat()
    if isinstance(value, str) and value:
        return value
    return None


def face_items(face_state: dict, images: dict[str, str] | None = None) -> list[dict]:
    """Catalog faces plus the last time each was recognised."""
    images = images or {}
    catalog = face_state.get("catalog") if isinstance(face_state, dict) else None
    if not isinstance(catalog, dict):
        return []
    last_seen: dict[str, str] = {}
    for event in face_state.get("events") or []:
        if not isinstance(event, dict):
            continue
        face_id = str(event.get("face_id"))
        moment = _moment(event.get("recognized_at"))
        if moment and (face_id not in last_seen or moment > last_seen[face_id]):
            last_seen[face_id] = moment
    items = []
    for face_id, person in catalog.items():
        if not isinstance(person, dict):
            continue
        items.append({
            "face_id": str(face_id),
            "name": person.get("name") or None,
            "tag": person.get("tag") or None,
            "create_time": _moment(person.get("create_time")),
            "modify_time": _moment(person.get("modify_time")),
            "fresh_time": _moment(person.get("fresh_time")),
            "last_seen": last_seen.get(str(face_id)),
            "image_url": images.get(str(face_id)),
        })
    items.sort(key=lambda item: (item["name"] or "\uffff", item["face_id"]))
    return items


def person_items(people: dict, limit: int = 200) -> list[dict]:
    """Known people derived from cloud notification history."""
    if not isinstance(people, dict):
        return []
    items = []
    for event in people.values():
        if not isinstance(event, dict):
            continue
        items.append({
            "name": event.get("name"),
            "tag": event.get("tag"),
            "face_id": str(event.get("face_id")) if event.get("face_id") else None,
            "notified_at": _moment(event.get("notified_at")),
        })
    items.sort(key=lambda item: (item["notified_at"] or ""), reverse=True)
    return items[:limit]


def history_items(events: Iterable, *, tag: str | None = None, limit: int = HISTORY_LIMIT_DEFAULT) -> list[dict]:
    """Normalised, newest-first event list for the history tab."""
    limit = max(1, min(HISTORY_LIMIT_MAX, int(limit)))
    items = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        if tag and event.get("tag") != tag:
            continue
        items.append({
            "id": event.get("message_id") or event.get("id"),
            "name": event.get("name"),
            "tag": event.get("tag"),
            "face_id": str(event.get("face_id")) if event.get("face_id") else None,
            "message_type": event.get("message_type"),
            "source": event.get("source"),
            "notified_at": _moment(event.get("notified_at")),
        })
    items.sort(key=lambda item: (item["notified_at"] or ""), reverse=True)
    return items[:limit]


def license_summary(*, has_key: bool, claim: dict | None, checked: bool = True) -> dict:
    if not checked:
        return {"checked": False, "activated": has_key, "status": None}
    if not claim:
        return {"checked": True, "activated": False, "status": "inactive"}
    return {
        "checked": True,
        "activated": True,
        "status": claim.get("status"),
        "generation": claim.get("generation"),
        "valid_until": _moment(claim.get("validUntil")),
        "expires_at": _moment(claim.get("expiresAt")),
    }
