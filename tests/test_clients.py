"""Unit tests for the IloClient/IpmiClient wrappers.

hpilo and pyghmi are mocked throughout. The IPMI behaviors here (get_power
shape, set_power(wait=False), get_system_power_watts failing outright, a bad
password raising IpmiException("Incorrect password provided")) were all
confirmed against a real HPE Lights-Out 100 board on a DL160 G6, not just
guessed from the pyghmi API.
"""

from unittest.mock import MagicMock, patch

import hpilo
import pytest
from pyghmi.exceptions import IpmiException

from custom_components.hpilo.clients import (
    AuthenticationFailed,
    ConnectionFailed,
    IloClient,
    IpmiClient,
    build_client,
)
from custom_components.hpilo.const import CONF_CONNECTION_TYPE, CONNECTION_TYPE_IPMI

ENTRY_DATA = {
    "host": "192.168.1.10",
    "username": "user",
    "password": "pass",
}


def _make_ilo_client(mock_ilo):
    with patch("custom_components.hpilo.clients.hpilo.Ilo", return_value=mock_ilo):
        return IloClient("192.168.1.10", "user", "pass", legacy_ssl=True)


def _make_ipmi_client(mock_command):
    with patch(
        "custom_components.hpilo.clients.IpmiCommand", return_value=mock_command
    ):
        return IpmiClient("192.168.1.10", "user", "pass")


def test_ilo_client_unpacks_power_reading_tuple():
    mock_ilo = MagicMock()
    mock_ilo.get_power_readings.return_value = {"present_power_reading": (123, "Watts")}
    client = _make_ilo_client(mock_ilo)

    assert client.get_power_watts() == 123


def test_ilo_client_handles_missing_power_readings():
    mock_ilo = MagicMock()
    mock_ilo.get_power_readings.side_effect = hpilo.IloError("not supported")
    client = _make_ilo_client(mock_ilo)

    assert client.get_power_watts() is None


def test_ilo_client_get_power_state():
    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.return_value = "ON"
    client = _make_ilo_client(mock_ilo)

    assert client.get_power_state() == "ON"


def test_ilo_client_raises_authentication_failed_on_login_failure():
    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = hpilo.IloLoginFailed("bad login")
    client = _make_ilo_client(mock_ilo)

    with pytest.raises(AuthenticationFailed):
        client.get_power_state()


def test_ilo_client_raises_connection_failed_on_communication_error():
    mock_ilo = MagicMock()
    mock_ilo.get_host_power_status.side_effect = hpilo.IloCommunicationError("timeout")
    client = _make_ilo_client(mock_ilo)

    with pytest.raises(ConnectionFailed):
        client.get_power_state()


def test_ilo_client_set_power_forwards():
    mock_ilo = MagicMock()
    client = _make_ilo_client(mock_ilo)

    client.set_power(True)

    mock_ilo.set_host_power.assert_called_once_with(True)


def test_ilo_client_press_power_button_forwards():
    mock_ilo = MagicMock()
    client = _make_ilo_client(mock_ilo)

    client.press_power_button()

    mock_ilo.press_pwr_btn.assert_called_once()


def test_ipmi_client_get_power_state_on():
    mock_command = MagicMock()
    mock_command.get_power.return_value = {"powerstate": "on"}
    client = _make_ipmi_client(mock_command)

    assert client.get_power_state() == "ON"


def test_ipmi_client_get_power_state_off():
    mock_command = MagicMock()
    mock_command.get_power.return_value = {"powerstate": "off"}
    client = _make_ipmi_client(mock_command)

    assert client.get_power_state() == "OFF"


def test_ipmi_client_get_power_watts_unsupported():
    # LO100 doesn't implement this IPMI command at all.
    mock_command = MagicMock()
    mock_command.get_system_power_watts.side_effect = IpmiException("Invalid command")
    client = _make_ipmi_client(mock_command)

    assert client.get_power_watts() is None


def test_ipmi_client_set_power_uses_wait_false():
    # wait=True crashes on LO100's transient "BMC initialization in
    # progress" error right after a power transition - must stay False.
    mock_command = MagicMock()
    client = _make_ipmi_client(mock_command)

    client.set_power(True)

    mock_command.set_power.assert_called_once_with("on", wait=False)


def test_ipmi_client_press_power_button_sends_shutdown():
    mock_command = MagicMock()
    client = _make_ipmi_client(mock_command)

    client.press_power_button()

    mock_command.set_power.assert_called_once_with("shutdown", wait=False)


def test_ipmi_client_maps_password_error_to_authentication_failed():
    mock_command = MagicMock()
    mock_command.get_power.side_effect = IpmiException("Incorrect password provided")
    client = _make_ipmi_client(mock_command)

    with pytest.raises(AuthenticationFailed):
        client.get_power_state()


def test_ipmi_client_maps_password_error_from_constructor():
    # pyghmi logs in synchronously inside IpmiCommand's own constructor and
    # raises IpmiException directly from there on bad credentials - not
    # just from later calls like get_power() - confirmed against real
    # hardware where a wrong password fails right at Command(...).
    with (
        patch(
            "custom_components.hpilo.clients.IpmiCommand",
            side_effect=IpmiException("Incorrect password provided"),
        ),
        pytest.raises(AuthenticationFailed),
    ):
        IpmiClient("192.168.1.10", "user", "wrong-password")


def test_ipmi_client_maps_other_ipmi_errors_to_connection_failed():
    mock_command = MagicMock()
    mock_command.get_power.side_effect = IpmiException("timed out")
    client = _make_ipmi_client(mock_command)

    with pytest.raises(ConnectionFailed):
        client.get_power_state()


def test_build_client_defaults_to_ilo_when_connection_type_missing():
    # Config entries created before CONF_CONNECTION_TYPE existed have no
    # such key at all; they must keep working as iLO.
    with patch("custom_components.hpilo.clients.hpilo.Ilo") as mock_ilo_cls:
        client = build_client(ENTRY_DATA)

    assert isinstance(client, IloClient)
    mock_ilo_cls.assert_called_once()


def test_build_client_builds_ipmi_client():
    entry_data = {**ENTRY_DATA, CONF_CONNECTION_TYPE: CONNECTION_TYPE_IPMI}
    with patch("custom_components.hpilo.clients.IpmiCommand") as mock_command_cls:
        client = build_client(entry_data)

    assert isinstance(client, IpmiClient)
    mock_command_cls.assert_called_once()
