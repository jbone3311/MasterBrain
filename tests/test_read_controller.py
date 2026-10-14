"""Read operator contracts: private fictional files, no network or live database."""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
from test_processing_controller import controller_files, private_write

from email_brain import cli
from email_brain import read_controller as control
from email_brain.connectors.jmap import ScopedMailWindow
from email_brain.processing_controller import ControllerError


def read_files(root, tenant=None, actor=None, account=None):
    path, config, creds, token = controller_files(root, tenant, actor, account)
    config.pop("image_id")
    config.pop("docker_binary")
    config.update(
        job_kind="fastmail-read",
        provider_account_id="provider-a",
        provider_secret_ref="synthetic:none",
        provider_token_file=str(path.parent / "provider-token"),
    )
    creds[0]["scopes"] = ["email.ingest"]
    private_write(path, config)
    private_write(path.parent / "credentials.json", creds)
    private_write(path.parent / "provider-token", b"synthetic-provider-token-only")
    return path, config, creds, token


@pytest.fixture
def configured(tmp_path, monkeypatch):
    files = read_files(tmp_path)
    store = MagicMock()
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = {
        "provider_account_id": "provider-a",
        "secret_ref": "synthetic:none",
        "read_scope_sha256": None,
        "paused": False,
    }
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    client = Mock()
    monkeypatch.setattr(control, "_GuardedFastmail", Mock(return_value=client))
    worker = Mock()
    worker.step.return_value = "progress"
    monkeypatch.setattr(control, "ReadWorker", Mock(return_value=worker))
    return files, store, client, worker


def run(path, **options):
    return control.run_read_controller(path, "synthetic", allow_provider_read=True, **options)


def scoped(configured):
    (path, config, _, _), store, _, _ = configured
    config["version"] = 2
    config["read_scope"] = {
        "mailbox_id": "inbox",
        "after": "2026-09-18T00:00:00Z",
        "before": "2026-09-21T00:00:00Z",
    }
    private_write(path, config)
    window = control.ScopedReadWindowConfig.model_validate(config["read_scope"]).window()
    store.transaction.return_value.__enter__.return_value.execute.return_value.fetchone.return_value[
        "read_scope_sha256"
    ] = window.fingerprint()
    return path, config, store, window


def test_scoped_preflight_and_worker_bind_exact_window(configured):
    path, _, _, window = scoped(configured)
    assert control.run_read_controller(path, "synthetic", check=True)["provider_requests"] == 0
    control._GuardedFastmail.assert_not_called()
    control.ReadWorker.assert_not_called()
    assert run(path)["results"]["progress"] == 1
    selected = control.ReadWorker.call_args.kwargs["scope"]
    assert isinstance(selected, ScopedMailWindow)
    assert selected == window


def test_scoped_exclusion_is_private_config_and_exact_pin(configured):
    path, config, store, previous = scoped(configured)
    config["read_scope"]["excluded_mailbox_ids"] = ["private"]
    private_write(path, config)
    with pytest.raises(ControllerError):
        control.run_read_controller(path, "synthetic", check=True)
    assert previous.fingerprint() != control.ScopedReadWindowConfig.model_validate(
        config["read_scope"]
    ).window().fingerprint()
    selected = control.ScopedReadWindowConfig.model_validate(config["read_scope"]).window()
    store.transaction.return_value.__enter__.return_value.execute.return_value.fetchone.return_value[
        "read_scope_sha256"
    ] = selected.fingerprint()
    assert control.run_read_controller(path, "synthetic", check=True)["provider_requests"] == 0
    control._GuardedFastmail.assert_not_called()


@pytest.mark.parametrize("excluded", ["private", ["inbox"], ["z", "a"],
                                      ["private", "private"], [1], ["private\n"]])
def test_bad_exclusion_config_fails_before_database(configured, excluded):
    (path, config, _, _), _, _, _ = configured
    config["version"] = 2
    config["read_scope"] = {
        "mailbox_id": "inbox", "after": "2026-09-18T00:00:00Z",
        "before": "2026-09-21T00:00:00Z", "excluded_mailbox_ids": excluded,
    }
    private_write(path, config)
    with pytest.raises(ControllerError):
        run(path)
    control.Store.assert_not_called()


