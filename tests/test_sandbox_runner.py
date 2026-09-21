"""Offline controller contracts and real pipe pressure, never a live Docker daemon."""

import json
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from email_brain import sandbox_runner as runner
from email_brain.mime_sandbox import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES, MimeUnavailable

IMAGE = "sha256:" + "a" * 64
CID = "b" * 64
RAW = b"Subject: Synthetic\r\n\r\nHello"


def state(name):
    return {
        "Id": CID,
        "Name": "/" + name,
        "Image": IMAGE,
        "State": {"Status": "created"},
        "Mounts": [],
        "Config": {
            "Labels": {runner._LABEL: name},
            "Volumes": None,
            "User": "10001:10001",
            "WorkingDir": "/app",
            "Entrypoint": ["/app/.venv/bin/python"],
            "Cmd": runner._COMMAND,
            "Healthcheck": {"Test": ["NONE"]},
            "OpenStdin": True,
            "Tty": False,
            "Env": [f"{key}={value}" for key, value in runner._ENV.items()],
        },
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "CapAdd": None,
            "SecurityOpt": ["no-new-privileges:true"],
            "Memory": runner._MEMORY,
            "MemorySwap": runner._MEMORY,
            "NanoCpus": 1_000_000_000,
            "PidsLimit": 32,
            "LogConfig": {"Type": "none"},
            "IpcMode": "private",
            "RestartPolicy": {"Name": "no"},
        },
    }


def fake_docker(monkeypatch, *, mutate=None, image_config=None, started_error=False):
    processor = runner.DockerMimeProcessor(IMAGE)
    calls = []
    name = None
    finished = False

    def invoke(args, raw=b"", **kwargs):
        nonlocal name, finished
        calls.append((args, raw, kwargs))
        if args[0] == "info":
            return b'["name=seccomp,profile=builtin"]'
        if args[:2] == ["image", "inspect"]:
            return json.dumps(
                [
                    {
                        "Id": IMAGE,
                        "Config": image_config or {"Env": ["PATH=/old"], "Volumes": None},
                    }
                ]
            ).encode()
        if args[:2] == ["container", "create"]:
            name = args[args.index("--name") + 1]
            return CID.encode() + b"\n"
        if args[:2] == ["container", "inspect"]:
            result = deepcopy(state(name))
            if finished:
                result["State"] = {"Status": "exited", "ExitCode": 0, "OOMKilled": False}
            if mutate:
                mutate(result)
            return json.dumps([result]).encode()
        if args[:2] == ["container", "start"]:
            if started_error:
                raise RuntimeError("private input secret")
            finished = True
            return b"bounded child response"
        if args[:2] == ["container", "rm"]:
            return CID.encode() + b"\n"
        pytest.fail(f"unexpected command {args[0:2]}")

    monkeypatch.setattr(processor, "_invoke", invoke)
    decode = Mock(return_value=(None, [], True))
    monkeypatch.setattr(runner, "decode_response", decode)
    return processor, calls, decode


@pytest.mark.parametrize(
    "image", ["latest", "repository:tag", "sha256:abc", "A" * 64, IMAGE + "\n"]
)
def test_only_immutable_local_image_ids(image):
    with pytest.raises(MimeUnavailable):
        runner.DockerMimeProcessor(image)


@pytest.mark.parametrize("binary", ["/usr/bin/docker", Path("docker"), Path("/tmp/../docker")])
def test_binary_is_explicit_absolute_path(binary):
    with pytest.raises(MimeUnavailable):
        runner.DockerMimeProcessor(IMAGE, docker_binary=binary)


