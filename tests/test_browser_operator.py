"""Generated TLS material only; no trusted certificate installation or live issuer."""

import ipaddress
import json
import ssl
from datetime import UTC, datetime, timedelta

import pytest
import test_oidc as oidc
from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from test_browser_auth import configuration
from uvicorn.config import create_ssl_context

from email_brain import browser_operator, cli
from email_brain.browser_operator import CIPHERS, tls_options
from email_brain.store import Store

keys = oidc.keys


def handshake(server_context, client_context, hostname):
    """Real OpenSSL handshake over bounded in-memory buffers, without a socket."""
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    client_in, client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    server = server_context.wrap_bio(incoming, outgoing, server_side=True)
    client = client_context.wrap_bio(client_in, client_out, server_hostname=hostname)
    complete = set()
    for _ in range(20):
        for name, peer in (("server", server), ("client", client)):
            if name not in complete:
                try:
                    peer.do_handshake()
                    complete.add(name)
                except ssl.SSLWantReadError:
                    pass
        incoming.write(client_out.read())
        client_in.write(outgoing.read())
        if len(complete) == 2:
            return server, client
    pytest.fail("TLS handshake failed to converge within bounded steps")


def material(tmp_path, key, *, san="localhost", when="current", eku=None, encrypted=False):
    tmp_path.chmod(0o700)
    now = datetime.now(UTC)
    start, end = now - timedelta(minutes=5), now + timedelta(days=1)
    if when == "expired":
        start, end = now - timedelta(days=2), now - timedelta(days=1)
    if when == "future":
        start, end = now + timedelta(days=1), now + timedelta(days=2)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(end)
    )
    if san is not None:
        try:
            entry = x509.IPAddress(ipaddress.ip_address(san))
        except ValueError:
            entry = x509.DNSName(san)
        builder = builder.add_extension(x509.SubjectAlternativeName([entry]), critical=False)
    if eku is not None:
        builder = builder.add_extension(x509.ExtendedKeyUsage([eku]), critical=False)
    certificate, private_key = tmp_path / "certificate.pem", tmp_path / "private.pem"
    certificate.write_bytes(
        builder.sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM)
    )
    private_key.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b"fictional-password")
            if encrypted
            else serialization.NoEncryption(),
        )
    )
    certificate.chmod(0o600)
    private_key.chmod(0o600)
    return certificate, private_key


@pytest.mark.parametrize("kind", ["rsa", "p256", "p384", "ip"])
def test_valid_private_tls_options(tmp_path, keys, kind):
    key = (
        keys[0]
        if kind in {"rsa", "ip"}
        else ec.generate_private_key(ec.SECP256R1() if kind == "p256" else ec.SECP384R1())
    )
    host = "127.0.0.1" if kind == "ip" else "localhost"
    paths = material(tmp_path, key, san=host, eku=ExtendedKeyUsageOID.SERVER_AUTH)
    cfg = configuration(public_origin=f"https://{host}:8765")
    assert tls_options(cfg, 8765, *paths) == {
        "ssl_certfile": str(paths[0]),
        "ssl_keyfile": str(paths[1]),
        "ssl_version": ssl.PROTOCOL_TLS_SERVER,
        "ssl_ciphers": CIPHERS,
    }


@pytest.mark.parametrize("protocol", [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3])
def test_uvicorn_context_real_tls_handshake(tmp_path, keys, protocol):
    paths = material(tmp_path, keys[0])
    options = tls_options(configuration(public_origin="https://localhost:8765"), 8765, *paths)
    server_context = create_ssl_context(
        certfile=options["ssl_certfile"],
        keyfile=options["ssl_keyfile"],
        ssl_version=options["ssl_version"],
        ciphers=options["ssl_ciphers"],
        password=None,
        cert_reqs=ssl.CERT_NONE,
        ca_certs=None,
    )
    assert server_context.minimum_version >= ssl.TLSVersion.TLSv1_2
    client_context = ssl.create_default_context(cafile=str(paths[0]))
    client_context.minimum_version = protocol
    client_context.maximum_version = protocol
    server, client = handshake(server_context, client_context, "localhost")
    assert (
        client.version()
        == server.version()
        == ("TLSv1.2" if protocol == ssl.TLSVersion.TLSv1_2 else "TLSv1.3")
    )
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(server_context, client_context, "wrong.example.invalid")
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(server_context, ssl.create_default_context(), "localhost")


@pytest.mark.parametrize(
    "changes",
    [
        {"when": "expired"},
        {"when": "future"},
        {"san": None},
        {"san": "other.example.invalid"},
        {"san": "*.localhost"},
        {"eku": ExtendedKeyUsageOID.CLIENT_AUTH},
        {"encrypted": True},
    ],
)
def test_bad_certificate_refused_without_details(tmp_path, keys, changes):
    paths = material(tmp_path, keys[0], **changes)
    with pytest.raises(ValueError, match="^invalid private browser TLS configuration$"):
        tls_options(configuration(public_origin="https://localhost:8765"), 8765, *paths)


