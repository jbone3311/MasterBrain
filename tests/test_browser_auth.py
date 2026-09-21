"""Generated access tokens and fake HTTPS exercise the complete server-side flow."""

import base64
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import psycopg
import pytest
import test_oidc as oidc
from fastapi.testclient import TestClient

from email_brain.api import create_app
from email_brain.auth import AuthenticationUnavailable, Principal
from email_brain.browser_auth import (
    SESSION_COOKIE,
    BrowserAuth,
    BrowserConfig,
    BrowserDenied,
)
from email_brain.domain.models import ExternalIdentity, TenantContext
from email_brain.oidc import OIDCAuthenticator
from email_brain.store import AccessDenied

keys = oidc.keys


def configuration(identity=None, **changes):
    identity = identity or oidc.config()
    origin = urlsplit(identity.issuer)
    root = f"{origin.scheme}://{origin.netloc}"
    if identity.profile == "entra-v2":
        root += f"/{identity.entra_tenant_id}/oauth2/v2.0"
    return BrowserConfig.model_validate(
        {
            "version": 1,
            "identity": identity,
            "public_origin": "https://brain.example.invalid",
            "authorization_endpoint": root + "/authorize",
            "token_endpoint": root + "/token",
            "client_id": oidc.CLIENT,
            "client_secret": "fictional-client-credential",
            "scopes": ["email.access"],
            **changes,
        }
    )


class FakeStore:
    def __init__(self):
        self.denied = False
        self.offline = False
        self.barrier = None

    @contextmanager
    def transaction(self, context):
        if self.offline:
            raise psycopg.OperationalError("private database detail")
        if self.denied:
            raise AccessDenied()
        if self.barrier:
            self.barrier.wait(timeout=3)
        yield SimpleNamespace(execute=lambda *_: None)

    def search(self, context, body):
        with self.transaction(context):
            return []


class Fixture:
    def __init__(self, key, profile="rfc9068", *, real_auth=None, raw=None, identity=None):
        self.fake = oidc.FakeIssuer(key, identity or oidc.config(profile))
        self.config = configuration(self.fake.config)
        self.store = real_auth.store if real_auth else FakeStore()
        self.auth = real_auth or OIDCAuthenticator(self.store, self.fake.verifier())
        if real_auth is None:
            self.auth.resolve = self.resolve
        self.raw = raw or oidc.token(key, self.config.identity)
        self.data = {"token_type": "Bearer", "access_token": self.raw, "expires_in": 3600}
        self.status = 200
        self.raw_response = None
        self.response_headers = {}
        self.calls = []
        self.now = 0.0
        self.wall = float(int(time.time()))
        self.kind = "human"
        self.mapped = True
        self.exchange_hook = None
        self.browser = BrowserAuth(
            self.config,
            self.auth,
            transport=httpx.MockTransport(self.exchange),
            monotonic=lambda: self.now,
            wall_clock=lambda: self.wall,
        )

    def resolve(self, verified):
        if not self.mapped:
            return None
        identity = ExternalIdentity(
            uuid4(),
            verified.issuer,
            verified.subject,
            verified.client_id,
            1,
            self.kind,
            verified.expires_at,
        )
        return Principal(
            TenantContext(uuid4(), uuid4(), frozenset({"email.search"}), uuid4(), identity),
            self.kind,
        )

    def exchange(self, request):
        assert str(request.url) == self.config.token_endpoint
        assert request.method == "POST"
        assert "cookie" not in request.headers and "authorization" not in request.headers
        self.calls.append(parse_qs(request.content.decode()))
        if self.exchange_hook:
            self.exchange_hook()
        if self.raw_response is not None:
            return httpx.Response(
                self.status, content=self.raw_response, headers=self.response_headers
            )
        return httpx.Response(self.status, json=self.data, headers=self.response_headers)

    def begin(self, previous=None):
        cookie, csrf = self.browser.prepare(None)
        url = self.browser.start(cookie, csrf, previous)
        return cookie, parse_qs(urlsplit(url).query)

    def login(self, previous=None):
        flow, query = self.begin(previous)
        cookie = self.browser.finish(flow, {"state": query["state"][0], "code": "fictional-code"})
        return cookie

    def client(self):
        return TestClient(
            create_app(self.store, self.auth, browser_auth=self.browser),
            base_url=self.config.public_origin,
            follow_redirects=False,
        )


