# ruff: noqa: BLE001
"""Owned pytapo connection; sanitize all exceptions at the upstream boundary."""

from __future__ import annotations

import asyncio
import time

from .client import (
    TapoAuthError,
    TapoCamera,
    TapoConnectionError,
    TapoProtocolError,
    TapoRequestError,
)
from .controls import validate_write
from .linked import READ_METHODS

AUTH_MODES = ("tapo_account", "camera_account")


class PytapoCamera(TapoCamera):
    """Run pytapo's native transport on an owned session and executor loop."""

    def __init__(
        self, host: str, password: str, username: str = "admin", *,
        port: int = 443, auth_mode: str = "tapo_account", transport_factory=None,
    ) -> None:
        if auth_mode not in AUTH_MODES or not isinstance(password, str) or not password:
            raise ValueError("Choose an account type and enter its password")
        if auth_mode == "tapo_account":
            username = "admin"
        elif not isinstance(username, str) or not username.strip():
            raise ValueError("Enter the camera account username")
        super().__init__(host, password, username, port=port, transport_factory=transport_factory)
        self.auth_mode = auth_mode
        self._closed = False
        self._batch_supported = True

    def _build_transport(self):
        if self._factory is not None:
            return self._factory(self.host, self._port, self._username, self.password)
        try:
            from pytapo.asyncHandler import AsyncHandler
            from pytapo.logger import Logger
            from pytapo.transport.pytapo.pytapo import pyTapo
            from pytapo.transport.transport import Transport
        except ImportError as error:
            raise TapoConnectionError(
                "Install pytapo==3.4.19 for standalone camera login"
            ) from error
        class NativeTransport(Transport):
            def _request(self, method, url, transientRetryCount=1, **kwargs):
                return pyTapo._request(self, method, url, transientRetryCount=1, **kwargs)

        return NativeTransport(
            host=self.host,
            controlPort=self._port,
            user=self._username,
            password=self.password,
            cloudPassword=self.password if self.auth_mode == "tapo_account" else "",
            method="pytapo",
            asyncHandler=AsyncHandler(None),
            logger=Logger(False, False),
            reuseSession=True,
            retryStok=False,
            redactConfidentialInformation=True,
        )

    async def _send(self, body: dict, read_only: bool) -> dict:
        method = body["params"]["requests"][0]["method"]
        if method == "do":
            request = body["params"]["requests"][0]
            response = await self._exchange({"method": "do", **request["params"]}, False)
            self._check_error(response, "do", allow_missing=False)
            return {}
        response = await self._exchange(body, read_only)
        return self._method_result(response, method, compatible=True)

    async def _exchange(self, body: dict, read_only: bool) -> dict:
        method = body["params"]["requests"][0]["method"] if body["method"] == "multipleRequest" else body["method"]
        try:
            if self._transport is None:
                self._transport = self._build_transport()
            if self._factory is not None:
                return await self._transport.send(body)
            from pytapo.const import MAX_LOGIN_RETRIES

            return await self._transport.send(body, retry=MAX_LOGIN_RETRIES - 1 if read_only else MAX_LOGIN_RETRIES)
        except (TapoAuthError, TapoRequestError, TapoProtocolError):
            raise
        except Exception as error:
            if self._is_auth_error(error) or "temporary suspension" in str(error).lower():
                raise TapoAuthError("Camera rejected or temporarily blocked login") from None
            code = getattr(error, "error_code", None)
            if isinstance(code, int) and not isinstance(code, bool):
                raise TapoRequestError(method, code) from None
            raise TapoConnectionError(
                "Standalone pytapo transport failed; raw response suppressed"
            ) from None

    def call(self, method: str, params: dict | None = None, *, read_only: bool = False) -> dict:
        if read_only:
            if method not in READ_METHODS:
                raise TapoConnectionError("Only known read methods are permitted")
        else:
            try:
                validate_write(method, params or {})
            except (TypeError, ValueError, OverflowError):
                raise TapoConnectionError("Only validated camera control payloads are permitted") from None
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise TapoConnectionError("Call the standalone client from an executor")
        with self._lock:
            if self._closed:
                raise TapoConnectionError("Standalone client is closed")
            return super().call(method, params, read_only=read_only)

    def _optional_many(self, queries: dict) -> None:
        if not self._batch_supported or self._factory is not None:
            super()._optional_many(queries)
            return
        pending = [(method, params) for method, params in queries.items() if self._retry_at.get(method, 0) <= time.monotonic()]
        for offset in range(0, len(pending), 8):
            group = pending[offset:offset + 8]
            body = {"method": "multipleRequest", "params": {"requests": [
                {"method": method, "params": params} for method, params in group
            ]}}
            try:
                response = self._runner.run(self._exchange(body, True))
                self._check_error(response, "multipleRequest", allow_missing=True)
                replies = response.get("result", {}).get("responses")
                if not isinstance(replies, list) or len(replies) != len(group):
                    raise TapoProtocolError("Invalid batch reply")
                for (method, params), reply in zip(group, replies, strict=True):
                    try:
                        result = self._method_result({"result": {"responses": [reply]}}, method, compatible=True)
                    except TapoRequestError as error:
                        status = "unsupported" if error.code == -40106 else "rejected"
                        self._statuses[method] = {"status": status, "error_code": error.code}
                        self._retry_at[method] = time.monotonic() + (3600 if status == "unsupported" else 300)
                        self._results.pop(method, None)
                    else:
                        self._results[method] = result
                        self._statuses[method] = {"status": "ok"}
                        self._retry_at.pop(method, None)
            except TapoAuthError:
                raise
            except (TapoRequestError, TapoProtocolError, AttributeError, TypeError):
                self._batch_supported = False
                super()._optional_many(dict(pending[offset:]))
                return

    def close(self) -> None:
        with self._lock:
            self._closed = True
            try:
                super().close()
            except Exception:
                raise TapoConnectionError("Standalone connection cleanup failed") from None
