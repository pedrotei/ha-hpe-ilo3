"""DataUpdateCoordinator for HPE iLO.

All hpilo calls are synchronous network I/O (RIBCL/XML over HTTPS), so every
call into the `hpilo.Ilo` client is routed through
`hass.async_add_executor_job` to keep the event loop unblocked.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

import hpilo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_TIMEOUT
from .ssl_helper import build_legacy_ilo_ssl_context

_LOGGER = logging.getLogger(__name__)


@dataclass
class IloData:
    """A single poll's worth of state, as read from one iLO."""

    power_state: str  # "ON" or "OFF", verbatim from hpilo.get_host_power_status()
    power_watts: float | None  # None if the firmware doesn't expose readings


class IloCoordinator(DataUpdateCoordinator[IloData]):
    """Polls a single iLO host for power state and power draw.

    One coordinator (and one `hpilo.Ilo` client/session) per config entry,
    shared by all entities of that device so we only log in to the iLO once
    per poll cycle instead of once per entity.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        username: str,
        password: str,
        legacy_ssl: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"hpilo-{host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.host = host
        # legacy_ssl=False lets users on newer iLO generations (4+) use a
        # normal, verified TLS connection instead of the iLO 3 workarounds.
        ssl_context = build_legacy_ilo_ssl_context() if legacy_ssl else None
        self._ilo = hpilo.Ilo(
            host,
            login=username,
            password=password,
            timeout=DEFAULT_TIMEOUT,
            ssl_context=ssl_context,
        )

    @property
    def ilo(self) -> hpilo.Ilo:
        """Expose the underlying client for entities that need direct access."""
        return self._ilo

    def _fetch(self) -> IloData:
        """Blocking: read power state and power draw. Runs in the executor."""
        power_state = self._ilo.get_host_power_status()
        watts = None
        try:
            readings = self._ilo.get_power_readings()
            reading = readings.get("present_power_reading")
            # hpilo returns (value, unit) tuples, e.g. (123, "Watts"), so pull
            # out just the number for the sensor.
            watts = reading[0] if isinstance(reading, tuple) else reading
        except Exception:  # noqa: BLE001 - not all iLO models/firmwares expose this
            _LOGGER.debug("get_power_readings not available on %s", self.host, exc_info=True)
        return IloData(power_state=power_state, power_watts=watts)

    async def _async_update_data(self) -> IloData:
        """Entry point called by the coordinator on each poll interval."""
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except hpilo.IloLoginFailed as err:
            raise ConfigEntryNotReady(f"Login to {self.host} failed") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error communicating with {self.host}: {err}") from err

    def set_power(self, on: bool) -> None:
        """Force the host power state on/off (blocking; call via executor).

        This is a hard power control command (like holding the physical
        power button until it responds), not a graceful OS shutdown request.
        """
        self._ilo.set_host_power(on)

    def press_power_button(self) -> None:
        """Momentarily press the virtual power button (blocking; call via executor).

        Equivalent to a quick tap of the physical power button: triggers a
        graceful ACPI shutdown/wake in a running OS, unlike `set_power()`.
        """
        self._ilo.press_pwr_btn()
