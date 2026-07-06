"""Power consumption sensor for HPE iLO managed hosts."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IloCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the iLO power sensor."""
    coordinator: IloCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IloPowerSensor(coordinator, entry)])


class IloPowerSensor(CoordinatorEntity[IloCoordinator], SensorEntity):
    """Reports the server's current power draw, as read from iLO.

    Not every iLO generation/firmware exposes power readings; when it
    doesn't, the coordinator leaves power_watts as None and this entity
    reports itself unavailable rather than showing a misleading 0 W.
    """

    _attr_has_entity_name = True
    _attr_name = "Power draw"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: IloCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_power_watts"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.power_watts

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.power_watts is not None
