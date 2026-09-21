"""Generated keys and fictional HTTPS only; never a real issuer or saved token."""

import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import email_brain.oidc as identity_module
from email_brain.api import create_app
from email_brain.auth import AuthenticationUnavailable, Principal
from email_brain.domain.models import TenantContext
from email_brain.oidc import AccessTokenVerifier, OIDCAuthenticator, OIDCConfig, VerifiedToken
from email_brain.store import Store

TENANT = "a2328309-1d13-4793-b129-b88973dcd4ea"
API = str(UUID(int=1001))  # Fictional application identifier, never a credential.
CLIENT = "18987a1a-915e-4926-a0a2-381ce2e73101"


def config(profile="rfc9068"):
    issuer = (
        "https://issuer.example.invalid"
        if profile == "rfc9068"
        else f"https://login.microsoftonline.com/{TENANT}/v2.0"
    )
    return OIDCConfig(
        version=1,
        profile=profile,
        issuer=issuer,
        discovery_url=issuer + "/.well-known/openid-configuration",
        jwks_url=(
            issuer + "/keys"
            if profile == "rfc9068"
            else "https://login.microsoftonline.com/common/discovery/v2.0/keys"
        ),
        audience=API,
        client_ids=(CLIENT,),
        admission_scope="email.access",
        entra_tenant_id=None if profile == "rfc9068" else TENANT,
    )


def claims(cfg, **changes):
    now = int(time.time())
    result = dict(
        iss=cfg.issuer,
        sub="fictional-owner",
        aud=cfg.audience,
        iat=now - 10,
        exp=now + 3600,
        nbf=now - 10,
    )
    if cfg.profile == "rfc9068":
        result.update(client_id=CLIENT, jti=str(uuid4()), scope="email.access")
    else:
        result.update(azp=CLIENT, tid=TENANT, ver="2.0", scp="email.access")
    result.update(changes)
    return result


def token(key, cfg, *, payload=None, headers=None):
    head = dict(kid="first", typ="at+jwt" if cfg.profile == "rfc9068" else "JWT")
    head.update(headers or {})
    return jwt.encode(payload or claims(cfg), key, algorithm="RS256", headers=head)


class FakeIssuer:
    def __init__(self, key, cfg=None):
        self.config = cfg or config()
        self.key = key
        self.entries = [self.jwk(key, "first")]
        self.urls = []
        self.metadata = {"issuer": self.config.issuer, "jwks_uri": self.config.jwks_url}
        self.status = 200
        self.headers = {}
        self.raw = None
        self.now = 0.0

    @staticmethod
    def jwk(key, kid):
        data = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        return {**data, "kid": kid, "alg": "RS256", "use": "sig"}

    def serve(self, request):
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        assert request.method == "GET" and not request.content
        self.urls.append(str(request.url))
        assert str(request.url) in {self.config.discovery_url, self.config.jwks_url}
        if self.raw is not None:
            return httpx.Response(self.status, content=self.raw, headers=self.headers)
        data = (
            self.metadata
            if str(request.url) == self.config.discovery_url
            else {"keys": self.entries}
        )
        return httpx.Response(self.status, json=data, headers=self.headers)

    def verifier(self):
        return AccessTokenVerifier(
            self.config, transport=httpx.MockTransport(self.serve), monotonic=lambda: self.now
        )


@pytest.fixture(scope="module")
def keys():
    return tuple(rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))


@pytest.fixture
def issuer(keys):
    return FakeIssuer(keys[0])


@pytest.mark.parametrize("profile", ["rfc9068", "entra-v2"])
def test_profile_verifies_access_token_not_authority(keys, profile):
    fake = FakeIssuer(keys[0], config(profile))
    raw = token(
        keys[0],
        fake.config,
        payload=claims(
            fake.config,
            tenant_id=str(uuid4()),
            roles=["owner"],
            email="not-an-identity@example.invalid",
        ),
    )
    result = fake.verifier().verify(raw)
    assert result == VerifiedToken(
        fake.config.issuer,
        "fictional-owner",
        CLIENT,
        datetime.fromtimestamp(jwt.decode(raw, options={"verify_signature": False})["exp"], UTC),
    )
    assert len(fake.urls) == 2


