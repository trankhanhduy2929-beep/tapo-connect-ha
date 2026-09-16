"""Detection configuration is not live motion/person presence."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import (
    CONF_CONNECTION_MODE,
    CONF_TAPO_CONTROL_ENTRY,
    MODE_CLOUD_NOTIFICATIONS,
)
from .entity import TapoEntity, coordinator_for


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
        from .notification_binary_sensor import async_setup_notification_binary_sensors

        await async_setup_notification_binary_sensors(hass, entry, async_add_entities)
        return
    coordinator = coordinator_for(hass, entry)
    if not coordinator.observations:
        from .observations import observations

        coordinator.observations = observations(coordinator.basic)
    added = set()
    async_add_entities([TapoLensCoverBinarySensor(coordinator)])
    added.add("lens_cover")

    def discover() -> None:
        entities = []
        for key, item in coordinator.observations.items():
            if item["kind"] in {"binary_sensor", "setting"} and key not in added and (entry.data.get(CONF_TAPO_CONTROL_ENTRY) or key not in coordinator.settings):
                entities.append(TapoSettingBinarySensor(coordinator, key, item["name"]))
                added.add(key)
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class TapoLensCoverBinarySensor(TapoEntity, BinarySensorEntity):
    _attr_translation_key = "lens_cover"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "lens_cover")
        self._attr_unique_id = f"{coordinator.device_id}_lens_cover"

    @property
    def is_on(self):
        return self.coordinator.observations.get("lens_cover", {}).get("value")

    @property
    def available(self) -> bool:
        return super().available and "lens_cover" in self.coordinator.observations


class TapoSettingBinarySensor(TapoEntity, BinarySensorEntity):
    def __init__(self, coordinator, key, name) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key

    @property
    def is_on(self):
        return self.coordinator.observations.get(self._key, {}).get("value")

    @property
    def available(self) -> bool:
        return super().available and self._key in self.coordinator.observations
