"""Camera entity backed by the camera's local RTSP stream."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TapoDataCoordinator
from .entity import TapoEntity, coordinator_for

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = coordinator_for(hass, entry)
    entities = []
    for key in ("stream", "sub_stream"):
        if hass.data[DOMAIN][entry.entry_id].get(f"{key}_url"):
            entities.append(TapoCameraEntity(hass, entry, coordinator, key))
    async_add_entities(entities)


class TapoCameraEntity(TapoEntity, Camera):
    """Streams the camera through Home Assistant's generic RTSP/HLS pipeline."""

    _attr_translation_key = "stream"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: TapoDataCoordinator,
        key: str = "stream",
    ) -> None:
        TapoEntity.__init__(self, coordinator, key)
        Camera.__init__(self)
        self._entry = entry
        self._hass = hass
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_id}_{key}"

    async def stream_source(self) -> str | None:
        if self.coordinator.observations.get("lens_cover", {}).get("value") is True:
            return None
        return self._hass.data[DOMAIN][self._entry.entry_id].get(f"{self._key}_url")

    async def async_stream_source(self) -> str | None:
        """Keep the pre-0.6 helper available for local callers."""
        return await self.stream_source()

    async def async_camera_image(self, width=None, height=None):
        if not self.available or not (source := await self.stream_source()):
            return None
        from homeassistant.components.ffmpeg import async_get_image

        try:
            return await async_get_image(self._hass, source, width=width, height=height)
        except (HomeAssistantError, KeyError, OSError, RuntimeError, TimeoutError, ValueError):
            _LOGGER.debug("Could not read a video frame; stream URL suppressed")
            return None