@pytest.mark.parametrize("typ", ["at+jwt", "at+JWT", "application/at+jwt"])
def test_rfc_media_type(issuer, typ):
    assert issuer.verifier().verify(token(issuer.key, issuer.config, headers={"typ": typ}))


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "https://evil.example.invalid"},
        {"aud": CLIENT},
        {"aud": [API, CLIENT]},
        {"sub": ""},
        {"sub": "bad\x00subject"},
        {"sub": "\ud800"},
        {"sub": "x" * 513},
        {"sub": None},
        {"client_id": "unknown"},
        {"jti": ""},
        {"scope": "openid"},
        {"scope": ["email.access"]},
        {"scope": "email.access  other"},
        {"scope": "email.access\tother"},
        {"exp": True},
        {"exp": "2000000000"},
        {"iat": 1.0},
        {"nbf": False},
        {"iat": -1},
        {"iat": 4000000000},
        {"exp": 1},
        {"exp": 4000000000},
        {"nbf": 4000000000},
    ],
)
def test_invalid_claims_do_not_fetch(issuer, change):
    raw = token(issuer.key, issuer.config, payload=claims(issuer.config, **change))
    assert issuer.verifier().verify(raw) is None
    assert issuer.urls == []


@pytest.mark.parametrize("name", ["iss", "aud", "sub", "exp", "iat", "client_id", "jti", "scope"])
def test_missing_rfc_claim(issuer, name):
    payload = claims(issuer.config)
    del payload[name]
    assert issuer.verifier().verify(token(issuer.key, issuer.config, payload=payload)) is None
    assert issuer.urls == []


@pytest.mark.parametrize(
    "change",
    [
        {"typ": "JWT"},
        {"typ": "id+jwt"},
        {"typ": None},
        {"kid": ""},
        {"jku": "https://evil.example.invalid/keys"},
        {"jwk": {}},
        {"crit": []},
        {"b64": True},
        {"x5u": "https://evil.example.invalid/cert"},
        {"zip": "DEF"},
    ],
)
def test_untrusted_jose_controls_rejected(issuer, change):
    raw = token(issuer.key, issuer.config, headers=change)
    if "b64" in change:  # PyJWT's encoder removes b64=True; exercise the actual header.
        parts = raw.split(".")
        header = {"alg": "RS256", "typ": "at+jwt", "kid": "first", **change}
        parts[0] = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        raw = ".".join(parts)
    assert issuer.verifier().verify(raw) is None
    assert issuer.urls == []


@pytest.mark.parametrize(
    "change",
    [
        {"ver": "1.0"},
        {"tid": str(uuid4())},
        {"scp": None},
        {"scp": "openid"},
        {"azp": API},
        {"idtyp": "app"},
        {"nbf": None},
    ],
)
def test_entra_profile_is_explicit(keys, change):
    fake = FakeIssuer(keys[0], config("entra-v2"))
    assert (
        fake.verifier().verify(token(keys[0], fake.config, payload=claims(fake.config, **change)))
        is None
    )
    assert fake.urls == []


def test_signature_and_algorithm_confusion(issuer, keys):
    verifier = issuer.verifier()
    assert verifier.verify(token(keys[1], issuer.config)) is None
    for algorithm, key in [("HS256", b"x" * 32), ("none", "")]:
        raw = jwt.encode(
            claims(issuer.config),
            key,
            algorithm=algorithm,
            headers={"typ": "at+jwt", "kid": "first"},
        )
        assert verifier.verify(raw) is None
    raw = token(issuer.key, issuer.config)
    parts = raw.split(".")
    header = {"alg": "PS256", "typ": "at+jwt", "kid": "first"}
    parts[0] = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    assert verifier.verify(".".join(parts)) is None


@pytest.mark.parametrize(
    "raw", ["", "x", "a.b.c.d", "é.a.b", "x" * 16385, "e30=.e30.AA", "e30.e30.A", "!.e30.AA"]
)
def test_malformed_tokens(issuer, raw):
    assert issuer.verifier().verify(raw) is None
    assert issuer.urls == []


@pytest.mark.parametrize(
    "part,data",
    [
        (0, b'{"alg":"RS256","alg":"RS256","kid":"first","typ":"at+jwt"}'),
        (1, b'{"sub":"owner","sub":"other"}'),
        (1, b'{"exp":NaN}'),
        (1, b'{"nested":' + b"[" * 1100 + b"0" + b"]" * 1100 + b"}"),
    ],
)
def test_ambiguous_json_rejected_before_signature(issuer, part, data):
    parts = token(issuer.key, issuer.config).split(".")
    parts[part] = base64.urlsafe_b64encode(data).decode().rstrip("=")
    assert issuer.verifier().verify(".".join(parts)) is None
    assert issuer.urls == []


