# ADR-120 — Content-safe sandbox failure-stage diagnostics

Status: accepted for the trusted local controller and synthetic CI.

## Context

The isolated MIME controller correctly fails closed as `MimeUnavailable`, but
its blanket exception handling also erases which trusted Docker/pipe stage
failed. The same large synthetic MIME check passed on PR #66, failed on the
first merged-main run, then passed on an unchanged-commit rerun (issue #64).
That evidence is not enough to distinguish process I/O, timeout, container
exit/OOM, response validation or cleanup. Guessing a larger timeout or
weakening the gate would conceal a real failure.

## Decision

- Keep the public exception and fail-closed behavior unchanged. Only the
  trusted controller emits a warning with a fixed profile, stage and reason
  code on failure. No source bytes, paths, container IDs, image IDs, command
  arguments, stderr/stdout, exception messages or tracebacks enter the log.
- Record bounded pipe reasons for spawn, deadline, output limit, short input,
  nonzero CLI exit, I/O and reap failures. It distinguishes a verified worker
  OOM, nonzero worker exit and malformed/incomplete worker state without
  recording a raw exit code. The outer controller records the
  fixed Docker stage: image check, creation, pre-start inspection, isolated
  start, post-start inspection, worker exit, response decode or cleanup.
  Unknown exceptions become `unexpected`, not their message or string form.
- Do not automatically retry a failed processing attempt, change resource
  limits, trust a partial output or treat a rerun as evidence of correctness.
  The real restricted-container CI check remains mandatory.
- Diagnostic events are operational telemetry on the privileged controller,
  not durable evidence or user-facing API content. Protected collection,
  retention and correlation remain production operations requirements.

## Verification and rollback

Inject each failure class into the offline controller/pipe tests and assert
fixed codes, unchanged `MimeUnavailable`, no secret-bearing strings, no raw
input before isolation inspection and exact-owned cleanup. Run the full
suite and hosted container check. Rollback filters this dedicated warning
logger or redeploys the previous controller; the previously fail-closed
behavior remains. Use the next real
recurrence to identify a cause before changing timeout/CPU/memory policy.
