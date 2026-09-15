"""HA lifecycle guard, separate from camera transports and polling."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .license_client import (
    LICENSE_INSTANCE,
    LicenseError,
    LicenseUnavailable,
    enrollment_url,
    load_policy,
    new_identity,
    request_lease,
    verify_lease,
)


class LicenseStore:
    def __init__(self, hass, identifier):
        self.identifier = str(uuid.UUID(identifier))
        self.store = Store(hass, 1, f"{DOMAIN}.license.{self.identifier}", private=True)

    async def load(self):
        value = await self.store.async_load()
        return value or {"identity": new_identity(self.identifier)}

    async def save(self, data):
        await self.store.async_save(data)

async def async_license_form(flow, user_input=None, entry=None):
    lock = flow.hass.data.setdefault(f"{DOMAIN}_license_lock", asyncio.Lock())
    async with lock:
        return await _async_license_form(flow, user_input, entry)

async def _async_license_form(flow, user_input=None, entry=None):
    import voluptuous as vol
    from homeassistant.helpers import selector

    errors = {}
    try:
        policy = await flow.hass.async_add_executor_job(load_policy)
        policy.check()
        index_store = Store(flow.hass, 1, f"{DOMAIN}.license_index", private=True)
        index = await index_store.async_load() or {}
        if entry is None:
            owner = index.get("pending_flow")
            active = {item["flow_id"] for item in flow.hass.config_entries.flow.async_progress()}
            if owner != flow.flow_id and owner in active:
                return flow.async_abort(reason="license_flow_in_progress")
            index["pending_flow"] = flow.flow_id
        draft = f"entry:{entry.entry_id}" if entry else "pending"
        existing = {other.data.get(LICENSE_INSTANCE) for other in flow.hass.config_entries.async_entries(DOMAIN)}
        if draft not in index or entry is None and index[draft] in existing:
            index[draft] = str(uuid.uuid4())
        identifier = getattr(flow, "_license_identifier", None) or (entry.data.get(LICENSE_INSTANCE) if entry else None) or index[draft]
        await index_store.async_save(index)
        key = str(user_input.get("license_key", "")).strip() if user_input else ""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        if key and entry is None and key_hash in index:
            identifier = index[key_hash]
        flow._license_identifier = identifier
        store = LicenseStore(flow.hass, identifier)
        data = await store.load()
        await store.save(data)
        if user_input is not None:
            try:
                if any(other.data.get(LICENSE_INSTANCE) == identifier and (entry is None or other.entry_id != entry.entry_id) for other in flow.hass.config_entries.async_entries(DOMAIN)):
                    raise LicenseError("license_in_use")
                token = await request_lease(async_get_clientsession(flow.hass), policy, data["identity"], key, "activate")
                await store.save({**data, "key": key, "lease": token})
                index[key_hash] = identifier
                await index_store.async_save(index)
            except LicenseUnavailable:
                errors["base"] = "license_unavailable"
            except LicenseError:
                errors["base"] = "license_rejected"
            else:
                if entry is not None:
                    flow.hass.config_entries.async_update_entry(entry, data={**entry.data, LICENSE_INSTANCE: identifier, "license_required": True})
                    return flow.async_create_entry(title="", data=dict(entry.options))
                flow._license_verified = True
                return await flow.async_step_cloud_login()
        return flow.async_show_form(step_id="license", errors=errors, data_schema=vol.Schema({vol.Required("license_key"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))}), description_placeholders={"license_url": enrollment_url(policy, data["identity"])})
    except (LicenseError, OSError, ValueError):
        return flow.async_abort(reason="license_configuration")

class LicenseGuard:
    def __init__(self, hass, entry, policy):
        self.hass, self.entry, self.policy = hass, entry, policy
        self.store = LicenseStore(hass, entry.data[LICENSE_INSTANCE])
        self.lock = asyncio.Lock()
        self.claim = None
        self.next_attempt = 0

    async def check(self):
        async with self.lock:
            data = await self.store.load()
            key = data.get("key", "")
            if not key:
                raise LicenseError("license_missing")
            try:
                token = await request_lease(async_get_clientsession(self.hass), self.policy, data["identity"], key, "validate")
            except LicenseUnavailable:
                self.claim = verify_lease(self.policy, data["identity"], key, data.get("lease", ""))
                self.next_attempt = time.time() + 60
            except LicenseError:
                data.pop("lease", None)
                await self.store.save(data)
                raise
            else:
                self.claim = verify_lease(self.policy, data["identity"], key, token)
                await self.store.save({**data, "lease": token})
                self.next_attempt = self.claim["refreshAfter"]

    async def tick(self, _now):
        if time.time() < min(self.next_attempt, self.claim["validUntil"] if self.claim else 0):
            return
        try:
            await self.check()
        except (LicenseError, OSError):
            self.hass.async_create_task(self.hass.config_entries.async_reload(self.entry.entry_id))

    def start(self):
        self.entry.async_on_unload(async_track_time_interval(self.hass, self.tick, timedelta(seconds=30)))

async def async_prepare_license(hass, entry):
    try:
        policy = await hass.async_add_executor_job(load_policy)
        identifier = entry.data.get(LICENSE_INSTANCE)
        if not identifier:
            if not entry.data.get("license_required") and (not policy.enabled or policy.grandfather_existing):
                return None
            raise LicenseError("license_missing")
        policy.check()
        if any(other.entry_id < entry.entry_id and other.data.get(LICENSE_INSTANCE) == identifier for other in hass.config_entries.async_entries(DOMAIN)):
            raise LicenseError("license_in_use")
        guard = LicenseGuard(hass, entry, policy)
        await guard.check()
        return guard
    except (LicenseError, OSError, ValueError) as error:
        raise ConfigEntryNotReady("Tapo Connect: license chưa hợp lệ. Mở Cấu hình → License để nhập key; phần camera và tài khoản Tapo được giữ nguyên.") from error
