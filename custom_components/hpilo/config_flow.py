"""Config flow for HPE iLO / Lights-Out 100 (LO100).

Two connection types, picked via a menu step, each validated by actually
logging in and reading power status before the entry is created:
- "ilo": real HPE iLO (2 and up), over RIBCL/XML.
- "ipmi": HPE Lights-Out 100, over plain IPMI 2.0 (e.g. the DL160 G6, which
  never had a real iLO at all).

There's no separate options flow - re-adding the integration for the same
host (its unique_id) is how you'd change settings.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .clients import AuthenticationFailed, ConnectionFailed, build_client
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_LEGACY_SSL,
    CONNECTION_TYPE_ILO,
    CONNECTION_TYPE_IPMI,
    DEFAULT_LEGACY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_ILO_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_LEGACY_SSL, default=DEFAULT_LEGACY_SSL): bool,
    }
)

STEP_IPMI_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _test_connection(entry_data: dict[str, Any]) -> str:
    """Log in and fetch power status; runs in the executor (blocking I/O).

    Returns the power state on success purely so the caller has proof the
    round trip worked; raises on failure, which async_step_* maps to
    config-flow error codes.

    This client is discarded right after (the coordinator builds its own
    long-lived one on setup), so it's always closed here - notably, LO100's
    tiny embedded BMC only supports a handful of concurrent IPMI sessions,
    and repeated connection tests that never close their session can
    exhaust that pool and lock out real use for a while.
    """
    client = build_client(entry_data)
    try:
        return client.get_power_state()
    finally:
        client.close()


class HpiloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HPE iLO / LO100."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step: pick which protocol this host actually speaks."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["ilo", "ipmi"],
        )

    async def async_step_ilo(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Connect/validate a real iLO host."""
        return await self._async_step_connection(
            user_input,
            step_id="ilo",
            connection_type=CONNECTION_TYPE_ILO,
            schema=STEP_ILO_DATA_SCHEMA,
        )

    async def async_step_ipmi(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Connect/validate a Lights-Out 100 (LO100) host."""
        return await self._async_step_connection(
            user_input,
            step_id="ipmi",
            connection_type=CONNECTION_TYPE_IPMI,
            schema=STEP_IPMI_DATA_SCHEMA,
        )

    async def _async_step_connection(
        self,
        user_input: dict[str, Any] | None,
        *,
        step_id: str,
        connection_type: str,
        schema: vol.Schema,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            # Host is the unique_id: one config entry per physical host.
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            entry_data = {**user_input, CONF_CONNECTION_TYPE: connection_type}
            try:
                await self.hass.async_add_executor_job(_test_connection, entry_data)
            except AuthenticationFailed as err:
                _LOGGER.info("Authentication to %s failed: %s", host, err)
                errors["base"] = "invalid_auth"
            except (ConnectionFailed, OSError, TimeoutError) as err:
                _LOGGER.info("Could not connect to %s: %s", host, err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to %s", host)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=host, data=entry_data)

        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)