@pytest.fixture
def fixture(keys):
    return Fixture(keys[0])


@pytest.mark.parametrize("profile", ["rfc9068", "entra-v2"])
def test_code_pkce_session_and_token_not_retained(keys, profile):
    fixture = Fixture(keys[0], profile)
    flow, query = fixture.begin()
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [fixture.config.redirect_uri]
    assert "nonce" not in query and "openid" not in query["scope"][0]
    cookie = fixture.browser.finish(
        flow,
        {
            "state": query["state"][0],
            "code": "fictional-code",
            "iss": fixture.config.identity.issuer,
        },
    )
    sent = fixture.calls[0]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(sent["code_verifier"][0].encode()).digest())
        .decode()
        .rstrip("=")
    )
    assert query["code_challenge"] == [challenge]
    assert sent["client_id"] == [fixture.config.client_id]
    assert sent["redirect_uri"] == [fixture.config.redirect_uri]
    assert sent["grant_type"] == ["authorization_code"]
    session = fixture.browser.authenticate(cookie)
    assert session.principal.client_kind == "human"
    assert session.principal.context.identity.client_id == fixture.config.client_id
    assert fixture.raw not in repr(fixture.browser._sessions)
    assert cookie not in fixture.browser._sessions
    with pytest.raises(BrowserDenied):
        fixture.browser.finish(flow, {"state": query["state"][0], "code": "fictional-code"})
    assert len(fixture.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"public_origin": "http://brain.example.invalid"},
        {"public_origin": "https://brain.example.invalid/"},
        {"public_origin": "https://user@brain.example.invalid"},
        {"public_origin": "https://brain.example.invalid?next=evil"},
        {"public_origin": "https://localhost:0"},
        {"public_origin": "https://localhost#"},
        {"public_origin": "https://localhost?"},
        {"public_origin": "https://localhost:443"},
        {"authorization_endpoint": "https://evil.example.invalid/authorize"},
        {"token_endpoint": "http://issuer.example.invalid/token"},
        {"token_endpoint": "https://issuer.example.invalid/token?next=evil"},
        {"client_id": "not-configured"},
        {"client_secret": "short"},
        {"scopes": ["openid"]},
        {"scopes": ["offline_access"]},
        {"scopes": ["profile"]},
        {"scopes": ["email"]},
        {"scopes": []},
        {"scopes": ["email.access", "email.access"]},
        {"scopes": ["email.access other"]},
        {"unexpected": True},
    ],
)
def test_closed_configuration(change):
    with pytest.raises(ValueError):
        configuration(**change)


@pytest.mark.parametrize("origin", ["https://localhost:8765", "https://127.0.0.1:8765"])
def test_explicit_loopback_tls_origin(origin):
    assert configuration(public_origin=origin).redirect_uri == origin + "/auth/callback"


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "x" * 43},
        {"iss": "https://evil.example.invalid"},
        {"error": "access_denied"},
        {"code": ""},
        {"code": "x" * 4097},
        {"code": "bad\x00code"},
        {"code": "é"},
        {"access_token": "never-accepted"},
        {"redirect_uri": "https://evil.example.invalid"},
    ],
)
def test_callback_denial_consumes_flow_without_exchange(fixture, changes):
    flow, query = fixture.begin()
    params = {"state": query["state"][0], "code": "fictional-code"}
    with pytest.raises(BrowserDenied):
        fixture.browser.finish(flow, {**params, **changes})
    with pytest.raises(BrowserDenied):
        fixture.browser.finish(flow, params)
    assert not fixture.calls


