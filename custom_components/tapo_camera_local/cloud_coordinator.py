"""Independent, slower cloud settings sync with readback-confirmed commands."""

import asyncio
import logging
from datetime import timedelta
from functools import partial

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud_camera import CloudCamera
from .notification_client import NotificationError
from .tapo_proto.client import TapoConnectionError
from .tapo_proto.controls import SETTINGS
from .tapo_proto.models import DeviceInfo

_LOGGER = logging.getLogger(__name__)
SETTINGS_INTERVAL = 30


class CloudSettingsCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, entry, notifications):
        super().__init__(hass, _LOGGER, name="Tapo cloud camera settings", update_interval=timedelta(seconds=SETTINGS_INTERVAL), config_entry=entry)
        self.notifications = notifications
        self.camera = None
        self.basic = {}
        self.device_info = None
        self.settings = {}
        self._command_lock = asyncio.Lock()
        self._closing = False

    @property
    def device_id(self):
        return self.notifications.device_id

    @property
    def device_name(self):
        return "Tapo C260"

    async def _async_camera(self):
        client = self.notifications.client
        if self._closing or client is None or getattr(client, "auth_failed", False):
            raise NotificationError("Cloud session is not ready; check notification login")
        profile = getattr(client, "profile", None)
        if not isinstance(profile, dict):
            raise NotificationError("Cloud camera profile is unavailable")
        profile = dict(profile)
        if self.camera is None:
            self.camera = await self.hass.async_add_executor_job(CloudCamera, profile)
        else:
            await self.hass.async_add_executor_job(self.camera.update_profile, profile)
        return self.camera

    def _accept(self, snapshot):
        basic = snapshot.get("device_info", {}).get("basic_info")
        if not isinstance(basic, dict) or not basic.get("device_model"):
            raise TapoConnectionError("Cloud camera information missing")
        identifier = basic.get("dev_id", basic.get("device_id"))
        if not isinstance(identifier, str) or identifier.casefold() != self.device_id.casefold():
            raise TapoConnectionError("Cloud camera identity mismatch")
        self.device_info = DeviceInfo.from_basic_info(basic)
        self.basic = snapshot
        self.settings = {setting.key: setting for setting in SETTINGS if setting.value(snapshot) is not None}
        return snapshot

    async def _async_update_data(self):
        async with self._command_lock:
            try:
                camera = await self._async_camera()
                snapshot = await self.hass.async_add_executor_job(camera.device_snapshot)
                result = self._accept(snapshot)
            except (NotificationError, TapoConnectionError, ValueError, TypeError):
                self.update_interval = timedelta(seconds=min(300, self.update_interval.total_seconds() * 2))
                raise UpdateFailed("Không đọc được setting qua cloud; thông báo vẫn chạy độc lập. Kiểm tra camera đang online và quyền tài khoản.") from None
            self.update_interval = timedelta(seconds=SETTINGS_INTERVAL)
            return result

    async def async_set_setting(self, key, value):
        async with self._command_lock:
            attempted = False
            try:
                camera = await self._async_camera()
                if not self.last_update_success or key not in self.settings:
                    raise TapoConnectionError("Setting unavailable; refresh camera first")
                attempted = True
                await self.hass.async_add_executor_job(camera.set_setting, key, value)
            except (NotificationError, TapoConnectionError, ValueError, TypeError):
                if attempted and self.camera is not None and self.basic:
                    self.async_set_updated_data(self._accept(self.camera.snapshot()))
                raise HomeAssistantError("Chưa xác nhận được setting. Lệnh không tự gửi lại; hãy làm mới và kiểm tra trạng thái thật của camera.") from None
            self.async_set_updated_data(self._accept(camera.snapshot()))

    async def async_command(self, action, *arguments, refresh=True):
        async with self._command_lock:
            try:
                await self._async_camera()
                if not self.last_update_success:
                    raise TapoConnectionError("Camera settings unavailable")
                await self.hass.async_add_executor_job(partial(action, *arguments))
            except (NotificationError, TapoConnectionError, ValueError, TypeError):
                raise HomeAssistantError("Lệnh cloud chưa được xác nhận; không tự gửi lại.") from None
        if refresh:
            await self.async_request_refresh()

    async def async_close(self):
        self._closing = True
        async with self._command_lock:
            if self.camera is not None:
                await self.hass.async_add_executor_job(self.camera.close)
