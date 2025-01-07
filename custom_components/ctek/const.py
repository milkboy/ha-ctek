"""Constants for ctek."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "ctek"

API_HOST = "https://iot.ctek.com"

OAUTH2_TOKEN_URL = "https://iot.ctek.com/oauth/token"
OAUTH2_CLIENT_ID = "android_nS865khcg3ZWiBWF"
OAUTH2_CLIENT_SECRET = "secret_@PhIL@gBdV<tpqBW7^2tQR8Yrq8;mvm_"

DEVICE_LIST_URL = "https://iot.ctek.com/api/v3/device/list"
CONTROL_URL = "https://iot.ctek.com/api/v3/device/control"

WS_USER_AGENT = "okhttp/4.12.0"
WS_URL = "wss://iot.ctek.com/api/v1/socket/devices/transaction/"
