"""Constants for the HPE iLO integration."""

DOMAIN = "hpilo"

# Config entry key for which management processor protocol to speak.
# Entries created before this option existed have no such key at all, so
# every read of it must fall back to DEFAULT_CONNECTION_TYPE (see
# clients.build_client) rather than assume the key is present.
CONF_CONNECTION_TYPE = "connection_type"

# Real iLO (2 and up): RIBCL/XML over HTTPS, via the hpilo library.
CONNECTION_TYPE_ILO = "ilo"
# HPE Lights-Out 100 (LO100): IPMI 2.0, via pyghmi. Found on entry-level
# ProLiant "hundred series" G6/G7 servers (e.g. the DL160 G6) that never got
# a real iLO at all - LO100 doesn't speak RIBCL/XML.
CONNECTION_TYPE_IPMI = "ipmi"

DEFAULT_CONNECTION_TYPE = CONNECTION_TYPE_ILO

# Config entry key for the "use legacy SSL" checkbox in the config flow.
CONF_LEGACY_SSL = "legacy_ssl"

# iLO 3 and older need the legacy TLS/SSL context by default; newer
# generations (iLO 4+) generally work fine with modern TLS and can untick it.
DEFAULT_LEGACY_SSL = True

# hpilo's own socket timeout, in seconds, for each RIBCL request.
DEFAULT_TIMEOUT = 10

# Standard IPMI-over-LAN port.
DEFAULT_IPMI_PORT = 623

# How often the coordinator polls the host for power state/readings.
# iLO/LO100 management processors are slow and not meant for tight polling
# loops, so this is intentionally conservative.
DEFAULT_SCAN_INTERVAL = 30
