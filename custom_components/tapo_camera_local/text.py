"""One validated JSON schedule per day; advanced controls are disabled initially."""

from homeassistant.components.text import TextEntity, TextMode

from .control_entity import TapoSettingEntity, async_setup_settings


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_settings(hass, entry, async_add_entities, "text", TapoScheduleText)


class TapoScheduleText(TapoSettingEntity, TextEntity):
    _attr_mode = TextMode.TEXT
    _attr_native_min = 2
    _attr_native_max = 255
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        return self.setting_value

    async def async_set_value(self, value):
        await super().async_set_value(value)
