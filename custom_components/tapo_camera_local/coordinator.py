"""Data coordinator for the Tapo Connect integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TapoAuthError,
    TapoCamera,
    TapoConnectionError,
)
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .face import FaceHistory
from .observations import observations
from .tapo_proto.controls import SETTINGS
from .tapo_proto.models import DeviceInfo

_LOGGER = logging.getLogger(__name__)


class TapoDataCoordinator(DataUpdateCoordinator[dict]):
    """Poll a compact state snapshot from the camera."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, camera: TapoCamera
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data.get(CONF_HOST, 'camera')}",
            update_interval=timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            config_entry=entry,
        )
        self.camera = camera
        self.config_entry = entry
        self.device_info = None
        self.basic: dict = {}
        self.face_history = FaceHistory()
        self.observations = {}
        self.settings = {}
        self._command_lock = asyncio.Lock()

    async def _async_setup(self) -> None:
        """The first snapshot already authenticates and reads device information."""

    async def _async_update_data(self) -> dict:
        async with self._command_lock:
            return await self._async_snapshot()

    async def _async_snapshot(self) -> dict:
        try:
            snapshot = await self.hass.async_add_executor_job(
                self.camera.device_snapshot
            )
        except TapoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TapoConnectionError as err:
            raise UpdateFailed(str(err)) from err
        info = DeviceInfo.from_basic_info(snapshot["device_info"]["basic_info"])
        expected_id = getattr(self.config_entry, "unique_id", None)
        if expected_id and expected_id != self.camera.host and info.device_id != expected_id:
            raise UpdateFailed("Camera identity changed; check the configured IP address")
        self.basic = snapshot
        self.device_info = info
        self.observations = observations(snapshot)
        self.settings = {setting.key: setting for setting in SETTINGS if setting.value(snapshot) is not None}
        events = self.face_history.update(snapshot.get("face_data") or {})
        for event in events:
            self.hass.bus.async_fire(f"{DOMAIN}_face_recognized", {"camera_id": self.device_id, **event})
        return snapshot

    async def async_command(self, action, *arguments, refresh: bool = True) -> None:
        async with self._command_lock:
            error = None
            try:
                await self.hass.async_add_executor_job(partial(action, *arguments))
            except (TapoConnectionError, ValueError) as caught:
                error = caught
            if refresh:
                try:
                    snapshot = await self._async_snapshot()
                except (UpdateFailed, ConfigEntryAuthFailed) as caught:
                    self.async_set_update_error(caught)
                    if error is None:
                        error = TapoConnectionError("Command sent but state refresh failed")
                else:
                    self.async_set_updated_data(snapshot)
            if error is not None:
                raise HomeAssistantError(str(error)) from error

    async def async_set_setting(self, key: str, value) -> None:
        await self.async_command(self.camera.set_setting, key, value)

    @property
    def device_name(self) -> str:
        if self.device_info is not None and self.device_info.name:
            return self.device_info.name
        return f"Tapo {self.camera.host}"

    @property
    def device_id(self) -> str:
        if self.device_info is not None and self.device_info.device_id:
            return self.device_info.device_id
        return self.camera.host

    def default_stream_url(self) -> None:
        """RTSP credentials must be configured separately from API credentials."""
        return
