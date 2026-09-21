"""Private-file TLS preflight for the explicitly selected loopback browser mode."""

from __future__ import annotations

import ipaddress
import ssl
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID

from email_brain.browser_auth import BrowserConfig
from email_brain.processing_controller import private_bytes

CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20"


def tls_options(
    config: BrowserConfig, port: int, certificate: Path, private_key: Path
) -> dict[str, Any]:
    """Validate without network or interactive prompts; return only server options."""
    try:
        origin = urlsplit(config.public_origin)
        if type(port) is not int or not 1 <= port <= 65535 or (origin.port or 443) != port:
            raise ValueError("origin and listener ports differ")
        cert = x509.load_pem_x509_certificate(private_bytes(certificate))
        key = serialization.load_pem_private_key(private_bytes(private_key), password=None)
        if isinstance(key, rsa.RSAPrivateKey):
            valid_key = (
                2048 <= key.key_size <= 4096 and key.public_key().public_numbers().e == 65537
            )
        else:
            valid_key = isinstance(key, ec.EllipticCurvePrivateKey) and isinstance(
                key.curve, (ec.SECP256R1, ec.SECP384R1)
            )
        if not valid_key:
            raise ValueError("unsupported TLS private key")
        encoding = serialization.Encoding.DER
        form = serialization.PublicFormat.SubjectPublicKeyInfo
        if cert.public_key().public_bytes(encoding, form) != key.public_key().public_bytes(
            encoding, form
        ):
            raise ValueError("TLS certificate and private key differ")
        now = datetime.now(UTC)
        if not cert.not_valid_before_utc <= now < cert.not_valid_after_utc:
            raise ValueError("TLS certificate is not currently valid")
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        host = origin.hostname
        assert host is not None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            matched = host in [value.lower() for value in san.get_values_for_type(x509.DNSName)]
        else:
            matched = address in san.get_values_for_type(x509.IPAddress)
        if not matched:
            raise ValueError("exact configured-host SAN required")
        try:
            eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        except x509.ExtensionNotFound:
            pass
        else:
            if ExtendedKeyUsageOID.SERVER_AUTH not in eku:
                raise ValueError("TLS server usage required")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.set_ciphers(CIPHERS)
        if context.minimum_version < ssl.TLSVersion.TLSv1_2:
            raise ValueError("TLS 1.2 minimum required")
        # Explicit password callback refuses encrypted keys without a terminal prompt.
        context.load_cert_chain(str(certificate), str(private_key), password=lambda: "")
        return {
            "ssl_certfile": str(certificate),
            "ssl_keyfile": str(private_key),
            "ssl_version": ssl.PROTOCOL_TLS_SERVER,
            "ssl_ciphers": CIPHERS,
        }
    except (
        ValueError,
        TypeError,
        OSError,
        UnsupportedAlgorithm,
        x509.ExtensionNotFound,
        x509.DuplicateExtension,
    ):
        raise ValueError("invalid private browser TLS configuration") from None
