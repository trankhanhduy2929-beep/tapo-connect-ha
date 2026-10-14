"""Create Home Assistant entries for cloud cameras (sign-in and manual scan)."""

from __future__ import annotations

import logging
import uuid
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry

from .cloud_storage import CloudSessionStore
from .const import CONF_CONNECTION_MODE, DOMAIN, MODE_CLOUD_NOTIFICATIONS
from .license_client import LICENSE_INSTANCE

_LOGGER = logging.getLogger(__name__)

# TapoConfigFlow.VERSION / MINOR_VERSION
ENTRY_VERSION = 2
ENTRY_MINOR_VERSION = 1


def camera_unique_id(camera_id: str) -> str:
    return f"cloud_notifications:{camera_id}"


def camera_configured(hass, camera_id: str) -> bool:
    return hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, camera_unique_id(camera_id)) is not None


async def async_add_camera_entry(hass, account, camera_id: str, cloud_email: str, license_identifier: str | None = None) -> bool:
    """Add one cloud camera entry with its own stored session copy."""
    try:
        await hass.async_add_executor_job(account.check_camera, camera_id)
        identifier = uuid.uuid4().hex
        store = CloudSessionStore(hass, identifier)
        await store.async_save(account.session_data)
        model = ((getattr(account, "device_models", {}) or {}).get(camera_id) or "").strip()
        data = {CONF_CONNECTION_MODE: MODE_CLOUD_NOTIFICATIONS, "camera_id": camera_id, "cloud_credentials_id": identifier, "cloud_email": cloud_email}
        if model:
            data["cloud_model"] = model
        if license_identifier:
            data[LICENSE_INSTANCE] = license_identifier
            data["license_required"] = True
        entry = ConfigEntry(
            data=data,
            discovery_keys=MappingProxyType({}),
            domain=DOMAIN,
            minor_version=ENTRY_MINOR_VERSION,
            options={},
            source="user",
            subentries_data=None,
            title=f"Tapo {model or 'C260'} · Cloud",
            unique_id=camera_unique_id(camera_id),
            version=ENTRY_VERSION,
        )
        await hass.config_entries.async_add(entry)
        return True
    except Exception:  # one camera must not block the others
        _LOGGER.exception("Không thêm được camera cloud %s", camera_id[-6:])
        return False


async def async_scan_cameras(hass, entry) -> int:
    """List the owner account and add any camera that has no entry yet."""
    from .cloud_account import CloudAccount

    session_id = entry.data.get("cloud_credentials_id")
    if not session_id:
        return 0
    store = CloudSessionStore(hass, session_id)
    session = await store.async_load()
    account = await hass.async_add_executor_job(CloudAccount.from_session, session)
    await hass.async_add_executor_job(account.cameras)
    cloud_email = entry.data.get("cloud_email", "")
    license_identifier = entry.data.get(LICENSE_INSTANCE)
    added = 0
    for camera_id in account.devices:
        if camera_configured(hass, camera_id):
            continue
        if await async_add_camera_entry(hass, account, camera_id, cloud_email, license_identifier):
            added += 1
    if added:
        _LOGGER.info("Đã thêm %d camera cloud mới từ quét tài khoản", added)
    return added


__all__ = ["async_add_camera_entry", "async_scan_cameras", "camera_configured", "camera_unique_id"]
