"""Config flow for the Tapo Connect integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import (
    PytapoCamera,
    TapoAuthError,
    TapoConnectionError,
    TapoProtocolError,
    TapoRequestError,
)
from .cloud_flow import CloudLoginFlow
from .const import (
    CONF_AUTH_MODE,
    CONF_CONNECTION_MODE,
    CONF_PUSH_ENABLED,
    CONF_SCAN_INTERVAL,
    CONF_STREAM_URL,
    CONF_SUB_STREAM_URL,
    CONF_TAPO_CONTROL_ENTRY,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MAX_CLOUD_SCAN_INTERVAL,
    MIN_CLOUD_SCAN_INTERVAL,
    MODE_CLOUD_NOTIFICATIONS,
    MODE_STANDALONE,
)
from .tapo_proto.linked import (
    SOURCE_DOMAIN,
    TapoControlCamera,
    TapoSourceError,
    source_controller,
)
from .tapo_proto.pytapo_client import AUTH_MODES

_LOGGER = logging.getLogger(__name__)

def _standalone_schema(defaults: dict[str, Any]) -> vol.Schema:
    def required(key: str, default: Any = None):
        if key in defaults:
            return vol.Required(key, default=defaults[key])
        if default is None:
            return vol.Required(key)
        return vol.Required(key, default=default)

    def optional(key: str, default: Any):
        return vol.Optional(key, default=defaults.get(key, default))

    fields = {
        required(CONF_HOST): selector.TextSelector(),
        optional(CONF_PORT, DEFAULT_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=65535, mode="box", step=1)
        ),
        required(CONF_AUTH_MODE, "tapo_account"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(AUTH_MODES), translation_key="auth_mode", mode="dropdown"
            )
        ),
        optional(CONF_USERNAME, DEFAULT_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        optional(CONF_NAME, DEFAULT_NAME): selector.TextSelector(),
        vol.Optional(CONF_STREAM_URL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
    return vol.Schema(fields)


class TapoConfigFlow(CloudLoginFlow, ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration of one local Tapo camera."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TapoOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        from .license_policy_locked import load_policy

        if (await self.hass.async_add_executor_job(load_policy)).enabled:
            return await self.async_step_license(user_input)
        return await self.async_step_cloud_login()

    async def async_step_license(self, user_input=None):
        from .licensing import async_license_form

        return await async_license_form(self, user_input)

    def _entry_to_update(self):
        if self.context.get("source") == "reconfigure":
            return self._get_reconfigure_entry()
        if self.context.get("source") == "reauth":
            return self._get_reauth_entry()
        return None

    async def _async_finish(self, info, data: dict[str, Any]) -> ConfigFlowResult:
        from .license_client import LICENSE_INSTANCE
        from .license_policy_locked import load_policy

        identifier = info.device_id or data[CONF_HOST]
        if entry := self._entry_to_update():
            for key in (LICENSE_INSTANCE, "license_required"):
                if key in entry.data:
                    data[key] = entry.data[key]
            if identifier != (entry.unique_id or entry.data[CONF_HOST]):
                return self.async_abort(reason="wrong_device")
            options = dict(entry.options)
            if data.get(CONF_CONNECTION_MODE) == MODE_STANDALONE:
                options.pop(CONF_STREAM_URL, None)
            return self.async_update_reload_and_abort(entry, data=data, options=options)
        if (await self.hass.async_add_executor_job(load_policy)).enabled:
            return self.async_abort(reason="license_required")
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()
        title = data.get(CONF_NAME) or info.name or f"Tapo {data[CONF_HOST]}"
        return self.async_create_entry(title=title, data=data)

    async def async_step_standalone(self, user_input=None) -> ConfigFlowResult:
        return await self._async_standalone(user_input, "standalone")

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        if self._get_reconfigure_entry().data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
            return await self.async_step_cloud_notifications(user_input)
        return await self._async_standalone(user_input, "reconfigure")

    async def async_step_reauth(self, entry_data) -> ConfigFlowResult:
        if entry_data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
            return await self.async_step_cloud_notifications()
        if entry_data.get(CONF_TAPO_CONTROL_ENTRY):
            return self.async_abort(reason="source_reauth")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        return await self._async_standalone(user_input, "reauth_confirm")

    async def _async_standalone(self, user_input, step_id: str) -> ConfigFlowResult:
        entry = self._entry_to_update()
        defaults = dict(entry.data) if entry is not None else {}
        if entry is not None and CONF_STREAM_URL in entry.options:
            defaults[CONF_STREAM_URL] = entry.options[CONF_STREAM_URL]
        errors: dict[str, str] = {}
        if user_input is not None:
            defaults.update(user_input)
            try:
                validate_stream(defaults.get(CONF_STREAM_URL, ""))
                port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
                if port != float(user_input.get(CONF_PORT, DEFAULT_PORT)):
                    raise ValueError("Control port must be a whole number")
                camera = PytapoCamera(
                    host=user_input[CONF_HOST],
                    password=user_input[CONF_PASSWORD],
                    username=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    port=port,
                    auth_mode=user_input.get(CONF_AUTH_MODE, "tapo_account"),
                )
                info = await self.hass.async_add_executor_job(_probe, camera)
            except TapoAuthError:
                errors["base"] = "invalid_auth"
            except TapoProtocolError:
                errors["base"] = "unexpected_response"
            except TapoRequestError as error:
                _LOGGER.warning("Standalone basic-info query rejected: %s", error)
                errors["base"] = "request_rejected"
            except TapoConnectionError:
                errors["base"] = "cannot_connect"
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_input"
            except (OSError, RuntimeError):
                _LOGGER.error("Standalone probe failed; raw exception suppressed")
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_CONNECTION_MODE: MODE_STANDALONE,
                    CONF_HOST: camera.host,
                    CONF_PORT: port,
                    CONF_AUTH_MODE: camera.auth_mode,
                    CONF_USERNAME: camera.username,
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_NAME: user_input.get(CONF_NAME) or (entry.title if entry else info.name) or DEFAULT_NAME,
                }
                if stream := defaults.get(CONF_STREAM_URL):
                    data[CONF_STREAM_URL] = stream
                return await self._async_finish(info, data)
        return self.async_show_form(
            step_id=step_id, data_schema=_standalone_schema(defaults), errors=errors,
        )

    async def async_step_tapo_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        choices = {entry.entry_id: entry.title for entry in self.hass.config_entries.async_entries(SOURCE_DOMAIN)}
        if not choices:
            return self.async_abort(reason="no_tapo_control")
        errors: dict[str, str] = {}
        if user_input is not None:
            source_id = user_input.get(CONF_TAPO_CONTROL_ENTRY)
            if source_id not in choices:
                errors["base"] = "source_not_ready"
            else:
                try:
                    controller = source_controller(self.hass, source_id)
                    host = getattr(controller, "host", None)
                    if not isinstance(host, str) or not host:
                        raise TapoSourceError("Source controller does not expose a camera host")
                    camera = TapoControlCamera(self.hass, source_id, host)
                    info = await self.hass.async_add_executor_job(_probe, camera)
                except TapoSourceError as err:
                    _LOGGER.warning("Tapo Control source is not ready: %s", err)
                    errors["base"] = "source_not_ready"
                except TapoProtocolError as err:
                    _LOGGER.warning("Tapo Control response could not be parsed: %s", err)
                    errors["base"] = "unexpected_response"
                except TapoRequestError as err:
                    _LOGGER.warning("Tapo Control camera rejected probe: %s", err)
                    errors["base"] = "request_rejected"
                except (TapoConnectionError, ValueError):
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(info.device_id or host)
                    self._abort_if_unique_id_configured()
                    title = info.name or f"Tapo {host}"
                    return self.async_create_entry(title=title, data={
                        CONF_HOST: host, CONF_NAME: title, CONF_TAPO_CONTROL_ENTRY: source_id,
                    })
        return self.async_show_form(
            step_id="tapo_control",
            data_schema=vol.Schema({vol.Required(CONF_TAPO_CONTROL_ENTRY): vol.In(choices)}),
            errors=errors,
        )

def _probe(camera: PytapoCamera | TapoControlCamera):
    try:
        return camera.basic_info()
    finally:
        camera.close()


def validate_stream(value):
    if not value:
        return
    if not isinstance(value, str) or any(character.isspace() for character in value):
        raise ValueError("Invalid RTSP URL")
    url = urlsplit(value)
    if url.scheme != "rtsp" or not url.hostname or url.fragment or url.port is not None and not 1 <= url.port <= 65535:
        raise ValueError("Use an RTSP URL with a valid host and port")


class TapoOptionsFlow(OptionsFlowWithReload):
    async def async_step_license_menu(self, user_input=None):
        return self.async_show_menu(step_id="license_menu", menu_options=["license", "camera_options"])

    async def async_step_license(self, user_input=None):
        from .licensing import async_license_form

        return await async_license_form(self, user_input, self.config_entry)

    async def async_step_camera_options(self, user_input=None):
        return await self._async_camera_options(user_input, "camera_options")

    async def async_step_cloud_notifications(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_CLOUD_SCAN_INTERVAL)
            if isinstance(interval, bool) or not MIN_CLOUD_SCAN_INTERVAL <= float(interval) <= MAX_CLOUD_SCAN_INTERVAL or int(interval) != float(interval):
                errors[CONF_SCAN_INTERVAL] = "invalid_input"
            else:
                options = dict(self.config_entry.options)
                options[CONF_SCAN_INTERVAL] = int(interval)
                options[CONF_PUSH_ENABLED] = bool(user_input.get(CONF_PUSH_ENABLED, DEFAULT_PUSH_ENABLED))
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="cloud_notifications", errors=errors, data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_CLOUD_SCAN_INTERVAL)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=MIN_CLOUD_SCAN_INTERVAL, max=MAX_CLOUD_SCAN_INTERVAL, step=1, mode="box", unit_of_measurement="s")
                ),
                vol.Optional(CONF_PUSH_ENABLED, default=self.config_entry.options.get(CONF_PUSH_ENABLED, DEFAULT_PUSH_ENABLED)): selector.BooleanSelector(),
            }),
        )

    async def async_step_init(self, user_input=None):
        from .license_client import LICENSE_INSTANCE
        from .license_policy_locked import load_policy

        if self.config_entry.data.get(LICENSE_INSTANCE) or (await self.hass.async_add_executor_job(load_policy)).enabled:
            return await self.async_step_license_menu(user_input)
        return await self._async_camera_options(user_input)

    async def _async_camera_options(self, user_input=None, step_id="init"):
        if self.config_entry.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS:
            return await self.async_step_cloud_notifications(user_input)
        errors = {}
        if user_input is not None:
            try:
                interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                if isinstance(interval, bool) or not 5 <= float(interval) <= 300 or int(interval) != float(interval):
                    raise ValueError("Polling interval must be an integer between 5 and 300")
                for key in (CONF_STREAM_URL, CONF_SUB_STREAM_URL):
                    validate_stream(user_input.get(key, ""))
            except (TypeError, ValueError):
                errors["base"] = "invalid_input"
            else:
                options = dict(self.config_entry.options)
                options.update(user_input)
                options[CONF_SCAN_INTERVAL] = int(interval)
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id=step_id, errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=300, step=1, mode="box", unit_of_measurement="s")
            ),
            vol.Optional(CONF_STREAM_URL): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Optional(CONF_SUB_STREAM_URL): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }))
