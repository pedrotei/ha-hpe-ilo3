"""Virtual power button for HPE iLO managed hosts."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IloCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the iLO virtual power button."""
    coordinator: IloCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IloPowerButton(coordinator, entry)])


class IloPowerButton(CoordinatorEntity[IloCoordinator], ButtonEntity):
    """A momentary press of the server's physical power button, via iLO.

    Unlike the power switch (which forces the power state), this requests a
    graceful ACPI shutdown/wake from the running OS — the same as someone
    briefly tapping the physical button on the chassis.
    """

    _attr_has_entity_name = True
    _attr_name = "Power button"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: IloCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_power_button"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.coordinator.press_power_button)
        await self.coordinator.async_request_refresh()
