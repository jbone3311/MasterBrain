"""Opt-in logical restore proof using a fresh, synthetic-only local Docker cluster.

No DSN, input archive, target database, Docker host, or output-path argument exists.
Run only on a disposable Linux Docker runner. Never a production backup command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from email_brain.attachments import Attachment
from email_brain.auth import Principal
from email_brain.blobs import BlobError, BlobRef, EncryptedBlobStore
from email_brain.document_jobs import POLICY, DocumentJobs
from email_brain.domain.models import TenantContext
from email_brain.memory import Memory
from email_brain.memory_schema import MemoryWrite, Trip
from email_brain.migrate import grant_runtime, migrate
from email_brain.normalize import PARSER_VERSION, NormalizedMessage
from email_brain.oidc import AccessTokenVerifier, OIDCAuthenticator, OIDCConfig, VerifiedToken
from email_brain.pdf_contract import PdfPage, PdfResult, source_for
from email_brain.recovery import Recovery
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.rules.control import RuleControl
from email_brain.schemas import (
    FeaturePayload,
    ProposalRequest,
    ReviewRequest,
    RulePayload,
    SearchRequest,
)
from email_brain.store import AccessDenied, IngestItem, NotFound, Store
from email_brain.synthetic_formats import pdf_bytes
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.fileos import SNAPSHOT_VERSION
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import ClaimWrite, EntityWrite

DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]
LABEL = "com.cw-email-brain.synthetic-restore"
IMAGE = "postgres:17"
PREFIX = "email_brain_test_restore_"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024


class DrillFailure(Exception):
    """Safe diagnostic only; original process/SQL errors are never printed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DrillFailure(message)


def stage(name: str) -> None:
    print(json.dumps({"stage": name, "synthetic_only": True}), flush=True)


def database_name(name: str) -> str:
    require(
        bool(re.fullmatch(PREFIX + r"[a-f0-9]{16}_(source|target|control)", name)),
        "unsafe disposable database name",
    )
    return name


def owned_container(record: object, name: str, nonce: str) -> str:
    require(isinstance(record, dict), "invalid container inspection")
    assert isinstance(record, dict)
    require(record.get("Name") == "/" + name, "container name mismatch")
    config = record.get("Config")
    require(isinstance(config, dict), "missing container configuration")
    assert isinstance(config, dict)
    labels = config.get("Labels")
    require(
        isinstance(labels, dict) and labels.get(LABEL) == nonce,
        "container ownership label mismatch; refusing cleanup",
    )
    identity = record.get("Id")
    require(
        isinstance(identity, str) and bool(re.fullmatch(r"[a-f0-9]{64}", identity)),
        "invalid container identity",
    )
    assert isinstance(identity, str)
    return identity


def published_port(record: dict[str, Any]) -> int:
    try:
        mappings = record["NetworkSettings"]["Ports"]["5432/tcp"]
        require(isinstance(mappings, list) and len(mappings) == 1, "invalid port mapping")
        mapping = mappings[0]
        require(mapping["HostIp"] == "127.0.0.1", "database port is not loopback-only")
        value = mapping["HostPort"]
        require(isinstance(value, str) and value.isascii() and value.isdigit(), "invalid port")
        port = int(value)
        require(1024 <= port <= 65535, "invalid ephemeral database port")
        return port
    except (KeyError, TypeError, ValueError):
        raise DrillFailure("invalid container port configuration") from None


def command(
    args: list[str],
    *,
    stdout: BinaryIO | None = None,
    stdin: BinaryIO | None = None,
    environment: dict[str, str] | None = None,
    timeout: int = 180,
) -> bytes:
    try:
        result = subprocess.run(
            [*DOCKER, *args],
            stdin=stdin,
            stdout=stdout if stdout is not None else subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise DrillFailure("Docker command unavailable or timed out; output suppressed") from None
    require(result.returncode == 0, "Docker command failed; output suppressed")
    return result.stdout if stdout is None else b""


def inspect_container(name: str) -> dict[str, Any] | None:
    # Missing exact name is safe during cleanup; no listing/glob/prune is used.
    try:
        result = subprocess.run(
            [*DOCKER, "container", "inspect", name],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise DrillFailure("cannot inspect exact drill container") from None
    if result.returncode != 0:
        # Differentiate an absent name from daemon/network errors without echoing output.
        if b"No such container" in result.stderr or b"No such object" in result.stderr:
            return None
        raise DrillFailure("container inspection failed; output suppressed")
    try:
        records = json.loads(result.stdout)
        require(
            isinstance(records, list) and len(records) == 1 and isinstance(records[0], dict),
            "invalid container inventory",
        )
        record: dict[str, Any] = records[0]
        return record
    except (ValueError, TypeError):
        raise DrillFailure("invalid container inventory") from None


def cleanup_container(name: str, nonce: str) -> None:
    record = inspect_container(name)
    if record is not None:
        identity = owned_container(record, name, nonce)
        command(["container", "rm", "--force", "--volumes", identity], timeout=30)


def dsn(port: int, password: str, name: str, user: str = "postgres") -> str:
    return make_conninfo(
        host="127.0.0.1",
        hostaddr="127.0.0.1",
        port=port,
        dbname=database_name(name),
        user=user,
        password=password,
        connect_timeout=2,
        options="-c statement_timeout=10000 -c lock_timeout=3000",
    )


def make_runtime(admin: str, role: str) -> Store:
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE "
                "NOREPLICATION PASSWORD {}"
            ).format(sql.Identifier(role), sql.Literal(password))
        )
        grant_runtime(conn, role)
    return Store(make_conninfo(admin, user=role, password=password))


