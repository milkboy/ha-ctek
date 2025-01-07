"""Sample API Client."""

from __future__ import annotations

import asyncio
import hashlib
import socket
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.util.dt import DEFAULT_TIME_ZONE

from .const import (
    CONTROL_URL,
    DEVICE_LIST_URL,
    LOGGER,
    OAUTH2_CLIENT_ID,
    OAUTH2_CLIENT_SECRET,
    OAUTH2_TOKEN_URL,
)

DEBUG = False


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


def _needs_refresh(response: aiohttp.ClientResponse) -> bool:
    """Check if we need to update tokens."""
    return response.status == 401


def _assert_success(response: dict) -> bool:
    """Check if we need to update tokens."""
    return response["data"]["success"]


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise CtekApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class CtekApiClient:
    """Sample API Client."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        refresh_token: str | None = None,
    ) -> None:
        """Sample API Client."""
        self._username = username
        self._password = password
        self._session = session
        self._access_token = None
        self._refresh_token = refresh_token
        self._cache = None
        self._cache_timestamp: datetime
        self._cache_duration = timedelta(minutes=1)

    async def refresh_access_token(self) -> None:
        """Refresh the access token."""
        if self._refresh_token is not None:
            LOGGER.debug("Trying to refresh access token using refresh token")
            try:
                res = await self._api_wrapper(
                    method="POST",
                    url=f"{OAUTH2_TOKEN_URL}",
                    data={
                        "client_id": OAUTH2_CLIENT_ID,
                        "client_secret": OAUTH2_CLIENT_SECRET,
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
                    "client_id": OAUTH2_CLIENT_ID,
                    "client_secret": OAUTH2_CLIENT_SECRET,
                    "grant_type": "password",
                    "password": self.hash_password(self._password),
                    "username": self._username,
                },
            )

            LOGGER.debug("Access token refreshed: %s", res["access_token"])
        self._access_token = res["access_token"]
        self._refresh_token = res["refresh_token"]

    async def start_charge(
        self, device_id: str, connector_id: int = 1, override_schedule: bool = True
    ) -> bool:
        """Set a configuration value."""
        LOGGER.debug(
            "Trying to start charge on %s (Override schedule: %s)",
            device_id,
            "true" if override_schedule else "false",
        )
        res = await self._api_wrapper(
            method="POST",
            url=CONTROL_URL,
            data={
                "connector_id": 1,
                "device_id": device_id,
                "instruction": "START_CHARGING",
            },
            auth=True,
        )
        LOGGER.debug(res["data"])
        _assert_success(res)
        if res["data"]["instruction"]["accepted"]:
            return True
        return False

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

    async def listDevices(self) -> dict:
        """
        Asynchronously lists the devices.

        Args:
            access_token (str): The access token for authentication.

        Returns:
            dict: The devices response received from the service.

        Raises:
            Exception: If the response status is not 200, an exception is raised with the status code.

        """
        current_time = datetime.now()
        if self._cache and (
            current_time - self._cache_timestamp < self._cache_duration
        ):
            return self._cache

        res = await self._api_wrapper(method="GET", url=DEVICE_LIST_URL, auth=True)

        self._cache = res
        self._cache_timestamp = datetime.now()

        return res

    async def get_configuration(self, device_id: str) -> dict:
        """Fetch data from the configs data."""
        url = f"https://iot.ctek.com/api/v3/device/configurations?deviceId={device_id}"
        return await self._api_wrapper(method="GET", url=url, auth=True)

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
        auth: bool = False,
    ) -> Any:
        """Get information from the API."""
        try:
            if headers is None:
                headers = {}
            headers.update(
                {
                    "Timezone": str(DEFAULT_TIME_ZONE),
                    "User-Agent": "CTEK App/4.0.3 (Android 11; OnePlus; ONEPLUS A3003; OnePlus3)",
                    "App-Profile": "ctek4",
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
                return await response.json()

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

    def hash_password(self, password: str) -> str:
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
