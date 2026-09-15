"""Set up the Tapo Connect integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import (
    PytapoCamera,
    TapoAuthError,
    TapoConnectionError,
    TapoSecureTransportRequired,
)
from .const import (
    CONF_AUTH_MODE,
    CONF_CONNECTION_MODE,
    CONF_STREAM_URL,
    CONF_SUB_STREAM_URL,
    CONF_TAPO_CONTROL_ENTRY,
    DOMAIN,
    MODE_CLOUD_NOTIFICATIONS,
    MODE_STANDALONE,
)
from .coordinator import TapoDataCoordinator
from .tapo_proto.linked import TapoControlCamera

_LOGGER = logging.getLogger(__name__)

IMAGE_PLATFORM = getattr(Platform, "IMAGE", None)
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.TEXT,
    Platform.SENSOR,
    Platform.SWITCH,
]
if IMAGE_PLATFORM is not None:
    PLATFORMS.append(IMAGE_PLATFORM)

type TapoConfigEntry = ConfigEntry[dict[str, object]]


def platforms_for(entry: ConfigEntry) -> list[Platform]:
    if entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
        return [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SWITCH, Platform.NUMBER, Platform.SELECT, Platform.TEXT]
    linked = bool(entry.data.get(CONF_TAPO_CONTROL_ENTRY))
    if linked:
        platforms = [Platform.BINARY_SENSOR, Platform.SENSOR]
        if IMAGE_PLATFORM is not None:
            platforms.insert(1, IMAGE_PLATFORM)
        return platforms
    platforms = list(PLATFORMS)
    if Platform.CAMERA in platforms and not any(entry.options.get(key, entry.data.get(key)) for key in (CONF_STREAM_URL, CONF_SUB_STREAM_URL)):
        platforms.remove(Platform.CAMERA)
    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: TapoConfigEntry) -> bool:
    """Connect to one camera and register its entities."""
    from .license_client import LICENSE_INSTANCE, load_policy

    policy = await hass.async_add_executor_job(load_policy)
    guard = None
    if entry.data.get(LICENSE_INSTANCE) or entry.data.get("license_required") or policy.enabled and not policy.grandfather_existing:
        from .licensing import async_prepare_license

        guard = await async_prepare_license(hass, entry)
    data = entry.data
    if data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
        from .cloud_coordinator import CloudSettingsCoordinator
        from .notification_coordinator import NotificationCoordinator

        coordinator = NotificationCoordinator(hass, entry)
        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception:
            await coordinator.async_close()
            raise
        platforms = platforms_for(entry)
        settings = CloudSettingsCoordinator(hass, entry, coordinator)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"notification_coordinator": coordinator, "coordinator": settings, "platforms": platforms}
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
        entry.async_create_background_task(hass, settings.async_refresh(), "Tapo cloud settings discovery")
        if guard:
            guard.start()
        return True
    if source_id := data.get(CONF_TAPO_CONTROL_ENTRY):
        camera = TapoControlCamera(hass, source_id, data[CONF_HOST])
    else:
        camera = PytapoCamera(
            host=data[CONF_HOST],
            password=data[CONF_PASSWORD],
            username=data.get(CONF_USERNAME, "admin"),
            port=int(data.get(CONF_PORT, 443)),
            auth_mode=data.get(CONF_AUTH_MODE, "tapo_account" if data.get(CONF_USERNAME, "admin") == "admin" else "camera_account"),
        )
    coordinator = TapoDataCoordinator(hass, entry, camera)
    try:
        await coordinator.async_config_entry_first_refresh()
    except TapoSecureTransportRequired as err:
        await hass.async_add_executor_job(camera.close)
        _LOGGER.error(
            "Tapo camera %s needs encrypted local transport: %s", camera.host, err
        )
        raise ConfigEntryNotReady(str(err)) from err
    except (TapoAuthError, TapoConnectionError) as err:
        await hass.async_add_executor_job(camera.close)
        raise ConfigEntryNotReady(str(err)) from err
    except Exception:
        await hass.async_add_executor_job(camera.close)
        raise

    platforms = platforms_for(entry)
    runtime = {
        "camera": camera,
        "coordinator": coordinator,
        "name": coordinator.device_name,
        "platforms": platforms,
        "stream_url": entry.options.get(CONF_STREAM_URL, entry.data.get(CONF_STREAM_URL)),
        "sub_stream_url": entry.options.get(CONF_SUB_STREAM_URL, entry.data.get(CONF_SUB_STREAM_URL)),
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    if guard:
        guard.start()
    return True

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version > 2:
        return False
    if entry.version == 1:
        data = dict(entry.data)
        if not data.get(CONF_TAPO_CONTROL_ENTRY):
            data[CONF_CONNECTION_MODE] = MODE_STANDALONE
            data.setdefault(CONF_AUTH_MODE, "tapo_account" if data.get(CONF_USERNAME, "admin") == "admin" else "camera_account")
        data.pop("verify_ssl", None)
        data.pop("timeout", None)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TapoConfigEntry) -> bool:
    """Unload a config entry."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    platforms = runtime.get("platforms", platforms_for(entry))
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if runtime:
            if coordinator := runtime.get("notification_coordinator"):
                if settings := runtime.get("coordinator"):
                    await settings.async_close()
                await coordinator.async_close()
            else:
                await hass.async_add_executor_job(runtime["camera"].close)
    return unloaded

async def async_remove_entry(hass: HomeAssistant, entry: TapoConfigEntry) -> None:
    if entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
        from homeassistant.helpers.storage import Store

        await Store(hass, 1, f"{DOMAIN}.notifications.{entry.entry_id}", private=True).async_remove()
    if identifier := entry.data.get("cloud_credentials_id"):
        from .cloud_storage import CloudSessionStore

        await CloudSessionStore(hass, identifier).async_remove()
