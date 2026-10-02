"""Explicit synthetic PDF operator workflow; never broadens MIME approvals."""

from pathlib import Path
from threading import Event
from typing import Any, Literal

from email_brain.document_jobs import DocumentJobs, PdfProcessor
from email_brain.pdf_contract import PdfResult
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.processing_controller import (
    ControllerConfig,
    ControllerError,
    WorkerIdentity,
    _json,
    configured_store,
    poll_jobs,
    validate_run_options,
)


class DocumentControllerConfig(ControllerConfig):
    job_kind: Literal["pdf-document"]
    policy_version: Literal["synthetic-unscanned-pdf-v1"]


class _AuthenticatedPdf:
    def __init__(self, processor: PdfProcessor, identity: WorkerIdentity) -> None:
        self.processor, self.identity = processor, identity

    @property
    def processor_version(self) -> str:
        return self.processor.processor_version

    def extract(self, raw: bytes, *, part_path: str, part_sha256: str) -> PdfResult:
        self.identity.authenticate()
        result = self.processor.extract(raw, part_path=part_path, part_sha256=part_sha256)
        self.identity.authenticate()
        return result


def run_document_controller(
    path: Path,
    dsn: str,
    *,
    check: bool = False,
    max_iterations: int = 1,
    idle_seconds: int = 5,
    stop: Event | None = None,
    tenant_bound_db: bool = False,
) -> dict[str, Any]:
    try:
        validate_run_options(dsn, max_iterations, idle_seconds)
        config = DocumentControllerConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope="email.document.process")
        principal = identity.authenticate()
        store = configured_store(
            config, dsn, principal, synthetic_only=True, tenant_bound_db=tenant_bound_db
        )
        identity.authenticate()
        if check:
            return {"configuration_valid": True, "execution_verified": False, "claims": 0}
        processor = _AuthenticatedPdf(
            DockerPdfProcessor(config.image_id, docker_binary=config.docker_binary), identity
        )
        jobs = DocumentJobs(store, processor.processor_version)
        return poll_jobs(
            identity,
            lambda current: jobs.run_once(current, config.account_id, processor),
            max_iterations=max_iterations,
            idle_seconds=idle_seconds,
            stop=stop,
        )
    except Exception:
        raise ControllerError() from None