@pytest.mark.parametrize(
    "scope",
    [
        None,
        {},
        {"mailbox_id": 1, "after": "2026-09-18T00:00:00Z", "before": "2026-09-21T00:00:00Z"},
        {"mailbox_id": " inbox", "after": "2026-09-18T00:00:00Z", "before": "2026-09-21T00:00:00Z"},
        {
            "mailbox_id": "inbox", "after": "2026-09-18T00:00:00+00:00",
            "before": "2026-09-21T00:00:00Z",
        },
        {
            "mailbox_id": "inbox", "after": "2026-09-18T00:00:00.000Z",
            "before": "2026-09-21T00:00:00Z",
        },
        {"mailbox_id": "inbox", "after": "2026-09-32T00:00:00Z", "before": "2026-09-21T00:00:00Z"},
        {"mailbox_id": "inbox", "after": "2026-09-21T00:00:00Z", "before": "2026-09-18T00:00:00Z"},
        {"mailbox_id": "inbox", "after": "2026-09-18T00:00:00Z", "before": "2026-10-20T00:00:00Z"},
        {
            "mailbox_id": "inbox", "after": "2026-09-18T00:00:00Z",
            "before": "2026-09-21T00:00:00Z", "extra": True,
        },
    ],
)
def test_invalid_scoped_config_never_opens_database(configured, scope):
    (path, config, _, _), _, _, _ = configured
    config["version"] = 2
    if scope is not None:
        config["read_scope"] = scope
    private_write(path, config)
    with pytest.raises(ControllerError):
        run(path)
    control.Store.assert_not_called()


@pytest.mark.parametrize("scope", [None, {
    "mailbox_id": "inbox",
    "after": "2026-09-18T00:00:00Z",
    "before": "2026-09-21T00:00:00Z",
}])
def test_version_one_cannot_carry_scoped_window(configured, scope):
    (path, config, _, _), _, _, _ = configured
    config["read_scope"] = scope
    private_write(path, config)
    with pytest.raises(ControllerError):
        run(path)
    control.Store.assert_not_called()


def test_scoped_preflight_rejects_unpinned_or_wrong_pin(configured):
    path, _, store, _ = scoped(configured)
    conn = store.transaction.return_value.__enter__.return_value
    row = conn.execute.return_value.fetchone.return_value
    for digest in (None, "0" * 64):
        row["read_scope_sha256"] = digest
        with pytest.raises(ControllerError):
            control.run_read_controller(path, "synthetic", check=True)
    control._GuardedFastmail.assert_not_called()
    control.ReadWorker.assert_not_called()


def test_preflight_does_not_construct_client_claim_or_advance(configured):
    (path, _, _, _), _, client, worker = configured
    assert control.run_read_controller(path, "synthetic", check=True) == {
        "configuration_valid": True,
        "execution_verified": False,
        "claims": 0,
        "provider_requests": 0,
    }
    control._GuardedFastmail.assert_not_called()
    control.ReadWorker.assert_not_called()
    worker.step.assert_not_called()
    client.close.assert_not_called()


def test_bound_read_reopen_uses_same_tenant_login(configured):
    (path, _, creds, _), _, _, _ = configured
    assert run(path, tenant_bound_db=True)["results"]["progress"] == 1
    assert control.Store.call_count == 2  # preflight and poll-time reopen
    assert all(
        call.kwargs["tenant_dsns"] == {UUID(creds[0]["tenant_id"]): "synthetic"}
        for call in control.Store.call_args_list
    )


