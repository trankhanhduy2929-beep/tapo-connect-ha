"""Read-only companion using a controller owned by Tapo: Cameras Control."""

from __future__ import annotations

import asyncio
from typing import Any

from .client import (
    READ_QUERIES,
    TapoAuthError,
    TapoCamera,
    TapoConnectionError,
    TapoRequestError,
)

SOURCE_DOMAIN = "tapo_control"
READ_METHODS = frozenset(READ_QUERIES) | {
    "getDeviceInfo",
    "searchFacesInfo",
    "doSearchFaceTrackingList",
    "doFaceInfoGet",
}


class TapoSourceError(TapoConnectionError):
    """The owner integration must reconnect, reload or be updated."""


def source_controller(hass: Any, source_entry_id: str) -> Any:
    runtime = hass.data.get(SOURCE_DOMAIN, {}).get(source_entry_id)
    controller = runtime.get("controller") if isinstance(runtime, dict) else None
    if controller is None or not callable(getattr(controller, "performRequest", None)):
        raise TapoSourceError("Tapo Control controller is not ready; connect that integration first")
    return controller


class TapoControlCamera(TapoCamera):
    """Borrow the current controller without copying credentials or owning its session."""

    def __init__(self, hass: Any, source_entry_id: str, host: str) -> None:
        super().__init__(host, password="")
        self.hass = hass
        self.source_entry_id = source_entry_id
        self._closed = False

    def call(self, method: str, params: dict | None = None, *, read_only: bool = False) -> dict:
        if not read_only or method not in READ_METHODS:
            raise TapoConnectionError("Tapo Control companion only permits known read-only queries")
        try:
            if asyncio.get_running_loop() is self.hass.loop:
                raise TapoConnectionError("Call the synchronous companion client from an executor")
        except RuntimeError:
            pass
        with self._lock:
            if self._closed:
                raise TapoSourceError("Companion client is closed")
            controller = source_controller(self.hass, self.source_entry_id)
            body = {"method": "multipleRequest", "params": {"requests": [
                {"method": method, "params": params or {}}
            ]}}
            try:
                response = controller.performRequest(body)
            except Exception as error:  # noqa: BLE001
                if self._is_auth_error(error):
                    raise TapoSourceError("Authentication must be repaired in Tapo Control") from None
                code = getattr(error, "error_code", None)
                if isinstance(code, int) and not isinstance(code, bool):
                    raise TapoRequestError(method, code) from None
                raise TapoSourceError("Tapo Control request failed; raw response suppressed") from None
            try:
                return self._method_result(response, method, compatible=True)
            except TapoAuthError:
                raise TapoSourceError("Authentication must be repaired in Tapo Control") from None

    def close(self) -> None:
        with self._lock:
            self._closed = True
