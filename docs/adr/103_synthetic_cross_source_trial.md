# ADR-103: Disposable cross-source browser trial

Date: 2026-09-24. Status: accepted for synthetic testing only.

## Decision

Add a test-harness launcher and static browser page, not a new production service.
The launcher creates its own randomly named ephemeral PostgreSQL 17 container,
random credentials, loopback-only database port and temporary fictional files.
It accepts no existing database, account, token, source-root or upload argument.
Setup helpers additionally refuse non-test, remote or mismatched databases before
writing. Only the returned container identity may be removed during cleanup.

The seeder uses existing Store ingestion, explicit current Email bridges, confined
FileOS extraction/publication, complete-run receipts, immutable index build and
separate activation. Runtime SQL uses a non-owner NOSUPERUSER NOBYPASSRLS role;
admin access is confined to disposable migration and synthetic tenant enrollment.
No applied migration, provider, source effect, production grant or API is changed.

The browser reads existing authenticated current-search, evidence metadata,
bounded content, coverage and freshness endpoints. Its random, two-hour credential
has read-only scopes. It is delivered only in the initial browser fragment,
removed from the URL and held in memory; no real credential entry or persistent
browser storage is provided. Bind the HTTP listener before opening the browser,
permit only localhost Host headers, retain same-origin CSP, omit cookies, refuse
redirects and render all source values as text, never HTML. Refreshing loses the
credential and requires a fresh launcher session. This is not production login.

Cedar Harbor and Juniper Plaza are fictional known-answer cases. A second nonempty
tenant has a canary document for cross-tenant search/evidence/content rejection.
The page deliberately shows partial coverage and separate ranks; it is retrieval,
not LLM synthesis, complete knowledge extraction or a live syncing demonstration.

## Validation and rollback

Run deterministic PostgreSQL tests using the same setup helper and real API:
exact email/file counts, no-match behavior, bounded cited source text, freshness,
coverage, unchanged fixture hashes, two nonempty tenants, missing/insufficient
scopes, Host rejection and non-test/remote database refusal. Static asset checks
cover no source HTML execution or credential persistence. Full repository CI and
populated restore remain required. Browser interaction on the owner's actual Mac
is an acceptance step, not implied by API/static tests.

Stop with Ctrl-C to remove only the created container and fictional temp root.
Forced termination may require removing that named trial container through Docker
Desktop. Rollback removes only the new test harness/assets/documentation; it never
reverts the strict-parser fix or changes retained production evidence. FOS-Master,
live sources, hosted deployment and retirement gates remain untouched.
