"""Set up some magic to make tests work."""

import logging

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

disable_loggers = ["homeassistant.loader"]


# This fixture enables loading of custom components
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: bool) -> None:  # noqa: FBT001
    """?."""
    return


def pytest_configure() -> None:
    """Disable some loggers to avoid extra output on tests."""
    for logger in disable_loggers:
        logging.getLogger(logger).disabled = True
