"""Tests for the HPE iLO config flow: success, error mapping, and dedup."""

from unittest.mock import MagicMock, patch

import hpilo
from homeassistant import config_entries, data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hpilo.const import CONF_LEGACY_SSL, DOMAIN

USER_INPUT = {
    "host": "192.168.1.10",
    "username": "pedrotei",
    "password": "secret",
    CONF_LEGACY_SSL: True,
}


async def _start_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_successful_setup_creates_entry(hass):
    result = await _start_flow(hass)

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.return_value = "ON"
    with patch("custom_components.hpilo.config_flow.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.10"
    assert result["data"] == USER_INPUT


async def test_invalid_auth_shows_error(hass):
    result = await _start_flow(hass)

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = hpilo.IloLoginFailed("bad login")
    with patch("custom_components.hpilo.config_flow.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_communication_error_shows_cannot_connect(hass):
    result = await _start_flow(hass)

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = hpilo.IloCommunicationError("timeout")
    with patch("custom_components.hpilo.config_flow.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unexpected_error_shows_unknown(hass):
    result = await _start_flow(hass)

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = ValueError("boom")
    with patch("custom_components.hpilo.config_flow.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_duplicate_host_aborts(hass):
    existing = MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.10", data=USER_INPUT)
    existing.add_to_hass(hass)

    result = await _start_flow(hass)

    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.return_value = "ON"
    with patch("custom_components.hpilo.config_flow.hpilo.Ilo", return_value=mock_ilo):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
