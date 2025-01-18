"""Test the config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.ctek.api import CtekApiClient
from custom_components.ctek.config_flow import CtekConfigFlowContext
from custom_components.ctek.const import DOMAIN


# This fixture is needed for testing config flows
@pytest.fixture(autouse=True)
def bypass_setup_fixture() -> Generator:
    """Prevent setup."""
    with patch(
        "custom_components.ctek.async_setup_entry",
        return_value=True,
    ):
        yield


#    with (
#        patch(
#            "custom_components.ctek.async_setup_entry",
#            return_value=True,
##        ),
#        patch(
#            "custom_components.ctek.async_setup",
#            return_value=True,
#        ),
#    ):
#        yield


class TestConfigFlow:
    """Test the config flow."""

    async def test_user_step(self, hass: HomeAssistant) -> None:
        """Test that config entry is created."""
        mock_client = AsyncMock(CtekApiClient)
        mock_client.list_devices.return_value = {
            "data": [{"device_id": "mockdev1", "device_alias": "Mock Alias"}]
        }
        """Test we get the form."""
        context: CtekConfigFlowContext = CtekConfigFlowContext(
            source=config_entries.SOURCE_USER,
            client=mock_client,
        )  # type: ignore[no-overload, unused-ignore]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context=context,
        )
        if result.get("type") != data_entry_flow.FlowResultType.FORM:
            pytest.fail(f"Expected form, got {result.get('type')}")
        if result.get("errors") != {}:
            pytest.fail(f"Expected no errors, got {result.get('errors')}")

        fake_credentials = AsyncMock(returns=True)

        # Test form submission with mock data
        with patch(
            "custom_components.ctek.config_flow.CtekConfigFlowHandler._test_credentials",
            new=fake_credentials,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "username": "test-username",
                    "password": "test-password",
                    "client_id": "foo",
                    "client_secret": "bar",
                },
            )
            await hass.async_block_till_done()

        if result2.get("type") != data_entry_flow.FlowResultType.FORM:
            pytest.fail(f"Expected form, got {result.get('type')}")
        if result2.get("step_id") != "done":
            pytest.fail(f"Expected step 'done', got {result.get('step_id')}")
        if result2.get("errors") != {}:
            pytest.fail(f"Expected no errors, got {result.get('errors')}")

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "device_id": "mockdev1",
            },
        )
        await hass.async_block_till_done()

        if result3.get("type") != data_entry_flow.FlowResultType.CREATE_ENTRY:
            pytest.fail(f"Expected create entry, got {result3.get('type')}")

        if result3.get("title") != "Ctek Mock Alias":
            pytest.fail(f"Expected 'Ctek Mock Alias', got {result3.get('title')}")

        expected = {
            "username": "test-username",
            "password": "test-password",
            "device_id": "mockdev1",
            "client_id": "foo",
            "client_secret": "bar",
        }
        if result3.get("data") != expected:
            pytest.fail(f"Expected '{expected}', got {result3.get('data')}")

    async def test_user_step_errors(self, hass: HomeAssistant) -> None:
        """Test we get the form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        if result.get("type") != data_entry_flow.FlowResultType.FORM:
            pytest.fail(f"Expected form, got {result.get('type')}")
        if result.get("errors") != {}:
            pytest.fail(f"Expected no errors, got {result.get('errors')}")

        # Test form submission with mock data
        with patch(
            "custom_components.ctek.config_flow.CtekConfigFlowHandler._test_credentials",
            return_value=True,
        ):
            with pytest.raises(data_entry_flow.InvalidData) as excinfo:
                await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    {
                        "username": "bar",
                    },
                )
            if str(excinfo.value.msg) != "Schema validation failed":
                pytest.fail("Invalid data was not detected")


class TestOptionsFlow:
    """Test options flow."""

    async def test_options_flow(self, hass: HomeAssistant) -> None:  # noqa: ARG002
        """FIXME."""
        pytest.skip("FIXME")
