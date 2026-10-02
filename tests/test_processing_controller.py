"""Private operator configuration and bounded orchestration; no real services."""

import hashlib
import json
import os
import secrets
import signal
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest

from email_brain import processing_controller as control
from email_brain.cli import main


def private_write(path, data):
    value = data if isinstance(data, bytes) else json.dumps(data).encode()
    path.write_bytes(value)
    path.chmod(0o600)


def controller_files(root, tenant=None, actor=None, account=None, image=None):
    root = root.resolve()
    root.chmod(0o700)
    token = secrets.token_urlsafe(40)
    private_write(root / "token", token.encode())
    creds = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(tenant or uuid4()),
            "actor_id": str(actor or uuid4()),
            "scopes": ["email.process"],
            "client_kind": "worker",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    ]
    private_write(root / "credentials.json", creds)
    config = {
        "version": 1,
        "account_id": str(account or uuid4()),
        "image_id": image or "sha256:" + "a" * 64,
        "docker_binary": "/usr/bin/docker",
        "credentials_file": str(root / "credentials.json"),
        "token_file": str(root / "token"),
    }
    path = root / "controller.json"
    private_write(path, config)
    return path, config, creds, token


@pytest.fixture
def configured(tmp_path, monkeypatch):
    files = controller_files(tmp_path)
    store = MagicMock()
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = {"ok": 1}
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    processor = Mock(parser_version="sandbox-mime-v1-" + "a" * 64, max_raw_bytes=16 * 1024**2)
    factory = Mock(return_value=processor)
    monkeypatch.setattr(control, "DockerMimeProcessor", factory)
    jobs = Mock()
    jobs.run_once.return_value = None
    monkeypatch.setattr(control, "RecoveryJobs", Mock(return_value=jobs))
    return files, store, factory, jobs


def test_check_has_no_claim_or_docker_side_effect(configured):
    (path, _, _, _), store, processor, jobs = configured
    assert control.run_controller(path, "synthetic", check=True) == {
        "configuration_valid": True,
        "execution_verified": False,
        "claims": 0,
    }
    store.transaction.assert_called_once()
    processor.assert_not_called()
    jobs.run_once.assert_not_called()


def test_bound_preflight_routes_both_encrypted_store_instances(configured):
    (path, config, creds, _), _, factory, jobs = configured
    root = path.parent / "objects"
    root.mkdir(mode=0o700)
    config.update(blob_root=str(root), keys_file=str(path.parent / "keys.json"))
    private_write(path, config)
    private_write(path.parent / "keys.json", {
        "tenant_id": creds[0]["tenant_id"],
        "keys": [{"key_id": "k1", "key_hex": "a" * 64}],
    })
    assert control.run_controller(
        path, "synthetic", check=True, tenant_bound_db=True
    )["configuration_valid"]
    assert control.Store.call_count == 2
    assert all(
        call.kwargs["tenant_dsns"] == {UUID(creds[0]["tenant_id"]): "synthetic"}
        for call in control.Store.call_args_list
    )
    assert control.Store.call_args.kwargs["blobs"]._active_keys == {}
    factory.assert_not_called()
    jobs.run_once.assert_not_called()


def test_bound_mode_rejects_non_boolean_before_store(configured):
    (path, _, _, _), _, _, _ = configured
    with pytest.raises(control.ControllerError):
        control.run_controller(path, "synthetic", check=True, tenant_bound_db=1)
    control.Store.assert_not_called()


