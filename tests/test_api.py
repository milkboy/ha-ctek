import logging
from unittest.mock import MagicMock

import aiohttp
import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant

from custom_components.ctek.api import CtekApiClient
from custom_components.ctek.const import (
    CONTROL_URL,
    OAUTH2_TOKEN_URL,
    CtekApiClientAuthenticationError,
)


@pytest.fixture
def api_client(hass: HomeAssistant):
    return CtekApiClient(
        hass=hass,
        client_id="test_id",
        client_secret="test_secret",
        username="test_user",
        password="test_pass",
        app_profile="",
        user_agent="",
        session=MagicMock(),
    )


@pytest.mark.asyncio
async def test_login(api_client, caplog):
    caplog.set_level(logging.WARNING, logger="custom_components")
    # Mock the response of the POST request
    with aioresponses() as m:
        m.post(
            OAUTH2_TOKEN_URL,
            payload={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
            },
        )
        async with aiohttp.ClientSession() as s:
            api_client._access_token = None
            api_client._refresh_token = None
            api_client._set_session(s)
            await api_client.refresh_access_token()

    # Assertions
    assert api_client.get_access_token() == "new_access_token"
    assert api_client.get_refresh_token() == "new_refresh_token"


@pytest.mark.asyncio
async def test_refresh_access_token(api_client):
    # Mock the response of the POST request
    with aioresponses() as m:
        m.post(
            OAUTH2_TOKEN_URL,
            payload={
                "access_token": "new_access_token1",
                "refresh_token": "new_refresh_token1",
            },
        )
        async with aiohttp.ClientSession() as s:
            api_client._access_token = None
            api_client._refresh_token = "foo bar"
            api_client._set_session(s)
            await api_client.refresh_access_token()

    # Assertions
    assert api_client.get_access_token() == "new_access_token1"
    assert api_client.get_refresh_token() == "new_refresh_token1"


def test_get_access_token(api_client):
    # Set a known access token
    api_client._access_token = "test_access_token"

    # Call the method
    access_token = api_client.get_access_token()

    # Assertions
    assert access_token == "test_access_token"


def test_get_refresh_token(api_client):
    # Set a known refresh token
    api_client._refresh_token = "test_refresh_token"

    # Call the method
    refresh_token = api_client.get_refresh_token()

    # Assertions
    assert refresh_token == "test_refresh_token"


@pytest.mark.asyncio
async def test_refresh_token_rejected_falls_back_to_password_login(api_client, caplog):
    """If the refresh token is rejected with 401, fall back to password login."""
    caplog.set_level(logging.WARNING, logger="custom_components")
    with aioresponses() as m:
        # First call (refresh token attempt) returns 401
        m.post(OAUTH2_TOKEN_URL, status=401)
        # Second call (password login) succeeds
        m.post(
            OAUTH2_TOKEN_URL,
            payload={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
            },
        )
        async with aiohttp.ClientSession() as s:
            api_client._refresh_token = "expired_refresh_token"
            api_client._set_session(s)
            await api_client.refresh_access_token()

    assert api_client.get_access_token() == "new_access_token"
    assert api_client.get_refresh_token() == "new_refresh_token"
    assert "Refresh token rejected" in caplog.text


@pytest.mark.asyncio
async def test_api_wrapper_retries_with_new_token_on_401(api_client):
    """After a 401, the retry request must use the refreshed token in headers."""
    with aioresponses() as m:
        # First request returns 401
        m.post(CONTROL_URL, status=401)
        # Token refresh succeeds
        m.post(
            OAUTH2_TOKEN_URL,
            payload={
                "access_token": "refreshed_token",
                "refresh_token": "refreshed_refresh_token",
            },
        )
        # Retry with new token succeeds
        m.post(
            CONTROL_URL,
            payload={"data": {"instruction_id": "abc", "status": "ok"}},
        )
        async with aiohttp.ClientSession() as s:
            api_client._access_token = "old_token"
            api_client._refresh_token = None
            api_client._set_session(s)
            await api_client.send_command(device_id="dev1", command="REBOOT")

    assert api_client.get_access_token() == "refreshed_token"


@pytest.mark.asyncio
async def test_auth_error_propagates_from_api_wrapper(api_client):
    """CtekApiClientAuthenticationError must not be swallowed as a generic error."""
    with aioresponses() as m:
        # First request 401 triggers refresh, refresh also fails with 401
        m.post(CONTROL_URL, status=401)
        m.post(OAUTH2_TOKEN_URL, status=401)
        async with aiohttp.ClientSession() as s:
            api_client._access_token = "old_token"
            api_client._refresh_token = None
            api_client._set_session(s)
            with pytest.raises(CtekApiClientAuthenticationError):
                await api_client.send_command(device_id="dev1", command="REBOOT")
