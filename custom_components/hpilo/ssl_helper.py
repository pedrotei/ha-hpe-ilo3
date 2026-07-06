"""Legacy SSL context for old HPE iLO (e.g. iLO 3) generations.

iLO 3 only speaks TLSv1.1 / SSLv3 with weak ciphers and does secure
renegotiation the old (pre-RFC 5746) way. OpenSSL 3.x refuses all of that at
its default security level, so we have to drop to SECLEVEL=0 and explicitly
re-enable legacy server connections.
"""
from __future__ import annotations

import ssl


def build_legacy_ilo_ssl_context() -> ssl.SSLContext:
    """Build an SSLContext compatible with HPE iLO 3.

    Each setting below relaxes one specific OpenSSL 3.x default that would
    otherwise reject the handshake outright:

    - PROTOCOL_TLSv1_1: iLO 3's management processor never got a firmware
      update to speak TLS 1.2+, so we have to pin the client to the highest
      version it does support.
    - SECLEVEL=0 (not 1): SECLEVEL=1 alone stops OpenSSL raising
      "unsafe legacy renegotiation disabled", but iLO 3 also signs its
      handshake with algorithms OpenSSL calls "legacy" and rejects below
      SECLEVEL=0 ("legacy sigalg disallowed or unsupported").
    - OP_NO_SSLv3 cleared: allows falling back to SSLv3 if a given iLO unit
      needs it (some very old firmware revisions do).
    - OP_LEGACY_SERVER_CONNECT: re-enables the pre-RFC 5746 renegotiation
      iLO 3 uses; without it the handshake fails with
      "UNSAFE_LEGACY_RENEGOTIATION_DISABLED".
    - check_hostname / verify_mode: iLO ships a self-signed cert with no
      usable hostname, so certificate verification is disabled entirely.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
    context.set_ciphers("ALL:@SECLEVEL=0")
    context.options &= ~ssl.OP_NO_SSLv3
    context.options |= ssl.OP_LEGACY_SERVER_CONNECT
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context