def test_bound_read_encrypted_store_keeps_tenant_route(configured):
    (path, config, creds, _), _, _, _ = configured
    root = path.parent / "objects"
    root.mkdir(mode=0o700)
    config.update(
        blob_root=str(root), keys_file=str(path.parent / "keys.json"), active_key_id="key"
    )
    private_write(path, config)
    private_write(path.parent / "keys.json", {
        "tenant_id": creds[0]["tenant_id"],
        "keys": [{"key_id": "key", "key_hex": "a" * 64}],
    })
    assert control.run_read_controller(
        path, "synthetic", check=True, tenant_bound_db=True
    )["configuration_valid"]
    assert control.Store.call_count == 2
    assert all(
        call.kwargs["tenant_dsns"] == {UUID(creds[0]["tenant_id"]): "synthetic"}
        for call in control.Store.call_args_list
    )
    assert control.Store.call_args.kwargs["blobs"]._active_keys == {
        UUID(creds[0]["tenant_id"]): "key"
    }


def test_bound_mode_rejects_non_boolean_before_store(configured):
    (path, _, _, _), _, _, _ = configured
    with pytest.raises(ControllerError):
        control.run_read_controller(path, "synthetic", check=True, tenant_bound_db=1)
    control.Store.assert_not_called()


def test_execution_requires_explicit_flag_before_io(configured):
    (path, _, _, _), _, _, _ = configured
    with pytest.raises(ControllerError):
        control.run_read_controller(path, "synthetic")
    control.Store.assert_not_called()
    control._GuardedFastmail.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", "1"),
        ("version", 1.0),
        ("version", 2),
        ("job_kind", "pdf-document"),
        ("job_kind", "fastmail-read "),
        ("account_id", "bad"),
        ("provider_account_id", ""),
        ("provider_account_id", "x" * 513),
        ("provider_account_id", "x\n"),
        ("provider_secret_ref", ""),
        ("provider_secret_ref", "secret\n"),
        ("provider_secret_ref", " secret"),
        ("provider_token_file", "relative"),
        ("provider_token_file", "/private/Dropbox-test/token"),
        ("provider_token_file", "/private/../tmp/token"),
        ("max_raw_bytes", True),
        ("max_raw_bytes", 1),
        ("max_raw_bytes", 17 * 1024**2),
        ("max_raw_bytes", "1048576"),
        ("max_raw_bytes", 2 * 1024**2),
        ("blob_root", "/private/tmp/objects"),
        ("active_key_id", "key"),
        ("endpoint", "https://example.invalid"),
        ("image_id", "latest"),
    ],
)
def test_invalid_closed_config_before_database(configured, field, value):
    (path, config, _, _), _, _, _ = configured
    config[field] = value
    private_write(path, config)
    with pytest.raises(ControllerError):
        run(path)
    control.Store.assert_not_called()


@pytest.mark.parametrize("data", [b'{"version":1,"version":1}', b'{"x":NaN}', b"[]", b"\xff"])
def test_closed_json(configured, data):
    (path, _, _, _), _, _, _ = configured
    private_write(path, data)
    with pytest.raises(ControllerError):
        run(path)
    control.Store.assert_not_called()


@pytest.mark.parametrize(
    "kind,scopes",
    [
        ("human", ["email.ingest"]),
        ("assistant", ["email.ingest"]),
        ("worker", ["email.process"]),
        ("worker", ["email.document.process"]),
        ("worker", ["email.ingest", "email.search"]),
        ("worker", []),
    ],
)
def test_exact_worker_identity(configured, kind, scopes):
    (path, _, creds, _), _, _, _ = configured
    creds[0].update(client_kind=kind, scopes=scopes)
    private_write(path.parent / "credentials.json", creds)
    with pytest.raises(ControllerError):
        run(path)
    control.Store.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_iterations", 0),
        ("max_iterations", 1001),
        ("max_iterations", True),
        ("idle_seconds", 0),
        ("idle_seconds", 61),
        ("idle_seconds", 1.0),
        ("check", "yes"),
    ],
)
def test_options_fail_before_io(configured, field, value):
    (path, _, _, _), _, _, _ = configured
    with pytest.raises(ControllerError):
        run(path, **{field: value})
    control.Store.assert_not_called()