@dataclass(frozen=True)
class SeededTenant:
    context: TenantContext
    account_id: UUID
    evidence_id: UUID
    proposal_id: UUID
    rule_proposal_id: UUID
    simulation_id: UUID
    category: str
    keyword: str
    evidence_digest: str
    job_ids: tuple[UUID, UUID, UUID]
    document_jobs: tuple[UUID, UUID, UUID]
    document_id: UUID
    document_digest: str
    identity_id: UUID
    brain_document_id: str
    brain_evidence_id: str
    brain_run_id: UUID
    knowledge_entity_id: str
    knowledge_claim_id: str


class SyntheticDocumentProcessor:
    """Known-answer result for restore, not real extraction/isolation acceptance."""

    processor_version = "sandbox-pdf-v1-" + "a" * 64

    def extract(self, raw: bytes, *, part_path: str, part_sha256: str) -> PdfResult:
        return PdfResult(
            source_for(raw, part_path, part_sha256),
            "extracted",
            "bounded_pdf_v1",
            1,
            (PdfPage(1, "restoredocumentproof"),),
        )


class SyntheticRestoreProcessor:
    """Only exercise durable rejection; not an actual container/isolation proof."""

    parser_version = "sandbox-mime-v1-" + "a" * 64
    max_raw_bytes = 16 * 1024 * 1024

    def prepare(self, raw: bytes) -> tuple[NormalizedMessage | None, list[Attachment], bool]:
        require(raw == b"", "restore processor only accepts empty synthetic MIME")
        return None, [], True


def stable_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def synthetic_mime(keyword: str) -> bytes:
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Subject"] = f"Synthetic restore {keyword}"
    message["Message-ID"] = f"<{keyword}@example.invalid>"
    message.set_content(f"Synthetic evidence {keyword}; no real payment or mail.")
    message.add_attachment(
        f"Attachment proof {keyword} spreadsheet".encode(),
        maintype="text",
        subtype="plain",
        filename="proof.txt",
    )
    message.add_attachment(
        pdf_bytes(("restoredocumentproof",)),
        maintype="application",
        subtype="pdf",
        filename="unparsed.pdf",
    )
    calendar = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Synthetic restore//EN\r\n"
        "BEGIN:VEVENT\r\nUID:restore-event@example.invalid\r\n"
        "DTSTAMP:20260920T120000Z\r\nDTSTART:20261001T120000Z\r\n"
        f"SUMMARY:restorecalendarproof {keyword}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    message.add_attachment(
        calendar.encode(), maintype="text", subtype="calendar", filename="meeting.ics"
    )
    return message.as_bytes()


