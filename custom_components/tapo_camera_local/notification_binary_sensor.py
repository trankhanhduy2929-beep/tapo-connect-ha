"""Short pulses for newly received notifications, not sustained presence."""

import time

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .notification_data import CORE_CATEGORIES, RECENT_SECONDS


async def async_setup_notification_binary_sensors(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["notification_coordinator"]
    async_add_entities([NotificationBinarySensor(coordinator, category) for category in CORE_CATEGORIES])


class NotificationBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, category):
        super().__init__(coordinator)
        self.category = category
        self._until = 0
        self._cancel = None
        self._attr_translation_key = f"cloud_recent_{category}"
        self._attr_unique_id = f"{coordinator.device_id}_cloud_recent_{category}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.device_id)}, manufacturer="TP-Link", model="C260", name="Tapo C260")

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}_notification", self._receive))

    @callback
    def _receive(self, event):
        if event.data.get("camera_id") != self.coordinator.device_id or event.data.get("tag") != self.category:
            return
        self._until = time.monotonic() + RECENT_SECONDS
        if self._cancel:
            self._cancel()
        self._cancel = async_call_later(self.hass, RECENT_SECONDS, self._expire)
        self.async_write_ha_state()

    @callback
    def _expire(self, _now):
        self._until = 0
        self._cancel = None
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        if self._cancel:
            self._cancel()
            self._cancel = None
        await super().async_will_remove_from_hass()

    @property
    def is_on(self):
        return time.monotonic() < self._until

    @property
    def extra_state_attributes(self):
        event = self.coordinator.history.categories.get(self.category) or {}
        return {"source": "tapo_cloud_notification", "pulse_seconds": RECENT_SECONDS, "notified_at": event.get("notified_at"), "presence_sensor": False}