def test_isolation_inspected_before_raw_and_exact_owned_cleanup(monkeypatch):
    processor, calls, decode = fake_docker(monkeypatch)
    assert processor.parser_version == "sandbox-mime-v1-" + "a" * 64
    assert processor.max_raw_bytes == MAX_INPUT_BYTES
    assert processor.prepare(RAW) == (None, [], True)
    create = next(args for args, _, _ in calls if args[:2] == ["container", "create"])
    for control in (
        "--pull=never",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--memory=512m",
        "--memory-swap=512m",
        "--cpus=1",
        "--pids-limit=32",
        "--security-opt=no-new-privileges:true",
        "--log-driver=none",
        "--user=10001:10001",
    ):
        assert control in create
    assert create[-5:] == [IMAGE, *runner._COMMAND]
    raw_calls = [(args, kwargs) for args, raw, kwargs in calls if raw]
    assert raw_calls == [
        (
            ["container", "start", "--attach", "--interactive", CID],
            {"limit": MAX_OUTPUT_BYTES, "timeout": 30},
        )
    ]
    assert [args[:2] for args, _, _ in calls] == [
        ["info", "--format"],
        ["image", "inspect"],
        ["container", "create"],
        ["container", "inspect"],
        ["container", "start"],
        ["container", "inspect"],
        ["container", "inspect"],
        ["container", "rm"],
    ]
    assert calls[-1][0] == ["container", "rm", "--force", CID]
    decode.assert_called_once_with(b"bounded child response", RAW)


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("HostConfig", "NetworkMode", "host"),
        ("HostConfig", "ReadonlyRootfs", False),
        ("HostConfig", "Privileged", True),
        ("HostConfig", "CapAdd", ["SYS_ADMIN"]),
        ("HostConfig", "SecurityOpt", ["seccomp=unconfined"]),
        ("HostConfig", "Memory", 0),
        ("HostConfig", "MemorySwap", -1),
        ("HostConfig", "NanoCpus", 0),
        ("HostConfig", "PidsLimit", -1),
        ("HostConfig", "Binds", ["/private:/private"]),
        ("HostConfig", "PidMode", "host"),
        ("HostConfig", "IpcMode", "host"),
        ("HostConfig", "LogConfig", {"Type": "json-file"}),
        ("Config", "User", "0"),
        ("Config", "Env", ["SECRET=private"]),
        ("Config", "Volumes", {"/data": {}}),
        ("Config", "Cmd", ["arbitrary"]),
        ("Config", "Entrypoint", ["sh"]),
        ("Config", "Healthcheck", {"Test": ["CMD", "arbitrary"]}),
        ("Config", "Tty", True),
    ],
)
def test_unverified_isolation_never_receives_email(monkeypatch, section, key, value):
    processor, calls, decode = fake_docker(
        monkeypatch, mutate=lambda state: state[section].update({key: value})
    )
    with pytest.raises(MimeUnavailable):
        processor.prepare(RAW)
    assert not any(raw for _, raw, _ in calls)
    assert calls[-1][0] == ["container", "rm", "--force", CID]
    decode.assert_not_called()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s.update(Id="c" * 64),
        lambda s: s.update(Name="/unrelated"),
        lambda s: s.update(Image="sha256:" + "c" * 64),
        lambda s: s["Config"].update(Labels={}),
    ],
)
def test_cleanup_never_removes_unowned_container(monkeypatch, mutate):
    processor, calls, _ = fake_docker(monkeypatch, mutate=mutate)
    with pytest.raises(MimeUnavailable):
        processor.prepare(RAW)
    assert not any(args[:2] == ["container", "rm"] for args, _, _ in calls)
    assert not any(raw for _, raw, _ in calls)


@pytest.mark.parametrize(
    "config",
    [
        {"Env": ["AWS_SECRET=secret"]},
        {"Env": ["PYTHONPATH=/untrusted"]},
        {"Env": ["PATH=a", "PATH=b"]},
        {"Env": [], "Volumes": {"/data": {}}},
    ],
)
def test_image_defaults_cannot_add_secrets_or_mounts(monkeypatch, config):
    processor, calls, _ = fake_docker(monkeypatch, image_config=config)
    with pytest.raises(MimeUnavailable):
        processor.prepare(RAW)
    assert not any(args[0] == "container" for args, _, _ in calls)


def test_storage_or_child_failure_is_scrubbed_and_cleaned(monkeypatch):
    processor, calls, _ = fake_docker(monkeypatch, started_error=True)
    with pytest.raises(MimeUnavailable) as failure:
        processor.prepare(RAW)
    assert "private" not in str(failure.value)
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_input_limit_before_subprocess(monkeypatch):
    processor, calls, _ = fake_docker(monkeypatch)
    with pytest.raises(MimeUnavailable):
        processor.prepare(b"x" * (MAX_INPUT_BYTES + 1))
    assert calls == []


