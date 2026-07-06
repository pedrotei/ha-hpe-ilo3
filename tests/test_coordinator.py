"""Unit tests for IloCoordinator's polling/error-mapping glue.

The PowerControlClient itself is faked here (see tests/test_clients.py for
the real IloClient/IpmiClient behavior) - these tests are purely about the
coordinator's own logic: delegating to whatever client build_client()
returns, and mapping client exceptions into HA's own exception types.
"""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hpilo.clients import AuthenticationFailed
from custom_components.hpilo.coordinator import IloCoordinator, IloData


async def _make_coordinator(hass, mock_client):
    entry = MockConfigEntry(domain="hpilo", data={"host": "192.168.1.10"})
    entry.add_to_hass(hass)
    coordinator = IloCoordinator(hass, entry)
    with patch(
        "custom_components.hpilo.coordinator.build_client", return_value=mock_client
    ):
        await coordinator.async_setup_client()
    return coordinator


async def test_fetch_returns_client_data(hass):
    mock_client = MagicMock()
    mock_client.get_power_state.return_value = "ON"
    mock_client.get_power_watts.return_value = 123
    coordinator = await _make_coordinator(hass, mock_client)

    data = await hass.async_add_executor_job(coordinator._fetch)

    assert data == IloData(power_state="ON", power_watts=123)


async def test_fetch_handles_no_power_watts(hass):
    mock_client = MagicMock()
    mock_client.get_power_state.return_value = "OFF"
    mock_client.get_power_watts.return_value = None
    coordinator = await _make_coordinator(hass, mock_client)

    data = await hass.async_add_executor_job(coordinator._fetch)

    assert data == IloData(power_state="OFF", power_watts=None)


async def test_update_data_raises_not_ready_on_authentication_failure(hass):
    mock_client = MagicMock()
    mock_client.get_power_state.side_effect = AuthenticationFailed("bad login")
    coordinator = await _make_coordinator(hass, mock_client)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator._async_update_data()


async def test_update_data_raises_update_failed_on_other_errors(hass):
    mock_client = MagicMock()
    mock_client.get_power_state.side_effect = OSError("network unreachable")
    coordinator = await _make_coordinator(hass, mock_client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_set_power_forwards_to_client(hass):
    mock_client = MagicMock()
    coordinator = await _make_coordinator(hass, mock_client)

    coordinator.set_power(True)

    mock_client.set_power.assert_called_once_with(True)


async def test_press_power_button_forwards_to_client(hass):
    mock_client = MagicMock()
    coordinator = await _make_coordinator(hass, mock_client)

    coordinator.press_power_button()

    mock_client.press_power_button.assert_called_once()
