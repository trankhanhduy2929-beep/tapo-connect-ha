"""Independent cloud notification polling; never blocks local camera controls."""

import logging
import time
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud_account import open_managed_client
from .const import (
    CLOUD_IDLE_AFTER,
    CLOUD_IDLE_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DOMAIN,
    MAX_CLOUD_SCAN_INTERVAL,
    MIN_CLOUD_SCAN_INTERVAL,
)
from .notification_client import NotificationAuthError, NotificationError, open_client
from .notification_data import NotificationHistory

_LOGGER = logging.getLogger(__name__)
CURSOR_PERSIST_SECONDS = 300


class NotificationCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, entry):
        configured = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_CLOUD_SCAN_INTERVAL)
        try:
            fast = int(configured)
        except (TypeError, ValueError):
            fast = DEFAULT_CLOUD_SCAN_INTERVAL
        self.fast_interval = min(MAX_CLOUD_SCAN_INTERVAL, max(MIN_CLOUD_SCAN_INTERVAL, fast))
        super().__init__(hass, _LOGGER, name="Tapo camera notifications", update_interval=timedelta(seconds=self.fast_interval), config_entry=entry)
        self.config_entry = entry
        self.client = None
        self.history = NotificationHistory()
        self.device_id = entry.data["camera_id"]
        self.session_store = None
        if entry.data.get("cloud_credentials_id"):
            from .cloud_storage import CloudSessionStore

            self.session_store = CloudSessionStore(hass, entry.data["cloud_credentials_id"])
        self._last_activity = time.monotonic()
        self._cursor_saved = None
        self._cursor_saved_at = None
        self.history_store = Store(hass, 1, f"{DOMAIN}.notifications.{entry.entry_id}", private=True)
        self._history_loaded = False
        self._history_saved_at = None
        self._history_restored = False

    def _apply_interval(self):
        idle = time.monotonic() - self._last_activity >= CLOUD_IDLE_AFTER
        wanted = max(self.fast_interval, CLOUD_IDLE_INTERVAL) if idle else self.fast_interval
        if self.update_interval is None or self.update_interval.total_seconds() != wanted:
            self.update_interval = timedelta(seconds=wanted)

    async def async_refresh_now(self):
        """Force a cloud read; used by the refresh button for an instant check."""
        await self.async_refresh()

    async def _async_update_data(self):
        if not self._history_loaded:
            try:
                saved = await self.history_store.async_load()
                self._history_restored = self.history.restore(saved, self.device_id, time.time())
            except (HomeAssistantError, OSError, ValueError):
                _LOGGER.debug("Notification history could not be restored")
            self._history_loaded = True
        try:
            if self.client is None:
                if self.session_store is not None:
                    session = await self.session_store.async_load()
                    if not self._history_restored:
                        session.pop("notification_cursor", None)
                    self.client = await self.hass.async_add_executor_job(open_managed_client, session, self.device_id)
                else:
                    self.client = await self.hass.async_add_executor_job(open_client, self.hass.config.config_dir, self.config_entry.data["cloud_session_file"])
            if self.client.camera_id != self.device_id:
                raise NotificationError("Cloud profile belongs to a different camera")
            try:
                result = await self.hass.async_add_executor_job(self.client.fetch)
            except NotificationAuthError:
                if self.session_store is None:
                    raise
                try:
                    await self.session_store.async_begin_renewal(self.client.session_data)
                except (HomeAssistantError, OSError):
                    raise ConfigEntryAuthFailed("Unable to protect the cloud session during renewal") from None
                try:
                    await self.hass.async_add_executor_job(self.client.renew)
                except (HomeAssistantError, OSError):
                    await self.async_close()
                    raise ConfigEntryAuthFailed("Cloud session renewal ended ambiguously") from None
                except NotificationError:
                    raise NotificationAuthError("Sign in again through Home Assistant") from None
                try:
                    await self.session_store.async_save(self.client.session_data)
                except (HomeAssistantError, OSError):
                    await self.async_close()
                    raise ConfigEntryAuthFailed("Renewed cloud session could not be persisted") from None
                result = await self.hass.async_add_executor_job(self.client.fetch)
        except NotificationAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except NotificationError as error:
            raise UpdateFailed(str(error)) from error
        now = time.time()
        events = self.history.update(result["notifications"], self.device_id, now, truncated=result["truncated"])
        if result.get("initial_sync"):
            events = []
        for event in events:
            payload = {"camera_id": self.device_id, **event, "notified_at": event["notified_at"].isoformat()}
            self.hass.bus.async_fire(f"{DOMAIN}_notification", payload)
            if event["tag"] in {"familiar", "stranger"}:
                self.hass.bus.async_fire(f"{DOMAIN}_face_notification", payload)
        if events or result["truncated"]:
            self._last_activity = time.monotonic()
        self._apply_interval()
        await self._async_persist_cursor()
        return {"count": self.history.count, "truncated": self.history.truncated, "interval_seconds": self.update_interval.total_seconds()}

    async def _async_persist_cursor(self):
        cursor = getattr(self.client, "cursor_ms", None)
        if cursor is None:
            return
        now = time.monotonic()
        if self._history_saved_at is None or now - self._history_saved_at >= CURSOR_PERSIST_SECONDS:
            try:
                await self.history_store.async_save(self.history.dump(self.device_id))
            except (HomeAssistantError, OSError):
                _LOGGER.debug("Notification history checkpoint failed; keeping the old cursor")
                return
            self._history_saved_at = now
        if self.session_store is None:
            return
        if self._cursor_saved == cursor:
            return
        if self._cursor_saved_at is not None and now - self._cursor_saved_at < CURSOR_PERSIST_SECONDS:
            return
        try:
            await self.session_store.async_save_cursor(self.client.session_data, cursor)
        except (HomeAssistantError, OSError):
            _LOGGER.debug("Cloud notification cursor was not persisted")
            return
        self._cursor_saved = cursor
        self._cursor_saved_at = now

    async def async_close(self):
        client = self.client
        if client is None:
            return
        self._cursor_saved_at = None
        self._history_saved_at = None
        await self._async_persist_cursor()
        await self.hass.async_add_executor_job(client.close)
