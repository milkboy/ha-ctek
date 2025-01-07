"""Tests for the config flow."""

from unittest.mock import ANY, AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from custom_components.ctek.const import DOMAIN


async def test_flow_user_init(hass: HomeAssistant):
    """Test the initialization of the form in the first step of the config flow."""
    with patch("homeassistant.loader.async_get_integration", return_value=AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        expected = {
            "data_schema": ANY,
            "description_placeholders": None,
            "errors": {},
            "flow_id": ANY,
            "handler": DOMAIN,
            "step_id": "user",
            "type": "form",
        }
        assert expected == result
