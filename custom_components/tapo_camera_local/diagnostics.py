"""Diagnostics intentionally exclude credentials, identifiers and face names."""

from .const import (
    CONF_AUTH_MODE,
    CONF_CONNECTION_MODE,
    CONF_TAPO_CONTROL_ENTRY,
    DOMAIN,
    MODE_CLOUD_NOTIFICATIONS,
    MODE_STANDALONE,
    MODE_TAPO_CONTROL,
    VERSION,
)
from .tapo_proto.linked import SOURCE_DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    if entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
        cloud = runtime.get("notification_coordinator")
        settings = runtime.get("coordinator")
        return {"integration_version": VERSION, "connection_mode": MODE_CLOUD_NOTIFICATIONS, "loaded": cloud is not None, "last_update_success": cloud.last_update_success if cloud else None, "poll_interval_seconds": cloud.update_interval.total_seconds() if cloud else None, "notification_count": cloud.history.count if cloud else None, "named_people_count": len(cloud.history.people) if cloud else None, "history_truncated": cloud.history.truncated if cloud else None, "timestamp_source": "notification.time", "image_supported": False, "tls_verification_enabled": True, "notification_categories": sorted(cloud.history.categories) if cloud else [], "settings_available": settings.last_update_success if settings else False, "settings_count": len(settings.settings) if settings else 0, "settings_poll_seconds": settings.update_interval.total_seconds() if settings else None, "settings_api_status": settings.basic.get("api_status", {}) if settings else {}}
    coordinator = runtime.get("coordinator")
    source_id = entry.data.get(CONF_TAPO_CONTROL_ENTRY)
    source_runtime = hass.data.get(SOURCE_DOMAIN, {}).get(source_id, {})
    controller = source_runtime.get("controller") if isinstance(source_runtime, dict) else None
    transport = getattr(getattr(controller, "transport", None), "method", None)
    port = getattr(controller, "controlPort", None)
    standalone = entry.data.get(CONF_CONNECTION_MODE) == MODE_STANDALONE and not source_id
    auth_mode = entry.data.get(CONF_AUTH_MODE)
    result = {
        "integration_version": VERSION,
        "connection_mode": MODE_TAPO_CONTROL if source_id else MODE_STANDALONE,
        "auth_mode": auth_mode if standalone and auth_mode in {"tapo_account", "camera_account"} else None,
        "owned_transport": "pytapo" if standalone else None,
        "loaded": coordinator is not None,
        "source_ready": controller is not None if source_id else None,
        "source_transport": transport if isinstance(transport, str) and transport in {"pytapo", "kasa", "klap"} else None,
        "source_port": port if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535 else None,
    }
    if coordinator is not None:
        info = coordinator.device_info
        state = coordinator.face_history.state
        result.update({
            "model": getattr(info, "model", None),
            "firmware": getattr(info, "firmware", None),
            "last_update_success": coordinator.last_update_success,
            "poll_interval_seconds": coordinator.update_interval.total_seconds(),
            "api_status": coordinator.basic.get("api_status", {}),
            "face_catalog_available": state["catalog_available"],
            "face_tracking_available": state["tracking_available"],
            "face_count": state["face_count"],
            "catalog_complete": state["catalog_complete"],
            "history_truncated": state["history_truncated"],
        })
    return result