def test_bounded_loop_counts_only_fixed_status(configured):
    (path, _, _, token), _, factory, jobs = configured
    jobs.run_once.side_effect = [
        None,
        {"status": "completed", "raw": token},
        {"status": "retry_wait"},
    ]
    stop = Mock(spec=Event)
    stop.is_set.return_value = False
    stop.wait.return_value = False
    result = control.run_controller(path, "synthetic", max_iterations=3, idle_seconds=2, stop=stop)
    assert result["polls"] == 3 and result["results"]["no_result"] == 1
    assert result["results"]["completed"] == result["results"]["retry_wait"] == 1
    assert not result["mailbox_effects"] and token not in json.dumps(result)
    assert stop.wait.call_count == 2
    stop.wait.assert_called_with(2)
    factory.assert_called_once()
    principal, account, processor = jobs.run_once.call_args.args
    assert principal.client_kind == "worker" and principal.context.scopes == {"email.process"}
    assert str(account) == json.loads(path.read_text())["account_id"]
    assert processor.parser_version == "sandbox-mime-v1-" + "a" * 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 1.0),
        ("version", "1"),
        ("version", 2),
        ("image_id", "latest"),
        ("image_id", "sha256:" + "a" * 64 + "\n"),
        ("account_id", "invalid"),
        ("credentials_file", "relative"),
        ("token_file", "/private/../tmp/token"),
        ("token_file", "/private/Dropbox-test/token"),
        ("docker_binary", "docker"),
        ("blob_root", "/private/tmp/objects"),
        ("keys_file", "/private/tmp/keys.json"),
        ("shell_command", "echo unsafe"),
    ],
)
def test_closed_config_rejected_before_database(configured, field, value):
    (path, data, _, _), _, processor, _ = configured
    data[field] = value
    private_write(path, data)
    with pytest.raises(control.ControllerError):
        control.run_controller(path, "synthetic", check=True)
    control.Store.assert_not_called()
    processor.assert_not_called()


@pytest.mark.parametrize("data", [b'{"version":1,"version":1}', b'{"x":NaN}', b"[]", b"\xff", b"{"])
def test_json_ambiguity_and_invalid_encoding_fail_closed(configured, data):
    (path, _, _, _), _, _, _ = configured
    private_write(path, data)
    with pytest.raises(control.ControllerError):
        control.run_controller(path, "synthetic")
    control.Store.assert_not_called()


@pytest.mark.parametrize(
    "mutation", ["expired", "human", "assistant", "broad", "no_scope", "actor", "tenant", "removed"]
)
def test_identity_denial_and_binding(configured, mutation):
    (path, config, creds, _), _, _, jobs = configured
    identity = control.WorkerIdentity(control.ControllerConfig.model_validate(config))
    identity.authenticate()
    if mutation == "expired":
        creds[0]["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    elif mutation in ("human", "assistant"):
        creds[0]["client_kind"] = mutation
    elif mutation == "broad":
        creds[0]["scopes"].append("email.search")
    elif mutation == "no_scope":
        creds[0]["scopes"] = []
    elif mutation in ("actor", "tenant"):
        creds[0][mutation + "_id"] = str(uuid4())
    else:
        creds = []
    private_write(path.parent / "credentials.json", creds)
    with pytest.raises(ValueError):
        identity.authenticate()
    jobs.run_once.assert_not_called()


@pytest.mark.parametrize(
    "kind",
    [
        "file_mode",
        "parent_mode",
        "symlink",
        "ancestor_link",
        "hardlink",
        "directory",
        "fifo",
        "oversize",
        "source_path",
    ],
)
def test_private_file_hostile_shapes(tmp_path, kind):
    root = tmp_path.resolve()
    root.chmod(0o700)
    path = root / "secret"
    private_write(path, b"synthetic")
    if kind == "file_mode":
        path.chmod(0o644)
    elif kind == "parent_mode":
        root.chmod(0o755)
    elif kind in ("symlink", "hardlink"):
        target = root / "link"
        if kind == "symlink":
            target.symlink_to(path)
        else:
            os.link(path, target)
        path = target
    elif kind == "ancestor_link":
        (root / "alias").symlink_to(root, target_is_directory=True)
        path = root / "alias" / "secret"
    elif kind == "directory":
        path = root
    elif kind == "fifo":
        path = root / "pipe"
        os.mkfifo(path, 0o600)
    elif kind == "oversize":
        private_write(path, b"x" * 65537)
    else:
        path = Path(__file__).resolve()
    with pytest.raises((ValueError, OSError)):
        control.private_bytes(path)


def test_file_exact_limit_and_newline_token(configured):
    (path, _, _, token), _, _, _ = configured
    private_write(path.parent / "token", (token + "\n").encode())
    assert control.run_controller(path, "synthetic")["polls"] == 1
    private_write(path.parent / "bounded", b"x" * 65536)
    assert len(control.private_bytes(path.parent / "bounded")) == 65536


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_iterations", 0),
        ("max_iterations", 1001),
        ("max_iterations", True),
        ("idle_seconds", 0),
        ("idle_seconds", 61),
        ("idle_seconds", 1.5),
    ],
)
def test_loop_limits_before_any_io(configured, field, value):
    (path, _, _, _), _, _, _ = configured
    with pytest.raises(control.ControllerError):
        control.run_controller(path, "synthetic", **{field: value})
    control.Store.assert_not_called()


