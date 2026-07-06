"""DataUpdateCoordinator for HPE iLO / Lights-Out 100 (LO100) hosts.

All client calls are synchronous network I/O, so every call into the
PowerControlClient is routed through `hass.async_add_executor_job` to keep
the event loop unblocked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .clients import AuthenticationFailed, PowerControlClient, build_client
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class IloData:
    """A single poll's worth of state, as read from one host."""

    power_state: str  # "ON" or "OFF"
    power_watts: (
        float | None
    )  # None if the connection type/firmware doesn't expose readings


class IloCoordinator(DataUpdateCoordinator[IloData]):
    """Polls a single iLO/LO100 host for power state and power draw.

    One coordinator (and one client/session) per config entry, shared by all
    entities of that device so we only log in once per poll cycle instead of
    once per entity.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        host = entry.data[CONF_HOST]
        super().__init__(
            hass,
            _LOGGER,
            name=f"hpilo-{host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.host = host
        self._client: PowerControlClient | None = None

    async def async_setup_client(self) -> None:
        """Build the underlying client. Must be awaited before the first
        refresh (see __init__.py).

        This can't happen in __init__: IpmiClient's constructor performs
        blocking network I/O (pyghmi logs in synchronously), and __init__
        runs directly on the event loop. Building it there would freeze
        all of Home Assistant while it connects, not just this integration.
        """
        self._client = await self.hass.async_add_executor_job(
            build_client, self.entry.data
        )

    def _fetch(self) -> IloData:
        """Blocking: read power state and power draw. Runs in the executor."""
        assert self._client is not None, "async_setup_client() wasn't awaited"
        power_state = self._client.get_power_state()
        watts = self._client.get_power_watts()
        return IloData(power_state=power_state, power_watts=watts)

    async def _async_update_data(self) -> IloData:
        """Entry point called by the coordinator on each poll interval."""
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except AuthenticationFailed as err:
            raise ConfigEntryNotReady(f"Login to {self.host} failed") from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with {self.host}: {err}") from err

    def set_power(self, on: bool) -> None:
        """Force the host power state on/off (blocking; call via executor).

        This is a hard power control command (like holding the physical
        power button until it responds), not a graceful OS shutdown request.
        """
        self._client.set_power(on)

    def press_power_button(self) -> None:
        """Momentarily press the virtual power button (blocking; call via executor).

        Equivalent to a quick tap of the physical power button: triggers a
        graceful ACPI shutdown/wake in a running OS, unlike `set_power()`.
        """
        self._client.press_power_button()
