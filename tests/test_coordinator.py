"""Unit tests for IloCoordinator's data-fetching and control logic.

hpilo itself is mocked throughout - these tests are about our glue code
(tuple unpacking, error mapping, executor plumbing), not about the hpilo
library or a real iLO.
"""
from unittest.mock import MagicMock, patch

import hpilo
import pytest
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hpilo.coordinator import IloCoordinator


def _make_coordinator(hass, mock_ilo_class):
    entry = MockConfigEntry(domain="hpilo", data={})
    entry.add_to_hass(hass)
    with patch("custom_components.hpilo.coordinator.hpilo.Ilo", mock_ilo_class):
        return IloCoordinator(
            hass,
            entry,
            host="192.168.1.10",
            username="user",
            password="pass",
            legacy_ssl=True,
        )


async def test_fetch_unpacks_power_reading_tuple(hass):
    """get_power_readings returns (value, unit) tuples; only the number should surface."""
    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.return_value = "ON"
    mock_ilo.get_power_readings.return_value = {"present_power_reading": (123, "Watts")}
    coordinator = _make_coordinator(hass, MagicMock(return_value=mock_ilo))

    data = await hass.async_add_executor_job(coordinator._fetch)

    assert data.power_state == "ON"
    assert data.power_watts == 123


async def test_fetch_handles_missing_power_readings(hass):
    """Some iLO firmwares don't expose get_power_readings at all."""
    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.return_value = "OFF"
    mock_ilo.get_power_readings.side_effect = hpilo.IloError("not supported")
    coordinator = _make_coordinator(hass, MagicMock(return_value=mock_ilo))

    data = await hass.async_add_executor_job(coordinator._fetch)

    assert data.power_state == "OFF"
    assert data.power_watts is None


async def test_update_data_raises_not_ready_on_login_failure(hass):
    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = hpilo.IloLoginFailed("bad credentials")
    coordinator = _make_coordinator(hass, MagicMock(return_value=mock_ilo))

    with pytest.raises(ConfigEntryNotReady):
        await coordinator._async_update_data()


async def test_update_data_raises_update_failed_on_other_errors(hass):
    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = OSError("network unreachable")
    coordinator = _make_coordinator(hass, MagicMock(return_value=mock_ilo))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_set_power_forwards_to_ilo(hass):
    mock_ilo = MagicMock()
    coordinator = _make_coordinator(hass, MagicMock(return_value=mock_ilo))

    coordinator.set_power(True)

    mock_ilo.set_host_power.assert_called_once_with(True)


async def test_press_power_button_forwards_to_ilo(hass):
    mock_ilo = MagicMock()
    coordinator = _make_coordinator(hass, MagicMock(return_value=mock_ilo))

    coordinator.press_power_button()

    mock_ilo.press_pwr_btn.assert_called_once()