@pytest.mark.parametrize(
    "row",
    [
        None,
        {"provider_account_id": None, "secret_ref": "synthetic:none", "paused": False},
        {"provider_account_id": "other", "secret_ref": "synthetic:none", "paused": False},
        {"provider_account_id": "provider-a", "secret_ref": "other", "paused": False},
    ],
)
def test_binding_precedes_client(configured, row):
    (path, _, _, _), store, _, _ = configured
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = row
    with pytest.raises(ControllerError):
        run(path)
    control._GuardedFastmail.assert_not_called()


@pytest.mark.parametrize(
    "token", [b"short", b"a" * 4097, b"a" * 20 + b"\r\n", b"a b" * 20, b"\xff" * 30]
)
def test_provider_token_format_never_reaches_client(configured, token):
    (path, _, _, _), _, _, _ = configured
    private_write(path.parent / "provider-token", token)
    with pytest.raises(ControllerError):
        run(path)
    control._GuardedFastmail.assert_not_called()


@pytest.mark.parametrize("file", ["controller.json", "credentials.json", "token", "provider-token"])
def test_private_permissions_apply_to_all_input_files(configured, file):
    (path, _, _, _), _, _, _ = configured
    (path.parent / file).chmod(0o644)
    with pytest.raises(ControllerError):
        run(path)
    control._GuardedFastmail.assert_not_called()


def test_symlink_provider_token_refused(configured):
    (path, config, _, _), _, _, _ = configured
    link = path.parent / "link"
    link.symlink_to(path.parent / "provider-token")
    config["provider_token_file"] = str(link)
    private_write(path, config)
    with pytest.raises(ControllerError):
        run(path)
    control._GuardedFastmail.assert_not_called()


def test_counts_bounds_sleep_close_and_no_content(configured):
    (path, _, _, token), _, client, worker = configured
    worker.step.side_effect = ["progress", "caught_up", "not_due"]
    stop = Mock(spec=Event)
    stop.is_set.return_value = stop.wait.return_value = False
    result = run(path, max_iterations=3, idle_seconds=2, stop=stop)
    assert (
        result["polls"] == 3 and not result["attention_required"] and not result["mailbox_effects"]
    )
    assert all(result["results"][s] == 1 for s in ("progress", "caught_up", "not_due"))
    assert client.close.call_count == 3 and stop.wait.call_count == 2
    stop.wait.assert_called_with(2)
    assert token not in json.dumps(result) and "provider-a" not in json.dumps(result)


@pytest.mark.parametrize(
    "outcome", ["auth_required", "protocol_error", "parse_error", "resync_required"]
)
def test_pause_outcomes_stop_without_reset(configured, outcome):
    (path, _, _, _), _, client, worker = configured
    worker.step.return_value = outcome
    result = run(path, max_iterations=100)
    assert result["attention_required"] and result["polls"] == 1
    assert result["results"][outcome] == 1 and client.close.call_count == 1


def test_existing_pause_constructs_no_client(configured):
    (path, _, _, _), store, _, worker = configured
    store.transaction.return_value.__enter__.return_value.execute.return_value.fetchone.return_value[
        "paused"
    ] = True
    result = run(path)
    assert (
        result["attention_required"] and result["polls"] == 0 and result["results"]["paused"] == 1
    )
    control._GuardedFastmail.assert_not_called()
    worker.step.assert_not_called()


def test_stop_before_and_after_step(configured):
    (path, _, _, _), _, client, worker = configured
    stop = Event()
    stop.set()
    assert run(path, stop=stop)["polls"] == 0
    control._GuardedFastmail.assert_not_called()
    stop.clear()
    worker.step.side_effect = lambda *args: (stop.set(), "progress")[1]
    result = run(path, stop=stop, max_iterations=100)
    assert result["stopped"] and result["polls"] == 1 and client.close.call_count == 1


