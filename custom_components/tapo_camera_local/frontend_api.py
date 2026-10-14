"""Websocket API backing the Tapo Connect sidebar panel.

The handlers are thin: gather Home Assistant state, hand it to the plain
builders in :mod:`panel_data`, and answer. Nothing here writes to a camera.
"""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from . import panel_data
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

WS_CAMERAS = f"{DOMAIN}/cameras"
WS_OVERVIEW = f"{DOMAIN}/overview"
WS_FACES = f"{DOMAIN}/faces"
WS_HISTORY = f"{DOMAIN}/history"


def _registered(hass: HomeAssistant) -> dict:
    return hass.data.setdefault(f"{DOMAIN}_panel_registered", {})


def _entries(hass: HomeAssistant) -> list:
    return list(hass.config_entries.async_entries(DOMAIN))


def _runtime(hass: HomeAssistant, entry) -> dict:
    return panel_data.runtime_for(hass.data.get(DOMAIN), entry.entry_id)


def _registry_entries(hass: HomeAssistant, entry) -> list:
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    return list(er.async_entries_for_config_entry(registry, entry.entry_id))


def _entry_or_raise(hass: HomeAssistant, entry_id: str):
    entry = hass.config_entries.async_get_entry(entry_id) if entry_id else None
    if entry is None or entry.domain != DOMAIN:
        raise LookupError("config entry not found")
    return entry


async def async_cameras(hass: HomeAssistant) -> list[dict]:
    return [
        panel_data.camera_summary(entry, _runtime(hass, entry))
        for entry in _entries(hass)
    ]


async def async_overview(hass: HomeAssistant, entry_id: str) -> dict:
    entry = _entry_or_raise(hass, entry_id)
    runtime = _runtime(hass, entry)
    registry_entries = _registry_entries(hass, entry)
    states = hass.states
    return {
        "camera": panel_data.camera_summary(entry, runtime),
        "settings": panel_data.settings_items(registry_entries, states),
        "observations": panel_data.observation_items(registry_entries, states),
        "license": await _license_payload(hass, entry),
        "capabilities": _capabilities(entry, runtime),
    }


async def async_faces(hass: HomeAssistant, entry_id: str) -> dict:
    entry = _entry_or_raise(hass, entry_id)
    runtime = _runtime(hass, entry)
    if panel_data.is_cloud(entry):
        notifications = runtime.get("notification_coordinator")
        people = notifications.history.people if notifications is not None else {}
        return {
            "mode": "cloud",
            "catalog_available": False,
            "people": panel_data.person_items(people),
            "items": [],
        }
    coordinator = runtime.get("coordinator")
    state = getattr(getattr(coordinator, "face_history", None), "state", {}) or {}
    images = _face_images(hass, entry)
    return {
        "mode": "local",
        "catalog_available": bool(state.get("catalog_available")),
        "tracking_available": bool(state.get("tracking_available")),
        "face_count": state.get("face_count"),
        "items": panel_data.face_items(state, images),
    }


def _face_images(hass: HomeAssistant, entry) -> dict[str, str]:
    images: dict[str, str] = {}
    for registry_entry in _registry_entries(hass, entry):
        if getattr(registry_entry, "domain", None) != "image":
            continue
        state = hass.states.get(registry_entry.entity_id)
        if state is None:
            continue
        face_id = (state.attributes or {}).get("face_id")
        picture = (state.attributes or {}).get("entity_picture")
        if face_id is not None and picture:
            images[str(face_id)] = picture
    return images


async def async_history(hass: HomeAssistant, entry_id: str, *, tag: str | None = None, limit: int = panel_data.HISTORY_LIMIT_DEFAULT) -> dict:
    entry = _entry_or_raise(hass, entry_id)
    runtime = _runtime(hass, entry)
    if panel_data.is_cloud(entry):
        notifications = runtime.get("notification_coordinator")
        events = notifications.history.events(tag=tag, limit=limit) if notifications is not None else []
        return {"mode": "cloud", "tag": tag, "items": panel_data.history_items(events, tag=tag, limit=limit)}
    coordinator = runtime.get("coordinator")
    state = getattr(getattr(coordinator, "face_history", None), "state", {}) or {}
    catalog = state.get("catalog") or {}
    events = []
    for event in state.get("events") or []:
        person = catalog.get(event.get("face_id"), {})
        occurred = event.get("recognized_at")
        events.append({
            "id": f"{event.get('face_id')}:{occurred.isoformat() if hasattr(occurred, 'isoformat') else occurred}",
            "name": person.get("name"),
            "tag": person.get("tag"),
            "face_id": event.get("face_id"),
            "message_type": None,
            "source": event.get("source"),
            "notified_at": occurred,
        })
    return {"mode": "local", "tag": tag, "items": panel_data.history_items(events, tag=tag, limit=limit)}


