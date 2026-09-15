"""Constants for the Tapo Connect integration."""

DOMAIN = "tapo_camera_local"
MANUFACTURER = "TP-Link"
VERSION = "0.11.2"

CONF_ACCOUNT_HOST = "account_email"
CONF_ACCOUNT_PASSWORD = "account_password"
CONF_STREAM_URL = "stream_url"
CONF_TAPO_CONTROL_ENTRY = "tapo_control_entry_id"
CONF_USE_CLOUD = "use_cloud"
CONF_CONNECTION_MODE = "connection_mode"
CONF_AUTH_MODE = "auth_mode"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SUB_STREAM_URL = "sub_stream_url"

MODE_STANDALONE = "standalone"
MODE_TAPO_CONTROL = "tapo_control"
MODE_CLOUD_NOTIFICATIONS = "cloud_notifications"

DEFAULT_NAME = "Tapo Connect"
DEFAULT_USERNAME = "admin"
DEFAULT_PORT = 443
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_STREAM_PATHS = ("stream1", "stream2")

# Cloud face notifications: fast polling with an idle back-off, since the only
# verified delivery channel is the app notification API (no push in HA).
DEFAULT_CLOUD_SCAN_INTERVAL = 5
MIN_CLOUD_SCAN_INTERVAL = 5
MAX_CLOUD_SCAN_INTERVAL = 300
CLOUD_IDLE_INTERVAL = 30
CLOUD_IDLE_AFTER = 600
CLOUD_EVENT_WINDOW = 120

ATTR_DEVICE_INFO = "device_info"
