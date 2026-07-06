# HPE iLO for Home Assistant

A Home Assistant custom integration for HPE Integrated Lights-Out (iLO)
management processors. See your server's power state, turn it on/off, and
tap the virtual power button, all from Home Assistant.

Built with older iLO generations (iLO 3 and earlier) specifically in mind:
they only speak TLSv1.1/SSLv3 with weak ciphers, which modern OpenSSL
refuses to negotiate by default. This integration includes a legacy SSL
context that works around that (see [How the legacy SSL workaround
works](#how-the-legacy-ssl-workaround-works)).

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
  the iLO firmware exposes it.
- Config flow (UI-based setup), no YAML required.
- One config entry per iLO host; add as many as you have.

## Requirements

- Home Assistant 2024.1 or newer.
- Network access from your Home Assistant instance to the iLO's management
  IP/hostname on port 443.
- iLO credentials with permission to view/change server power (a dedicated,
  least-privilege iLO user is recommended over an administrator account).

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations** → the **⋮** menu → **Custom repositories**.
2. Add this repository's URL with category **Integration**.
3. Search for **HPE iLO** in HACS and install it.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/hpilo` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

Entirely done through the UI:

1. **Settings → Devices & Services → Add Integration → "HPE iLO"**.
2. Enter:
   - **Host**: the iLO's IP address or hostname.
   - **Username** / **Password**.
   - **Use legacy SSL**: leave this checked for iLO 3 and older. Untick it
     for iLO 4+ if you'd rather use a normal, verified TLS connection.
3. The integration logs in and reads the current power status before
   creating the entry, so connection/auth problems are reported immediately
   in the form instead of failing silently later.

Repeat for each additional iLO host — each gets its own device with its own
switch, button, and sensor entities.

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

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

The test suite (`tests/`) mocks the `hpilo` library throughout — it never
talks to a real iLO — and covers:

- `test_ssl_helper.py` — the legacy SSL context's exact flags.
- `test_coordinator.py` — polling, error mapping, and power/button control.
- `test_config_flow.py` — the UI setup flow's success and error paths.
- `test_integration.py` — end-to-end config entry setup and entity/service
  behavior.

## Disclaimer

This is a community project, not affiliated with or endorsed by
Hewlett Packard Enterprise. Use at your own risk.

## License

[MIT](LICENSE)
