"""Known-face profile images exposed through Home Assistant's image platform."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import monotonic

from homeassistant.components.image import ImageEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MANUFACTURER
from .entity import coordinator_for, entry_name

_LOGGER = logging.getLogger(__name__)
IMAGE_CACHE_SECONDS = 300
IMAGE_RETRY_SECONDS = 30

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = coordinator_for(hass, entry)
    entities: dict[str, TapoFaceImage] = {}

    def discover() -> None:
        new_entities = []
        for identifier in coordinator.face_history.state["catalog"]:
            if identifier not in entities:
                entity = TapoFaceImage(hass, coordinator, identifier)
                entities[identifier] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))

class TapoFaceImage(ImageEntity):
    """One image entity per face in the camera's local face catalog."""

    _attr_has_entity_name = True
    _attr_translation_key = "face_image"

    def __init__(self, hass, coordinator, identifier: str) -> None:
        super().__init__(hass)
        self.coordinator = coordinator
        self.identifier = identifier
        self._image_bytes: bytes | None = None
        self._image_expires = 0.0
        self._next_retry = 0.0
        self._content_type = "image/jpeg"
        self._last_updated: datetime | None = None
        self._attr_unique_id = f"{coordinator.device_id}_face_{identifier}_image"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator.device_name or entry_name(coordinator),
            manufacturer=MANUFACTURER,
            model=getattr(coordinator.device_info, "model", "") or "Tapo camera",
            sw_version=getattr(coordinator.device_info, "firmware", "") or None,
        )
        self._update_name()
        self.async_on_remove(coordinator.async_add_listener(self._coordinator_updated))

    def _person(self) -> dict:
        person = self.coordinator.face_history.state["catalog"].get(self.identifier)
        return person if isinstance(person, dict) else {}

    def _update_name(self) -> None:
        self._attr_translation_placeholders = {"face_id": self.identifier}

    @property
    def extra_state_attributes(self):
        return {"face_id": self.identifier, "name": self._person().get("name"), "experimental": True}

    def _coordinator_updated(self) -> None:
        self._update_name()
        if self.identifier not in self.coordinator.face_history.state["catalog"]:
            self._image_bytes = None
            self._image_expires = 0.0
        if self.entity_id:
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        state = self.coordinator.face_history.state
        return bool(
            self.coordinator.last_update_success
            and state["catalog_available"]
            and self.identifier in state["catalog"]
        )

    @property
    def content_type(self) -> str:
        return self._content_type

    @property
    def image_last_updated(self) -> datetime | None:
        return self._last_updated

    def _load_image(self) -> bytes | None:
        return self.coordinator.camera.face_image(self.identifier)

    async def async_image(self) -> bytes | None:
        if not self.available:
            return None
        now = monotonic()
        if self._image_bytes is not None and now < self._image_expires:
            return self._image_bytes
        if now < self._next_retry or not self.available:
            return self._image_bytes
        try:
            image = await self.hass.async_add_executor_job(self._load_image)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Unable to load face image; response and identifier suppressed")
            self._next_retry = now + IMAGE_RETRY_SECONDS
            return self._image_bytes
        if image is None:
            self._next_retry = now + IMAGE_RETRY_SECONDS
            return None
        self._image_bytes = image
        self._image_expires = now + IMAGE_CACHE_SECONDS
        self._next_retry = 0.0
        self._content_type = self._detect_content_type(image)
        self._last_updated = datetime.now(UTC)
        if self.entity_id:
            self.async_write_ha_state()
        return image

    @staticmethod
    def _detect_content_type(image: bytes) -> str:
        if image.startswith(b"\x89PNG"):
            return "image/png"
        if image.startswith(b"GIF8"):
            return "image/gif"
        if image.startswith(b"RIFF"):
            return "image/webp"
        return "image/jpeg"