def test_single_audience_array(issuer):
    assert issuer.verifier().verify(
        token(issuer.key, issuer.config, payload=claims(issuer.config, aud=[API]))
    )


def test_cache_rotation_cooldown_and_removal(issuer, keys):
    verifier = issuer.verifier()
    first = token(keys[0], issuer.config)
    second = token(keys[1], issuer.config, headers={"kid": "second"})
    assert verifier.verify(first)
    issuer.entries = [issuer.jwk(keys[1], "second")]
    assert verifier.verify(second) is None  # refresh cooldown, not automatic trust
    issuer.now += 31
    assert verifier.verify(second)
    assert verifier.verify(first) is None  # removed key not merged into new cache
    assert len(issuer.urls) == 4
    for index in range(20):
        assert (
            verifier.verify(token(keys[1], issuer.config, headers={"kid": f"unknown-{index}"}))
            is None
        )
    assert len(issuer.urls) == 4


def test_cache_outage_never_extends_expired_keys(issuer):
    verifier = issuer.verifier()
    raw = token(issuer.key, issuer.config)
    assert verifier.verify(raw)
    issuer.status = 503
    issuer.now = 31
    with pytest.raises(AuthenticationUnavailable):
        verifier.verify(token(issuer.key, issuer.config, headers={"kid": "new"}))
    assert verifier.verify(raw)  # valid original TTL, not extended by failed refresh
    issuer.now = 301
    with pytest.raises(AuthenticationUnavailable):
        verifier.verify(raw)
    count = len(issuer.urls)
    with pytest.raises(AuthenticationUnavailable):
        verifier.verify(raw)
    assert len(issuer.urls) == count
    issuer.now += 31
    issuer.status = 200
    assert verifier.verify(raw)


def test_concurrent_cold_cache_one_fetch(issuer):
    verifier = issuer.verifier()
    raw = token(issuer.key, issuer.config)
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert all(pool.map(verifier.verify, [raw] * 30))
    assert len(issuer.urls) == 2


@pytest.mark.parametrize(
    "change",
    [{"issuer": "https://evil.example.invalid"}, {"jwks_uri": "https://evil.example.invalid/keys"}],
)
def test_metadata_cannot_change_trust(issuer, change):
    issuer.metadata.update(change)
    with pytest.raises(AuthenticationUnavailable):
        issuer.verifier().verify(token(issuer.key, issuer.config))
    assert issuer.urls == [issuer.config.discovery_url]


@pytest.mark.parametrize(
    "status,headers,raw",
    [
        (302, {"Location": "https://evil.example.invalid"}, b""),
        (200, {"Content-Encoding": "gzip"}, b""),
        (200, {}, b"x" * 131073),
        (200, {"Content-Length": "500000"}, b"{}"),
        (200, {}, b'{"issuer":"a","issuer":"b"}'),
        (200, {}, b"[]"),
    ],
)
def test_untrusted_http_responses(issuer, status, headers, raw):
    issuer.status, issuer.headers, issuer.raw = status, headers, raw
    with pytest.raises(AuthenticationUnavailable):
        issuer.verifier().verify(token(issuer.key, issuer.config))
    assert len(issuer.urls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"alg": "HS256"},
        {"kty": "oct"},
        {"use": "enc"},
        {"key_ops": ["sign"]},
        {"d": "AA"},
        {"n": "AA"},
        {"e": "Aw"},
        {"kid": ""},
    ],
)
def test_bad_keys_fail_closed(issuer, change):
    issuer.entries[0].update(change)
    with pytest.raises(AuthenticationUnavailable):
        issuer.verifier().verify(token(issuer.key, issuer.config))


def test_duplicate_and_excessive_keys_fail_closed(issuer):
    issuer.entries *= 2
    with pytest.raises(AuthenticationUnavailable):
        issuer.verifier().verify(token(issuer.key, issuer.config))
    issuer.entries *= 40
    with pytest.raises(AuthenticationUnavailable):
        issuer.verifier().verify(token(issuer.key, issuer.config))


