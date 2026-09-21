"""Offline safety tests. The real dump/restore runs in its dedicated Docker CI job."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from psycopg.conninfo import conninfo_to_dict

from email_brain.attachments import receive_attachments
from email_brain.normalize import normalize

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "restore_drill.py"
SPEC = importlib.util.spec_from_file_location("email_brain_restore_drill", SCRIPT)
assert SPEC and SPEC.loader
drill = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = drill
SPEC.loader.exec_module(drill)

NAME = "email_brain_test_restore_0123456789abcdef"
NONCE = "0123456789abcdef0123456789abcdef"
IDENTITY = "a" * 64


def container():
    return {
        "Name": "/" + NAME,
        "Id": IDENTITY,
        "Config": {"Labels": {drill.LABEL: NONCE}},
        "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49123"}]}},
    }


@pytest.mark.parametrize(
    "name",
    [
        "postgres",
        "production",
        "email_brain_test",
        "../test",
        "email_brain_test_restore_prod_target",
        NAME,
        NAME + "_source; DROP DATABASE postgres",
    ],
)
def test_only_exact_generated_disposable_database_names(name):
    with pytest.raises(drill.DrillFailure):
        drill.database_name(name)


def test_database_dsn_is_explicitly_local_and_fresh_name_only():
    config = conninfo_to_dict(drill.dsn(49123, "synthetic-only", NAME + "_source"))
    assert config["host"] == config["hostaddr"] == "127.0.0.1"
    assert config["dbname"] == NAME + "_source"
    assert config["connect_timeout"] == "2"
    assert "statement_timeout" in config["options"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"Name": "/some-existing-container"},
        {"Id": "not-an-id"},
        {"Config": {"Labels": {drill.LABEL: "wrong-nonce"}}},
        {"Config": {}},
    ],
)
def test_cleanup_requires_exact_ownership(mutation, monkeypatch):
    record = {**container(), **mutation}
    monkeypatch.setattr(drill, "inspect_container", lambda _: record)
    monkeypatch.setattr(drill, "command", lambda *args, **kwargs: pytest.fail("must not remove"))
    with pytest.raises(drill.DrillFailure):
        drill.cleanup_container(NAME, NONCE)


def test_cleanup_removes_only_verified_exact_id(monkeypatch):
    calls = []
    monkeypatch.setattr(drill, "inspect_container", lambda _: container())
    monkeypatch.setattr(drill, "command", lambda args, **kwargs: calls.append(args))
    drill.cleanup_container(NAME, NONCE)
    assert calls == [["container", "rm", "--force", "--volumes", IDENTITY]]


def test_missing_container_cleanup_does_nothing(monkeypatch):
    monkeypatch.setattr(drill, "inspect_container", lambda _: None)
    monkeypatch.setattr(drill, "command", lambda *args, **kwargs: pytest.fail("must not remove"))
    drill.cleanup_container(NAME, NONCE)


@pytest.mark.parametrize(
    "mapping",
    [
        None,
        [],
        [{"HostIp": "0.0.0.0", "HostPort": "5432"}],
        [{"HostIp": "127.0.0.1", "HostPort": "80"}],
        [{"HostIp": "127.0.0.1", "HostPort": "65536"}],
        [{"HostIp": "127.0.0.1", "HostPort": "１２３４"}],
        [{"HostIp": "127.0.0.1", "HostPort": "5432"}] * 2,
    ],
)
def test_rejects_nonprivate_or_ambiguous_ports(mapping):
    record = container()
    record["NetworkSettings"]["Ports"]["5432/tcp"] = mapping
    with pytest.raises(drill.DrillFailure):
        drill.published_port(record)


@pytest.mark.parametrize("key", ["PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGDATABASE"])
def test_ambient_postgres_config_refused_before_docker(key, monkeypatch):
    monkeypatch.setenv(key, "do-not-use")
    monkeypatch.setattr(drill, "command", lambda *args, **kwargs: pytest.fail("no Docker call"))
    with pytest.raises(drill.DrillFailure, match="ambient"):
        drill.run_drill()


def test_commands_pin_local_docker_and_suppress_process_errors(monkeypatch):
    def failing(args, **kwargs):
        assert args[:3] == ["docker", "--host", "unix:///var/run/docker.sock"]
        assert kwargs.get("shell", False) is False
        return subprocess.CompletedProcess(args, 1, b"private body", b"private password")

    monkeypatch.setattr(drill.subprocess, "run", failing)
    with pytest.raises(drill.DrillFailure) as error:
        drill.command(["exec", IDENTITY, "pg_dump"])
    assert "private" not in str(error.value)


def test_synthetic_fixture_contains_extractable_and_deferred_attachments():
    raw = drill.synthetic_mime("restorealphazebra")
    assert "restorealphazebra" in normalize(raw).text
    attachments = receive_attachments(raw)
    assert len(attachments) == 2
    assert {item.status for item in attachments} == {"extracted", "deferred"}
    assert b"example.invalid" in raw


def test_cli_requires_explicit_opt_in_without_invoking_docker():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, timeout=10)
    assert result.returncode == 2
    assert b"--run-disposable" in result.stderr


def test_top_level_failure_does_not_print_sql_or_content(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--run-disposable"])

    def fail():
        raise ValueError("INSERT private message PASSWORD secret")

    monkeypatch.setattr(drill, "run_drill", fail)
    assert drill.main() == 1
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "failed"
    assert "private message" not in output and "PASSWORD" not in output