def test_browser_binding_and_one_use_start(fixture):
    first, csrf = fixture.browser.prepare(None)
    url = fixture.browser.start(first, csrf, None)
    query = parse_qs(urlsplit(url).query)
    second, _ = fixture.browser.prepare(None)
    params = {"state": query["state"][0], "code": "fictional-code"}
    with pytest.raises(BrowserDenied):
        fixture.browser.finish(second, params)
    with pytest.raises(BrowserDenied):
        fixture.browser.start(first, csrf, None)
    assert fixture.browser.finish(first, params)


@pytest.mark.parametrize(
    "response",
    [
        {"token_type": "MAC"},
        {"token_type": 7},
        {"access_token": "bad"},
        {"access_token": None},
        {"id_token": "never-retained"},
        {"refresh_token": "never-retained"},
        {"expires_in": 0},
        {"expires_in": True},
        {"expires_in": 7201},
    ],
)
def test_exchange_rejects_wrong_contract_and_tokens(fixture, response):
    fixture.data.update(response)
    with pytest.raises(BrowserDenied):
        fixture.login()
    assert not fixture.browser._sessions


@pytest.mark.parametrize(
    "status,error",
    [
        (302, BrowserDenied),
        (400, BrowserDenied),
        (401, BrowserDenied),
        (429, AuthenticationUnavailable),
        (500, AuthenticationUnavailable),
    ],
)
def test_exchange_status_is_scrubbed(fixture, status, error):
    fixture.status = status
    fixture.data = {"error_description": "private provider diagnostic"}
    with pytest.raises(error) as caught:
        fixture.login()
    assert str(caught.value) == ""
    assert not fixture.browser._sessions


@pytest.mark.parametrize(
    "raw", [b"not-json", b"[]", b'{"access_token":1,"access_token":2}', b"x" * 32769]
)
def test_exchange_payload_bounds(fixture, raw):
    fixture.raw_response = raw
    with pytest.raises(BrowserDenied):
        fixture.login()


@pytest.mark.parametrize("kind", ["assistant", "worker", "unknown"])
def test_only_existing_human_mapping(fixture, kind):
    fixture.kind = kind
    with pytest.raises(BrowserDenied):
        fixture.login()


def test_unknown_mapping(fixture):
    fixture.mapped = False
    with pytest.raises(BrowserDenied):
        fixture.login()


@pytest.mark.parametrize("case", ["pending", "idle", "absolute", "exchange"])
def test_deadlines(fixture, case):
    if case == "pending":
        flow, query = fixture.begin()
        fixture.now = 300
        with pytest.raises(BrowserDenied):
            fixture.browser.finish(flow, {"state": query["state"][0], "code": "fictional-code"})
        assert not fixture.calls
    elif case == "exchange":
        fixture.exchange_hook = lambda: setattr(fixture, "now", 11)
        with pytest.raises(AuthenticationUnavailable):
            fixture.login()
    else:
        cookie = fixture.login()
        if case == "idle":
            fixture.now = 900
        else:
            fixture.wall += 3600
        with pytest.raises(BrowserDenied):
            fixture.browser.authenticate(cookie)


def test_idle_renewal_cannot_extend_absolute_expiry(fixture):
    cookie = fixture.login()
    expiry = fixture.browser.authenticate(cookie).absolute_expiry
    for index in range(1, 5):
        fixture.now = index * 800
        fixture.wall += 600
        assert fixture.browser.authenticate(cookie).absolute_expiry == expiry
    fixture.wall = expiry
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(cookie)


def test_revocation_is_sticky_but_database_outage_is_not(fixture):
    cookie = fixture.login()
    fixture.store.offline = True
    with pytest.raises(AuthenticationUnavailable):
        fixture.browser.authenticate(cookie)
    fixture.store.offline = False
    assert fixture.browser.authenticate(cookie)
    fixture.store.denied = True
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(cookie)
    fixture.store.denied = False
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(cookie)


def test_logout_replay_and_reauthentication_rotation(fixture):
    old = fixture.login()
    new = fixture.login(old)
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(old)
    csrf = fixture.browser.authenticate(new).csrf
    fixture.browser.logout(new, csrf)
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(new)


