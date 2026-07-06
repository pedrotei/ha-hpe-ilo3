"""Constants for the HPE iLO integration."""

DOMAIN = "hpilo"

# Config entry key for the "use legacy SSL" checkbox in the config flow.
CONF_LEGACY_SSL = "legacy_ssl"

# iLO 3 and older need the legacy TLS/SSL context by default; newer
# generations (iLO 4+) generally work fine with modern TLS and can untick it.
DEFAULT_LEGACY_SSL = True

# hpilo's own socket timeout, in seconds, for each RIBCL request.
DEFAULT_TIMEOUT = 10

# How often the coordinator polls the iLO for power state/readings.
# iLO's management processor is slow and not meant for tight polling loops,
# so this is intentionally conservative.
DEFAULT_SCAN_INTERVAL = 30
