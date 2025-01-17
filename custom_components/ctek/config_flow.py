"""Config flow for CTEK app integration."""

from __future__ import annotations

from random import choice, randint
from typing import TYPE_CHECKING, Any

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
from .const import _LOGGER as LOGGER
from .const import DOMAIN
from .entity import callback

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

devs = [
    "Redmi Note 9 Pro",
    "OnePlus; ONEPLUS A3003; OnePlus3",
    "Huawei; MAR-LX1A; Huawei P30 lite",
    "Google",
    "Google; Pixel 7",
    "SM-G960U",
    "K",
    "SAMSUNG SM-A536B",
]

OPTIONS_SCHEMA = vol.Schema({vol.Required("car_quirks"): bool})
APP_PROFILE = "ctek4"
USER_AGENT = f"CTEK App/4.0.3 (Android {randint(7, 14)}; {choice(devs)})"  # noqa: S311


class CtekConfigFlowContext(config_entries.ConfigFlowContext):
    """Set up the typed context."""

    username: str
    password: str
    client_id: str
    client_secret: str
    device_id: str
    devices: dict[Any, Any]
    client: CtekApiClient


class CtekConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Config flow."""

    DOMAIN = DOMAIN
    VERSION = 3
    MINOR_VERSION = 2

    context: CtekConfigFlowContext

    async def async_step_user(  # type:ignore[no-untyped-def]
        self,
        user_input=None,  # noqa: ANN001
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    self.hass,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    client_secret=user_input["client_secret"],
                    client_id=user_input["client_id"],
                    app_profile=APP_PROFILE,
                    user_agent=USER_AGENT,
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
            },
        )

    async def _test_credentials(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
        user_agent: str,
        app_profile: str,
    ) -> None:
        """Validate credentials."""
        client = CtekApiClient(
            hass=hass,
            username=username,
            password=password,
            client_secret=client_secret,
            client_id=client_id,
            session=async_create_clientsession(self.hass),
            user_agent=user_agent,
            app_profile=app_profile,
        )
        self.context["client"] = client
        await client.refresh_access_token()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,  # noqa: ARG004
    ) -> CtekOptionsFlowHandler:
        """Create the options flow."""
        return CtekOptionsFlowHandler()


class CtekOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for CTEK."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        log_levels = [
            ("ERROR", "error"),
            ("WARN", "warning"),
            ("INFO", "info"),
            ("DEBUG", "debug"),
        ]
        options = self.config_entry.options

        if user_input is not None:
            if options.get("enable_quirks", False):
                return await self.async_step_quirks()

            return self.async_create_entry(title="", data=user_input)

        options_schema: vol.Schema = vol.Schema(
            {
                vol.Required(
                    "log_level",
                    default=options.get("log_level", "INFO"),
                ): selector.SelectSelector(
                    config=selector.SelectSelectorConfig(
                        translation_key="log_levels",
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in log_levels
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    "user_agent",
                    default=options.get("user_agent", USER_AGENT),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
                vol.Optional(
                    "app_profile",
                    default=options.get("app_profile", APP_PROFILE),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
                vol.Optional(
                    "enable_quirks",
                    default=options.get("enable_quirks", False),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)

    async def async_step_quirks(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the quirks options."""
        options = self.config_entry.options

        if user_input is not None:
            full_data = {**options, "enable_quirks": True, **user_input}
            return self.async_create_entry(title="", data=full_data)

        options_schema: vol.Schema = vol.Schema(
            {
                vol.Required(
                    "start_charge_min_current",
                    default=options.get(
                        "start_charge_min_current",
                        options.get("start_charge_min_current"),
                    ),
                ): bool,
                vol.Required(
                    "reboot_station_if_start_fails",
                    default=options.get(
                        "reboot_station_if_start_fails",
                        options.get("reboot_station_if_start_fails", False),
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="quirks", data_schema=options_schema)
