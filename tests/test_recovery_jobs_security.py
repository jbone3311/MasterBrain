"""Independent recovery-job authority/fence regressions; synthetic data only."""

from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from test_postgres import database as database
from test_postgres import tenant as tenant
from test_recovery_jobs import queued

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.recovery import Recovery, RecoveryFence
from email_brain.recovery_jobs import LeaseLost, _JobFence
from email_brain.store import AccessDenied, Conflict, Store


def principal(kind="human", scopes=frozenset({"email.review", "email.evidence.read"})):
    return Principal(TenantContext(uuid4(), uuid4(), scopes, uuid4()), kind)


def mocked_recovery(monkeypatch):
    store = MagicMock(spec=Store)
    store.require = Store.require
    recovery = Recovery(store)
    cached = {"id": uuid4(), "outcome": "recovered", "evidence_id": uuid4()}
    receipt = MagicMock(return_value={})
    attempt = MagicMock(return_value=cached)
    monkeypatch.setattr(recovery, "receipt", receipt)
    monkeypatch.setattr(recovery, "attempt", attempt)
    return recovery, store, cached, receipt, attempt


@pytest.mark.parametrize(
    ("kind", "scopes"),
    [
        ("worker", frozenset({"email.process", "email.review", "email.evidence.read"})),
        ("assistant", frozenset({"email.review", "email.evidence.read"})),
        ("human", frozenset({"email.review"})),
        ("human", frozenset({"email.evidence.read"})),
    ],
)
def test_fence_injection_does_not_turn_worker_into_human(monkeypatch, kind, scopes):
    recovery, store, _, _, _ = mocked_recovery(monkeypatch)
    fence = MagicMock(spec=RecoveryFence)
    with pytest.raises(AccessDenied):
        recovery._retry(
            principal(kind, scopes), uuid4(), uuid4(), recovery.parser_version, fence=fence
        )
    store.transaction.assert_not_called()
    fence.check.assert_not_called()
    fence.complete.assert_not_called()


def test_cached_attempt_cannot_bypass_initial_job_fence(monkeypatch):
    recovery, store, _, receipt, attempt = mocked_recovery(monkeypatch)
    fence = MagicMock(spec=RecoveryFence)
    fence.check.side_effect = Conflict("cancelled job")
    with pytest.raises(Conflict):
        recovery._retry(principal(), uuid4(), uuid4(), recovery.parser_version, fence=fence)
    receipt.assert_not_called()
    attempt.assert_not_called()
    store.audit.assert_not_called()
    store.load_raw.assert_not_called()
    fence.complete.assert_not_called()


def test_cached_attempt_completion_is_still_fenced_in_same_transaction(monkeypatch):
    recovery, store, cached, _, _ = mocked_recovery(monkeypatch)
    fence = MagicMock(spec=RecoveryFence)
    fence.complete.side_effect = Conflict("lease expired before completion")
    with pytest.raises(Conflict):
        recovery._retry(principal(), uuid4(), uuid4(), recovery.parser_version, fence=fence)
    conn = store.transaction.return_value.__enter__.return_value
    fence.check.assert_called_once_with(conn)
    fence.complete.assert_called_once_with(conn, cached)
    store.load_raw.assert_not_called()
    assert store.transaction.return_value.__exit__.call_args.args[0] is Conflict


@pytest.mark.postgres
@pytest.mark.parametrize("deadline", ["lease", "approval"])
@pytest.mark.parametrize("operation", ["check", "complete"])
def test_fence_uses_wall_clock_not_transaction_start(
    database, tenant, monkeypatch, deadline, operation
):
    store, admin = database
    ctx, account = tenant
    jobs, _, worker, receipt_id, job = queued(database, tenant, monkeypatch)
    claimed = jobs._claim(worker.context, account)
    assert claimed is not None and claimed["status"] == "running"
    fence = _JobFence(
        store,
        worker.context,
        job["id"],
        account,
        ctx.actor_id,
        receipt_id,
        claimed["parser_version"],
        claimed["lease_token"],
    )
    with pytest.raises(LeaseLost), store.transaction(ctx) as conn:
        # Start the worker transaction before the deadline. Admin-only fixture
        # time travel places expiry between its now() and actual wall time;
        # ordinary code cannot rewrite immutable approval times or active leases.
        conn.execute("SELECT now()")
        with psycopg.connect(admin) as clock:
            clock.execute("SET LOCAL session_replication_role=replica")
            if deadline == "lease":
                clock.execute(
                    "UPDATE recovery_jobs SET lease_until=statement_timestamp() "
                    "- interval '1 microsecond' WHERE id=%s",
                    (job["id"],),
                )
            else:
                clock.execute(
                    "UPDATE recovery_jobs SET expires_at=statement_timestamp() "
                    "- interval '1 microsecond',created_at=statement_timestamp() "
                    "- interval '1 microsecond' - interval '1 hour' WHERE id=%s",
                    (job["id"],),
                )
        field = "lease_until" if deadline == "lease" else "expires_at"
        timing = conn.execute(
            f"SELECT now()<{field} AS old_clock_allows, "
            f"clock_timestamp()>{field} AS expired FROM recovery_jobs WHERE id=%s",
            (job["id"],),
        ).fetchone()
        assert timing == {"old_clock_allows": True, "expired": True}
        if operation == "check":
            fence.check(conn)
        else:
            fence.complete(
                conn,
                {
                    "id": uuid4(),
                    "receipt_id": receipt_id,
                    "parser_version": claimed["parser_version"],
                    "outcome": "recovered",
                },
            )
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM message_versions").fetchone()["n"] == 0
    assert jobs.get(ctx, account, job["id"])["status"] == "running"
