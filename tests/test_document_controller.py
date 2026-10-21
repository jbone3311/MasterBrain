"""Explicit document controller contracts; all data and service doubles are fictional."""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from test_processing_controller import controller_files, private_write

from email_brain import cli
from email_brain import document_controller as document
from email_brain import processing_controller as mime
from email_brain.auth import TokenRegistry
from email_brain.document_jobs import POLICY

VERSION = "sandbox-pdf-v1-" + "a" * 64


def document_files(root, tenant=None, actor=None, account=None, image=None):
    path, config, creds, token = controller_files(root, tenant, actor, account, image)
    config.update(job_kind="pdf-document", policy_version=POLICY)
    creds[0]["scopes"] = ["email.document.process"]
    private_write(path, config)
    private_write(path.parent / "credentials.json", creds)
    return path, config, creds, token


@pytest.fixture
def configured(tmp_path, monkeypatch):
    files = document_files(tmp_path)
    store = MagicMock()
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = {
        "provider_account_id": None,
        "secret_ref": "synthetic:none",
    }
    monkeypatch.setattr(mime, "Store", Mock(return_value=store))
    processor = Mock(processor_version=VERSION)
    factory = Mock(return_value=processor)
    monkeypatch.setattr(document, "DockerPdfProcessor", factory)
    jobs = Mock()
    jobs.run_once.return_value = None
    monkeypatch.setattr(document, "DocumentJobs", Mock(return_value=jobs))
    return files, store, factory, jobs


def test_check_does_not_construct_processor_or_claim(configured):
    (path, _, _, _), store, factory, jobs = configured
    assert document.run_document_controller(path, "synthetic", check=True) == {
        "configuration_valid": True,
        "execution_verified": False,
        "claims": 0,
    }
    store.transaction.assert_called_once()
    factory.assert_not_called()
    document.DocumentJobs.assert_not_called()
    jobs.run_once.assert_not_called()


def test_bound_mode_rejects_non_boolean_before_store(configured):
    (path, _, _, _), _, _, _ = configured
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic", check=True, tenant_bound_db=1)
    mime.Store.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("job_kind", None),
        ("job_kind", "mime"),
        ("job_kind", "pdf-document\n"),
        ("policy_version", None),
        ("policy_version", "live-pdf-v1"),
        ("policy_version", POLICY + " "),
        ("version", True),
        ("version", "1"),
        ("version", 1.0),
        ("version", 2),
        ("account_id", "invalid"),
        ("image_id", "latest"),
        ("image_id", "sha256:" + "a" * 64 + "\n"),
        ("docker_binary", "docker"),
        ("credentials_file", "relative"),
        ("token_file", "/private/Dropbox-private/token"),
        ("token_file", "/private/../tmp/token"),
        ("blob_root", "/private/tmp/objects"),
        ("keys_file", "/private/tmp/keys.json"),
        ("command", "untrusted"),
    ],
)
def test_closed_document_configuration_before_database(configured, field, value):
    (path, config, _, _), _, factory, _ = configured
    if value is None:
        config.pop(field)
    else:
        config[field] = value
    private_write(path, config)
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic", check=True)
    mime.Store.assert_not_called()
    factory.assert_not_called()


@pytest.mark.parametrize("data", [b'{"version":1,"version":1}', b'{"x":NaN}', b"[]", b"\xff"])
def test_document_json_strictness(configured, data):
    (path, _, _, _), _, _, _ = configured
    private_write(path, data)
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic")
    mime.Store.assert_not_called()


def test_cross_channel_configurations_fail_before_database(configured):
    (path, config, _, _), _, _, _ = configured
    with pytest.raises(mime.ControllerError):
        mime.run_controller(path, "synthetic")
    config.pop("job_kind")
    config.pop("policy_version")
    private_write(path, config)
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic")
    mime.Store.assert_not_called()


