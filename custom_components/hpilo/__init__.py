"""The HPE iLO integration.

Sets up one IloCoordinator per config entry (i.e. per physical iLO/LO100
host) and forwards setup to the switch/sensor/button platforms, which each
read from that shared coordinator instead of talking to the host directly.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import IloCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HPE iLO from a config entry."""
    coordinator = IloCoordinator(hass, entry)
    await coordinator.async_setup_client()
    # Raises ConfigEntryNotReady on failure, which schedules an HA retry
    # instead of leaving the entry stuck in a failed setup state.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
