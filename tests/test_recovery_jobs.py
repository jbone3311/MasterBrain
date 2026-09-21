"""Real PostgreSQL job authorization, races and crash recovery; synthetic mail only."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from test_isolated_recovery import VERSION, FakeProcessor, make_held

from email_brain.auth import Principal
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, NotFound

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def worker_principal(admin, ctx):
    actor = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (ctx.tenant_id, actor),
        )
    return Principal(replace(ctx, actor_id=actor, scopes=frozenset({"email.process"})), "worker")


def queued(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs = RecoveryJobs(store, VERSION)
    human = Principal(ctx, "human")
    job = jobs.enqueue(human, account, receipt, VERSION, uuid4())
    worker = worker_principal(admin, ctx)
    return jobs, human, worker, receipt, job


def no_publication(admin, ctx):
    with psycopg.connect(admin) as conn:
        for table in ("recovery_attempts", "message_versions", "messages"):
            count = conn.execute(
                sql.SQL("SELECT count(*) FROM {} WHERE tenant_id=%s").format(sql.Identifier(table)),
                (ctx.tenant_id,),
            ).fetchone()[0]
            assert count == 0


def test_job_recovery_atomic_idempotent_and_image_bound(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    jobs, human, worker, receipt, job = queued(database, tenant, monkeypatch)
    assert job["status"] == "queued"
    assert {"lease_token", "raw_mime", "worker_actor_id", "blob_ref"}.isdisjoint(job)
    second = jobs.enqueue(human, account, receipt, VERSION, uuid4())
    processor = FakeProcessor()
    prepare = Mock(wraps=processor.prepare)
    monkeypatch.setattr(processor, "prepare", prepare)
    first = jobs.run_once(worker, account, processor)
    assert first["status"] == "completed"
    assert jobs.run_once(worker, account, processor)["status"] == "completed"
    assert jobs.run_once(worker, account, processor) is None
    assert prepare.call_count == 1
    assert jobs.get(ctx, account, job["id"])["status"] == "completed"
    assert jobs.get(ctx, account, second["id"])["status"] == "completed"
    assert jobs.cancel(human, account, job["id"])["status"] == "completed"
    hits = store.search(ctx, SearchRequest(query="Melron"))
    assert len(hits) == 1
    assert store.evidence(ctx, hits[0]["evidence_id"])["parser_version"] == VERSION
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM message_versions").fetchone()["n"] == 1
        assert (
            conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()["opaque_cursor"]
            == "held"
        )
        assert (
            conn.execute("SELECT actor_id FROM recovery_attempts").fetchone()["actor_id"]
            == ctx.actor_id
        )


def test_request_key_replay_conflicts_and_concurrent_enqueue(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs = RecoveryJobs(store, VERSION)
    human, key = Principal(ctx, "human"), uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(jobs.enqueue, human, account, receipt, VERSION, key) for _ in range(2)]
        results = [call.result(timeout=15) for call in calls]
    assert results[0]["id"] == results[1]["id"]
    with pytest.raises(Conflict):
        jobs.enqueue(human, account, uuid4(), VERSION, key)
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_jobs").fetchone()["n"] == 1


@pytest.mark.parametrize(
    "client_kind,scopes",
    [
        ("worker", {"email.review", "email.evidence.read"}),
        ("assistant", {"email.review", "email.evidence.read"}),
        ("human", {"email.review"}),
        ("human", {"email.evidence.read"}),
    ],
)
def test_enqueue_requires_human_and_both_scopes(database, tenant, monkeypatch, client_kind, scopes):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs = RecoveryJobs(store, VERSION)
    with pytest.raises(AccessDenied):
        jobs.enqueue(
            Principal(replace(ctx, scopes=frozenset(scopes)), client_kind),
            account,
            receipt,
            VERSION,
            uuid4(),
        )
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_jobs").fetchone()["n"] == 0


@pytest.mark.parametrize(
    "kind,scopes",
    [
        ("human", {"email.process"}),
        ("assistant", {"email.process"}),
        ("worker", {"email.review", "email.evidence.read"}),
    ],
)
def test_only_scoped_worker_claims(database, tenant, monkeypatch, kind, scopes):
    _, account = tenant
    jobs, _, worker, _, _ = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    monkeypatch.setattr(processor, "prepare", lambda raw: pytest.fail("unauthorized parser"))
    with pytest.raises(AccessDenied):
        jobs.run_once(
            Principal(replace(worker.context, scopes=frozenset(scopes)), kind), account, processor
        )


def test_worker_concurrency_claims_exactly_once(database, tenant, monkeypatch):
    _, account = tenant
    jobs, _, worker, _, job = queued(database, tenant, monkeypatch)
    entered, release = Event(), Event()
    processor = FakeProcessor()
    prepare = processor.prepare

    def blocked(raw):
        entered.set()
        assert release.wait(timeout=10)
        return prepare(raw)

    monkeypatch.setattr(processor, "prepare", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(jobs.run_once, worker, account, processor)
        try:
            assert entered.wait(timeout=10)
            assert jobs.run_once(worker, account, FakeProcessor()) is None
        finally:
            release.set()
        assert first.result(timeout=15)["id"] == job["id"]


def test_cancel_during_processing_fences_publication(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    jobs, human, worker, _, job = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    prepare = processor.prepare

    def cancelling(raw):
        result = prepare(raw)
        assert jobs.cancel(human, account, job["id"])["status"] == "cancelled"
        return result

    monkeypatch.setattr(processor, "prepare", cancelling)
    jobs.run_once(worker, account, processor)
    assert jobs.get(ctx, account, job["id"])["status"] == "cancelled"
    no_publication(admin, ctx)
    assert store.quarantines(ctx, account)["results"]


def test_deleted_provider_message_cannot_be_resurrected_by_job(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    jobs, _, worker, _, _ = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    prepare = processor.prepare

    def deleting(raw):
        result = prepare(raw)
        store.ingest_page(ctx, account, "held", "gone", [replace(pg.item("delete"), raw=None)])
        return result

    monkeypatch.setattr(processor, "prepare", deleting)
    jobs.run_once(worker, account, processor)
    no_publication(admin, ctx)
    assert store.search(ctx, SearchRequest(query="Melron")) == []


@pytest.mark.parametrize("actor", ["human", "worker"])
def test_actor_revocation_during_processing_prevents_publication(
    database, tenant, monkeypatch, actor
):
    _, admin = database
    ctx, account = tenant
    jobs, human, worker, _, _ = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    prepare = processor.prepare

    def revoking(raw):
        result = prepare(raw)
        target = human if actor == "human" else worker
        with psycopg.connect(admin) as conn:
            conn.execute(
                "DELETE FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s",
                (ctx.tenant_id, target.context.actor_id),
            )
        return result

    monkeypatch.setattr(processor, "prepare", revoking)
    try:
        jobs.run_once(worker, account, processor)
    except AccessDenied:
        pass  # Revoked caller cannot inspect or finalize its former job.
    no_publication(admin, ctx)


def test_cross_tenant_and_cross_account_jobs_are_invisible(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    jobs, human, worker, receipt, job = queued(database, tenant, monkeypatch)
    foreign, foreign_account = pg.tenant.__wrapped__(database)
    with pytest.raises(NotFound):
        jobs.get(foreign, account, job["id"])
    with pytest.raises(NotFound):
        jobs.get(foreign, foreign_account, job["id"])
    with pytest.raises(NotFound):
        jobs.enqueue(Principal(foreign, "human"), foreign_account, receipt, VERSION, uuid4())
    with store.transaction(foreign) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_jobs").fetchone()["n"] == 0
        assert (
            conn.execute(
                "UPDATE recovery_jobs SET status='cancelled' WHERE id=%s", (job["id"],)
            ).rowcount
            == 0
        )
    other_account = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','other@example.invalid','synthetic:none')",
            (other_account, ctx.tenant_id),
        )
    with pytest.raises(NotFound):
        jobs.get(ctx, other_account, job["id"])
    with pytest.raises(NotFound):
        jobs.cancel(human, other_account, job["id"])
    assert jobs.run_once(worker, other_account, FakeProcessor()) is None
    assert jobs.get(ctx, account, job["id"])["status"] == "queued"


def mutate_job(admin, job_id, assignment, parameters=()):
    """Administrator-only clock/lease fault injection; never a runtime path."""
    with psycopg.connect(admin) as conn:
        # Simulate time/crash/interleavings without weakening production triggers.
        conn.execute("SET LOCAL session_replication_role=replica")
        conn.execute(
            sql.SQL("UPDATE recovery_jobs SET {} WHERE id=%s").format(sql.SQL(assignment)),
            (*parameters, job_id),
        )


def expire_approval(admin, job_id):
    mutate_job(
        admin,
        job_id,
        "created_at=created_at-interval '2 hours', expires_at=expires_at-interval '2 hours'",
    )


def test_approval_identity_scope_and_expiry_are_immutable(database, tenant, monkeypatch):
    store, _ = database
    ctx, _ = tenant
    _, _, worker, _, job = queued(database, tenant, monkeypatch)
    changes = [
        ("actor_id=%s", (worker.context.actor_id,)),
        ("idempotency_key=%s", (uuid4(),)),
        ("parser_version=%s", ("sandbox-mime-v1-" + "b" * 64,)),
        ("approval_scopes=%s", (["email.review"],)),
        ("created_at=created_at-interval '1 second'", ()),
        ("expires_at=expires_at+interval '1 hour'", ()),
        ("receipt_id=%s", (uuid4(),)),
    ]
    for assignment, parameters in changes:
        with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
            conn.execute(
                sql.SQL("UPDATE recovery_jobs SET {} WHERE id=%s").format(sql.SQL(assignment)),
                (*parameters, job["id"]),
            )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute("DELETE FROM recovery_jobs WHERE id=%s", (job["id"],))
    with store.transaction(ctx) as conn:
        row = conn.execute("SELECT * FROM recovery_jobs WHERE id=%s", (job["id"],)).fetchone()
        assert row["actor_id"] == ctx.actor_id
        assert row["approval_scopes"] == ["email.evidence.read", "email.review"]
        assert (row["expires_at"] - row["created_at"]).total_seconds() == 3600


@pytest.mark.parametrize("when", ["before_claim", "during_processing"])
def test_approval_expiry_fences_new_evidence(database, tenant, monkeypatch, when):
    _, admin = database
    ctx, account = tenant
    jobs, _, worker, _, job = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    prepare = processor.prepare
    calls = []

    def expiring(raw):
        calls.append(True)
        result = prepare(raw)
        expire_approval(admin, job["id"])
        return result

    if when == "before_claim":
        expire_approval(admin, job["id"])
        monkeypatch.setattr(processor, "prepare", lambda raw: pytest.fail("expired approval"))
    else:
        monkeypatch.setattr(processor, "prepare", expiring)
    jobs.run_once(worker, account, processor)
    assert jobs.get(ctx, account, job["id"])["status"] == "expired"
    assert len(calls) == (1 if when == "during_processing" else 0)
    no_publication(admin, ctx)


@pytest.mark.parametrize("replacement", [False, True])
def test_stale_lease_cannot_publish_or_complete_job(database, tenant, monkeypatch, replacement):
    store, admin = database
    ctx, account = tenant
    jobs, _, worker, _, job = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    prepare = processor.prepare
    token = uuid4()

    def lose_lease(raw):
        result = prepare(raw)
        if replacement:
            mutate_job(admin, job["id"], "lease_token=%s", (token,))
        else:
            mutate_job(admin, job["id"], "lease_until=clock_timestamp()-interval '1 second'")
        return result

    monkeypatch.setattr(processor, "prepare", lose_lease)
    jobs.run_once(worker, account, processor)
    no_publication(admin, ctx)
    with store.transaction(ctx) as conn:
        row = conn.execute("SELECT * FROM recovery_jobs WHERE id=%s", (job["id"],)).fetchone()
        assert row["status"] != "completed" and row["attempt_id"] is None
        if replacement:
            assert row["lease_token"] == token and row["status"] == "running"


def test_unavailability_backs_off_three_times_without_caching_rejection(
    database, tenant, monkeypatch
):
    store, admin = database
    ctx, account = tenant
    jobs, _, worker, _, job = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()

    def unavailable(raw):
        raise TimeoutError("synthetic private parser diagnostic")

    monkeypatch.setattr(processor, "prepare", unavailable)
    for attempt in range(1, 4):
        result = jobs.run_once(worker, account, processor)
        assert result["attempts"] == attempt
        assert result["status"] == ("retry_wait" if attempt < 3 else "failed")
        assert "private" not in repr(result)
        no_publication(admin, ctx)
        if attempt < 3:
            with store.transaction(ctx) as conn:
                delay = conn.execute(
                    "SELECT extract(epoch FROM retry_at-clock_timestamp()) AS seconds "
                    "FROM recovery_jobs WHERE id=%s",
                    (job["id"],),
                ).fetchone()["seconds"]
                assert 60 * attempt - 10 <= delay <= 60 * attempt
            assert jobs.run_once(worker, account, processor) is None
            mutate_job(admin, job["id"], "retry_at=clock_timestamp()-interval '1 second'")
    assert jobs.run_once(worker, account, processor) is None


def test_expired_crash_leases_stop_after_three_claims(database, tenant, monkeypatch):
    _, admin = database
    ctx, account = tenant
    jobs, _, worker, _, job = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    claims = []

    class SyntheticCrash(BaseException):
        pass

    def crash(raw):
        claims.append(True)
        raise SyntheticCrash()

    monkeypatch.setattr(processor, "prepare", crash)
    for attempt in range(1, 4):
        with pytest.raises(SyntheticCrash):
            jobs.run_once(worker, account, processor)
        current = jobs.get(ctx, account, job["id"])
        assert current["status"] == "running" and current["attempts"] == attempt
        mutate_job(admin, job["id"], "lease_until=clock_timestamp()-interval '1 second'")
    jobs.run_once(worker, account, processor)
    assert jobs.get(ctx, account, job["id"])["status"] == "failed"
    assert len(claims) == 3
    no_publication(admin, ctx)


def test_disabled_or_changed_parser_cannot_enqueue_or_claim(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    jobs, human, worker, receipt, job = queued(database, tenant, monkeypatch)
    disabled = RecoveryJobs(store, None)
    assert disabled.capabilities(ctx, account)["enabled"] is False
    with pytest.raises(Conflict):
        disabled.enqueue(human, account, receipt, VERSION, uuid4())
    wrong = "sandbox-mime-v1-" + "b" * 64
    with pytest.raises(Conflict):
        jobs.enqueue(human, account, receipt, wrong, uuid4())
    processor = FakeProcessor()
    processor.parser_version = wrong
    with pytest.raises(Conflict):
        jobs.run_once(worker, account, processor)
    assert jobs.get(ctx, account, job["id"])["attempts"] == 0
    no_publication(admin, ctx)


def test_admission_cap_serializes_concurrent_human_requests(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs, human = RecoveryJobs(store, VERSION), Principal(ctx, "human")
    with store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO recovery_jobs(tenant_id,account_id,receipt_id,actor_id,"
            "idempotency_key,parser_version) SELECT %s,%s,%s,%s,gen_random_uuid(),%s "
            "FROM generate_series(1,99)",
            (ctx.tenant_id, account, receipt, ctx.actor_id, VERSION),
        )

    def enqueue_one():
        try:
            return jobs.enqueue(human, account, receipt, VERSION, uuid4())["status"]
        except Conflict:
            return "capacity_denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(enqueue_one) for _ in range(2)]
        assert sorted(future.result(timeout=15) for future in futures) == [
            "capacity_denied",
            "queued",
        ]
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_jobs").fetchone()["n"] == 100


def test_idempotency_key_is_bound_to_requesting_actor(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs = RecoveryJobs(store, VERSION)
    second_actor = worker_principal(admin, ctx).context
    other_human = Principal(replace(second_actor, scopes=ctx.scopes), "human")
    key = uuid4()
    first = jobs.enqueue(Principal(ctx, "human"), account, receipt, VERSION, key)
    second = jobs.enqueue(other_human, account, receipt, VERSION, key)
    assert first["id"] != second["id"]
    assert jobs.enqueue(other_human, account, receipt, VERSION, key)["id"] == second["id"]
