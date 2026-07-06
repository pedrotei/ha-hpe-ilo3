"""Power switch for HPE iLO managed hosts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Set up the iLO power switch."""
    coordinator: IloCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IloPowerSwitch(coordinator, entry)])


class IloPowerSwitch(CoordinatorEntity[IloCoordinator], SwitchEntity):
    """Represents the managed server's power state, controlled via iLO.

    Turning this on/off forces the power state directly (equivalent to
    holding the physical power button), it does not ask a running OS to
    shut down gracefully. For a graceful ACPI power event, use the
    "Power button" button entity instead.
    """

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_icon = "mdi:server"

    def __init__(self, coordinator: IloCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_power"
        # One device per config entry; switch/sensor/button all attach here
        # so they show up grouped together under a single iLO in the UI.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="HPE",
            model="iLO",
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.power_state == "ON"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.coordinator.set_power, True)
        # Request an immediate refresh so the UI reflects the new state
        # right away instead of waiting for the next poll interval.
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self.coordinator.set_power, False)
        await self.coordinator.async_request_refresh()
