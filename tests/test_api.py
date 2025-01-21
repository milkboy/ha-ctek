from unittest.mock import MagicMock

import aiohttp
import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant

from custom_components.ctek.api import CtekApiClient
from custom_components.ctek.const import OAUTH2_TOKEN_URL


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
async def test_login(api_client):
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
