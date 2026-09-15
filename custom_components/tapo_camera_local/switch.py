"""Camera settings exposed as writable switches, not motion sensors."""

from homeassistant.components.switch import SwitchEntity

from .control_entity import TapoSettingEntity, async_setup_settings


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_settings(hass, entry, async_add_entities, "switch", TapoSettingSwitch)


class TapoSettingSwitch(TapoSettingEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.setting_value

    async def async_turn_on(self, **kwargs):
        await self.async_set_value(True)

    async def async_turn_off(self, **kwargs):
        await self.async_set_value(False)
