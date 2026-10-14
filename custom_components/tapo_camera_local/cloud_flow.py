"""Simple Tapo account sign-in; every camera in the account is added automatically."""

import asyncio
import logging
import re
import uuid

import voluptuous as vol
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .cloud_account import CloudAccount, CloudAccountError
from .cloud_storage import CloudSessionStore
from .const import CONF_CONNECTION_MODE, DOMAIN, MODE_CLOUD_NOTIFICATIONS
from .notification_client import NotificationAuthError, NotificationError

_LOGGER = logging.getLogger(__name__)


def _same_cloud_account(account, other) -> bool:
    email = getattr(account, "email", "")
    return bool(email) and other.data.get(CONF_CONNECTION_MODE) == MODE_CLOUD_NOTIFICATIONS and other.data.get("cloud_email") == email


class CloudLoginFlow:
    _cloud_account = None
    _cloud_task = None
    _cloud_busy = False

    async def _cloud_call(self, function, *args):
        if self._cloud_busy:
            raise CloudAccountError("cloud_busy")
        self._cloud_busy = True
        try:
            self._cloud_task = self.hass.async_add_executor_job(function, *args)
            return await asyncio.shield(self._cloud_task)
        finally:
            self._cloud_busy = False

    def _cloud_ready(self):
        if self._cloud_busy:
            raise CloudAccountError("cloud_busy")

    def _cloud_forget(self):
        self._cloud_account = None
        self._cloud_task = None

    @callback
    def async_remove(self):
        super().async_remove()
        task = self._cloud_task
        if task is not None:
            if task.done():
                _ignore_cloud_result(task)
            else:
                task.add_done_callback(_ignore_cloud_result)
        self._cloud_forget()

    async def async_step_cloud_notifications(self, user_input=None):
        return await self.async_step_cloud_login(user_input)

    async def async_step_cloud_login(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self._cloud_ready()
            except CloudAccountError as error:
                errors["base"] = error.kind
            else:
                try:
                    self._cloud_account = await self._cloud_call(CloudAccount)
                    authenticated = await self._cloud_call(self._cloud_account.begin, user_input.get("email"), user_input.get("password"), user_input.get("region", ""))
                except CloudAccountError as error:
                    errors["base"] = error.kind
                except NotificationAuthError:
                    errors["base"] = "cloud_invalid_auth"
                except NotificationError:
                    errors["base"] = "cloud_cannot_connect"
                else:
                    if not authenticated:
                        return await self.async_step_cloud_mfa()
                    return await self.async_step_cloud_device()
                self._cloud_forget()
        entry = self._entry_to_update()
        email = entry.data.get("cloud_email", "") if entry else ""
        return self.async_show_form(step_id="cloud_login", errors=errors, data_schema=vol.Schema({
            vol.Required("email", default=email): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
            vol.Required("password"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Optional("region", default=""): selector.TextSelector(),
        }))

    async def async_step_cloud_mfa(self, user_input=None):
        errors = {}
        if user_input is not None:
            code = user_input.get("code")
            if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
                errors["base"] = "cloud_invalid_code"
            else:
                try:
                    self._cloud_ready()
                    account = self._cloud_account
                    if account is None:
                        raise CloudAccountError("cloud_restart_login")
                    await self._cloud_call(account.verify, code)
                except CloudAccountError as error:
                    if error.kind == "cloud_busy":
                        errors["base"] = error.kind
                    else:
                        self._cloud_forget()
                        return self.async_abort(reason=error.kind)
                except NotificationError:
                    self._cloud_forget()
                    return self.async_abort(reason="cloud_restart_login")
                else:
                    return await self.async_step_cloud_device()
        account = self._cloud_account
        if account is None:
            return self.async_abort(reason="cloud_restart_login")
        return self.async_show_form(step_id="cloud_mfa", errors=errors, data_schema=vol.Schema({
            vol.Required("code"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }))

    def _camera_configured(self, camera_id) -> bool:
        from .cloud_provision import camera_configured

        return camera_configured(self.hass, camera_id)

    async def async_step_cloud_device(self, user_input=None):
        """Finish sign-in: add every camera in the account without a picker."""
        entry = self._entry_to_update()
        errors = {}
        account = None
        try:
            self._cloud_ready()
            account = self._cloud_account
            if account is None:
                raise CloudAccountError("cloud_restart_login")
            if not account.devices:
                await self._cloud_call(account.cameras)
            if entry is not None:
                camera_id = entry.data.get("camera_id")
                if camera_id not in account.devices:
                    errors["base"] = "cloud_invalid_device"
                else:
                    await self._cloud_call(account.check_camera, camera_id)
                    return await self._cloud_finish(account, camera_id, entry)
            else:
                return await self._cloud_finish_many(account)
        except CloudAccountError as error:
            errors["base"] = error.kind
        except NotificationAuthError:
            self._cloud_forget()
            return self.async_abort(reason="cloud_restart_login")
        except NotificationError:
            errors["base"] = "cloud_cannot_connect"
        if account is None:
            self._cloud_forget()
            return self.async_abort(reason="cloud_restart_login")
        return self.async_abort(reason=errors.get("base") or "cloud_no_devices")

    async def _cloud_finish_many(self, account):
        pending = [camera_id for camera_id in account.devices if not self._camera_configured(camera_id)]
        if not pending:
            self._cloud_forget()
            return self.async_abort(reason="already_configured")
        primary = pending[0]
        await self._cloud_call(account.check_camera, primary)
        result = await self._cloud_finish(account, primary, None)
        if result.get("type") == "create_entry" and len(pending) > 1:
            self.hass.async_create_task(self._cloud_add_cameras(account, pending[1:]))
        return result

    async def _cloud_add_cameras(self, account, camera_ids):
        from .cloud_provision import async_add_camera_entry

        license_identifier = getattr(self, "_license_identifier", None)
        for camera_id in camera_ids:
            await async_add_camera_entry(self.hass, account, camera_id, account.email, license_identifier)

    async def _cloud_finish(self, account, camera_id, entry):
        from .license_client import LICENSE_INSTANCE
        from .license_policy_locked import load_policy

        if entry is None and (await self.hass.async_add_executor_job(load_policy)).enabled and not getattr(self, "_license_verified", False):
            return self.async_abort(reason="license_required")
        if entry is None:
            await self.async_set_unique_id(f"cloud_notifications:{camera_id}")
            self._abort_if_unique_id_configured()
        identifier = entry.data.get("cloud_credentials_id") if entry else None
        identifier = identifier or uuid.uuid4().hex
        try:
            store = CloudSessionStore(self.hass, identifier)
            await store.async_save(account.session_data)
        except (HomeAssistantError, OSError):
            account.discard()
            self._cloud_forget()
            return self.async_abort(reason="cloud_storage")
        model = ((getattr(account, "device_models", {}) or {}).get(camera_id) or "").strip()
        data = {CONF_CONNECTION_MODE: MODE_CLOUD_NOTIFICATIONS, "camera_id": camera_id, "cloud_credentials_id": identifier, "cloud_email": account.email}
        if model:
            data["cloud_model"] = model
        license_identifier = entry.data.get(LICENSE_INSTANCE) if entry else getattr(self, "_license_identifier", None)
        if license_identifier:
            if entry is None and any(
                other.data.get(LICENSE_INSTANCE) == license_identifier and not _same_cloud_account(account, other)
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                return self.async_abort(reason="license_in_use")
            data[LICENSE_INSTANCE] = license_identifier
            data["license_required"] = True
        elif entry and entry.data.get("license_required"):
            data["license_required"] = True
        self._cloud_forget()
        if entry is not None:
            return self.async_update_reload_and_abort(entry, data=data)
        return self.async_create_entry(title=f"Tapo {model or 'C260'} · Cloud", data=data)


def _ignore_cloud_result(future):
    if not future.cancelled():
        future.exception()