@pytest.mark.parametrize(
    "mutation", ["revoked", "expired", "actor", "tenant", "scope", "provider_token"]
)
def test_guard_rechecks_authority_during_step(configured, mutation):
    (path, _, creds, _), _, client, worker = configured

    def change(*args):
        guard = control.ReadWorker.call_args.kwargs["authorize"]
        guard()
        if mutation == "provider_token":
            private_write(path.parent / "provider-token", b"synthetic-replacement-token")
        else:
            if mutation == "revoked":
                creds.clear()
            elif mutation == "expired":
                creds[0]["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
            elif mutation in {"actor", "tenant"}:
                creds[0][mutation + "_id"] = str(uuid4())
            else:
                creds[0]["scopes"].append("email.search")
            private_write(path.parent / "credentials.json", creds)
        with pytest.raises(control._ReadGuardDenied):
            guard()
        raise RuntimeError("fictional private exception")

    worker.step.side_effect = change
    with pytest.raises(ControllerError):
        run(path)
    client.close.assert_called_once()


def test_same_identity_rotation_between_steps(configured):
    (path, _, creds, _), _, client, worker = configured

    def rotate(*args):
        token = secrets.token_urlsafe(40)
        creds[0]["token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        private_write(path.parent / "credentials.json", creds)
        private_write(path.parent / "token", token.encode())
        private_write(path.parent / "provider-token", b"synthetic-rotated-provider")
        return "progress"

    worker.step.side_effect = rotate
    stop = Mock(spec=Event)
    stop.is_set.return_value = stop.wait.return_value = False
    assert run(path, max_iterations=2, stop=stop)["polls"] == 2
    assert control._GuardedFastmail.call_args.args[0] == "synthetic-rotated-provider"
    assert client.close.call_count == 2


def test_guard_surrounds_real_http_request_without_network():
    calls = []
    client = control._GuardedFastmail(
        "synthetic-token-only",
        lambda: calls.append("guard"),
        transport=httpx.MockTransport(
            lambda r: (calls.append("http"), httpx.Response(200, content=b"x"))[1]
        ),
        max_raw_bytes=1024**2,
    )
    try:
        assert client._request("GET", "https://api.fastmail.com/jmap/session") == b"x"
        assert calls == ["guard", "http", "guard"]
    finally:
        client.close()


@pytest.mark.parametrize(
    "problem", ["missing_key", "foreign", "duplicate", "missing_root", "valid"]
)
def test_encrypted_write_key_preflight(configured, problem):
    (path, config, creds, _), _, _, _ = configured
    root = path.parent / "objects"
    if problem != "missing_root":
        root.mkdir(mode=0o700)
    config.update(
        blob_root=str(root),
        keys_file=str(path.parent / "keys.json"),
        active_key_id="key",
        max_raw_bytes=2 * 1024**2,
    )
    keys = {"tenant_id": creds[0]["tenant_id"], "keys": [{"key_id": "key", "key_hex": "a" * 64}]}
    if problem == "missing_key":
        config["active_key_id"] = "absent"
    elif problem == "foreign":
        keys["tenant_id"] = str(uuid4())
    elif problem == "duplicate":
        keys["keys"] *= 2
    private_write(path, config)
    private_write(path.parent / "keys.json", keys)
    if problem == "valid":
        assert run(path, check=True)["claims"] == 0
        blobs = control.Store.call_args.kwargs["blobs"]
        assert blobs._active_keys == {UUID(creds[0]["tenant_id"]): "key"}
        assert not list(root.iterdir())
    else:
        with pytest.raises(ControllerError):
            run(path, check=True)
    control._GuardedFastmail.assert_not_called()


@pytest.mark.parametrize(
    "outcome,code", [("progress", None), ("protocol_error", 2), ("PRIVATE", 1)]
)
def test_cli_exit_and_redacted_output(configured, monkeypatch, capsys, outcome, code):
    (path, _, _, token), _, _, worker = configured
    worker.step.return_value = outcome
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "synthetic:" + token)
    monkeypatch.setattr(
        "sys.argv", ["email-brain", "sync-read", "--config", str(path), "--allow-provider-read"]
    )
    if code is None:
        cli.main()
    else:
        with pytest.raises(SystemExit) as error:
            cli.main()
        assert error.value.code == code
    output = capsys.readouterr()
    assert token not in output.out + output.err and "PRIVATE" not in output.out + output.err
    assert str(path) not in output.out + output.err