def test_fixed_daemon_and_environment(monkeypatch):
    pump = Mock(return_value=b"result")
    monkeypatch.setattr(runner, "_pump", pump)
    processor = runner.DockerMimeProcessor(IMAGE)
    assert processor._invoke(["info"]) == b"result"
    assert pump.call_args.args[0] == [
        "/usr/bin/docker",
        "--host=unix:///var/run/docker.sock",
        "--config=/nonexistent",
        "info",
    ]


def test_pipe_pump_concurrently_transfers_large_input():
    raw = b"synthetic" * 400000
    source = "import os\nwhile data:=os.read(0,65536):\n os.write(1,data)\n"
    assert runner._pump([sys.executable, "-c", source], raw, limit=len(raw), timeout=5) == raw


@pytest.mark.parametrize(
    "source,limit,timeout",
    [
        ("import os;os.write(1,b'x'*10001)", 10000, 5),
        ("import time;time.sleep(5)", 100, 0.05),
        ("raise RuntimeError('private secret')", 100, 5),
    ],
)
def test_pipe_pump_scrubs_flood_timeout_crash(source, limit, timeout):
    with pytest.raises(MimeUnavailable) as failure:
        runner._pump([sys.executable, "-c", source], b"", limit=limit, timeout=timeout)
    assert "private" not in str(failure.value)


def test_pipe_pump_inherits_no_secrets_and_discards_stderr(monkeypatch):
    monkeypatch.setenv("EMAIL_SECRET", "private")
    source = "import os;os.write(2,b'private');os.write(1,str(sorted(os.environ)).encode())"
    output = runner._pump([sys.executable, "-c", source], b"", limit=1000, timeout=5)
    assert b"EMAIL_SECRET" not in output and b"private" not in output
    assert b"DOCKER_HOST" not in output and b"DOCKER_CONFIG" not in output


@pytest.mark.parametrize(
    "change", [{"ExitCode": 70}, {"ExitCode": False}, {"OOMKilled": True}, {"Status": "running"}]
)
def test_valid_output_cannot_mask_worker_crash(monkeypatch, change):
    def mutate(state):
        if state["State"]["Status"] == "exited":
            state["State"].update(change)

    processor, calls, decode = fake_docker(monkeypatch, mutate=mutate)
    with pytest.raises(MimeUnavailable):
        processor.prepare(RAW)
    decode.assert_not_called()
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_cleanup_failure_cannot_return_success(monkeypatch):
    processor, _, decode = fake_docker(monkeypatch)
    invoke = processor._invoke

    def fail_removal(args, raw=b"", **kwargs):
        if args[:2] == ["container", "rm"]:
            raise OSError("private host path")
        return invoke(args, raw, **kwargs)

    monkeypatch.setattr(processor, "_invoke", fail_removal)
    with pytest.raises(MimeUnavailable) as failure:
        processor.prepare(RAW)
    decode.assert_called_once()
    assert "private" not in str(failure.value)


def test_malformed_create_reply_still_cleans_exact_labelled_container(monkeypatch):
    processor, calls, _ = fake_docker(monkeypatch)
    invoke = processor._invoke

    def malformed(args, raw=b"", **kwargs):
        result = invoke(args, raw, **kwargs)
        return b"invalid" if args[:2] == ["container", "create"] else result

    monkeypatch.setattr(processor, "_invoke", malformed)
    with pytest.raises(MimeUnavailable):
        processor.prepare(RAW)
    assert not any(raw for _, raw, _ in calls)
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_daemon_without_default_seccomp_refused_before_create(monkeypatch):
    processor, calls, _ = fake_docker(monkeypatch)
    invoke = processor._invoke

    def no_seccomp(args, raw=b"", **kwargs):
        return b'["name=apparmor"]' if args[0] == "info" else invoke(args, raw, **kwargs)

    monkeypatch.setattr(processor, "_invoke", no_seccomp)
    with pytest.raises(MimeUnavailable):
        processor.prepare(RAW)
    assert calls == []


def test_pipe_closed_stdout_does_not_bypass_deadline():
    source = "import os,time;os.close(1);time.sleep(5)"
    with pytest.raises(MimeUnavailable):
        runner._pump([sys.executable, "-c", source], b"", limit=10, timeout=0.05)


def test_empty_message_is_delivered_for_deterministic_rejection(monkeypatch):
    processor, _, decode = fake_docker(monkeypatch)
    assert processor.prepare(b"") == (None, [], True)
    decode.assert_called_once_with(b"bounded child response", b"")