def seed(
    admin: str,
    store: Store,
    *,
    object_root: Path | None = None,
    keys: dict[tuple[UUID, str], bytes] | None = None,
) -> list[SeededTenant]:
    tenants = []
    for keyword in ("restorealphazebra", "restorebetazebra"):
        tenant, actor, account = uuid4(), uuid4(), uuid4()
        identity_id = uuid4()
        with psycopg.connect(admin) as conn:
            conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic restore')", (tenant,))
            conn.execute(
                "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
                (tenant, actor),
            )
            conn.execute(
                "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
                "VALUES (%s,%s,'fastmail','owner@example.invalid','synthetic:none')",
                (account, tenant),
            )
            conn.execute(
                "INSERT INTO external_identities(id,tenant_id,actor_id,issuer,subject,client_id,"
                "scopes,client_kind) VALUES (%s,%s,%s,'https://issuer.example.invalid',%s,"
                "'restore-client',ARRAY['email.search','email.evidence.read'],'human')",
                (identity_id, tenant, actor, keyword),
            )
        context = TenantContext(
            tenant,
            actor,
            frozenset(
                {
                    "email.ingest",
                    "email.search",
                    "email.evidence.read",
                    "email.proposal.create",
                    "email.proposal.read",
                    "email.review",
                    "brain.source.ingest",
                    "brain.document.publish",
                    "brain.search",
                    "brain.changes.read",
                    "knowledge.review",
                    "knowledge.read",
                    "knowledge.search",
                    "knowledge.changes.read",
                }
            ),
            uuid4(),
        )
        now = datetime(2026, 9, 20, tzinfo=UTC)
        source_id = "files_" + keyword
        locator = "restore-proof.txt"
        body = f"masterbrainrestore {keyword} source evidence"
        body_bytes = body.encode()
        body_sha = hashlib.sha256(body_bytes).hexdigest()
        brain_item_id = stable_id("item", source_id, locator)
        brain_version_id = stable_id("version", brain_item_id, body_sha, str(len(body_bytes)))
        brain_manifest = {
            "manifest_version": SNAPSHOT_VERSION,
            "source": {"source_id": source_id, "kind": "fileos"},
            "observed_at": now.isoformat(),
            "policy": {"hash_algorithm": "sha256"},
            "counts": {"items": 1, "excluded": 0, "errors": 0},
            "items": [
                {
                    "item_id": brain_item_id,
                    "version_id": brain_version_id,
                    "locator": locator,
                    "observed_at": now.isoformat(),
                    "digest": {"algorithm": "sha256", "value": body_sha},
                    "size_bytes": len(body_bytes),
                    "media_type": "text/plain",
                    "metadata": {"synthetic": True},
                    "is_symlink": False,
                }
            ],
            "errors": [],
        }
        datacore = DataCoreStore(store)
        brain_run_id = uuid4()
        imported = datacore.import_fileos_snapshot(context, brain_manifest, brain_run_id)
        require(imported.new_versions == 1, "DataCore restore seed import failed")
        brain_document = datacore.publish_text(
            context,
            brain_version_id,
            body,
            code_revision="synthetic-restore-v1",
        )
        require(brain_document.changed, "DataCore restore seed publication failed")
        run_receipt = datacore.complete_fileos_run(
            context,
            brain_manifest,
            brain_run_id,
            outcomes={"extracted": 1},
            published_documents=1,
            code_revision="synthetic-restore-v1",
            document_processor_version=None,
        )
        require(run_receipt.recorded, "DataCore run receipt seed failed")
        knowledge = KnowledgeCore(store)
        entity = knowledge.publish(
            context,
            EntityWrite(
                kind="entity",
                entity_type="organization",
                name=f"Synthetic {keyword} organization",
                aliases=[f"Knowledge restore {keyword}"],
                evidence_ids=[brain_document.evidence_id],
                source_quote=body,
                confidence=1,
                observed_at=now,
                reviewed=True,
            ),
            uuid4(),
        )
        claim = knowledge.publish(
            context,
            ClaimWrite(
                kind="claim",
                subject_entity_id=entity.object_id,
                predicate="restore.status",
                value=f"knowledgecoreproof {keyword}",
                evidence_ids=[brain_document.evidence_id],
                source_quote=body,
                confidence=1,
                observed_at=now,
                reviewed=True,
            ),
            uuid4(),
        )
        items = [
            IngestItem("good-event", "good-message", "v1", now, synthetic_mime(keyword)),
            IngestItem("poison-event", "poison-message", "v1", now, b""),
        ]
        cursor = None
        if object_root is not None:
            assert keys is not None
            # Keep a legacy inline receipt alongside externally archived good/large mail.
            store.blobs = None
            store.ingest_page(context, account, None, "inline-checkpoint", [items.pop()])
            cursor = "inline-checkpoint"
            keys[(tenant, "drill-v1")] = secrets.token_bytes(32)
            store.blobs = EncryptedBlobStore(object_root, keys, {t: key for t, key in keys})
            items.append(
                IngestItem(
                    "large-event",
                    "large-message",
                    "v1",
                    now,
                    b"Subject: Synthetic large raw\r\n\r\n" + b"x" * (1024 * 1024),
                )
            )
        require(
            store.ingest_page(context, account, cursor, "synthetic-checkpoint", items) == 2,
            "synthetic seed accounting failed",
        )
        held = next(
            q["id"]
            for q in store.quarantines(context, account)["results"]
            if q["provider_id"] == "poison-message"
        )
        require(
            Recovery(store).retry(Principal(context, "human"), account, held, PARSER_VERSION)[
                "outcome"
            ]
            == "mime_rejected",
            "synthetic recovery attempt seed failed",
        )
        processor = SyntheticRestoreProcessor()
        jobs = RecoveryJobs(store, processor.parser_version)
        human = Principal(context, "human")
        completed_job = jobs.enqueue(human, account, held, processor.parser_version, uuid4())
        jobs.run_once(
            Principal(replace(context, scopes=frozenset({"email.process"})), "worker"),
            account,
            processor,
        )
        require(
            jobs.get(context, account, completed_job["id"])["status"] == "completed",
            "synthetic job completion failed",
        )
        cancelled_job = jobs.enqueue(human, account, held, processor.parser_version, uuid4())
        jobs.cancel(human, account, cancelled_job["id"])
        queued_job = jobs.enqueue(human, account, held, processor.parser_version, uuid4())
        job_ids = (completed_job["id"], cancelled_job["id"], queued_job["id"])
        hits = store.search(context, SearchRequest(query=keyword, include_attachments=False))
        require(len(hits) == 1, "synthetic seed search failed")
        evidence_id = hits[0]["evidence_id"]
        evidence = store.evidence(context, evidence_id)
        # Populated memory/history/receipt tables must survive the same hash restore.
        memory = Memory(store)
        memory_request = MemoryWrite(
            expected_revision=0,
            evidence_id=evidence_id,
            source_quote=keyword,
            payload=Trip(kind="trip", title="Fictional restore trip"),
            reviewed=True,
        )
        memory_record = uuid4()
        memory.publish(human, account, memory_record, memory_request, uuid4())
        memory.publish(
            human,
            account,
            memory_record,
            memory_request.model_copy(
                update={
                    "expected_revision": 1,
                    "payload": Trip(
                        kind="trip", title="Fictional restore trip", status="cancelled"
                    ),
                }
            ),
            uuid4(),
        )
        require(len(evidence["attachments"]) == 3, "synthetic attachment seed failed")
        document_processor = SyntheticDocumentProcessor()
        documents = DocumentJobs(store, document_processor.processor_version)
        attachment = next(
            a["id"] for a in evidence["attachments"] if a["media_type"] == "application/pdf"
        )
        saved = documents.enqueue(
            human, account, attachment, document_processor.processor_version, POLICY, uuid4()
        )
        output = documents.run_once(
            Principal(replace(context, scopes=frozenset({"email.document.process"})), "worker"),
            account,
            document_processor,
        )
        require(output is not None and output["status"] == "completed", "document seed failed")
        assert output is not None
        document_id = output["extraction_id"]
        cancelled = documents.enqueue(
            human, account, attachment, document_processor.processor_version, POLICY, uuid4()
        )
        documents.cancel(human, account, cancelled["id"])
        pending = documents.enqueue(
            human, account, attachment, document_processor.processor_version, POLICY, uuid4()
        )
        proposal = store.propose(
            context,
            ProposalRequest(
                payload=FeaturePayload(
                    kind="feature",
                    title="Synthetic restore proof",
                    desired_outcome="Verify preserved review state",
                ),
                reason="Synthetic drill",
                source="restore-drill",
                evidence_ids=[evidence_id],
            ),
            uuid4(),
        )
        store.review(
            context, proposal["id"], ReviewRequest(decision="approved", expected_version=1)
        )
        category = "investment" if keyword == "restorealphazebra" else "business"
        rule_proposal = store.propose(
            context,
            ProposalRequest(
                payload=RulePayload(
                    kind="rule",
                    sender_domain="example.invalid",
                    category=category,
                    canonical_mailbox="review",
                ),
                reason="Synthetic restore rule",
                source="restore-drill",
                evidence_ids=[evidence_id],
            ),
            uuid4(),
        )
        store.review(
            context, rule_proposal["id"], ReviewRequest(decision="approved", expected_version=1)
        )
        rule_control = RuleControl(store)
        human = Principal(context, "human")
        simulation = rule_control.simulate(human, rule_proposal["id"], 2)
        require(
            rule_control.activate(human, simulation["id"])["revision"] == 1,
            "synthetic rule activation failed",
        )
        tenants.append(
            SeededTenant(
                context,
                account,
                evidence_id,
                proposal["id"],
                rule_proposal["id"],
                simulation["id"],
                category,
                keyword,
                stable_digest(evidence),
                job_ids,
                (saved["id"], cancelled["id"], pending["id"]),
                document_id,
                stable_digest(store.document_evidence(context, document_id)),
                identity_id,
                brain_document.document_id,
                brain_document.evidence_id,
                brain_run_id,
                entity.object_id,
                claim.object_id,
            )
        )
    return tenants