def test_logout_wins_against_pending_reauthentication(fixture):
    old = fixture.login()
    csrf = fixture.browser.authenticate(old).csrf
    fixture.exchange_hook = lambda: fixture.browser.logout(old, csrf)
    with pytest.raises(BrowserDenied):
        fixture.login(old)
    assert not fixture.browser._sessions


def test_concurrent_reads_do_not_invalidate_each_other(fixture):
    cookie = fixture.login()
    fixture.store.barrier = threading.Barrier(4)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: fixture.browser.authenticate(cookie), range(4)))
    assert len(rows) == 4 and len({row.csrf for row in rows}) == 1


def test_concurrent_callback_has_one_winner(fixture):
    flow, query = fixture.begin()
    params = {"state": query["state"][0], "code": "fictional-code"}

    def finish(_):
        try:
            return fixture.browser.finish(flow, params)
        except BrowserDenied:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(value is not None for value in pool.map(finish, range(4))) == 1
    assert len(fixture.calls) == 1


def test_flow_capacity_and_expiry(fixture):
    for _ in range(128):
        fixture.browser.prepare(None)
    with pytest.raises(AuthenticationUnavailable):
        fixture.browser.prepare(None)
    fixture.now = 300
    assert fixture.browser.prepare(None)
    assert len(fixture.browser._flows) == 1


def web_start(client):
    info = client.get("/auth/session")
    assert info.status_code == 200 and not info.json()["authenticated"]
    response = client.post(
        "/auth/login",
        headers={
            "Origin": str(client.base_url).rstrip("/"),
            "X-CSRF-Token": info.json()["csrf_token"],
        },
    )
    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    return query["state"][0]


def web_login(client):
    state = web_start(client)
    callback = client.get("/auth/callback", params={"state": state, "code": "fictional-code"})
    assert callback.status_code == 303 and callback.headers["location"] == "/"
    return callback


def test_http_flow_cookie_security_search_logout_and_no_disclosure(fixture, caplog):
    caplog.set_level("INFO", logger="email_brain.requests")
    client = fixture.client()
    response = web_login(client)
    session_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(SESSION_COOKIE)
    )
    assert "Secure" in session_cookie and "HttpOnly" in session_cookie
    assert "SameSite=strict" in session_cookie and "Path=/" in session_cookie
    assert "Domain=" not in session_cookie
    info = client.get("/auth/session").json()
    assert info["authenticated"] and fixture.raw not in json.dumps(info)
    headers = {"Origin": fixture.config.public_origin, "X-CSRF-Token": info["csrf_token"]}
    assert client.post("/v1/search", headers=headers, json={"query": "Melron"}).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/readyz").status_code == 401
    assert fixture.raw not in caplog.text and "fictional-code" not in caplog.text
    assert "/auth/callback" in caplog.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://evil.example.invalid", "X-CSRF-Token": "x" * 43},
        {"Origin": "null", "X-CSRF-Token": "x" * 43},
        {"Origin": "https://brain.example.invalid"},
        {"Origin": "https://brain.example.invalid", "X-CSRF-Token": "wrong"},
    ],
)
def test_cookie_post_requires_origin_and_csrf(fixture, headers):
    client = fixture.client()
    web_login(client)
    assert client.post("/v1/search", headers=headers, json={"query": "Melron"}).status_code in {
        401,
        403,
    }


def test_mixed_credentials_and_duplicate_cookies_are_denied(fixture):
    client = fixture.client()
    web_login(client)
    assert (
        client.get("/readyz", headers={"Authorization": "Bearer " + fixture.raw}).status_code == 401
    )
    cookie = client.cookies.get(SESSION_COOKIE)
    assert (
        client.get(
            "/readyz", headers={"Cookie": f"{SESSION_COOKIE}={cookie}; {SESSION_COOKIE}={cookie}"}
        ).status_code
        == 401
    )
    assert client.get("/auth/session", headers={"Host": "evil.example.invalid"}).status_code == 403


