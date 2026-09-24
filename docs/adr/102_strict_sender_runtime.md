# ADR-102: Require security-patched strict sender parsing

Date: 2026-09-24. Status: accepted for the synthetic alpha fix.

## Decision

Retain CPython's `email.utils.parseaddr(..., strict=True)` behavior. Never fall
back to permissive parsing and do not implement a replacement address parser.
Both product packages must import one dependency-free runtime guard before their
CLI/API capabilities load. The guard checks the documented strict-parsing marker
and a known-valid strict call. Unsupported or broken capability is a loud
`RuntimeError`, not a per-message empty classification. Successful module import
performs the automatic probe once per process.

Classification continues to reject the parser's empty-address result and catch
per-message `ValueError`; unexpected `TypeError` propagates. Exact domain matching
is classification, never proof of sender authentication.

The upstream backport floors are 3.11.10 and 3.12.6. Package and lock metadata must
exclude 3.11.0-3.11.9 and 3.12.0-3.12.5. These are compatibility floors, not a
recommendation to deploy old patch releases. Prefer current supported security
patches. Retain the capability guard for vendor builds and direct source runs.

## Validation

Test exact positive effects and matched rule versions, malformed/ambiguous
rejections including empty-tuple results, propagated programming errors, both
package startup paths and missing/falsely advertised capability. Run dedicated
checks on the two minimum patched releases and current 3.11-3.14. Exercise actual
unsupported 3.11.9 and 3.12.4 imports without installing the project. Full CI and
populated restore remain required on the exact fix and merged commits.

## Tooling and rollback

A disposable preparation branch may run a narrowly scoped Actions job to refresh
`uv.lock` without dependency upgrades and store an unattached Git blob. Its token
has repository-content write only for blob creation, does not push branches/tags,
and does not access secrets or live data. This one-shot workflow is not part of the
fix branch. The reviewed fix references the resulting blob through the connector.
Normal test workflows remain contents-read only.

Rollback means reverting the fix only in synthetic development; do not restore
permissive parsing or operate a known incompatible runtime. Production rollout,
source effects, schema/grant changes and FOS-Master cutover are not authorized.

## Primary references

- Python 3.11.10 security release: https://www.python.org/downloads/release/python-31110/
- Python 3.12 email utilities: https://docs.python.org/3.12/library/email.utils.html
- CPython upstream security change: https://github.com/python/cpython/issues/102988
