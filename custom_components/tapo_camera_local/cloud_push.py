"""Realtime wakeup channel: MQTT 3.1.1 over WebSocket to the Tapo cloud gateway.

Protocol verified live on 2026-09-16 (see REPORT.md and poc/mqtt_push_probe.py):
  GET  https://app-server.iot.i.tplinknbu.com/v1/server-info   (ut|<access_token>)
  POST {securityServerUrl}/v2/auth/app   body token="ut|<access_token>" -> {"jwt"}
  wss://{cloudGatewayUrlV2}:443/mqtt     clientId app:<type>:<terminal>, password <jwt>
  Exact topics only; wildcard subscriptions are denied by the authorizer.

The gateway pushes short JSON payloads when device state or events change. This
client deliberately does NOT trust payload contents for HA state: every message
is a wakeup that forces the existing, read-back-verified REST refreshers to run
immediately. Polling stays the source of truth, so a broken, spoofed or missing
push can only make HA slower, never wrong.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import ssl
import threading
import time
import uuid

import certifi
import requests

from .cloud_account import app_parameters
from .cloud_storage import CloudSessionStore
from .const import CONF_PUSH_ENABLED, DEFAULT_PUSH_ENABLED, DOMAIN
from .notification_client import (
    NotificationError,
    VerifiedAdapter,
    cloud_base,
    signed_headers,
)

_LOGGER = logging.getLogger(__name__)

SERVER_INFO_URL = "https://app-server.iot.i.tplinknbu.com/v1/server-info"
APP_AUTH_PATH = "/v2/auth/app"
JWT_REFRESH_SECONDS = 12 * 3600
WAKE_MIN_INTERVAL = 3.0
BACKOFF_BASE = 30.0
BACKOFF_CAP = 900.0
WS_KEEPALIVE = 235
MAX_RESPONSE_BYTES = 65_536


def _app_headers(terminal: str) -> dict[str, str]:
    material = app_parameters()
    return {
        "app-cid": f"app:{material['app_type']}:{terminal}",
        "x-app-name": material["app_type"],
        "x-app-version": material["app_version"],
        "x-term-id": terminal,
        "x-ospf": "Android 13",
        "x-net-type": "wifi",
        "x-locale": "en_US",
    }


def _https_session() -> requests.Session:
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cadata="\n".join(app_parameters()["certificates"]))
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", VerifiedAdapter(context))
    return session


def fetch_broker_and_jwt(access_token: str, terminal: str) -> tuple[str, str]:
    """One-shot REST handshake returning (wss host, jwt password). Blocking."""
    material = app_parameters()
    headers = {"Authorization": "ut|" + access_token, **_app_headers(terminal)}
    with _https_session() as http:
        response = http.get(SERVER_INFO_URL, headers=headers, timeout=(8, 20), allow_redirects=False)
        if response.status_code != 200:
            raise NotificationError(f"cloud push handshake failed: server-info {response.status_code}")
        try:
            info = response.json()
        except ValueError:
            raise NotificationError("cloud push handshake returned non-JSON") from None
        host = str(info.get("cloudGatewayUrlV2") or info.get("cloudGatewayUrl") or "").split(":")[0]
        security = str(info.get("securityServerUrlV2") or "").rstrip("/")
        if not host:
            raise NotificationError("cloud push handshake missing gateway url")
        try:
            security_base = cloud_base(security) if security else None
            broker_host = cloud_base("https://" + host).removeprefix("https://")
        except NotificationError:
            raise NotificationError("cloud push endpoints outside tplinkcloud.com; keeping polling") from None
        if not security_base:
            raise NotificationError("cloud push handshake missing security server")
        body = {"appType": material["app_type"], "terminalUUID": terminal, "token": "ut|" + access_token}
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        signed = signed_headers(payload, APP_AUTH_PATH, material["access_key"], material["signing_secret"], str(uuid.uuid4()))
        response = http.post(
            security_base + APP_AUTH_PATH, data=payload,
            headers={**signed, **_app_headers(terminal)}, timeout=(8, 20), allow_redirects=False,
        )
        if response.status_code != 200:
            raise NotificationError(f"cloud push handshake failed: app-auth {response.status_code}")
        try:
            jwt = response.json()["jwt"]
        except (ValueError, KeyError, TypeError):
            raise NotificationError("cloud push handshake returned no jwt") from None
        if not isinstance(jwt, str) or not 0 < len(jwt) <= 4096:
            raise NotificationError("cloud push handshake jwt is invalid")
    return broker_host, str(jwt)


class CloudPushClient:
    """Background MQTT-over-WebSocket listener that only wakes existing coordinators."""

    def __init__(self, hass, entry, notification_coordinator, settings_coordinator):
        self.hass = hass
        self.entry = entry
        self.notifications = notification_coordinator
        self.settings = settings_coordinator
        self.device_id = entry.data["camera_id"]
        self.store = CloudSessionStore(hass, entry.data["cloud_credentials_id"])
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self._last_wake: dict[str, float] = {}
        self._futures: list = []
        self.connected = False
        self.last_event_at: float | None = None
        self.stats = {"events": 0, "reconnects": 0, "handshake_failures": 0}

    async def async_start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name=f"{DOMAIN}-push-{self.entry.entry_id}", daemon=True)
        await self.hass.async_add_executor_job(self.thread.start)

    def _load_session(self) -> dict:
        try:
            future = asyncio.run_coroutine_threadsafe(self.store.async_load(), self.hass.loop)
            session = future.result(timeout=20) or {}
        except Exception:  # noqa: BLE001 - session store may be transiently unavailable; keep old connection
            return {}
        return session if isinstance(session, dict) else {}

    def _topics(self, terminal: str) -> dict[str, str]:
        material = app_parameters()
        return {
            f"$tpiot/things/{self.device_id}/events/accepted": "events",
            f"$tpiot/apps/{material['app_type']}/{terminal}/api/reply": "events",
            f"$tpiot/things/{self.device_id}/shadow/update/accepted": "settings",
            f"$tpiot/things/{self.device_id}/real-time-map/download": "events",
        }

    def _run(self):
        backoff = BACKOFF_BASE
        while not self.stop_event.is_set():
            session = self._load_session()
            token, terminal = session.get("access_token"), session.get("terminal")
            try:
                if not token or not terminal:
                    raise NotificationError("cloud session unavailable for push")
                host, jwt = fetch_broker_and_jwt(token, terminal)
                fatal = self._listen(host, jwt, terminal)
                backoff = BACKOFF_BASE
                if fatal:
                    break
            except Exception:
                self.stats["handshake_failures"] += 1
                _LOGGER.debug("Tapo push cycle failed for %s; polling continues unaffected", self.device_id, exc_info=True)
            self.connected = False
            if self.stop_event.wait(backoff + random.uniform(0, 10)):
                break
            backoff = min(BACKOFF_CAP, backoff * 2)
            self.stats["reconnects"] += 1

    def _listen(self, host: str, jwt: str, terminal: str) -> bool:
        """Connect and pump until stop/failure. Returns True when reconnect must reload session."""
        import paho.mqtt.client as mqtt

        topics = self._topics(terminal)
        material = app_parameters()
        context = ssl.create_default_context(cafile=certifi.where())
        context.load_verify_locations(cadata="\n".join(material["certificates"]))
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # AWS-fronted gateway serves non-TP-Link chains; app pins its own verifier

        connack_box: list = []
        ever_connected = [False]

        def on_connect(client, _userdata, _flags, reason_code, _properties):
            connack_box.append(reason_code)
            if not reason_code.is_failure:
                self.connected = True
                note = " (first connect)" if not ever_connected[0] else " (reconnected)"
                ever_connected[0] = True
                for topic in topics:
                    client.subscribe(topic, qos=0)
                _LOGGER.debug("Tapo push connected%s; %d topics", note, len(topics))

        def on_message(client, _userdata, message):
            self.last_event_at = time.time()
            kind = topics.get(message.topic)
            if kind is None:
                return
            self.stats["events"] += 1
            try:
                self.hass.loop.call_soon_threadsafe(self._wake, kind)
            except RuntimeError:
                pass  # HA stopping

        def on_disconnect(client, _userdata, _flags, reason_code, _properties):
            self.connected = False

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=f"app:{material['app_type']}:{terminal}",
            protocol=mqtt.MQTTv311, transport="websockets",
        )
        client.ws_set_options(path="/mqtt")
        client.username_pw_set(f"{material['app_type']}:v{material['app_version']}:Android 13:en_US", jwt)
        client.tls_set_context(context)
        client.tls_insecure_set(True)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        try:
            client.connect(host, 443, keepalive=WS_KEEPALIVE)
        except OSError as error:
            raise NotificationError(f"cloud push connect failed: {error}") from error
        client.loop_start()
        deadline = time.monotonic() + JWT_REFRESH_SECONDS
        try:
            while not self.stop_event.is_set():
                if connack_box and connack_box[-1].is_failure:
                    return True  # authorizer rejected: reload the (possibly renewed) session
                if time.monotonic() >= deadline:
                    return False  # jwt nearing lifetime: redo handshake
                if self.stop_event.wait(1.0):
                    break
        finally:
            try:
                client.disconnect()
            except Exception:  # noqa: S110, BLE001 - teardown best-effort
                pass
            client.loop_stop()
        return False

    def _wake(self, kind: str):
        now = time.monotonic()
        if now - self._last_wake.get(kind, 0.0) < WAKE_MIN_INTERVAL:
            return
        self._last_wake[kind] = now
        coordinator = self.notifications if kind == "events" else self.settings
        if coordinator is None:
            return
        self._futures[:] = [item for item in self._futures if not item.done()]
        self._futures.append(self.hass.async_create_task(coordinator.async_refresh()))

    async def async_stop(self):
        self.stop_event.set()
        if self.thread is not None:
            await self.hass.async_add_executor_job(self.thread.join, 10)
            self.thread = None
        for future in self._futures:
            if not future.done():
                future.cancel()
        self._futures.clear()

    def status(self) -> dict:
        return {
            "enabled": True,
            "connected": self.connected,
            "last_event_at": self.last_event_at,
            **self.stats,
        }


def push_enabled(entry) -> bool:
    return bool(entry.options.get(CONF_PUSH_ENABLED, entry.data.get(CONF_PUSH_ENABLED, DEFAULT_PUSH_ENABLED)))


async def async_setup_push(hass, entry, notification_coordinator, settings_coordinator):
    if not push_enabled(entry) or not entry.data.get("cloud_credentials_id"):
        return None
    client = CloudPushClient(hass, entry, notification_coordinator, settings_coordinator)
    await client.async_start()
    return client
