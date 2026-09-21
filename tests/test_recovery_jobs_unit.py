"""Queue boundary checks that need no database or privileged worker."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.recovery_jobs import RecoveryJobs, _public
from email_brain.store import AccessDenied, Conflict, Store

VERSION = "sandbox-mime-v1-" + "a" * 64


def principal(kind="human", scopes=frozenset({"email.review", "email.evidence.read"})):
    return Principal(TenantContext(uuid4(), uuid4(), scopes, uuid4()), kind)


@pytest.mark.parametrize(
    "version", ["latest", "", "sandbox-mime-v1-" + "A" * 64, VERSION + "\n", 1]
)
def test_channel_requires_exact_image_version(version):
    store = MagicMock(spec=Store)
    with pytest.raises(ValueError):
        RecoveryJobs(store, version)
    store.transaction.assert_not_called()


@pytest.mark.parametrize("kind", ["assistant", "worker"])
def test_nonhuman_cannot_create_or_cancel_durable_approval(kind):
    store = MagicMock(spec=Store)
    jobs = RecoveryJobs(store, VERSION)
    for method, args in (
        (jobs.enqueue, (uuid4(), uuid4(), VERSION, uuid4())),
        (jobs.cancel, (uuid4(), uuid4())),
    ):
        with pytest.raises(AccessDenied):
            method(principal(kind), *args)
    store.transaction.assert_not_called()


@pytest.mark.parametrize(
    "scopes", [frozenset(), frozenset({"email.review"}), frozenset({"email.evidence.read"})]
)
def test_both_approval_scopes_required(scopes):
    store = MagicMock(spec=Store)
    with pytest.raises(AccessDenied):
        RecoveryJobs(store, VERSION).enqueue(
            principal(scopes=scopes), uuid4(), uuid4(), VERSION, uuid4()
        )
    store.transaction.assert_not_called()


def test_worker_identity_and_processing_scope_checked_before_claim():
    store = MagicMock(spec=Store)
    store.require = Store.require
    jobs = RecoveryJobs(store, VERSION)
    processor = MagicMock(parser_version=VERSION, max_raw_bytes=16 * 1024 * 1024)
    for who in (principal(), principal("worker", frozenset({"email.evidence.read"}))):
        with pytest.raises(AccessDenied):
            jobs.run_once(who, uuid4(), processor)
    store.transaction.assert_not_called()


def test_worker_configuration_mismatch_before_claim():
    store = MagicMock(spec=Store)
    store.require = Store.require
    processor = MagicMock(parser_version="sandbox-mime-v1-" + "b" * 64)
    with pytest.raises(Conflict):
        RecoveryJobs(store, VERSION).run_once(
            principal("worker", frozenset({"email.process"})),
            uuid4(),
            processor,
        )
    store.transaction.assert_not_called()
    processor.prepare.assert_not_called()


def test_status_projection_cannot_disclose_leases_or_approval_credentials():
    row = dict.fromkeys(
        (
            "id",
            "account_id",
            "receipt_id",
            "parser_version",
            "status",
            "attempts",
            "created_at",
            "expires_at",
            "retry_at",
            "completed_at",
            "attempt_id",
            "outcome",
        )
    )
    row.update(
        lease_token="secret",
        worker_actor_id="private",
        approval_scopes=["email.review"],
        actor_id="private",
        arbitrary="private",
    )
    value = _public(row)
    assert "secret" not in str(value) and "private" not in str(value)
    assert value["mailbox_effects"] is False
