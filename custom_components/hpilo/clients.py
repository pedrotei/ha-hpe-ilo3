"""Power-control clients for the two management processor protocols this
integration supports, behind one common interface (get_power_state,
get_power_watts, set_power, press_power_button) so the coordinator and
entities don't need to know which protocol a given host actually speaks.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol

import hpilo
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from pyghmi.exceptions import IpmiException
from pyghmi.ipmi.command import Command as IpmiCommand

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_LEGACY_SSL,
    CONNECTION_TYPE_IPMI,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_IPMI_PORT,
    DEFAULT_LEGACY_SSL,
    DEFAULT_TIMEOUT,
)
from .ssl_helper import build_legacy_ilo_ssl_context

_LOGGER = logging.getLogger(__name__)


class AuthenticationFailed(Exception):
    """Raised by either client when the host rejects the given credentials."""


class ConnectionFailed(Exception):
    """Raised by either client when the host can't be reached at all
    (network/timeout/protocol errors, as opposed to bad credentials).
    """


class PowerControlClient(Protocol):
    """Common interface both IloClient and IpmiClient implement."""

    def get_power_state(self) -> str:
        """Blocking. Returns "ON" or "OFF". Raises AuthenticationFailed on bad creds."""

    def get_power_watts(self) -> float | None:
        """Blocking. Returns current power draw, or None if unsupported."""

    def set_power(self, on: bool) -> None:
        """Blocking. Force the power state (like holding the power button)."""

    def press_power_button(self) -> None:
        """Blocking. Momentary press, for a graceful ACPI shutdown/wake."""


class IloClient(PowerControlClient):
    """Wraps hpilo.Ilo for real HPE iLO (2 and up) management processors."""

    def __init__(
        self, host: str, username: str, password: str, legacy_ssl: bool
    ) -> None:
        # legacy_ssl=False lets users on newer iLO generations (4+) use a
        # normal, verified TLS connection instead of the iLO 3 workarounds.
        ssl_context = build_legacy_ilo_ssl_context() if legacy_ssl else None
        self._ilo = hpilo.Ilo(
            host,
            login=username,
            password=password,
            timeout=DEFAULT_TIMEOUT,
            ssl_context=ssl_context,
        )

    def get_power_state(self) -> str:
        try:
            return self._ilo.get_host_power_status()
        except hpilo.IloLoginFailed as err:
            raise AuthenticationFailed(str(err)) from err
        except hpilo.IloCommunicationError as err:
            raise ConnectionFailed(str(err)) from err

    def get_power_watts(self) -> float | None:
        try:
            readings = self._ilo.get_power_readings()
        except Exception:  # noqa: BLE001 - not all iLO models/firmwares expose this
            _LOGGER.debug("get_power_readings not available", exc_info=True)
            return None
        reading = readings.get("present_power_reading")
        # hpilo returns (value, unit) tuples, e.g. (123, "Watts"), so pull out
        # just the number for the sensor.
        return reading[0] if isinstance(reading, tuple) else reading

    def set_power(self, on: bool) -> None:
        """This is a hard power control command (like holding the physical
        power button until it responds), not a graceful OS shutdown request.
        """
        self._ilo.set_host_power(on)

    def press_power_button(self) -> None:
        self._ilo.press_pwr_btn()


class IpmiClient(PowerControlClient):
    """Wraps pyghmi's IPMI command client, for HPE Lights-Out 100 (LO100)
    boards found on entry-level ProLiant "hundred series" servers (e.g. the
    DL160 G6). These never got a real iLO - LO100 only speaks plain IPMI
    2.0, not iLO's RIBCL/XML protocol, so hpilo can't talk to them at all.

    Confirmed against real LO100 hardware: power status and set_power('on'/
    'off') both work; get_system_power_watts() doesn't (LO100 has no power
    monitoring), so the power sensor is always unavailable for this
    connection type.
    """

    def __init__(self, host: str, username: str, password: str) -> None:
        try:
            # pyghmi logs in synchronously inside this constructor and
            # raises IpmiException directly from here on bad credentials or
            # an unreachable host - not just from later calls like
            # get_power() - so this needs the same error mapping as those.
            self._command = IpmiCommand(
                bmc=host, userid=username, password=password, port=DEFAULT_IPMI_PORT
            )
        except IpmiException as err:
            raise self._map_error(err) from err

    def get_power_state(self) -> str:
        try:
            result = self._command.get_power()
        except IpmiException as err:
            raise self._map_error(err) from err
        return "ON" if result.get("powerstate") == "on" else "OFF"

    def get_power_watts(self) -> float | None:
        try:
            watts = self._command.get_system_power_watts()
        except Exception:  # noqa: BLE001 - LO100 doesn't support this at all
            _LOGGER.debug("get_system_power_watts not available", exc_info=True)
            return None
        return watts

    def set_power(self, on: bool) -> None:
        self._set_power("on" if on else "off")

    def press_power_button(self) -> None:
        # IPMI's "soft shutdown via ACPI" chassis control command is exactly
        # our button's intended semantics: request a graceful shutdown from
        # the running OS, rather than force the power state.
        self._set_power("shutdown")

    def _set_power(self, powerstate: str) -> None:
        try:
            # wait=False: pyghmi's wait=True polling loop doesn't tolerate
            # the transient "BMC initialization in progress" error LO100
            # returns right after a power transition, and raises instead of
            # retrying - confirmed against real LO100 hardware. We rely on
            # the coordinator's own next poll to observe the new state.
            self._command.set_power(powerstate, wait=False)
        except IpmiException as err:
            raise self._map_error(err) from err

    @staticmethod
    def _map_error(err: IpmiException) -> Exception:
        # pyghmi has no distinct authentication-failure exception type -
        # both bad credentials and network/timeout issues raise the same
        # IpmiException, differentiated only by message text (confirmed
        # against real hardware: a bad password raises IpmiException
        # "Incorrect password provided").
        if "password" in str(err).lower():
            return AuthenticationFailed(str(err))
        return ConnectionFailed(str(err))


def build_client(entry_data: Mapping[str, Any]) -> PowerControlClient:
    """Construct the right client for a config entry's connection type.

    Entries created before CONF_CONNECTION_TYPE existed have no such key at
    all, hence the default fallback to iLO (the only connection type that
    used to exist) rather than a required lookup.
    """
    connection_type = entry_data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    host = entry_data[CONF_HOST]
    username = entry_data[CONF_USERNAME]
    password = entry_data[CONF_PASSWORD]
    if connection_type == CONNECTION_TYPE_IPMI:
        return IpmiClient(host, username, password)
    return IloClient(
        host, username, password, entry_data.get(CONF_LEGACY_SSL, DEFAULT_LEGACY_SSL)
    )
