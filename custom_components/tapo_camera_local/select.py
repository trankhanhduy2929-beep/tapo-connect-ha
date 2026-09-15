"""Enumerated settings and PTZ preset commands."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .control_entity import TapoSettingEntity, async_setup_settings
from .entity import TapoEntity, coordinator_for


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_settings(hass, entry, async_add_entities, "select", TapoSettingSelect)
    coordinator = coordinator_for(hass, entry)
    added = False

    def discover():
        nonlocal added
        if not added and preset_options(coordinator.basic):
            added = True
            async_add_entities([TapoPresetSelect(coordinator)])

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class TapoSettingSelect(TapoSettingEntity, SelectEntity):
    def __init__(self, coordinator, setting):
        super().__init__(coordinator, setting)
        self._attr_options = list(setting.choices)

    @property
    def current_option(self):
        return self.setting_value

    async def async_select_option(self, option):
        await self.async_set_value(option)


def preset_options(snapshot):
    preset = snapshot.get("preset", {}).get("preset", {})
    if not isinstance(preset, dict):
        return {}
    names, identifiers = preset.get("name"), preset.get("id")
    if not isinstance(names, list) or not isinstance(identifiers, list):
        return {}
    return {f"{str(name)[:200]} [{identifier}]": str(identifier) for name, identifier in zip(names, identifiers) if str(identifier).isdigit()}


class TapoPresetSelect(TapoEntity, SelectEntity):
    _attr_translation_key = "preset"

    def __init__(self, coordinator):
        super().__init__(coordinator, "preset")

    @property
    def options(self):
        return list(preset_options(self.coordinator.basic))

    @property
    def current_option(self):
        return None

    @property
    def available(self):
        return super().available and bool(self.options)

    async def async_select_option(self, option):
        identifier = preset_options(self.coordinator.basic).get(option)
        if identifier is None:
            raise HomeAssistantError("Unknown preset")
        await self.coordinator.async_command(self.coordinator.camera.move_to_preset, int(identifier))
