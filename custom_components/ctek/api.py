"""Sample API Client."""

from __future__ import annotations

import asyncio
import hashlib
import socket
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.dt import DEFAULT_TIME_ZONE

from .const import (
    _LOGGER,
    APP_PROFILE,
    CONTROL_URL,
    DEVICE_LIST_URL,
    DOMAIN,
    OAUTH2_TOKEN_URL,
    USER_AGENT,
    CtekApiClientAuthenticationError,
    CtekApiClientCommunicationError,
    CtekApiClientError,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import InstructionResponseType

DEBUG = False
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
LOGGER = _LOGGER.getChild("api")


def _needs_refresh(response: aiohttp.ClientResponse) -> bool:
    return bool(response.status == HTTP_UNAUTHORIZED)


def _assert_success(response: dict) -> bool:
    """Check if we need to update tokens."""
    val: bool = response.get("data", {}).get("success", False)
    if val is False:
        LOGGER.error(response)
        msg = "Operation failed"
        _raise_home_assistant_error(msg)
    return True


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
        msg = "Invalid credentials"
        raise CtekApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


def _raise_home_assistant_error(msg: str) -> None:
    """Raise HomeAssistantError with the given message."""
    raise HomeAssistantError(msg)


class CtekApiClient:
    """Sample API Client."""

    _cache: dict | None

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
        session: aiohttp.ClientSession,
        refresh_token: str | None = None,
    ) -> None:
        """Sample API Client."""
        self.hass = hass
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session
        self._access_token = None
        self._refresh_token = refresh_token

    async def refresh_access_token(self) -> None:
        """Refresh the access token."""
        if self._refresh_token is not None:
            LOGGER.debug("Trying to refresh access token using refresh token")
            try:
                res = await self._api_wrapper(
                    method="POST",
                    url=f"{OAUTH2_TOKEN_URL}",
                    data={
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": self._refresh_token,
                    },
                    auth=False,
                )
                LOGGER.debug("Access token refreshed using refresh token")
            except CtekApiClientCommunicationError:
                self._refresh_token = None

        if self._refresh_token is None:
            LOGGER.info("No refresh token available, doing login")
            res = await self._api_wrapper(
                method="POST",
                url=f"{OAUTH2_TOKEN_URL}",
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "password",
                    "password": self.hash_password(self._password),
                    "username": self._username,
                },
            )

            LOGGER.debug("Access token refreshed: %s", res["access_token"])
        if self._access_token != res["access_token"]:
            self.hass.bus.fire(
                event_type=f"{DOMAIN}_tokens_updated",
                event_data={
                    "access": res["access_token"],
                    "refresh": res["refresh_token"],
                },
            )
        self._access_token = res["access_token"]
        self._refresh_token = res["refresh_token"]

    async def start_charge(
        self,
        *,
        device_id: str,
        connector_id: int = 1,
        override_schedule: bool = True,
        resume_charging: bool = False,
    ) -> InstructionResponseType:
        """Set a configuration value."""
        LOGGER.debug(
            "Trying to start charge on %s (Resume: %s, Override schedule: %s)",
            device_id,
            "true" if resume_charging else "false",
            "true" if override_schedule else "false",
        )
        # Might additionally need START_CHARGING if a schedule is active
        res = await self._api_wrapper(
            method="POST",
            url=CONTROL_URL,
            data={
                "connector_id": connector_id,
                "device_id": device_id,
                "instruction": "RESUME_CHARGING"
                if resume_charging
                else "START_TRANSACTION",
            },
            auth=True,
        )
        if res.get("data", {}).get("error_code", None) is not None:
            error_code = res.get("data", {}).get("error_code", None)
            error_message = res.get("data", {}).get("error_message", None)
            msg = f"Failed to start charging: {error_code}: {error_message}"
            raise HomeAssistantError(msg)
        LOGGER.debug(res["data"])
        # _assert_success(res)
        return self.parse_instruction_response(res)

    async def stop_charge(
        self,
        *,
        device_id: str,
        connector_id: int = 1,
        resume_schedule: bool = False,
    ) -> InstructionResponseType:
        """Set a configuration value."""
        LOGGER.debug(
            "Trying to stop charge on %s (Resume schedule: %s)",
            device_id,
            "true" if resume_schedule else "false",
        )
        res = await self._api_wrapper(
            method="POST",
            url=CONTROL_URL,
            data={
                "connector_id": connector_id,
                "device_id": device_id,
                "instruction": "RESUME_SCHEDULE"
                if resume_schedule
                else "PAUSE_CHARGING",
            },
            auth=True,
        )
        if res.get("data", {}).get("error_code", None) is not None:
            error_code = res.get("data", {}).get("error_code", None)
            error_message = res.get("data", {}).get("error_message", None)
            msg = f"Failed to stop charging: {error_code}: {error_message}"
            raise HomeAssistantError(msg)
        LOGGER.debug(res["data"])
        # _assert_success(res)
        return self.parse_instruction_response(res["data"])

    async def send_command(
        self, *, device_id: str, command: str
    ) -> InstructionResponseType:
        """Send arbitrary command."""
        LOGGER.debug(
            "Trying to send command %s to charger %s)",
            command,
            device_id,
        )
        try:
            res = await self._api_wrapper(
                method="POST",
                url=CONTROL_URL,
                data={"device_id": device_id, "instruction": command},
                # data={
                #    "connector_id": connector_id,
                #    "device_id": device_id,
                #    "instruction": "RESUME_SCHEDULE"
                #    if resume_schedule
                #    else "PAUSE_CHARGING",
                # },
                auth=True,
            )
            if res.get("data", {}).get("error_code", None) is not None:
                error_code = res.get("data", {}).get("error_code", None)
                error_message = res.get("data", {}).get("error_message", None)
                msg = f"Failed to stop charging: {error_code}: {error_message}"
                _raise_home_assistant_error(msg)
            LOGGER.debug(res["data"])
            # _assert_success(res)
            return self.parse_instruction_response(res["data"])
        except Exception:
            LOGGER.exception("Failed to send command")
            raise

    async def set_config(self, device_id: str, name: str, value: str) -> None:
        """Set a configuration value."""
        LOGGER.debug("Posting new config: %s = %s", name, value)
        if DEBUG:
            return
        res = await self._api_wrapper(
            method="POST",
            url=f"https://iot.ctek.com/api/v3/device/configuration?deviceId={device_id}&pushToDevice=true&key={name}&value={value}",
            auth=True,
        )
        LOGGER.debug(res["data"])
        _assert_success(res)

    async def list_devices(self) -> dict:
        """
        Asynchronously lists the devices.

        Args:
            access_token (str): The access token for authentication.

        Returns:
            dict: The devices response received from the service.

        Raises:
            Exception: If the response status is not 200, an exception is raised with
              the status code.

        """
        return await self._api_wrapper(method="GET", url=DEVICE_LIST_URL, auth=True)

    async def get_configuration(self, device_id: str) -> dict:
        """Fetch data from the configs data."""
        url = f"https://iot.ctek.com/api/v3/device/configurations?deviceId={device_id}"
        return await self._api_wrapper(method="GET", url=url, auth=True)

    async def _api_wrapper(
        self,
        *,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
        auth: bool = False,
    ) -> dict:
        """Get information from the API."""
        try:
            if headers is None:
                headers = {}
            headers.update(
                {
                    "Timezone": str(DEFAULT_TIME_ZONE),
                    "User-Agent": USER_AGENT,
                    "App-Profile": APP_PROFILE,
                }
            )
            if auth:
                if self._access_token is None:
                    await self.refresh_access_token()
                headers.update({"Authorization": f"Bearer {self._access_token}"})
            async with asyncio.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                if _needs_refresh(response):
                    LOGGER.debug("Access token expired? refreshing")
                    await self.refresh_access_token()
                    response = await self._session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=data,
                    )
                _verify_response_or_raise(response)
                return await response.json()  # type: ignore[no-any-return]

        except (TimeoutError, asyncio.CancelledError) as exception:
            msg = f"Timeout error during {method} - {exception}"
            raise CtekApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error during {method} - {exception}"
            raise CtekApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise CtekApiClientError(
                msg,
            ) from exception

    def hash_password(self, password: str | None) -> str:
        """Hash the password using SHA-256."""
        if password is None:
            err = "Password cannot be null"
            raise ValueError(err)

        # Create a SHA-256 hash of the password
        hash_object = hashlib.sha256(password.encode())
        return hash_object.hexdigest()

    def get_access_token(self) -> str | None:
        """Get the access token."""
        return self._access_token

    def get_refresh_token(self) -> str | None:
        """Get the access token."""
        return self._refresh_token

    def parse_instruction_response(self, res: dict) -> InstructionResponseType:
        """
        Parse the instruction response from a given dictionary.

        Args:
            res (dict): The response dictionary containing instruction data.

        Returns:
            InstructionResponseType: A dictionary containing parsed instruction
              response data.

        """
        data: InstructionResponseType = {
            "device_id": res.get("device_id", ""),
            "information": res.get("information", {}),
            "instruction": {
                "connector_id": res.get("instruction", {}).get("connector_id"),
                "device_id": res.get("instruction", {}).get("device_id"),
                "info": {
                    "firmware": res.get("instruction", {})
                    .get("info", {})
                    .get("firmware"),
                    "id": res.get("instruction", {}).get("info", {}).get("id"),
                    "key": res.get("instruction", {}).get("info", {}).get("key"),
                    "units": res.get("instruction", {}).get("info", {}).get("units"),
                    "value": res.get("instruction", {}).get("info", {}).get("value"),
                },
                "id": res.get("instruction", {}).get("id"),
                "instruction": res.get("instruction", {}).get("instruction"),
                "timeout": res.get("instruction", {}).get("timeout"),
                "transaction_id": res.get("instruction", {}).get("transaction_id"),
                "user_id": res.get("instruction", {}).get("user_id"),
                "user_id_is_owner": res.get("instruction", {}).get("user_id_is_owner"),
            },
            "ocpp": {},
            "accepted": res.get("accepted"),
        }

        return data
