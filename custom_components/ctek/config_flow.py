"""Config flow for CTEK app integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify

from .api import (
    CtekApiClient,
    CtekApiClientAuthenticationError,
    CtekApiClientCommunicationError,
    CtekApiClientError,
)
from .const import DOMAIN, LOGGER


class CtekConfigFlowContext(config_entries.ConfigFlowContext):  # type: ignore[misc]
    """Set up the expected context."""

    username: str
    password: str
    client_id: str
    client_secret: str
    device_id: str
    refresh_token: str
    devices: dict[Any, Any]
    client: CtekApiClient


class CtekConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc,call-arg]
    """Config flow."""

    DOMAIN = DOMAIN
    VERSION = 3

    context: CtekConfigFlowContext

    async def async_step_user(  # type: ignore[no-untyped-def]
        self,
        user_input=None,  # noqa: ANN001
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    client_secret=user_input["client_secret"],
                    client_id=user_input["client_id"],
                )
            except CtekApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except CtekApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except CtekApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                self.context["username"] = user_input[CONF_USERNAME]
                self.context["password"] = user_input[CONF_PASSWORD]
                self.context["client_id"] = user_input["client_id"]
                self.context["client_secret"] = user_input["client_secret"]
                return await self.async_step_done()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Required(
                        "client_id",
                        default=(user_input or {}).get("client_id", vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        "client_secret",
                        default=(user_input or {}).get("client_secret", vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def async_step_done(self, user_input=None) -> config_entries.ConfigFlowResult:  # type: ignore[no-untyped-def] # noqa: ANN001
        """List detected devices."""
        errors: dict[str, Any] = {}
        if self.context.get("devices") is None:
            self.context["devices"] = await self.context["client"].list_devices()
        devices = {
            device["device_id"]: device["device_id"]
            + " ("
            + device.get("device_alias")
            + ")"
            for device in self.context["devices"]["data"]
        }

        if user_input is None:
            return self.async_show_form(
                step_id="done",
                data_schema=vol.Schema({vol.Required("device_id"): vol.In(devices)}),
                errors=errors,
            )

        await self.async_set_unique_id(unique_id=slugify(user_input[CONF_DEVICE_ID]))
        # Only one integration per device
        self._abort_if_unique_id_configured()

        device_alias = next(
            (
                device.get("device_alias")
                for device in self.context["devices"]["data"]
                if device["device_id"] == user_input[CONF_DEVICE_ID]
            ),
            None,
        )

        return self.async_create_entry(
            title=f"Ctek {device_alias or user_input[CONF_DEVICE_ID]}",
            data={
                CONF_USERNAME: self.context[CONF_USERNAME],
                CONF_PASSWORD: self.context[CONF_PASSWORD],
                CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                "client_id": self.context["client_id"],
                "client_secret": self.context["client_secret"],
                "refresh_token": self.context["client"].get_refresh_token(),
            },
        )

    async def _test_credentials(
        self, username: str, password: str, client_id: str, client_secret: str
    ) -> None:
        """Validate credentials."""
        client = CtekApiClient(
            username=username,
            password=password,
            client_secret=client_secret,
            client_id=client_id,
            session=async_create_clientsession(self.hass),
        )
        self.context["client"] = client
        await client.refresh_access_token()