def test_stop_before_claim_and_after_inflight(configured):
    (path, _, _, _), _, _, jobs = configured
    stop = Event()
    stop.set()
    assert control.run_controller(path, "synthetic", stop=stop)["polls"] == 0
    jobs.run_once.assert_not_called()
    stop.clear()

    def finish(*args):
        stop.set()
        return {"status": "completed"}

    jobs.run_once.side_effect = finish
    result = control.run_controller(path, "synthetic", max_iterations=100, stop=stop)
    assert result["polls"] == 1 and result["stopped"]
    assert result["results"]["completed"] == 1


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_signal_handler_restored_even_on_exception(sig):
    previous = signal.getsignal(sig)
    stop = Event()
    with pytest.raises(RuntimeError), control.shutdown_signals(stop):
        signal.raise_signal(sig)
        assert stop.is_set()
        raise RuntimeError("synthetic")
    assert signal.getsignal(sig) == previous


def test_token_removed_during_parse_blocks_result(configured):
    (path, config, _, _), _, _, _ = configured
    identity = control.WorkerIdentity(control.ControllerConfig.model_validate(config))
    identity.authenticate()

    def revoked(raw):
        private_write(path.parent / "credentials.json", [])
        return None, [], True

    processor = control._AuthenticatedProcessor(Mock(prepare=revoked), identity)
    with pytest.raises(control.ControllerError):
        processor.prepare(b"fictional")


@pytest.mark.parametrize("failure", ["sql", "status", "registry"])
def test_command_scrubs_errors(configured, monkeypatch, capsys, failure):
    (path, _, _, token), store, _, jobs = configured
    if failure == "sql":
        store.transaction.side_effect = RuntimeError(token)
    elif failure == "status":
        jobs.run_once.return_value = {"status": token}
    else:
        private_write(path.parent / "credentials.json", token.encode())
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "synthetic:" + token)
    monkeypatch.setattr("sys.argv", ["email-brain", "process-jobs", "--config", str(path)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == "" and "Sensitive exception details suppressed" in output.err
    assert token not in output.err and str(path) not in output.err


@pytest.mark.parametrize(
    "failure", ["foreign", "duplicate", "bad_key", "missing_root", "symlink", "valid"]
)
def test_keyring_preflight(configured, failure):
    (path, config, creds, _), _, factory, jobs = configured
    root = path.parent / "objects"
    if failure != "missing_root":
        root.mkdir(mode=0o700)
    config.update(blob_root=str(root), keys_file=str(path.parent / "keys.json"))
    keys = {"tenant_id": creds[0]["tenant_id"], "keys": [{"key_id": "k1", "key_hex": "a" * 64}]}
    if failure == "foreign":
        keys["tenant_id"] = str(uuid4())
    elif failure == "duplicate":
        keys["keys"] *= 2
    elif failure == "bad_key":
        keys["keys"][0]["key_hex"] = "invalid"
    elif failure == "symlink":
        (path.parent / "alias").symlink_to(root, target_is_directory=True)
        config["blob_root"] = str(path.parent / "alias")
    private_write(path, config)
    private_write(path.parent / "keys.json", keys)
    if failure == "valid":
        assert control.run_controller(path, "synthetic", check=True)["configuration_valid"]
        blob = control.Store.call_args.kwargs["blobs"]
        assert blob._active_keys == {}
    else:
        with pytest.raises(control.ControllerError):
            control.run_controller(path, "synthetic", check=True)
    factory.assert_not_called()
    jobs.run_once.assert_not_called()
    if failure == "missing_root":
        assert not root.exists()
