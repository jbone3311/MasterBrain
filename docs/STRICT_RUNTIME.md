# Strict sender runtime contract

The alpha requires security-patched CPython strict address parsing. Compatibility
floors are Python 3.11.10 and 3.12.6; current supported 3.13/3.14 releases also
provide it. Prefer the latest security patch, not these historical minimums.
`>=3.11.10` alone is insufficient because it still admits 3.12.0-3.12.5.
The package and refreshed lock exclude that separate gap without upgrading any
locked dependency versions.

## Behavior

Importing either `masterbrain` or `email_brain` loads one dependency-free guard
before any CLI/API capability. The guard checks Python's documented
`supports_strict_parsing` marker and a known-valid strict call. A missing marker,
unsupported keyword or broken positive probe raises an actionable `RuntimeError`.
The automatic check is performed once per process through module import caching.

`classify` retains `strict=True`, recognizes the standard-library empty-address
failure result and catches per-message `ValueError`. Unexpected `TypeError` is
not transformed into success with empty effects. There is no permissive fallback,
replacement parser, sender-authentication claim or provider/mailbox effect.

## Operator recovery and tests

Stop the misconfigured process, upgrade to a currently patched supported Python,
recreate its virtual environment and run `uv sync --locked --extra dev`. Re-run
`uv run pytest -q tests/test_strict_runtime.py tests/test_rule_control.py` against
a disposable PostgreSQL test database before trying the alpha again.

The dedicated CI matrix covers both patched floors and current 3.11-3.14, with
real PostgreSQL rule simulations. Separate source-import jobs exercise actual
3.11.9 and 3.12.4 startup refusal without installing an unsupported package.
Assertions include exact positive effects/version IDs, strict empty-tuple
rejections, no downgrade path and both package startup boundaries. A green
focused matrix does not replace full CI, container checks or populated restore.

No data migration, source permission, hosted deployment or FileOS cutover is
part of this change. See [ADR-102](adr/102_strict_sender_runtime.md) and the
[alpha guide](ALPHA_TESTING.md). Rollback must never enable permissive parsing;
keep unsupported deployments stopped.
