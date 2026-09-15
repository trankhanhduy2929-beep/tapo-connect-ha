"""Shared entity helpers for the Tapo Connect integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TapoDataCoordinator


def coordinator_for(hass: HomeAssistant, entry: ConfigEntry) -> TapoDataCoordinator:
    return hass.data[DOMAIN][entry.entry_id]["coordinator"]


def stream_url_for(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    return hass.data[DOMAIN][entry.entry_id].get("stream_url")


async def async_setup_entry_helper(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    builder,
) -> None:
    coordinator = coordinator_for(hass, entry)
    async_add_entities(builder(hass, entry, coordinator))


class TapoEntity(CoordinatorEntity[TapoDataCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TapoDataCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        info = coordinator.device_info
        model = getattr(info, "model", "") or "Tapo camera"
        hw = getattr(info, "hardware", "") or None
        identifiers = {(DOMAIN, coordinator.device_id)}
        self._attr_device_info = DeviceInfo(
            identifiers=identifiers,
            name=coordinator.device_name or entry_name(coordinator),
            manufacturer=MANUFACTURER,
            model=model,
            hw_version=hw,
            sw_version=getattr(info, "firmware", "") or None,
        )

    @property
    def camera_data(self) -> dict:
        return self.coordinator.basic or {}

    def module_section(self, module: str, section: str) -> dict:
        data = (self.camera_data.get(module) or {}).get(section)
        return data if isinstance(data, dict) else {}


def entry_name(coordinator: TapoDataCoordinator) -> str:
    entry = coordinator.config_entry
    return entry.data.get(CONF_NAME) or f"Tapo {entry.data.get(CONF_HOST, '')}"
