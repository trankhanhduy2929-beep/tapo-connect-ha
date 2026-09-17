"""Capability-driven metadata and face-event sensors."""

from __future__ import annotations

from typing import ClassVar

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from .const import (
    CONF_CONNECTION_MODE,
    CONF_TAPO_CONTROL_ENTRY,
    MODE_CLOUD_NOTIFICATIONS,
)
from .entity import TapoEntity, coordinator_for

FACE_FIELDS = {
    "face_count": "Face catalog count",
    "last_face_id": "Last face ID",
    "last_face_name": "Last recognized face",
    "last_face_tag": "Last face tag",
    "last_recognized_at": "Last recognized at",
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
        from .notification_sensor import async_setup_notification_sensors

        await async_setup_notification_sensors(hass, entry, async_add_entities)
        return
    coordinator = coordinator_for(hass, entry)
    if not coordinator.observations:
        from .observations import observations

        coordinator.observations = observations(coordinator.basic)
    async_add_entities([
        TapoInfoSensor(coordinator, "device_model", "model"),
        TapoInfoSensor(coordinator, "firmware", "firmware"),
        TapoInfoSensor(coordinator, "hardware", "hardware"),
        TapoInfoSensor(coordinator, "mac", "mac"),
        TapoInfoSensor(coordinator, "ip", "ip_address"),
        TapoInfoSensor(coordinator, "connection_type", "connection_type"),
        TapoInfoSensor(coordinator, "sd_status", "sd_card"),
        TapoSignalSensor(coordinator),
    ])
    added: set[str] = {"model", "firmware", "hardware", "mac", "ip_address", "connection_type", "sd_card", "wifi_signal"}
    async_add_entities([TapoFaceStatusSensor(coordinator)])

    def discover() -> None:
        entities = []
        for key, item in coordinator.observations.items():
            writable = not entry.data.get(CONF_TAPO_CONTROL_ENTRY) and key in coordinator.settings
            if item["kind"] == "sensor" and key not in added and not writable:
                entities.append(TapoValueSensor(coordinator, key, item))
                added.add(key)
        state = coordinator.face_history.state
        for key, title in FACE_FIELDS.items():
            supported = state["catalog_available"] if key == "face_count" else state["tracking_available"]
            if supported and key not in added:
                entities.append(TapoFaceSensor(coordinator, key, title))
                added.add(key)
        for identifier in state["catalog"]:
            name_key = f"face_{identifier}_name"
            if name_key not in added:
                entities.append(TapoFaceNameSensor(coordinator, identifier))
                added.add(name_key)
            key = f"face_{identifier}_last_seen"
            if key not in added:
                entities.append(TapoPersonSensor(coordinator, identifier))
                added.add(key)
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class TapoValueSensor(TapoEntity, SensorEntity):
    def __init__(self, coordinator, key: str, item: dict) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = item.get("translation_key", self._key)
        self._attr_translation_placeholders = item.get("placeholders", {})
        self._attr_device_class = item["device_class"]
        self._attr_native_unit_of_measurement = item["unit"]

    @property
    def native_value(self):
        return self.coordinator.observations.get(self._key, {}).get("value")

    @property
    def available(self) -> bool:
        return super().available and self._key in self.coordinator.observations


class TapoInfoSensor(TapoEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    def __init__(self, coordinator, key: str, translation_key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.device_id}_{translation_key}"

    @property
    def native_value(self):
        info = self.coordinator.device_info
        if self._key == "device_model":
            return getattr(info, "model", None)
        if self._key == "firmware":
            return getattr(info, "firmware", None)
        if self._key == "hardware":
            return getattr(info, "hardware", None)
        if self._key == "mac":
            return getattr(info, "mac", None)
        basic = self.module_section("device_info", "basic_info")
        if self._key == "ip":
            return basic.get("local_ip")
        if self._key == "connection_type":
            return basic.get("connection_type")
        if self._key == "sd_status":
            sd = self.module_section("sd_security", "status") or self.module_section("harddisk_manage", "hd_info")
            if sd:
                return sd.get("status") or sd.get("err_code")
            from .observations import storage_records

            cards = list(storage_records(self.camera_data.get("harddisk_manage", {}).get("hd_info")))
            return cards[0][1].get("status") if cards else None
        return None


class TapoSignalSensor(TapoEntity, SensorEntity):
    _attr_translation_key = "wifi_signal"
    _attr_native_unit_of_measurement = "dBm"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "signal")
        self._attr_unique_id = f"{coordinator.device_id}_wifi_signal"

    @property
    def native_value(self):
        basic = self.module_section("device_info", "basic_info")
        value = basic.get("rssi")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None


def _face_image_proxy(hass, device_id: str, face_id) -> str | None:
    """Return the image-proxy URL for a catalog face, or None if the entity is absent."""
    if face_id is None:
        return None
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "image", "tapo_camera_local", f"{device_id}_face_{face_id}_image"
    )
    if entity_id is None:
        return None
    return f"/api/image_proxy/{entity_id}"


