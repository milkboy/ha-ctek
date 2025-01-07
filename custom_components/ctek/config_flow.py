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


class CtekConfigFlowContext(config_entries.ConfigFlowContext):
    """Set up the expected context."""

    username: str
    password: str
    device_id: str
    refresh_token: str
    devices: dict[Any, Any]
    client: CtekApiClient


class CtekConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow."""

    DOMAIN = DOMAIN
    VERSION = 2

    context: CtekConfigFlowContext

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
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
                },
            ),
            errors=_errors,
        )

    async def async_step_done(self, user_input=None) -> config_entries.ConfigFlowResult:
        """List detected devices."""
        errors: dict[str, Any] = {}
        if self.context.get("devices") is None:
            self.context["devices"] = await self.context["client"].listDevices()
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
                "refresh_token": self.context["client"].get_refresh_token(),
            },
        )

    async def async_step_reauth(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """FIXME Handle reauthorization with the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
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
                entry = await self.async_set_unique_id(self.context["unique_id"])
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        "refresh_token": self.context["client"].get_refresh_token(),
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
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
                    vol.Required(
                        CONF_PASSWORD,
                        default=(user_input or {}).get(CONF_PASSWORD, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(self, username: str, password: str) -> None:
        """Validate credentials."""
        client = CtekApiClient(
            username=username,
            password=password,
            session=async_create_clientsession(self.hass),
        )
        self.context["client"] = client
        await client.refresh_access_token()
