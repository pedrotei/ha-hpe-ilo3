"""Tests for the HPE iLO / LO100 config flow: menu, success, error mapping,
and dedup, for both connection types.
"""

from unittest.mock import MagicMock, patch

import hpilo
from homeassistant import config_entries, data_entry_flow
from pyghmi.exceptions import IpmiException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hpilo.const import CONF_CONNECTION_TYPE, DOMAIN

ILO_INPUT = {
    "host": "192.168.1.10",
    "username": "pedrotei",
    "password": "secret",
    "legacy_ssl": True,
}

IPMI_INPUT = {
    "host": "192.168.1.20",
    "username": "admin",
    "password": "secret",
}


async def _start_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_first_step_is_a_menu(hass):
    result = await _start_flow(hass)

    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert set(result["menu_options"]) == {"ilo", "ipmi"}


async def test_successful_ilo_setup_creates_entry(hass):
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ilo"}
    )

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.return_value = "ON"
    with patch("custom_components.hpilo.clients.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ILO_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.10"
    assert result["data"] == {**ILO_INPUT, "connection_type": "ilo"}


async def test_successful_ipmi_setup_creates_entry(hass):
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ipmi"}
    )

    mock_command = MagicMock()
    mock_command.get_power.return_value = {"powerstate": "off"}
    with patch(
        "custom_components.hpilo.clients.IpmiCommand", return_value=mock_command
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], IPMI_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.20"
    assert result["data"] == {**IPMI_INPUT, "connection_type": "ipmi"}


async def test_ilo_invalid_auth_shows_error(hass):
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ilo"}
    )

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = hpilo.IloLoginFailed("bad login")
    with patch("custom_components.hpilo.clients.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ILO_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_ipmi_invalid_auth_shows_error(hass):
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ipmi"}
    )

    mock_command = MagicMock()
    mock_command.get_power.side_effect = IpmiException("Incorrect password provided")
    with patch(
        "custom_components.hpilo.clients.IpmiCommand", return_value=mock_command
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], IPMI_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_communication_error_shows_cannot_connect(hass):
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ilo"}
    )

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = hpilo.IloCommunicationError("timeout")
    with patch("custom_components.hpilo.clients.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ILO_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unexpected_error_shows_unknown(hass):
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ilo"}
    )

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = ValueError("boom")
    with patch("custom_components.hpilo.clients.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ILO_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_duplicate_host_aborts(hass):
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.10",
        data={**ILO_INPUT, CONF_CONNECTION_TYPE: "ilo"},
    )
    existing.add_to_hass(hass)

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ilo"}
    )

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.return_value = "ON"
    with patch("custom_components.hpilo.clients.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ILO_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
