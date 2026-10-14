"""Register the Tapo Connect sidebar panel and its static assets."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_URL_PATH = "tapo-connect"
PANEL_WEBCOMPONENT = "tapo-connect-panel"
PANEL_FILENAME = "tapo-connect-panel.js"
PANEL_MODULE_URL = f"/{DOMAIN}/{PANEL_FILENAME}"
PANEL_TITLE = "Tapo Connect"
PANEL_ICON = "mdi:cctv"


async def async_setup_panel(hass: HomeAssistant) -> None:
    """Serve the module, register the websocket API and the sidebar panel once."""
    from .frontend_api import async_register_commands

    registered = hass.data.setdefault(f"{DOMAIN}_panel_registered", {})
    if not registered.get("static"):
        from homeassistant.components.http import StaticPathConfig

        asset = Path(__file__).with_name("www") / PANEL_FILENAME
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_MODULE_URL, str(asset), cache_headers=False)]
        )
        registered["static"] = True
    await async_register_commands(hass)
    if not registered.get("panel"):
        from homeassistant.components import panel_custom

        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=PANEL_WEBCOMPONENT,
            frontend_url_path=PANEL_URL_PATH,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=PANEL_MODULE_URL,
            config={},
            require_admin=False,
        )
        registered["panel"] = True