def snapshot(admin: str, blobs: EncryptedBlobStore | None = None) -> dict[str, tuple[int, str]]:
    """Hash every public table row without exporting content into diagnostics."""
    results = {}
    with psycopg.connect(admin) as conn:
        tables = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ).fetchall()
        for (table,) in tables:
            rows = conn.execute(
                sql.SQL("SELECT to_jsonb(t)::text FROM {} t ORDER BY to_jsonb(t)::text").format(
                    sql.Identifier(table)
                )
            ).fetchall()
            results[table] = (len(rows), stable_digest(rows))
        objects = conn.execute(
            "SELECT tenant_id,account_id,sha256,raw_mime,blob_ref FROM raw_objects"
        ).fetchall()
    for tenant, account, expected, raw, ref in objects:
        if ref is not None:
            require(blobs is not None, "external evidence storage is required")
            assert blobs is not None
            raw = blobs.get(tenant, account, BlobRef(**ref))
        require(hashlib.sha256(bytes(raw)).hexdigest() == expected, "raw evidence hash mismatch")
    return results


def verify_restored(admin: str, store: Store, tenants: list[SeededTenant]) -> None:
    # SQL mapping/authorization proof only; signature/HTTP proof has separate fake-issuer tests.
    identity_auth = OIDCAuthenticator(
        store,
        AccessTokenVerifier(
            OIDCConfig(
                version=1,
                profile="rfc9068",
                issuer="https://issuer.example.invalid",
                discovery_url="https://issuer.example.invalid/.well-known/openid-configuration",
                jwks_url="https://issuer.example.invalid/keys",
                audience="restore-api",
                client_ids=("restore-client",),
                admission_scope="email.access",
            )
        ),
    )
    with psycopg.connect(admin) as conn:
        rls = conn.execute(
            "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r' "
            "AND EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid "
            "AND a.attname='tenant_id' AND NOT a.attisdropped)"
        ).fetchall()
        require(
            bool(rls) and all(enabled and forced for _, enabled, forced in rls),
            "restored tenant RLS disabled",
        )
    for current, foreign in ((tenants[0], tenants[1]), (tenants[1], tenants[0])):
        ctx = current.context
        verified = VerifiedToken(
            "https://issuer.example.invalid",
            current.keyword,
            "restore-client",
            datetime.now(UTC) + timedelta(minutes=10),
        )
        mapped = identity_auth.resolve(verified)
        require(mapped is not None, "restored identity missing")
        assert mapped is not None and mapped.context.identity is not None
        require(
            mapped.context.tenant_id == ctx.tenant_id
            and mapped.context.identity.binding_id == current.identity_id
            and mapped.context.scopes == frozenset({"email.search", "email.evidence.read"}),
            "restored identity authority changed",
        )
        require(
            bool(store.search(mapped.context, SearchRequest(query=current.keyword))),
            "restored identity cannot search",
        )
        require(
            not store.search(mapped.context, SearchRequest(query=foreign.keyword)),
            "restored identity crosses tenant",
        )
        with store.transaction(mapped.context) as conn:
            identities = conn.execute("SELECT id FROM external_identities").fetchall()
            require(
                [r["id"] for r in identities] == [current.identity_id],
                "restored identity lookup RLS failed",
            )
        with store.transaction(ctx) as conn:
            require(
                not conn.execute("SELECT id FROM external_identities").fetchall(),
                "unverified context exposed identity mappings",
            )
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE external_identities SET active=false WHERE id=%s", (current.identity_id,)
            )
        require(identity_auth.resolve(verified) is None, "revoked restored identity accepted")
        try:
            store.search(mapped.context, SearchRequest(query=current.keyword))
        except AccessDenied:
            pass
        else:
            raise DrillFailure("saved restored identity survived revocation")
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE external_identities SET active=true WHERE id=%s", (current.identity_id,)
            )
        renewed = identity_auth.resolve(verified)
        require(
            renewed is not None
            and renewed.context.identity is not None
            and renewed.context.identity.revision == 3,
            "identity revision not restored",
        )
        documents = DocumentJobs(store, SyntheticDocumentProcessor.processor_version)
        for job_id, expected in zip(
            current.document_jobs, ("completed", "cancelled", "queued"), strict=True
        ):
            require(
                documents.get(ctx, current.account_id, job_id)["status"] == expected,
                "restored document job changed",
            )
        require(
            stable_digest(store.document_evidence(ctx, current.document_id))
            == current.document_digest,
            "restored document evidence changed",
        )
        document_hits = store.search(
            ctx, SearchRequest(query="restoredocumentproof", include_documents=True)
        )
        require(
            len(document_hits) == 1 and document_hits[0]["document_id"] == current.document_id,
            "restored document search failed",
        )
        brain_hits = DataCoreStore(store).search(ctx, f"masterbrainrestore {current.keyword}")
        require(
            len(brain_hits) == 1
            and brain_hits[0].document_id == current.brain_document_id
            and brain_hits[0].evidence_id == current.brain_evidence_id,
            "restored DataCore lexical evidence changed",
        )
        require(
            not DataCoreStore(store).search(ctx, foreign.keyword),
            "foreign restored DataCore evidence accessible",
        )
        freshness = DataCoreStore(store).fileos_freshness(ctx, f"files_{current.keyword}")
        require(
            freshness["status"] == "complete"
            and freshness["latest_complete_run"]["run_id"] == current.brain_run_id,
            "restored DataCore FileOS completion receipt changed",
        )
        knowledge = KnowledgeCore(store)
        knowledge_hits = knowledge.search(ctx, f"knowledgecoreproof {current.keyword}")
        require(
            len(knowledge_hits) == 1
            and knowledge_hits[0].object_id == current.knowledge_claim_id
            and knowledge_hits[0].evidence_ids == (current.brain_evidence_id,),
            "restored KnowledgeCore retrieval changed",
        )
        require(
            knowledge.get(ctx, "entity", current.knowledge_entity_id)["name"]
            == f"Synthetic {current.keyword} organization",
            "restored KnowledgeCore entity changed",
        )
        require(
            not knowledge.search(ctx, f"knowledgecoreproof {foreign.keyword}"),
            "foreign restored KnowledgeCore assertion accessible",
        )
        try:
            knowledge.get(ctx, "entity", foreign.knowledge_entity_id)
        except NotFound:
            pass
        else:
            raise DrillFailure("foreign restored KnowledgeCore entity accessible")
        try:
            store.document_evidence(ctx, foreign.document_id)
        except NotFound:
            pass
        else:
            raise DrillFailure("foreign restored document accessible")
        jobs = RecoveryJobs(store, SyntheticRestoreProcessor.parser_version)
        history = jobs.list(ctx, current.account_id)
        require(
            [row["id"] for row in history["results"]] == list(reversed(current.job_ids))
            and history["next_after"] is None,
            "restored processing history changed",
        )
        for job_id, expected in zip(
            current.job_ids, ("completed", "cancelled", "queued"), strict=True
        ):
            job = jobs.get(ctx, current.account_id, job_id)
            require(job["status"] == expected, "restored job state changed")
            require("lease_token" not in job, "restored job exposes lease authority")
            if expected == "completed":
                require(job["outcome"] == "mime_rejected", "restored job outcome changed")
        try:
            jobs.get(ctx, foreign.account_id, foreign.job_ids[0])
        except NotFound:
            pass
        else:
            raise DrillFailure("foreign restored job accessible")
        hits = store.search(ctx, SearchRequest(query=current.keyword, include_attachments=False))
        require(
            len(hits) == 1,
            "restored full-text search failed",
        )
        classification = hits[0]["classification"]
        require(
            classification["rules_revision"] == 1
            and classification["virtual_only"]
            and classification["effects"]
            == {"category": current.category, "canonical_mailbox": "review"},
            "restored rule classification changed",
        )
        control = RuleControl(store)
        rules = control.list(ctx)
        require(
            rules["revision"] == 1
            and len(rules["rules"]) == 1
            and rules["rules"][0]["payload"]["category"] == current.category,
            "restored active rule revision changed",
        )
        try:
            control.activate(Principal(ctx, "human"), foreign.simulation_id)
        except NotFound:
            pass
        else:
            raise DrillFailure("foreign simulation receipt is accessible")
        require(
            not store.search(ctx, SearchRequest(query=foreign.keyword)),
            "foreign tenant search leak",
        )
        evidence = store.evidence(ctx, current.evidence_id)
        require(stable_digest(evidence) == current.evidence_digest, "restored evidence changed")
        attachment_hits = store.search(ctx, SearchRequest(query="spreadsheet"))
        calendar_hits = store.search(ctx, SearchRequest(query="restorecalendarproof"))
        require(
            len(calendar_hits) == 1 and calendar_hits[0]["result_type"] == "attachment",
            "restored calendar attachment search failed",
        )
        require(
            len(attachment_hits) == 1 and attachment_hits[0]["result_type"] == "attachment",
            "restored attachment search failed",
        )
        try:
            store.evidence(ctx, foreign.evidence_id)
        except NotFound:
            pass
        else:
            raise DrillFailure("foreign evidence was exposed")
        status = store.sync_status(ctx, current.account_id)
        held = next(
            q["id"]
            for q in store.quarantines(ctx, current.account_id)["results"]
            if q["provider_id"] == "poison-message"
        )
        require(
            Recovery(store).retry(
                Principal(ctx, "human"), current.account_id, held, PARSER_VERSION
            )["outcome"]
            == "mime_rejected",
            "restored recovery attempt changed",
        )
        require(
            status["message_counts"]["ready"] == 1
            and status["message_counts"]["quarantined"] == (2 if store.blobs else 1),
            "quarantine state changed",
        )
        proposals = store.proposals(ctx)
        require(
            len(proposals) == 2
            and {proposal["id"] for proposal in proposals}
            == {current.proposal_id, current.rule_proposal_id}
            and all(proposal["status"] == "approved" for proposal in proposals),
            "proposal review state changed",
        )
        with store.transaction(ctx) as conn:
            require(
                conn.execute(
                    "SELECT id FROM rule_simulations WHERE id=%s", (foreign.simulation_id,)
                ).fetchone()
                is None,
                "foreign rule receipt SQL leak",
            )
            message_count = conn.execute("SELECT count(*) AS n FROM messages").fetchone()
            require(
                message_count is not None and message_count["n"] == 1,
                "unfiltered SQL tenant isolation failed",
            )
            cursor = conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()
            require(
                cursor is not None and cursor["opaque_cursor"] == "synthetic-checkpoint",
                "restored checkpoint changed",
            )
        try:
            with store.transaction(ctx) as conn:
                conn.execute("UPDATE raw_objects SET raw_mime=raw_mime")
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise DrillFailure("runtime can modify raw evidence")
        try:
            Store(admin).search(ctx, SearchRequest(query=current.keyword))
        except AccessDenied:
            pass
        else:
            raise DrillFailure("unsafe owner runtime accepted")
    with psycopg.connect(store.dsn) as conn:
        count = conn.execute("SELECT count(*) FROM messages").fetchone()
        require(
            count is not None and count[0] == 0,
            "missing tenant context exposes rows",
        )
    try:
        with psycopg.connect(admin) as conn:
            conn.execute("UPDATE raw_objects SET raw_mime=raw_mime")
    except psycopg.errors.RaiseException:
        pass
    else:
        raise DrillFailure("restored immutable evidence trigger is missing")