def test_duplicate_callback_query_consumes_flow(fixture):
    client = fixture.client()
    info = client.get("/auth/session").json()
    response = client.post(
        "/auth/login",
        headers={
            "Origin": fixture.config.public_origin,
            "X-CSRF-Token": info["csrf_token"],
        },
    )
    state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    assert client.get(f"/auth/callback?state={state}&code=one&code=two").status_code == 401
    assert client.get(f"/auth/callback?state={state}&code=one").status_code == 401
    assert not fixture.calls


def test_browser_routes_absent_unless_explicit(fixture):
    client = TestClient(create_app(fixture.store, fixture.auth))
    assert client.get("/auth/session").status_code == 404


def test_app_cannot_mix_authenticator(fixture):
    with pytest.raises(ValueError):
        create_app(fixture.store, object(), browser_auth=fixture.browser)


def test_clock_rollback_cannot_extend_session_lifetime(fixture):
    cookie = fixture.login()
    fixture.wall -= 10000
    for index in range(1, 5):
        fixture.now = index * 800
        fixture.browser.authenticate(cookie)
    fixture.now = 3600
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(cookie)


def test_response_expiry_caps_session(fixture):
    fixture.data["expires_in"] = 5
    cookie = fixture.login()
    assert fixture.browser.authenticate(cookie).absolute_expiry == fixture.wall + 5
    fixture.now += 5
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(cookie)


def test_wrong_csrf_does_not_renew_idle(fixture):
    cookie = fixture.login()
    fixture.now = 899
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(cookie, csrf="wrong")
    fixture.now = 900
    with pytest.raises(BrowserDenied):
        fixture.browser.authenticate(cookie)


def test_logout_wins_while_request_rechecks_database(fixture):
    cookie = fixture.login()
    csrf = fixture.browser.authenticate(cookie).csrf
    entered, release = threading.Event(), threading.Event()

    @contextmanager
    def transaction(_):
        entered.set()
        assert release.wait(timeout=3)
        yield None

    fixture.store.transaction = transaction
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fixture.browser.authenticate, cookie)
        assert entered.wait(timeout=3)
        fixture.browser.logout(cookie, csrf)
        release.set()
        with pytest.raises(BrowserDenied):
            future.result(timeout=3)


def test_session_capacity_does_not_evict_valid_sessions(fixture):
    cookie = fixture.login()
    row = fixture.browser.authenticate(cookie)
    for index in range(1023):
        fixture.browser._sessions[f"synthetic-capacity-{index}"] = row
    with pytest.raises(AuthenticationUnavailable):
        fixture.login()
    assert fixture.browser.authenticate(cookie)
    replacement = fixture.login(cookie)
    assert fixture.browser.authenticate(replacement)
    assert len(fixture.browser._sessions) == 1024


def test_exchange_read_timeout_is_unavailable(fixture):
    def fail():
        raise httpx.ReadTimeout("private endpoint and diagnostic")

    fixture.exchange_hook = fail
    with pytest.raises(AuthenticationUnavailable) as caught:
        fixture.login()
    assert not str(caught.value)


def test_compressed_exchange_refused(fixture):
    # Empty bytes avoid asking HTTPX to decode an intentionally fictional gzip stream.
    fixture.raw_response = b""
    fixture.response_headers = {"Content-Encoding": "gzip"}
    with pytest.raises(BrowserDenied):
        fixture.login()


@pytest.mark.parametrize(
    "headers",
    [
        [("Origin", "https://brain.example.invalid"), ("Origin", "https://brain.example.invalid")],
        [
            ("Origin", "https://brain.example.invalid"),
            ("X-CSRF-Token", "one"),
            ("X-CSRF-Token", "two"),
        ],
    ],
)
def test_duplicate_browser_headers_denied(fixture, headers):
    client = fixture.client()
    client.get("/auth/session")
    assert client.post("/auth/login", headers=headers).status_code == 403
    assert not fixture.calls


