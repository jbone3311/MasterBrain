# ADR-104 — Privacy-safe request failure observability

Status: accepted for the local synthetic alpha, 2026-09-24.

## Context

The API already emits a server-generated request ID and content-free completion log
for ordinary responses. An unexpected exception can bypass that response path and
leave only a framework error, while database and storage failures deliberately hide
unsafe diagnostics. Operators need a correlation signal without publishing MIME,
SQL details, credentials, source paths or request bodies to logs.

## Decision

Catch unexpected application exceptions at the request-metadata boundary and return
a fixed `internal_error` 500 JSON body. Preserve the server-generated request ID,
no-store and security headers, and emit one ERROR event containing only request ID,
fixed route template, status, stable code and exception class. Emit the same safe
event for the existing bounded 503 infrastructure handlers. Never log exception
strings, tracebacks, URLs, parameters, headers or submitted content. Expected 4xx
refusals retain their existing responses and completion logging; they are not
promoted to infrastructure errors.

This is a local process diagnostic, not a durable security audit, distributed trace,
protected log pipeline or guarantee about middleware and background-task failures.
Production alerting, retention and incident response remain release gates.

## Verification and rollback

Unit tests inject exceptions whose messages and queries contain a fictional canary.
They assert exact status/body, security and request-ID headers, one safe error event,
and absence of the canary from both response and event. Full repository CI and
populated restore remain required for the PR. Rollback is application-code only;
no schema, evidence or permission change occurs. Reverting must not enable raw
exception logging or weaken the existing response sanitization.