@pytest.mark.parametrize(
    "kind,scopes",
    [
        ("human", ["email.document.process"]),
        ("assistant", ["email.document.process"]),
        ("worker", ["email.process"]),
        ("worker", ["email.document.process", "email.process"]),
        ("worker", ["email.document.process", "email.search"]),
        ("worker", []),
    ],
)
def test_exact_document_worker_identity(configured, kind, scopes):
    (path, _, creds, _), _, _, _ = configured
    creds[0].update(client_kind=kind, scopes=scopes)
    private_write(path.parent / "credentials.json", creds)
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic")
    mime.Store.assert_not_called()


def test_pdf_credentials_do_not_authorize_old_mime_command(configured):
    (path, config, _, _), _, _, _ = configured
    config.pop("job_kind")
    config.pop("policy_version")
    private_write(path, config)
    with pytest.raises(mime.ControllerError):
        mime.run_controller(path, "synthetic")
    mime.Store.assert_not_called()


@pytest.mark.parametrize(
    "row",
    [
        None,
        {"provider_account_id": "enrolled", "secret_ref": "synthetic:none"},
        {"provider_account_id": None, "secret_ref": "vault:real"},
    ],
)
def test_preflight_requires_active_unenrolled_synthetic_account(configured, row):
    (path, _, _, _), store, factory, jobs = configured
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = row
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic", check=True)
    factory.assert_not_called()
    jobs.run_once.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_iterations", 0),
        ("max_iterations", 1001),
        ("max_iterations", True),
        ("idle_seconds", 0),
        ("idle_seconds", 61),
        ("idle_seconds", 1.0),
    ],
)
def test_bounds_before_io(configured, field, value):
    (path, _, _, _), _, _, _ = configured
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic", **{field: value})
    mime.Store.assert_not_called()


def test_bounded_counts_do_not_disclose_result_fields(configured):
    (path, config, _, token), _, factory, jobs = configured
    jobs.run_once.side_effect = [
        None,
        {"status": "completed", "text": token},
        {"status": "retry_wait"},
    ]
    stop = Mock(spec=Event)
    stop.is_set.return_value = stop.wait.return_value = False
    result = document.run_document_controller(
        path, "synthetic", max_iterations=3, idle_seconds=2, stop=stop
    )
    assert result["polls"] == 3 and not result["mailbox_effects"]
    assert (
        result["results"]["no_result"]
        == result["results"]["completed"]
        == result["results"]["retry_wait"]
        == 1
    )
    assert token not in json.dumps(result)
    assert stop.wait.call_count == 2
    stop.wait.assert_called_with(2)
    factory.assert_called_once()
    principal, account, processor = jobs.run_once.call_args.args
    assert (
        principal.context.scopes == {"email.document.process"} and principal.client_kind == "worker"
    )
    assert str(account) == config["account_id"] and processor.processor_version == VERSION