def test_logout_cancels_pending_browser_flow(fixture):
    client = fixture.client()
    web_login(client)
    info = client.get("/auth/session").json()
    flow, query = fixture.begin(client.cookies.get(SESSION_COOKIE))
    client.cookies.set("__Host-emailbrain-flow", flow, domain="brain.example.invalid", path="/")
    assert (
        client.post(
            "/auth/logout",
            headers={
                "Origin": fixture.config.public_origin,
                "X-CSRF-Token": info["csrf_token"],
            },
        ).status_code
        == 204
    )
    with pytest.raises(BrowserDenied):
        fixture.browser.finish(flow, {"state": query["state"][0], "code": "fictional-code"})


@pytest.mark.parametrize("operation", ["discard", "replace"])
def test_cancelled_inflight_flow_cannot_publish(fixture, operation):
    flow, query = fixture.begin()
    fixture.exchange_hook = (
        (lambda: fixture.browser.discard_flow(flow))
        if operation == "discard"
        else (lambda: fixture.browser.prepare(flow))
    )
    with pytest.raises(BrowserDenied):
        fixture.browser.finish(flow, {"state": query["state"][0], "code": "fictional-code"})
    assert not fixture.browser._sessions


def test_other_allowed_api_client_is_not_this_browser_client(keys):
    cfg = oidc.config().model_copy(update={"client_ids": (oidc.CLIENT, "another-api-client")})
    fixture = Fixture(keys[0], identity=cfg)
    fixture.data["access_token"] = oidc.token(
        keys[0], cfg, payload=oidc.claims(cfg, client_id="another-api-client")
    )
    with pytest.raises(BrowserDenied):
        fixture.login()


def test_exchange_checks_slow_fragments_before_reading_more(fixture):
    chunks = []

    class Slow(httpx.SyncByteStream):
        def __iter__(self):
            for tick in (1, 11, 12):
                chunks.append(tick)
                assert len(chunks) <= 2, "deadline check was buffered"
                fixture.now = tick
                yield b"x"

    fixture.browser._transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Slow()))
    with pytest.raises(AuthenticationUnavailable):
        fixture.login()
    assert chunks == [1, 11]


@pytest.mark.parametrize("site", ["cross-site", "same-site", "unrecognized"])
def test_cross_site_discovery_cannot_clear_or_replace_cookies(fixture, site):
    client = fixture.client()
    response = client.get("/auth/session", headers={"Sec-Fetch-Site": site})
    assert response.status_code == 403 and "set-cookie" not in response.headers
    assert not fixture.browser._flows


def test_cross_site_top_level_callback_with_bound_state(fixture):
    client = fixture.client()
    state = web_start(client)
    response = client.get(
        "/auth/callback",
        params={"state": state, "code": "fictional-code"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 303


def test_restart_invalidates_session_without_database_mutation(fixture):
    cookie = fixture.login()
    restarted = BrowserAuth(fixture.config, fixture.auth)
    with pytest.raises(BrowserDenied):
        restarted.authenticate(cookie)


@pytest.mark.parametrize("case", ["valid", "public", "symlink", "invalid"])
def test_private_configuration_loading_is_scrubbed(tmp_path, case):
    tmp_path.chmod(0o700)
    cfg = configuration()
    data = cfg.model_dump(mode="json")
    secret = cfg.client_secret.get_secret_value()
    data["client_secret"] = secret
    if case == "invalid":
        data["public_origin"] = "http://brain.example.invalid"
    path = tmp_path / "browser.json"
    path.write_text(json.dumps(data))
    path.chmod(0o644 if case == "public" else 0o600)
    if case == "symlink":
        link = tmp_path / "linked.json"
        link.symlink_to(path)
        path = link
    if case == "valid":
        loaded = BrowserConfig.from_file(path)
        assert loaded == cfg and secret not in repr(loaded)
    else:
        with pytest.raises(ValueError, match="invalid private browser configuration") as caught:
            BrowserConfig.from_file(path)
        assert secret not in str(caught.value) and str(path) not in str(caught.value)
