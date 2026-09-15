"""Explicit PTZ/reboot actions plus the cloud notification refresh button."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CONNECTION_MODE, DOMAIN, MODE_CLOUD_NOTIFICATIONS
from .entity import TapoEntity, coordinator_for
from .tapo_proto.controls import ACTIONS


def action_keys(snapshot):
    keys = {"refresh", "reboot"}
    if isinstance(snapshot.get("preset", {}).get("preset"), dict):
        keys.update(key for key in ACTIONS if not key.startswith("manual_alarm"))
    if isinstance(snapshot.get("msg_alarm", {}).get("chn1_msg_alarm_info"), dict):
        keys.update({"manual_alarm_start", "manual_alarm_stop"})
    return keys


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
        async_add_entities([NotificationRefreshButton(hass.data[DOMAIN][entry.entry_id]["notification_coordinator"])])
    coordinator = coordinator_for(hass, entry)
    added = set()

    def discover():
        keys = action_keys(coordinator.basic)
        if entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
            from .cloud_camera import CLOUD_ACTIONS

            keys &= CLOUD_ACTIONS | {"refresh"}
        entities = [TapoActionButton(coordinator, key) for key in sorted(keys - added)]
        added.update(keys)
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class NotificationRefreshButton(CoordinatorEntity, ButtonEntity):
    """Instant cloud read; polling already covers automatic checks."""

    _attr_has_entity_name = True
    _attr_translation_key = "cloud_refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_cloud_refresh"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.device_id)}, manufacturer="TP-Link", model="C260", name="Tapo C260")

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_now()


class TapoActionButton(TapoEntity, ButtonEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        if key in {"reboot", "ptz_calibrate", "manual_alarm_start"}:
            self._attr_entity_registry_enabled_default = False
            self._attr_entity_category = EntityCategory.CONFIG
        elif key == "refresh":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        return super().available and self._key in action_keys(self.coordinator.basic)

    async def async_press(self):
        if self._key == "refresh":
            if self.coordinator.config_entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
                await self.coordinator.async_refresh()
            else:
                await self.coordinator.async_command(self.coordinator.camera.invalidate)
        else:
            await self.coordinator.async_command(self.coordinator.camera.run_action, self._key, refresh=self._key != "reboot")