@pytest.mark.parametrize("timing", ["before", "during"])
@pytest.mark.parametrize("mutation", ["removed", "expired", "tenant", "actor", "scope"])
def test_authentication_around_extraction(configured, timing, mutation):
    (path, config, creds, _), _, factory, _ = configured
    identity = mime.WorkerIdentity(
        document.DocumentControllerConfig.model_validate(config), scope="email.document.process"
    )
    identity.authenticate()

    def revoke():
        if mutation == "removed":
            private_write(path.parent / "credentials.json", [])
            return
        if mutation == "expired":
            creds[0]["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        elif mutation in {"tenant", "actor"}:
            creds[0][mutation + "_id"] = str(uuid4())
        else:
            creds[0]["scopes"].append("email.search")
        private_write(path.parent / "credentials.json", creds)

    if timing == "before":
        revoke()
    else:
        factory.return_value.extract.side_effect = lambda *a, **kw: revoke()
    processor = document._AuthenticatedPdf(factory.return_value, identity)
    with pytest.raises(ValueError):
        processor.extract(b"fictional", part_path="1.2", part_sha256="b" * 64)
    assert factory.return_value.extract.call_count == (0 if timing == "before" else 1)


def test_same_identity_rotation_between_polls_is_allowed(configured):
    (path, _, creds, _), _, _, jobs = configured
    calls = []

    def rotate(*args):
        calls.append(args)
        if len(calls) > 1:
            return None
        token = secrets.token_urlsafe(40)
        creds[0]["token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        private_write(path.parent / "credentials.json", creds)
        private_write(path.parent / "token", token.encode())
        return {"status": "completed"}

    jobs.run_once.side_effect = rotate
    stop = Mock(spec=Event)
    stop.is_set.return_value = stop.wait.return_value = False
    assert (
        document.run_document_controller(path, "synthetic", max_iterations=2, stop=stop)["polls"]
        == 2
    )
    assert len(calls) == 2


def test_stop_before_claim_and_after_inflight(configured):
    (path, _, _, _), _, _, jobs = configured
    stop = Event()
    stop.set()
    assert document.run_document_controller(path, "synthetic", stop=stop)["polls"] == 0
    jobs.run_once.assert_not_called()
    stop.clear()

    def finish(*args):
        stop.set()
        return {"status": "completed"}

    jobs.run_once.side_effect = finish
    result = document.run_document_controller(path, "synthetic", max_iterations=100, stop=stop)
    assert result["stopped"] and result["polls"] == 1


@pytest.mark.parametrize("failure", ["foreign", "duplicate", "bad_key", "missing_root", "valid"])
def test_document_keyring_preflight(configured, failure):
    (path, config, creds, _), _, factory, jobs = configured
    root = path.parent / "objects"
    if failure != "missing_root":
        root.mkdir(mode=0o700)
    config.update(blob_root=str(root), keys_file=str(path.parent / "keys.json"))
    keys = {
        "tenant_id": creds[0]["tenant_id"],
        "keys": [{"key_id": "pdf-key", "key_hex": "a" * 64}],
    }
    if failure == "foreign":
        keys["tenant_id"] = str(uuid4())
    elif failure == "duplicate":
        keys["keys"] *= 2
    elif failure == "bad_key":
        keys["keys"][0]["key_hex"] = "invalid"
    private_write(path, config)
    private_write(path.parent / "keys.json", keys)
    if failure == "valid":
        assert document.run_document_controller(path, "synthetic", check=True)["claims"] == 0
        assert mime.Store.call_args.kwargs["blobs"]._active_keys == {}
    else:
        with pytest.raises(mime.ControllerError):
            document.run_document_controller(path, "synthetic", check=True)
    factory.assert_not_called()
    jobs.run_once.assert_not_called()
    if failure == "missing_root":
        assert not root.exists()


def test_revocation_after_poll_stops_before_next_claim(configured):
    (path, _, _, _), _, _, jobs = configured

    def revoke(*args):
        private_write(path.parent / "credentials.json", [])
        return {"status": "completed"}

    jobs.run_once.side_effect = revoke
    with pytest.raises(mime.ControllerError):
        document.run_document_controller(path, "synthetic", max_iterations=2)
    assert jobs.run_once.call_count == 1


@pytest.mark.parametrize("failure", ["sql", "status", "registry"])
def test_cli_failures_are_redacted(configured, monkeypatch, capsys, failure):
    (path, _, _, token), store, _, jobs = configured
    if failure == "sql":
        store.transaction.side_effect = RuntimeError(token)
    elif failure == "status":
        jobs.run_once.return_value = {"status": token}
    else:
        private_write(path.parent / "credentials.json", token.encode())
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "synthetic:" + token)
    monkeypatch.setattr("sys.argv", ["email-brain", "process-documents", "--config", str(path)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    output = capsys.readouterr()
    assert output.out == "" and "Sensitive exception details suppressed" in output.err
    assert token not in output.err and str(path) not in output.err


def test_demo_generated_credentials_are_human_only_and_usable(tmp_path, monkeypatch, capsys):
    # Exercise real credential generation/serialization/validation, not a hand-authored fixture.
    monkeypatch.setenv("EMAIL_BRAIN_RUNTIME_PASSWORD", secrets.token_urlsafe(32))
    monkeypatch.setenv("EMAIL_BRAIN_ADMIN_DSN", "synthetic")
    monkeypatch.setattr(cli.psycopg, "connect", MagicMock())
    monkeypatch.setattr(cli, "grant_runtime", Mock())
    cli.provision_demo(tmp_path.resolve())
    token = (tmp_path / "owner-token.txt").read_text()
    registry = TokenRegistry.from_file(tmp_path / "credentials.json")
    principal = registry.authenticate(token)
    assert principal is not None and principal.client_kind == "human"
    assert principal.context.scopes == {
        "email.search",
        "email.evidence.read",
        "email.proposal.create",
        "email.proposal.read",
        "email.review",
    }
    assert token not in capsys.readouterr().out


def test_combined_demo_token_adds_reads_without_worker_or_effect_scopes(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.setenv("EMAIL_BRAIN_RUNTIME_PASSWORD", secrets.token_urlsafe(32))
    monkeypatch.setenv("EMAIL_BRAIN_ADMIN_DSN", "synthetic")
    monkeypatch.setattr(cli.psycopg, "connect", MagicMock())
    monkeypatch.setattr(cli, "grant_runtime", Mock())
    cli.provision_demo(tmp_path.resolve(), masterbrain=True)
    token = (tmp_path / "owner-token.txt").read_text()
    principal = TokenRegistry.from_file(tmp_path / "credentials.json").authenticate(token)
    assert principal is not None and principal.client_kind == "human"
    assert {"brain.search", "brain.evidence.read", "brain.content.read",
            "knowledge.search", "knowledge.review"} <= principal.context.scopes
    assert not any(scope.startswith("brain.source.") or scope.startswith("brain.fileos.")
                   or scope.endswith(".process") for scope in principal.context.scopes)
    assert (tmp_path / "masterbrain-demo.marker").read_text() == cli._DEMO_REVISION + "\n"
    assert token not in capsys.readouterr().out


@pytest.mark.parametrize("version", [None, VERSION])
def test_serve_explicit_document_channel_stays_loopback(tmp_path, monkeypatch, version):
    _, _, creds, _ = document_files(tmp_path)
    creds[0].update(
        client_kind="human", scopes=["email.search", "email.evidence.read", "email.review"]
    )
    private_write(tmp_path / "credentials.json", creds)
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "synthetic")
    monkeypatch.setenv("EMAIL_BRAIN_CREDENTIALS_FILE", str(tmp_path / "credentials.json"))
    app_factory = Mock(wraps=cli.create_app)
    monkeypatch.setattr(cli, "create_app", app_factory)
    run = Mock()
    monkeypatch.setattr(cli.uvicorn, "run", run)
    args = ["email-brain", "serve"]
    if version:
        args += ["--document-processor-version", version]
    monkeypatch.setattr("sys.argv", args)
    cli.main()
    assert app_factory.call_args.kwargs["document_processor_version"] == version
    assert app_factory.call_args.kwargs["recovery_parser_version"] is None
    assert run.call_args.kwargs == {
        "host": "127.0.0.1",
        "port": 8080,
        "access_log": False,
        "proxy_headers": False,
    }


def test_invalid_serve_document_version_never_starts(tmp_path, monkeypatch, capsys):
    document_files(tmp_path)
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "synthetic")
    monkeypatch.setenv("EMAIL_BRAIN_CREDENTIALS_FILE", str(tmp_path / "credentials.json"))
    run = Mock()
    monkeypatch.setattr(cli.uvicorn, "run", run)
    monkeypatch.setattr(
        "sys.argv",
        ["email-brain", "serve", "--document-processor-version", "sandbox-mime-v1-" + "a" * 64],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    run.assert_not_called()
    assert "sandbox-mime" not in capsys.readouterr().err
