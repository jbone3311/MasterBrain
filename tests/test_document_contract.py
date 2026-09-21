"""Offline permission/configuration boundary checks, no PDF parser or database."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.document_jobs import POLICY, DocumentJobs
from email_brain.domain.models import TenantContext
from email_brain.schemas import DocumentRequest, SearchRequest
from email_brain.store import AccessDenied, Conflict

VERSION = "sandbox-pdf-v1-" + "a" * 64


@pytest.mark.parametrize(
    "version",
    [
        "",
        "sandbox-mime-v1-" + "a" * 64,
        "latest",
        1,
        True,
        "sandbox-pdf-v1-" + "a" * 63,
        VERSION + "\n",
    ],
)
def test_processor_version_closed(version):
    with pytest.raises(ValueError):
        DocumentJobs(Mock(), version)


@pytest.mark.parametrize("kind", ["human", "assistant"])
def test_document_worker_scope_cannot_be_issued_to_clients(kind):
    credential = Credential(
        token_sha256="a" * 64,
        tenant_id=uuid4(),
        actor_id=uuid4(),
        scopes={"email.document.process"},
        client_kind=kind,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="worker-only"):
        TokenRegistry([credential])
    assert TokenRegistry([credential.model_copy(update={"client_kind": "worker"})])


@pytest.mark.parametrize(
    "extra",
    [
        {"image": "arbitrary"},
        {"password": ""},
        {"raw": "mail"},
        {"tenant_id": str(uuid4())},
        {"policy_version": "live"},
        {"expected_processor_version": "latest"},
    ],
)
def test_approval_request_cannot_select_runtime_or_policy(extra):
    with pytest.raises(ValidationError):
        DocumentRequest.model_validate(
            {"expected_processor_version": VERSION, "policy_version": POLICY, **extra}
        )


def test_unconfigured_and_wrong_channel_fail_before_database():
    ctx = TenantContext(
        uuid4(), uuid4(), frozenset({"email.review", "email.evidence.read"}), uuid4()
    )
    store = Mock()
    with pytest.raises(Conflict):
        DocumentJobs(store).enqueue(
            Principal(ctx, "human"), uuid4(), uuid4(), VERSION, POLICY, uuid4()
        )
    worker = Principal(replace(ctx, scopes=frozenset({"email.document.process"})), "worker")
    with pytest.raises(Conflict):
        DocumentJobs(store, VERSION).run_once(worker, uuid4(), Mock(processor_version="other"))
    store.transaction.assert_not_called()


def test_missing_human_scope_denied_before_database():
    ctx = TenantContext(uuid4(), uuid4(), frozenset(), uuid4())
    store = Mock()
    with pytest.raises(AccessDenied):
        DocumentJobs(store, VERSION).enqueue(
            Principal(ctx, "human"), uuid4(), uuid4(), VERSION, POLICY, uuid4()
        )
    store.transaction.assert_not_called()


def test_document_search_is_explicit_for_legacy_clients():
    assert not SearchRequest(query="proof").include_documents
    assert SearchRequest(query="proof", include_documents=True).include_documents
