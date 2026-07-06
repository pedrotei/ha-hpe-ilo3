"""End-to-end tests: config entry setup wires up real switch/sensor/button
entities backed by a single mocked client, and service calls on those
entities actually reach the mock. Covers both connection types.
"""

from unittest.mock import MagicMock, patch

from homeassistant.helpers import entity_registry as er
from pyghmi.exceptions import IpmiException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hpilo.const import (
    CONF_CONNECTION_TYPE,
    CONF_LEGACY_SSL,
    CONNECTION_TYPE_IPMI,
    DOMAIN,
)

ILO_ENTRY_DATA = {
    "host": "192.168.1.10",
    "username": "pedrotei",
    "password": "secret",
    CONF_LEGACY_SSL: True,
}

IPMI_ENTRY_DATA = {
    "host": "192.168.1.20",
    "username": "admin",
    "password": "secret",
    CONF_CONNECTION_TYPE: CONNECTION_TYPE_IPMI,
}


def _make_mock_ilo():
    """A fake iLO that actually tracks power state across calls."""
    mock_ilo = MagicMock()
    state = {"power": "OFF"}
    mock_ilo.get_host_power_status.side_effect = lambda: state["power"]
    mock_ilo.set_host_power.side_effect = lambda on: state.update(
        power="ON" if on else "OFF"
    )
    mock_ilo.press_pwr_btn.side_effect = lambda: state.update(power="ON")
    mock_ilo.get_power_readings.return_value = {"present_power_reading": (150, "Watts")}
    return mock_ilo, state


def _make_mock_ipmi_command():
    """A fake LO100 that actually tracks power state across calls."""
    mock_command = MagicMock()
    state = {"power": "off"}
    mock_command.get_power.side_effect = lambda: {"powerstate": state["power"]}
    # Real LO100 hardware doesn't implement this IPMI command at all.
    mock_command.get_system_power_watts.side_effect = IpmiException("Invalid command")

    def _set_power(powerstate, wait=False):
        state["power"] = "off" if powerstate in ("off", "shutdown") else "on"

    mock_command.set_power.side_effect = _set_power
    return mock_command, state


async def _setup_ilo_entry(hass, mock_ilo, host="192.168.1.10"):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=host, data={**ILO_ENTRY_DATA, "host": host}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.hpilo.clients.hpilo.Ilo", return_value=mock_ilo):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _setup_ipmi_entry(hass, mock_command, host="192.168.1.20"):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=host, data={**IPMI_ENTRY_DATA, "host": host}
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hpilo.clients.IpmiCommand", return_value=mock_command
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _entity_id(hass, domain, unique_id):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None, f"no {domain} entity registered for {unique_id}"
    return entity_id


async def test_setup_creates_switch_sensor_and_button(hass):
    mock_ilo, _ = _make_mock_ilo()
    entry = await _setup_ilo_entry(hass, mock_ilo)

    switch_id = _entity_id(hass, "switch", f"{entry.entry_id}_power")
    sensor_id = _entity_id(hass, "sensor", f"{entry.entry_id}_power_watts")
    button_id = _entity_id(hass, "button", f"{entry.entry_id}_power_button")

    assert hass.states.get(switch_id).state == "off"
    assert hass.states.get(sensor_id).state == "150"
    assert hass.states.get(button_id) is not None


async def test_turning_switch_on_calls_set_host_power(hass):
    mock_ilo, _ = _make_mock_ilo()
    entry = await _setup_ilo_entry(hass, mock_ilo)
    switch_id = _entity_id(hass, "switch", f"{entry.entry_id}_power")

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_ilo.set_host_power.assert_called_once_with(True)
    assert hass.states.get(switch_id).state == "on"


async def test_turning_switch_off_calls_set_host_power(hass):
    mock_ilo, state = _make_mock_ilo()
    state["power"] = "ON"
    entry = await _setup_ilo_entry(hass, mock_ilo)
    switch_id = _entity_id(hass, "switch", f"{entry.entry_id}_power")

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_ilo.set_host_power.assert_called_once_with(False)
    assert hass.states.get(switch_id).state == "off"


async def test_pressing_power_button_calls_press_pwr_btn(hass):
    mock_ilo, _ = _make_mock_ilo()
    entry = await _setup_ilo_entry(hass, mock_ilo)
    button_id = _entity_id(hass, "button", f"{entry.entry_id}_power_button")

    await hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_ilo.press_pwr_btn.assert_called_once()


async def test_sensor_unavailable_when_readings_unsupported(hass):
    mock_ilo, _ = _make_mock_ilo()
    mock_ilo.get_power_readings.side_effect = Exception("not supported")
    entry = await _setup_ilo_entry(hass, mock_ilo)

    sensor_id = _entity_id(hass, "sensor", f"{entry.entry_id}_power_watts")
    assert hass.states.get(sensor_id).state == "unavailable"


async def test_ipmi_setup_creates_switch_and_button(hass):
    mock_command, _ = _make_mock_ipmi_command()
    entry = await _setup_ipmi_entry(hass, mock_command)

    switch_id = _entity_id(hass, "switch", f"{entry.entry_id}_power")
    button_id = _entity_id(hass, "button", f"{entry.entry_id}_power_button")

    assert hass.states.get(switch_id).state == "off"
    assert hass.states.get(button_id) is not None


async def test_ipmi_sensor_unavailable_since_lo100_has_no_power_monitoring(hass):
    mock_command, _ = _make_mock_ipmi_command()
    entry = await _setup_ipmi_entry(hass, mock_command)

    sensor_id = _entity_id(hass, "sensor", f"{entry.entry_id}_power_watts")
    assert hass.states.get(sensor_id).state == "unavailable"


async def test_ipmi_turning_switch_on_calls_set_power(hass):
    mock_command, _ = _make_mock_ipmi_command()
    entry = await _setup_ipmi_entry(hass, mock_command)
    switch_id = _entity_id(hass, "switch", f"{entry.entry_id}_power")

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_command.set_power.assert_called_once_with("on", wait=False)
    assert hass.states.get(switch_id).state == "on"


async def test_ipmi_pressing_power_button_sends_shutdown(hass):
    mock_command, state = _make_mock_ipmi_command()
    state["power"] = "on"
    entry = await _setup_ipmi_entry(hass, mock_command)
    button_id = _entity_id(hass, "button", f"{entry.entry_id}_power_button")

    await hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_command.set_power.assert_called_once_with("shutdown", wait=False)