@pytest.mark.parametrize(
    "key_issuer,accepted",
    [
        (f"https://login.microsoftonline.com/{TENANT}/v2.0", True),
        ("https://login.microsoftonline.com/{tenantid}/v2.0", True),
        ("https://login.microsoftonline.com/other/v2.0", False),
    ],
)
def test_entra_signing_key_issuer(keys, key_issuer, accepted):
    fake = FakeIssuer(keys[0], config("entra-v2"))
    fake.entries[0]["issuer"] = key_issuer
    if accepted:
        assert fake.verifier().verify(token(keys[0], fake.config))
    else:
        with pytest.raises(AuthenticationUnavailable):
            fake.verifier().verify(token(keys[0], fake.config))


@pytest.mark.parametrize(
    "url",
    [
        "http://issuer.example.invalid",
        "https://localhost/x",
        "https://127.0.0.1/x",
        "https://169.254.169.254/x",
        "https://10.0.0.1/x",
        "https://[::1]/x",
        "https://user:password@issuer.example.invalid/x",
        "https://issuer.example.invalid:444/x",
        "https://issuer.example.invalid/x?y=z",
        "https://issuer.example.invalid/#x",
        "https://issuer.example.invalid/%2fother",
        "https://issuer.example.invalid/a/../b",
        "https://issuer.example.invalid\\evil/x",
        "https://service.internal/x",
    ],
)
def test_configuration_url_boundary(url):
    with pytest.raises(ValueError):
        OIDCConfig.model_validate({**config().model_dump(), "jwks_url": url})


@pytest.mark.parametrize(
    "change",
    [
        {"client_ids": [API]},
        {"client_ids": []},
        {"client_ids": [CLIENT, CLIENT]},
        {"profile": "anything"},
        {"entra_tenant_id": TENANT},
        {"version": True},
        {"extra": "field"},
        {"admission_scope": "two scopes"},
    ],
)
def test_configuration_closed_and_separated(change):
    with pytest.raises(ValueError):
        OIDCConfig.model_validate({**config().model_dump(), **change})


def test_private_configuration(tmp_path):
    directory = tmp_path.resolve()
    directory.chmod(0o700)
    path = directory / "issuer.json"
    path.write_text(config().model_dump_json())
    path.chmod(0o600)
    assert OIDCConfig.from_file(path) == config()
    path.chmod(0o644)
    with pytest.raises(ValueError):
        OIDCConfig.from_file(path)
    path.chmod(0o600)
    link = directory / "alias.json"
    link.symlink_to(path)
    with pytest.raises((ValueError, OSError)):
        OIDCConfig.from_file(link)


def test_network_timeout_and_client_security_options(issuer, monkeypatch):
    real_client = httpx.Client
    observed = []

    def factory(**kwargs):
        observed.append(kwargs)
        return real_client(**kwargs)

    def fail(request):
        raise httpx.ReadTimeout("sensitive transport diagnostics")

    monkeypatch.setattr(httpx, "Client", factory)
    verifier = AccessTokenVerifier(issuer.config, transport=httpx.MockTransport(fail))
    with pytest.raises(AuthenticationUnavailable) as exc:
        verifier.verify(token(issuer.key, issuer.config))
    assert str(exc.value) == ""
    assert observed[0]["trust_env"] is False and observed[0]["follow_redirects"] is False
    assert observed[0]["timeout"].read == 5 and observed[0]["timeout"].connect == 2


def test_slow_drip_cannot_delay_deadline_until_buffer_fills(issuer, monkeypatch):
    chunks = []
    times = iter([0.0, 1.0, 11.0])
    monkeypatch.setattr(
        identity_module, "time", SimpleNamespace(time=time.time, monotonic=lambda: next(times))
    )

    class Drip(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                chunks.append(1)
                assert len(chunks) <= 2, "deadline postponed while buffering response"
                yield b"x"

    verifier = AccessTokenVerifier(
        issuer.config,
        monotonic=lambda: 0.0,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Drip())),
    )
    with pytest.raises(AuthenticationUnavailable):
        verifier.verify(token(issuer.key, issuer.config))
    assert len(chunks) == 2


def test_weak_rsa_key_rejected(issuer):
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    issuer.entries = [issuer.jwk(weak, "first")]
    with pytest.raises(AuthenticationUnavailable):
        issuer.verifier().verify(token(issuer.key, issuer.config))