@pytest.mark.parametrize("kind", ["weak-rsa", "curve", "mismatch"])
def test_bad_private_key(tmp_path, keys, kind):
    key = (
        rsa.generate_private_key(public_exponent=65537, key_size=1024)
        if kind == "weak-rsa"
        else (ec.generate_private_key(ec.SECP521R1()) if kind == "curve" else keys[0])
    )
    paths = material(tmp_path, key)
    if kind == "mismatch":
        paths[1].write_bytes(
            keys[1].private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    with pytest.raises(ValueError, match="^invalid private browser TLS configuration$"):
        tls_options(configuration(public_origin="https://localhost:8765"), 8765, *paths)


@pytest.mark.parametrize("port", [True, 0, 65536, 8080, "8765"])
def test_listener_port_must_match(tmp_path, keys, port):
    paths = material(tmp_path, keys[0])
    with pytest.raises(ValueError, match="^invalid private browser TLS configuration$"):
        tls_options(configuration(public_origin="https://localhost:8765"), port, *paths)


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("fault", ["public", "symlink", "hardlink", "missing", "malformed"])
def test_private_file_boundary(tmp_path, keys, index, fault):
    paths = list(material(tmp_path, keys[0]))
    target = paths[index]
    if fault == "public":
        target.chmod(0o644)
    elif fault == "symlink":
        link = tmp_path / "linked.pem"
        link.symlink_to(target)
        paths[index] = link
    elif fault == "hardlink":
        (tmp_path / "linked.pem").hardlink_to(target)
    elif fault == "missing":
        target.unlink()
    else:
        target.write_bytes(b"private malformed material must never be echoed")
    with pytest.raises(ValueError, match="^invalid private browser TLS configuration$"):
        tls_options(configuration(public_origin="https://localhost:8765"), 8765, *paths)


@pytest.mark.parametrize(
    "error",
    [
        UnsupportedAlgorithm("private diagnostic"),
        x509.DuplicateExtension("private diagnostic", x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME),
    ],
)
def test_parser_failures_scrubbed(tmp_path, keys, monkeypatch, error):
    paths = material(tmp_path, keys[0])

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(browser_operator.x509, "load_pem_x509_certificate", fail)
    with pytest.raises(ValueError, match="^invalid private browser TLS configuration$"):
        tls_options(configuration(public_origin="https://localhost:8765"), 8765, *paths)


@pytest.fixture
def launch(tmp_path, keys, monkeypatch):
    certificate, key = material(tmp_path, keys[0])
    cfg = configuration(public_origin="https://localhost:8765")
    data = cfg.model_dump(mode="json")
    data["client_secret"] = cfg.client_secret.get_secret_value()
    path = tmp_path / "browser.json"
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "never-connect")
    monkeypatch.delenv("EMAIL_BRAIN_CREDENTIALS_FILE", raising=False)

    def denied(*args, **kwargs):
        pytest.fail("startup/preflight attempted database or issuer access")

    monkeypatch.setattr(Store, "transaction", denied)
    monkeypatch.setattr("psycopg.connect", denied)
    monkeypatch.setattr("httpx.Client.send", denied)
    args = [
        "email-brain",
        "serve",
        "--browser-config",
        str(path),
        "--port",
        "8765",
        "--tls-cert",
        str(certificate),
        "--tls-key",
        str(key),
    ]
    monkeypatch.setattr("sys.argv", args)
    return args, cfg


def test_cli_check_non_consuming(launch, monkeypatch, capsys):
    args, _ = launch
    args.append("--check")
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **kw: pytest.fail("listener started"))
    monkeypatch.setattr(cli, "create_app", lambda *a, **kw: pytest.fail("app constructed"))
    cli.main()
    assert json.loads(capsys.readouterr().out) == {
        "mode": "browser",
        "status": "configuration_valid",
        "database_checked": False,
        "network_contact": False,
    }


def test_cli_explicit_browser_start(launch, monkeypatch):
    captured = {}
    actual = cli.create_app

    def app(store, registry, **kwargs):
        assert kwargs["browser_auth"].authenticator is registry
        captured["browser"] = kwargs["browser_auth"]
        return actual(store, registry, **kwargs)

    monkeypatch.setattr(cli, "create_app", app)
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: captured.update(app=app, **kw))
    cli.main()
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
    assert captured["access_log"] is False and captured["proxy_headers"] is False
    assert captured["ssl_version"] == ssl.PROTOCOL_TLS_SERVER
    assert captured["ssl_ciphers"] == CIPHERS
    assert "/auth/callback" in captured["app"].openapi()["paths"]


@pytest.mark.parametrize(
    "fault",
    [
        "bootstrap",
        "oidc",
        "no-cert",
        "no-key",
        "no-browser",
        "check-only",
        "wrong-port",
        "bad-config",
    ],
)
def test_cli_rejects_ambiguous_or_incomplete_mode(launch, monkeypatch, capsys, fault):
    args, _ = launch
    if fault == "bootstrap":
        monkeypatch.setenv("EMAIL_BRAIN_CREDENTIALS_FILE", "/private/secret-bootstrap.json")
    elif fault == "oidc":
        args.extend(["--oidc-config", "/private/secret-issuer.json"])
    elif fault in {"no-cert", "no-key", "no-browser"}:
        flag = {"no-cert": "--tls-cert", "no-key": "--tls-key", "no-browser": "--browser-config"}[
            fault
        ]
        index = args.index(flag)
        del args[index : index + 2]
    elif fault == "check-only":
        args[:] = ["email-brain", "serve", "--check"]
    elif fault == "wrong-port":
        args[args.index("--port") + 1] = "8080"
    else:
        args[args.index("--browser-config") + 1] = "/private/secret-missing.json"
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **kw: pytest.fail("listener started"))
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert not output.out
    assert output.err == (
        "Operation failed. Check configuration, permissions and service availability. "
        "Sensitive exception details suppressed.\n"
    )
