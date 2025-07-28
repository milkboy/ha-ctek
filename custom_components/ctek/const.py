"""Constants for ctek."""

from logging import Logger, getLogger

BASE_LOGGER: Logger = getLogger(__package__)

DOMAIN = "ctek"

API_HOST = "https://iot.ctek.com"

OAUTH2_TOKEN_URL = "https://iot.ctek.com/oauth/token"  # noqa: S105 This is not a password :lol:

DEVICE_LIST_URL = "https://iot.ctek.com/api/v3/device/list"
CONTROL_URL = "https://iot.ctek.com/api/v3/device/control"

WS_USER_AGENT = "okhttp/4.12.0"
WS_URL = "wss://iot.ctek.com/api/v1/socket/devices/transaction/"

VERSION = "0.0.9"


class CtekApiClientError(Exception):
    """Exception to indicate a general API error."""


class CtekApiClientCommunicationError(
    CtekApiClientError,
):
    """Exception to indicate a communication error."""


class CtekApiClientAuthenticationError(
    CtekApiClientError,
):
    """Exception to indicate an authentication error."""


class CtekError(Exception):
    """Custom exception."""
