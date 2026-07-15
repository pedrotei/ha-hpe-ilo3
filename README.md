# HPE iLO for Home Assistant

A Home Assistant custom integration for HPE server management processors.
See your server's power state, turn it on/off, and tap the virtual power
button, all from Home Assistant. Supports two connection types:

- **iLO** (2 and up) — real HPE iLO, over its RIBCL/XML protocol via
  [python-hpilo](https://github.com/seveas/python-hpilo). Built with older
  generations (iLO 3 and earlier) specifically in mind: they only speak
  TLSv1.1/SSLv3 with weak ciphers, which modern OpenSSL refuses to negotiate
  by default. This integration includes a legacy SSL context that works
  around that (see [How the legacy SSL workaround
  works](#how-the-legacy-ssl-workaround-works)).
- **Lights-Out 100 (LO100)** — the much simpler IPMI 2.0 board found on
  entry-level ProLiant "hundred series" G6/G7 servers (e.g. the DL160 G6)
  that never had a real iLO at all, over plain IPMI via
  [pyghmi](https://opendev.org/openstack/pyghmi). No power-draw sensor,
  since LO100 has no power monitoring at all.

> [!WARNING]
> The "legacy SSL" option deliberately downgrades TLS to the weakest
> settings iLO 3 will accept (TLSv1.1/SSLv3, `SECLEVEL=0`, no certificate
> verification, pre-RFC 5746 renegotiation). This is **insecure** by modern
> standards and should only be used on a trusted, isolated management
> network (e.g. a dedicated management VLAN) — never expose an iLO
> configured this way directly to the internet or an untrusted network.
> Use at your own risk.

## Features

- **Switch** — reflects and controls the managed server's power state
  (`switch.<name>_power`). Turning it on/off forces the power state, similar
  to holding the physical power button.
- **Button** — momentarily presses the virtual power button
  (`button.<name>_power_button`), for a graceful ACPI shutdown/wake instead
  of a forced one.
- **Sensor** — current power draw in watts (`sensor.<name>_power_draw`), if
  the connection type/firmware exposes it (iLO only — LO100 never does).
- Config flow (UI-based setup), no YAML required.
- One config entry per host; add as many as you have, mixing iLO and LO100
  freely.

## Requirements

- Home Assistant 2024.1 or newer.
- Network access from your Home Assistant instance to the management
  IP/hostname, on port 443 for iLO or port 623/UDP for LO100.
- Credentials with permission to view/change server power (a dedicated,
  least-privilege user is recommended over an administrator account).

## Installation

This isn't in the HACS default store (it's not general-purpose enough to
submit there), so it has to be added as a **custom repository**.

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pedrotei&repository=ha-hpe-ilo3&category=integration)

One-click (if your browser is paired with your HA instance via [my.home-assistant.io](https://my.home-assistant.io)): click the badge above, confirm in HACS, then install.

Manual steps, if you'd rather not use the badge:

1. In HACS, go to **Integrations** → the **⋮** menu (top right) → **Custom repositories**.
2. Add `https://github.com/pedrotei/ha-hpe-ilo3` with category **Integration**.
3. Find **HPE iLO** in HACS (search or the newly-added repository) and click **Download**.
4. Restart Home Assistant.

### Manual (no HACS)

1. Copy `custom_components/hpilo` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

Entirely done through the UI:

1. **Settings → Devices & Services → Add Integration → "HPE iLO"**.
2. Pick a connection type:
   - **iLO** — enter the host, username, password, and **Use legacy SSL**
     (leave checked for iLO 3 and older; untick for iLO 4+ if you'd rather
     use a normal, verified TLS connection).
   - **Lights-Out 100 (LO100)** — enter the host, username, and password.
     No SSL option, since LO100 doesn't use TLS at all.
3. The integration logs in and reads the current power status before
   creating the entry, so connection/auth problems are reported immediately
   in the form instead of failing silently later.

Repeat for each additional host — each gets its own device with its own
switch, button, and (for iLO) sensor entities.

## How the legacy SSL workaround works

iLO 3's management processor never received a firmware update to support
TLS 1.2+, and OpenSSL 3.x (used by current Python/Home Assistant builds)
disables the old protocols, ciphers, and renegotiation behavior it needs, by
default. `custom_components/hpilo/ssl_helper.py` builds an `SSLContext` that
undoes just enough of that to let the handshake through:

| Setting | Why |
|---|---|
| `PROTOCOL_TLSv1_1` | The highest protocol version iLO 3 supports. |
| `SECLEVEL=0` | `SECLEVEL=1` alone isn't enough — iLO 3 signs its handshake with algorithms OpenSSL calls "legacy" and rejects below level 0. |
| `OP_NO_SSLv3` cleared | Allows falling back to SSLv3 for firmware revisions that need it. |
| `OP_LEGACY_SERVER_CONNECT` | Re-enables the pre-RFC 5746 renegotiation iLO 3 uses; without it the handshake fails with `UNSAFE_LEGACY_RENEGOTIATION_DISABLED`. |
| Certificate verification disabled | iLO ships a self-signed certificate with no usable hostname. |

See the warning at the top of this README — this table is exactly the set
of protections being turned off, and why.

## Architecture

`custom_components/hpilo/clients.py` defines a small `PowerControlClient`
interface (`get_power_state`, `get_power_watts`, `set_power`,
`press_power_button`) with two implementations, `IloClient` (wraps
`hpilo.Ilo`) and `IpmiClient` (wraps `pyghmi`'s IPMI command client). The
coordinator, entities, and config flow only ever talk to that interface, so
adding a third connection type wouldn't touch the coordinator or entities at
all.

The IPMI behaviors documented in `clients.py` (power status shape,
`set_power(wait=False)`, `get_system_power_watts()` failing outright, a bad
password raising a specific `IpmiException` message) were all confirmed
against a real Lights-Out 100 board, not just inferred from the pyghmi API -
notably, `wait=True` will crash on LO100 because it doesn't tolerate the
transient "BMC initialization in progress" error the board returns right
after a power transition.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
ruff check .
ruff format --check .
pylint custom_components tests
pytest
```

Note: this package's own folder is named `hpilo`, same as the third-party
`hpilo` PyPI library it wraps (Home Assistant requires the folder name to
match the integration's domain). This collides with how `pylint` and
`ruff`'s import sorter resolve `import hpilo`, causing false positives
(`no-member`, `cyclic-import`, import-group splitting) that are suppressed
in `pyproject.toml` with comments explaining why — if you see one of those
checks behaving strangely on this repo, that's why.

The test suite (`tests/`) mocks `hpilo`/`pyghmi` throughout — it never talks
to real hardware — and covers:

- `test_ssl_helper.py` — the legacy SSL context's exact flags.
- `test_clients.py` — IloClient/IpmiClient behavior for both connection
  types, including the error-mapping edge cases above.
- `test_coordinator.py` — polling and error-mapping glue, against a faked
  client (connection-type-agnostic).
- `test_config_flow.py` — the UI setup flow's menu, success, and error paths
  for both connection types.
- `test_integration.py` — end-to-end config entry setup and entity/service
  behavior, for both connection types.

## Disclaimer

This is a community project, not affiliated with or endorsed by
Hewlett Packard Enterprise. Use at your own risk.

## License

[MIT](LICENSE)
