"""Config flow for HPE iLO.

Single step: host/username/password/legacy_ssl, validated by actually
logging in and reading power status before the entry is created. There's no
separate options flow - re-adding the integration for the same host (its
unique_id) is how you'd change settings.
"""

from __future__ import annotations

import logging
from typing import Any

import hpilo
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_LEGACY_SSL, DEFAULT_LEGACY_SSL, DEFAULT_TIMEOUT, DOMAIN
from .ssl_helper import build_legacy_ilo_ssl_context

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_LEGACY_SSL, default=DEFAULT_LEGACY_SSL): bool,
    }
)


def _test_connection(host: str, username: str, password: str, legacy_ssl: bool) -> str:
    """Log in and fetch power status; runs in the executor (blocking I/O).

    Returns the power state on success purely so the caller has proof the
    round trip worked; raises hpilo's own exceptions on failure, which
    async_step_user maps to config-flow error codes.
    """
    ssl_context = build_legacy_ilo_ssl_context() if legacy_ssl else None
    ilo = hpilo.Ilo(
        host,
        login=username,
        password=password,
        timeout=DEFAULT_TIMEOUT,
        ssl_context=ssl_context,
    )
    return ilo.get_host_power_status()


class HpiloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HPE iLO."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            # Host is the unique_id: one config entry per physical iLO.
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(
                    _test_connection,
                    host,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_LEGACY_SSL],
                )
            except hpilo.IloLoginFailed:
                errors["base"] = "invalid_auth"
            except (hpilo.IloCommunicationError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to iLO")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=host, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