def _capabilities(entry, runtime: dict) -> dict:
    if panel_data.is_cloud(entry):
        return {"settings": True, "faces": False, "history": True, "face_write": False}
    coordinator = runtime.get("coordinator")
    state = getattr(getattr(coordinator, "face_history", None), "state", {}) or {}
    return {
        "settings": True,
        "faces": bool(state.get("catalog_available")),
        "history": True,
        "face_write": False,
    }


async def _license_payload(hass: HomeAssistant, entry) -> dict:
    from .license_client import LICENSE_INSTANCE, LicenseError, verify_lease
    from .license_policy_locked import load_policy
    from .licensing import LicenseStore

    identifier = entry.data.get(LICENSE_INSTANCE)
    if not identifier:
        return panel_data.license_summary(has_key=False, claim=None)
    store = LicenseStore(hass, identifier)
    try:
        data = await store.load()
    except (OSError, ValueError):
        return panel_data.license_summary(has_key=False, claim=None)
    key = data.get("key") or ""
    token = data.get("lease") or ""
    if not key:
        return panel_data.license_summary(has_key=False, claim=None)
    if not token:
        return {"checked": True, "activated": False, "status": "pending"}
    try:
        policy = await hass.async_add_executor_job(load_policy)
        claim = await hass.async_add_executor_job(verify_lease, policy, data["identity"], key, token)
    except (LicenseError, OSError, ValueError, KeyError):
        return {"checked": True, "activated": False, "status": "unverified"}
    return panel_data.license_summary(has_key=True, claim=claim)


@websocket_api.websocket_command({vol.Required("type"): WS_CAMERAS})
@websocket_api.async_response
async def ws_cameras(hass, connection, msg) -> None:
    try:
        connection.send_result(msg["id"], {"cameras": await async_cameras(hass)})
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Panel cameras failed: %s", err)
        connection.send_error(msg["id"], "tapo_panel_error", "Không đọc được danh sách camera")


@websocket_api.websocket_command({vol.Required("type"): WS_OVERVIEW, vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_overview(hass, connection, msg) -> None:
    try:
        payload = await async_overview(hass, msg["entry_id"])
    except LookupError:
        connection.send_error(msg["id"], "not_found", "Không tìm thấy camera")
        return
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Panel overview failed: %s", err)
        connection.send_error(msg["id"], "tapo_panel_error", "Không đọc được cài đặt")
        return
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command({vol.Required("type"): WS_FACES, vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_faces(hass, connection, msg) -> None:
    try:
        payload = await async_faces(hass, msg["entry_id"])
    except LookupError:
        connection.send_error(msg["id"], "not_found", "Không tìm thấy camera")
        return
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Panel faces failed: %s", err)
        connection.send_error(msg["id"], "tapo_panel_error", "Không đọc được Face ID")
        return
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command({
    vol.Required("type"): WS_HISTORY,
    vol.Required("entry_id"): str,
    vol.Optional("tag"): vol.Any(str, None),
    vol.Optional("limit"): int,
})
@websocket_api.async_response
async def ws_history(hass, connection, msg) -> None:
    try:
        payload = await async_history(hass, msg["entry_id"], tag=msg.get("tag"), limit=msg.get("limit") or panel_data.HISTORY_LIMIT_DEFAULT)
    except LookupError:
        connection.send_error(msg["id"], "not_found", "Không tìm thấy camera")
        return
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Panel history failed: %s", err)
        connection.send_error(msg["id"], "tapo_panel_error", "Không đọc được lịch sử")
        return
    connection.send_result(msg["id"], payload)


COMMANDS = (ws_cameras, ws_overview, ws_faces, ws_history)


async def async_register_commands(hass: HomeAssistant) -> None:
    registered = _registered(hass)
    if registered.get("commands"):
        return
    for command in COMMANDS:
        websocket_api.async_register_command(hass, command)
    registered["commands"] = True
