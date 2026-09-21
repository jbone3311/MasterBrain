"""Independent local-runtime confinement checks; no daemon, Docker or database calls."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest
from psycopg.conninfo import conninfo_to_dict

from email_brain.local_model import (
    LocalModelConfig,
    LocalModelRejected,
    OllamaLocalClassifier,
    classify_code_first,
)

MODEL = "synthetic-local:unit"
DIGEST = "a" * 64


@pytest.mark.parametrize("changed_state", ["digest", "tags-cloud", "show-cloud"])
def test_local_model_revalidates_before_each_new_email_disclosure(changed_state):
    changed = False
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path == "/api/tags":
            model = {"name": MODEL, "digest": DIGEST, "size": 100}
            if changed and changed_state == "digest":
                model["digest"] = "b" * 64
            if changed and changed_state == "tags-cloud":
                model["remote_host"] = "https://relay.example.invalid"
            return httpx.Response(200, json={"models": [model]})
        if request.url.path == "/api/show":
            shown = {"model_info": {"architecture": "synthetic"}, "details": {"format": "gguf"}}
            if changed and changed_state == "show-cloud":
                shown["remote_model"] = "remote-example-model"
            return httpx.Response(200, json=shown)
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "done": True,
                "done_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "category": "receipt",
                            "needs_reply": False,
                            "confidence": 0.9,
                            "evidence_excerpt": "First synthetic receipt",
                        }
                    ),
                },
            },
        )

    client = OllamaLocalClassifier(
        LocalModelConfig(MODEL, DIGEST, local_only_attested=True),
        transport=httpx.MockTransport(handle),
    )
    try:
        assert client.classify("First synthetic receipt").classification.category == "receipt"
        changed = True
        with pytest.raises(LocalModelRejected):
            client.classify("SECOND-EMAIL-MUST-NOT-LEAVE-THE-CALLER")
        assert sum(request.url.path == "/api/chat" for request in requests) == 1
        assert all(b"SECOND-EMAIL" not in request.content for request in requests)
        assert all(request.url.host == "127.0.0.1" for request in requests)
    finally:
        client.close()


def test_consequential_policy_prevents_even_model_metadata_calls():
    requests = []
    client = OllamaLocalClassifier(
        LocalModelConfig(MODEL, DIGEST, local_only_attested=True),
        transport=httpx.MockTransport(lambda request: requests.append(request)),
    )
    try:
        result = classify_code_first("Synthetic wire instruction", consequential=True, local=client)
        assert result.route == "human" and result.applied is False
        assert requests == []
    finally:
        client.close()


@pytest.fixture
def restore_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "restore_drill.py"
    name = "restore_drill_independent_review"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)


def test_restore_dsn_pins_network_address_not_only_host_name(restore_module, monkeypatch):
    # libpq defaults an unset hostaddr from PGHOSTADDR even when host is explicit.
    # https://www.postgresql.org/docs/17/libpq-envars.html
    monkeypatch.setenv("PGHOSTADDR", "192.0.2.99")
    values = conninfo_to_dict(
        restore_module.dsn(
            54321, "synthetic-secret", "email_brain_test_restore_0123456789abcdef_source"
        )
    )
    assert values["host"] == "127.0.0.1"
    assert values["hostaddr"] == "127.0.0.1"
    assert values["port"] == "54321"


def test_restore_cleanup_never_removes_container_with_foreign_ownership(
    restore_module, monkeypatch
):
    calls = []
    name = "email_brain_test_restore_0123456789abcdef"
    record = {
        "Name": "/" + name,
        "Id": "a" * 64,
        "Config": {"Labels": {restore_module.LABEL: "foreign-label"}},
    }
    monkeypatch.setattr(restore_module, "inspect_container", lambda _: record)
    monkeypatch.setattr(restore_module, "command", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(restore_module.DrillFailure, match="ownership"):
        restore_module.cleanup_container(name, "this-invocation")
    assert calls == []


def test_restore_cleanup_targets_verified_identity_not_a_reusable_name(restore_module, monkeypatch):
    calls = []
    name, nonce, identity = "email_brain_test_restore_0123456789abcdef", "owned", "b" * 64
    record = {
        "Name": "/" + name,
        "Id": identity,
        "Config": {"Labels": {restore_module.LABEL: nonce}},
    }
    monkeypatch.setattr(restore_module, "inspect_container", lambda _: record)
    monkeypatch.setattr(restore_module, "command", lambda *args, **kwargs: calls.append(args))
    restore_module.cleanup_container(name, nonce)
    assert calls == [(["container", "rm", "--force", "--volumes", identity],)]
