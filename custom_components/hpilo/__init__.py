"""The HPE iLO integration.

Sets up one IloCoordinator per config entry (i.e. per physical iLO host) and
forwards setup to the switch/sensor/button platforms, which each read from
that shared coordinator instead of talking to the iLO directly.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_LEGACY_SSL, DEFAULT_LEGACY_SSL, DOMAIN
from .coordinator import IloCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HPE iLO from a config entry."""
    coordinator = IloCoordinator(
        hass,
        entry,
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        legacy_ssl=entry.data.get(CONF_LEGACY_SSL, DEFAULT_LEGACY_SSL),
    )
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