class TapoFaceSensor(TapoEntity, SensorEntity):
    def __init__(self, coordinator, key: str, title: str) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        if key == "last_recognized_at":
            self._attr_device_class = "timestamp"

    @property
    def native_value(self):
        if self._key == "face_count":
            return self.coordinator.face_history.state["face_count"]
        return self.coordinator.face_history.latest().get(self._key)

    @property
    def entity_picture(self) -> str | None:
        if self._key != "last_face_name":
            return None
        return _face_image_proxy(
            self.hass, self.coordinator.device_id,
            self.coordinator.face_history.latest().get("last_face_id"),
        )

    @property
    def available(self) -> bool:
        state = self.coordinator.face_history.state
        source_available = state["catalog_available"] if self._key == "face_count" else state["tracking_available"]
        return super().available and source_available

    @property
    def extra_state_attributes(self):
        state = self.coordinator.face_history.state
        if self._key == "face_count":
            return {
                "faces": list(state["catalog"].values()),
                "catalog_complete": state["catalog_complete"],
                "reported_total": state["reported_total"],
                "fresh_time_is_recognition_time": False,
            }
        return {"source": "face_tracking", "history_truncated": state["history_truncated"]}


class TapoFaceNameSensor(TapoEntity, SensorEntity):
    _attr_translation_key = "face_name"

    def __init__(self, coordinator, identifier: str) -> None:
        super().__init__(coordinator, f"face_{identifier}_name")
        self._identifier = identifier
        self._attr_translation_placeholders = {"face_id": identifier}

    @property
    def native_value(self):
        person = self.coordinator.face_history.state["catalog"].get(self._identifier, {})
        return person.get("name")

    @property
    def available(self) -> bool:
        state = self.coordinator.face_history.state
        return super().available and state["catalog_available"] and self._identifier in state["catalog"]

    @property
    def entity_picture(self) -> str | None:
        return _face_image_proxy(self.hass, self.coordinator.device_id, self._identifier)

    @property
    def extra_state_attributes(self):
        person = self.coordinator.face_history.state["catalog"].get(self._identifier, {})
        return {"face_id": self._identifier, "tag": person.get("tag"), "source": "face_catalog"}


class TapoPersonSensor(TapoFaceSensor):
    def __init__(self, coordinator, identifier: str) -> None:
        super().__init__(coordinator, f"face_{identifier}_last_seen", f"Face {identifier} last seen")
        self._identifier = identifier
        self._attr_translation_key = "face_last_seen"
        self._attr_translation_placeholders = {"face_id": identifier}
        self._attr_device_class = "timestamp"

    @property
    def native_value(self):
        return self.coordinator.face_history.last_seen.get(self._identifier)

    @property
    def available(self) -> bool:
        state = self.coordinator.face_history.state
        return super().available and self._identifier in state["catalog"]

    @property
    def entity_picture(self) -> str | None:
        return _face_image_proxy(self.hass, self.coordinator.device_id, self._identifier)

    @property
    def extra_state_attributes(self):
        person = self.coordinator.face_history.state["catalog"].get(self._identifier, {})
        return {**person, "source": "face_tracking", "fresh_time_is_recognition_time": False}


class TapoFaceStatusSensor(TapoEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = "enum"
    _attr_options: ClassVar[list[str]] = ["available", "events_without_names", "catalog_only", "unsupported", "rejected", "transient_error", "invalid_response", "not_tested"]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "face_api_status")
        self._attr_translation_key = "face_api_status"

    @property
    def native_value(self):
        state = self.coordinator.face_history.state
        if state["tracking_available"]:
            return "available" if state["catalog_available"] else "events_without_names"
        if state["catalog_available"]:
            return "catalog_only"
        status = self.coordinator.basic.get("api_status", {}).get("searchFacesInfo", {})
        return status.get("status", "not_tested") if status.get("status") != "ok" else "invalid_response"

    @property
    def extra_state_attributes(self):
        return {"queries": self.coordinator.basic.get("api_status", {}), "polling": True}
