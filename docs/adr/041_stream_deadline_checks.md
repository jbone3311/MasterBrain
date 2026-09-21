# ADR-041: Check response deadlines without application chunk buffering

Status: accepted prototype correction, 2026-09-21.

## Context

Pressure review of ADR-040 identified that asking HTTPX to assemble fixed-size
chunks can postpone application deadline checks while a server drips small reads.
The Fastmail, Gmail, Graph and local Ollama readers used the same pattern.
Per-read socket timeouts alone do not bound a continually progressing response.

## Decision

Consume decoded transport chunks without additional fixed-size buffering. Check
the existing elapsed-time and byte budgets on each yielded chunk and after EOF.
Accumulate accepted bytes in a bytearray, not a list with one entry per fragment;
check the byte cap before extending it. Preserve existing endpoints, status/error
contracts, compression refusal, scopes and budgets. Fastmail gains the missing
post-EOF deadline check, including delayed empty responses.

This is cooperative response-body deadline enforcement, not a hard wall-clock
process deadline over DNS, TLS, blocked reads or a malicious custom transport.
Existing network timeouts and deployment supervision remain necessary. No live
provider, new grant, dependency, schema or mailbox action is introduced.

## Verification and operations

Use fictional HTTP streams and a controlled clock to prove rejection before a
third slow byte, rejection after delayed empty EOF, successful fragmented JSON,
byte-limit rejection and stream closure on every path. Prove slow-drip tests fail
the previous buffered implementation, then run the full quality/CI gates.
Existing scrubbed unavailable/protocol outcomes remain the telemetry contract;
do not log response content or credentials. Operators should investigate repeated
deadline failures using existing worker status, not weaken time or byte budgets.

Rollback is a normal source revision with no data migration. Reverting restores
the known buffering weakness; retain this correction when rolling back unrelated
features. Acceptance receipts identify the exact tested commit.
