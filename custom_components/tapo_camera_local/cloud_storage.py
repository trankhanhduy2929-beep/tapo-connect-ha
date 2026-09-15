"""HA-managed private session storage; users never copy credential files."""

import asyncio
import re

from homeassistant.helpers.storage import Store

from .cloud_account import validated_session
from .const import DOMAIN
from .notification_client import NotificationAuthError


class CloudSessionStore:
    def __init__(self, hass, identifier: str):
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise NotificationAuthError("Cloud credentials unavailable; sign in through Home Assistant")
        self.store = Store(hass, 1, f"{DOMAIN}.cloud.{identifier}", private=True)
        self._lock = hass.data.setdefault(f"{DOMAIN}_cloud_session_locks", {}).setdefault(identifier, asyncio.Lock())

    async def async_load(self) -> dict:
        async with self._lock:
            data = await self.store.async_load()
        if not isinstance(data, dict) or data.get("renewal_pending"):
            raise NotificationAuthError("Cloud session unavailable; sign in through Home Assistant")
        return validated_session(data)

    async def async_save(self, session: dict):
        async with self._lock:
            await self.store.async_save(validated_session(session))

    async def async_begin_renewal(self, session: dict):
        async with self._lock:
            stored = await self.store.async_load()
            if not isinstance(stored, dict) or stored.get("renewal_pending") or stored.get("access_token") != session.get("access_token"):
                raise NotificationAuthError("Cloud session changed; sign in through Home Assistant")
            await self.store.async_save({**validated_session(session), "renewal_pending": True})

    async def async_save_cursor(self, session: dict, cursor: int | None):
        """Persist only the read watermark; a missing cursor keeps the stored one."""
        async with self._lock:
            stored = await self.store.async_load()
            if not isinstance(stored, dict) or stored.get("renewal_pending"):
                return
            try:
                data = validated_session(stored)
            except NotificationAuthError:
                return
            if data["access_token"] != session.get("access_token"):
                return
            if type(cursor) is int and cursor > 0:
                data["notification_cursor"] = max(cursor, data.get("notification_cursor", 0))
            await self.store.async_save(data)

    async def async_remove(self):
        async with self._lock:
            await self.store.async_remove()
