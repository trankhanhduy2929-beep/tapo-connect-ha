"""Shared setting discovery and state mapping; never optimistic."""

from homeassistant.helpers.entity import EntityCategory

from .entity import TapoEntity, coordinator_for
from .tapo_proto.controls import SETTINGS


async def async_setup_settings(hass, entry, async_add_entities, kind, entity_class):
    coordinator = coordinator_for(hass, entry)
    added = set()

    def discover():
        entities = []
        for setting in SETTINGS:
            if setting.kind == kind and setting.key not in added and setting.value(coordinator.basic) is not None:
                entities.append(entity_class(coordinator, setting))
                added.add(setting.key)
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class TapoSettingEntity(TapoEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, setting):
        super().__init__(coordinator, setting.key)
        self.setting = setting
        self._attr_translation_key = {"led": "status_led", "privacy": "privacy_mode"}.get(setting.key, setting.key)

    @property
    def setting_value(self):
        return self.setting.value(self.coordinator.basic)

    @property
    def available(self):
        status = self.coordinator.basic.get("api_status", {}).get(self.setting.query, {}).get("status")
        return super().available and self.setting_value is not None and status in {None, "ok"}

    async def async_set_value(self, value):
        await self.coordinator.async_set_setting(self.setting.key, value)