def test_completed_metadata_response_still_obeys_deadline(issuer, monkeypatch):
    times = iter([0.0, 1.0, 11.0])
    monkeypatch.setattr(
        identity_module, "time", SimpleNamespace(time=time.time, monotonic=lambda: next(times))
    )
    with pytest.raises(AuthenticationUnavailable):
        issuer.verifier().verify(token(issuer.key, issuer.config))
    assert issuer.urls == [issuer.config.discovery_url]


def test_mixed_key_set_ignores_unsupported_keys(issuer):
    issuer.entries.append({"kid": "unsupported", "kty": "EC", "alg": "ES256"})
    assert issuer.verifier().verify(token(issuer.key, issuer.config))


def test_cached_key_expiry_refreshes_even_without_unknown_kid(issuer, keys):
    verifier = issuer.verifier()
    old = token(keys[0], issuer.config)
    changed = token(keys[1], issuer.config)
    assert verifier.verify(old)
    issuer.entries = [issuer.jwk(keys[1], "first")]
    assert verifier.verify(changed) is None
    assert len(issuer.urls) == 2
    issuer.now = 301
    assert verifier.verify(changed)
    assert verifier.verify(old) is None
    assert len(issuer.urls) == 4


def test_api_auth_errors_are_scrubbed(issuer, caplog):
    auth = OIDCAuthenticator(Store("never-connect"), issuer.verifier())
    client = TestClient(create_app(auth.store, auth))
    invalid = client.get("/readyz", headers={"Authorization": "Bearer malformed"})
    assert invalid.status_code == 401 and "invalid_token" in invalid.headers["www-authenticate"]
    issuer.status = 503
    raw = token(issuer.key, issuer.config)
    response = client.get("/readyz", headers={"Authorization": "Bearer " + raw})
    assert response.status_code == 503
    assert response.json() == {"error": "authentication_unavailable"}
    assert raw not in response.text + caplog.text
    assert "fictional-owner" not in response.text + caplog.text


def test_missing_credential_is_a_plain_bearer_challenge(issuer):
    auth = OIDCAuthenticator(Store("never-connect"), issuer.verifier())
    response = TestClient(create_app(auth.store, auth)).get("/readyz")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert issuer.urls == []


@pytest.mark.parametrize("valid_first", [True, False])
def test_duplicate_authorization_rejected_before_verification(issuer, valid_first):
    auth = OIDCAuthenticator(Store("never-connect"), issuer.verifier())
    valid = ("Authorization", "Bearer " + token(issuer.key, issuer.config))
    invalid = ("Authorization", "Bearer malformed")
    response = TestClient(create_app(auth.store, auth)).get(
        "/readyz", headers=[valid, invalid] if valid_first else [invalid, valid]
    )
    assert response.status_code == 401
    assert issuer.urls == []


def test_api_authority_comes_from_mapping_not_signed_roles(issuer, monkeypatch):
    auth = OIDCAuthenticator(Store("never-connect"), issuer.verifier())
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"email.search"}), uuid4())
    monkeypatch.setattr(auth, "resolve", lambda _: Principal(ctx, "assistant"))
    raw = token(
        issuer.key,
        issuer.config,
        payload=claims(issuer.config, roles=["owner"], scope="email.access email.review"),
    )
    client = TestClient(create_app(auth.store, auth))
    response = client.get(
        "/v1/evidence/" + str(uuid4()), headers={"Authorization": "Bearer " + raw}
    )
    assert response.status_code == 403


def test_cli_explicit_mode_no_bootstrap_fallback(issuer, monkeypatch):
    from email_brain import cli

    monkeypatch.setenv("EMAIL_BRAIN_DSN", "never-connect")
    monkeypatch.delenv("EMAIL_BRAIN_CREDENTIALS_FILE", raising=False)
    monkeypatch.setattr(OIDCConfig, "from_file", lambda _: issuer.config)
    captured = {}
    monkeypatch.setattr(
        cli,
        "create_app",
        lambda store, registry, **kw: captured.update(store=store, registry=registry) or "app",
    )
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: captured.update(kw))
    monkeypatch.setattr(
        "sys.argv", ["email-brain", "serve", "--oidc-config", "/private/issuer.json"]
    )
    cli.main()
    assert isinstance(captured["registry"], OIDCAuthenticator)
    assert captured["host"] == "127.0.0.1" and captured["proxy_headers"] is False
    assert issuer.urls == []  # configuration/startup does not contact issuer
    monkeypatch.setenv("EMAIL_BRAIN_CREDENTIALS_FILE", "/private/bootstrap.json")
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
