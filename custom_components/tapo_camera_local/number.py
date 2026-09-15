"""Bounded volume and detection sensitivity controls."""

from homeassistant.components.number import NumberEntity, NumberMode

from .control_entity import TapoSettingEntity, async_setup_settings


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_settings(hass, entry, async_add_entities, "number", TapoSettingNumber)


class TapoSettingNumber(TapoSettingEntity, NumberEntity):
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, setting):
        super().__init__(coordinator, setting)
        self._attr_native_min_value = setting.minimum
        self._attr_native_max_value = setting.maximum
        if setting.key in {"speaker_volume", "microphone_volume"}:
            self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self):
        return self.setting_value

    async def async_set_native_value(self, value):
        await self.async_set_value(value)
