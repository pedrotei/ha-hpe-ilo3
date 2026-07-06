"""Unit tests for the legacy SSL context builder.

These don't touch Home Assistant or the network at all; they just assert
the SSLContext has the exact flags iLO 3 needs, since a regression here is
what actually broke connectivity once already (see ssl_helper.py comments).
"""
import ssl

from custom_components.hpilo.ssl_helper import build_legacy_ilo_ssl_context


def test_uses_tlsv1_1_protocol():
    context = build_legacy_ilo_ssl_context()
    assert context.protocol == ssl.PROTOCOL_TLSv1_1


def test_allows_sslv3_fallback():
    context = build_legacy_ilo_ssl_context()
    assert not (context.options & ssl.OP_NO_SSLv3)


def test_enables_legacy_server_connect():
    context = build_legacy_ilo_ssl_context()
    assert context.options & ssl.OP_LEGACY_SERVER_CONNECT


def test_disables_certificate_verification():
    context = build_legacy_ilo_ssl_context()
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_returns_new_context_each_call():
    # Each config entry gets its own hpilo.Ilo client with its own context;
    # they must not be aliases of a single module-level context.
    assert build_legacy_ilo_ssl_context() is not build_legacy_ilo_ssl_context()