def run_drill() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="email-brain-objects-", dir="/tmp") as directory:
        return _run_drill(Path(directory).resolve())


def _run_drill(storage: Path) -> dict[str, object]:
    require(
        not any(key.startswith("PG") for key in os.environ),
        "ambient PostgreSQL settings are forbidden for this disposable drill",
    )
    nonce = uuid4().hex
    name = PREFIX + nonce[:16]
    source, target, control = (name + suffix for suffix in ("_source", "_target", "_control"))
    password = secrets.token_urlsafe(32)
    started = time.monotonic()
    # The fixed Docker UNIX socket defeats ambient remote Docker host/context settings.
    environment = dict(os.environ, POSTGRES_PASSWORD=password)
    try:
        stage("create_disposable_cluster")
        command(
            [
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--label",
                f"{LABEL}={nonce}",
                "--publish",
                "127.0.0.1::5432",
                "--env",
                "POSTGRES_PASSWORD",
                "--env",
                f"POSTGRES_DB={control}",
                IMAGE,
            ],
            environment=environment,
        )
        record = inspect_container(name)
        require(record is not None, "drill container was not created")
        assert record is not None
        identity = owned_container(record, name, nonce)
        port = published_port(record)
        control_dsn = dsn(port, password, control)
        for _ in range(40):
            try:
                with psycopg.connect(control_dsn) as conn:
                    require(170000 <= conn.info.server_version < 180000, "PostgreSQL 17 required")
                break
            except psycopg.OperationalError:
                time.sleep(1)
        else:
            raise DrillFailure("disposable PostgreSQL did not become ready")
        for utility in ("pg_dump", "pg_restore"):
            require(
                command(["exec", identity, utility, "--version"]).startswith(
                    f"{utility} (PostgreSQL) 17.".encode()
                ),
                "PostgreSQL utility version mismatch",
            )
        with psycopg.connect(control_dsn, autocommit=True) as conn:
            for database in (source, target):
                conn.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                        sql.Identifier(database_name(database))
                    )
                )
        source_dsn, target_dsn = dsn(port, password, source), dsn(port, password, target)
        root = Path(__file__).resolve().parents[1]
        stage("migrate_and_seed_synthetic_source")
        migrate(source_dsn, root / "migrations")
        source_store = make_runtime(source_dsn, "restore_source_runtime")
        keys: dict[tuple[UUID, str], bytes] = {}
        tenants = seed(source_dsn, source_store, object_root=storage / "source", keys=keys)
        before = snapshot(source_dsn, source_store.blobs)
        # Separate encrypted-byte backup; key material remains independently in memory.
        shutil.copytree(storage / "source", storage / "backup")
        with psycopg.connect(target_dsn) as conn:
            target_tables = conn.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
            ).fetchone()
            require(
                target_tables is not None and target_tables[0] == 0,
                "restore target is not empty",
            )
        with tempfile.TemporaryDirectory(prefix="email-brain-restore-", dir="/tmp") as directory:
            os.chmod(directory, 0o700)
            archive = Path(directory) / "synthetic.dump"
            stage("dump_synthetic_source")
            descriptor = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                command(
                    [
                        "exec",
                        identity,
                        "pg_dump",
                        "--username=postgres",
                        f"--dbname={source}",
                        "--format=custom",
                        "--no-acl",
                    ],
                    stdout=output,
                )
            require(stat.S_IMODE(archive.stat().st_mode) == 0o600, "archive permissions are unsafe")
            require(
                0 < archive.stat().st_size <= MAX_ARCHIVE_BYTES, "synthetic archive size invalid"
            )
            with archive.open("rb") as incoming:
                stage("restore_into_empty_target")
                command(
                    [
                        "exec",
                        "-i",
                        identity,
                        "pg_restore",
                        "--username=postgres",
                        f"--dbname={target}",
                        "--exit-on-error",
                        "--single-transaction",
                        "--no-owner",
                        "--no-acl",
                    ],
                    stdin=incoming,
                )
        stage("verify_restored_data_and_authorization")
        try:
            snapshot(target_dsn)
        except DrillFailure:
            pass
        else:
            raise DrillFailure("database-only restore accepted absent external evidence")
        target_blobs = EncryptedBlobStore(storage / "target", keys, {t: key for t, key in keys})
        try:
            snapshot(target_dsn, target_blobs)
        except BlobError:
            pass
        else:
            raise DrillFailure("empty object restore accepted missing evidence")
        shutil.copytree(storage / "backup", storage / "target", dirs_exist_ok=True)
        require(
            snapshot(target_dsn, target_blobs) == before,
            "restored table counts or content digests differ",
        )
        require(migrate(target_dsn, root / "migrations") == [], "restored migrations differ")
        restored_store = make_runtime(target_dsn, "restore_target_runtime")
        restored_store.blobs = target_blobs
        verify_restored(target_dsn, restored_store, tenants)
        return {
            "status": "passed",
            "synthetic_only": True,
            "postgres_major": 17,
            "tables_verified": len(before),
            "rows_verified": sum(n for n, _ in before.values()),
            "tenants_verified": len(tenants),
            "content_hashes_equal": True,
            "rls_verified": True,
            "identity_bindings_verified": len(tenants),
            "identity_revocation_verified": True,
            "database_only_restore_refused": True,
            "external_objects_verified": sum(
                len(target_blobs.object_keys(t.context.tenant_id, t.account_id)) for t in tenants
            ),
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
    finally:
        stage("cleanup_exact_owned_container")
        cleanup_container(name, nonce)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-disposable",
        action="store_true",
        required=True,
        help="Create and destroy a fresh synthetic PostgreSQL Docker container",
    )
    parser.parse_args()
    try:
        print(json.dumps(run_drill(), sort_keys=True))
        return 0
    except DrillFailure as error:
        print(json.dumps({"status": "failed", "synthetic_only": True, "detail": str(error)}))
        return 1
    except Exception:
        # PostgreSQL exceptions can embed rows/password SQL: do not emit tracebacks.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "synthetic_only": True,
                    "detail": "Synthetic restore drill failed; sensitive output suppressed",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
