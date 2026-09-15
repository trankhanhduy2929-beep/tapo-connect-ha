"""Native camera client and sanitized exceptions for Home Assistant."""

from .tapo_proto.client import (
    TapoAuthError,
    TapoCamera,
    TapoConnectionError,
    TapoProtocolError,
    TapoRequestError,
    TapoSecureTransportRequired,
)
from .tapo_proto.pytapo_client import PytapoCamera

__all__ = [
    "PytapoCamera",
    "TapoAuthError", "TapoCamera", "TapoConnectionError", "TapoProtocolError",
    "TapoRequestError", "TapoSecureTransportRequired",
]
