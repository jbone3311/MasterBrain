# ADR-204 — Fictional cross-source project-dossier acceptance

Status: accepted for synthetic/disposable test-harness implementation only.
No live source, new production route, model inference, FileOS effect or donor
cutover is authorized.

## Context

The existing loopback trial proves grouped Email/FileOS retrieval, evidence
drill-down, one reviewed cross-source commitment and an unreviewed statement
row. It does not yet exercise the owner's concrete “show me the deal and its
files, facts and timeline” workflow through the same project dossier used by
the first-party workspace and external read client. Individual project/fact/
artifact tests do not prove that composition on one coherent cross-source
fictional case.
The owner selected MasterBrain's current Markdown dossier export as the
example format for any later Librarian import. ADR-200 through 202 define the
current read-only inspection and limited unreviewed staging path; this trial
does not extend that path or imply a lossless round trip.

## Decision

Extend only the trial's fictional seeder to publish a reviewed Cedar Harbor
project, one source-stated loan-term fact, one appraisal event, one exact FileOS
term-sheet artifact link and its existing Email-plus-FileOS commitment. Use
the existing human-reviewed publication APIs with exact current evidence and
no new privileges. The fact is a source statement, not a verified financing
offer or investment; the statement proposal remains unreviewed and unrelated.

Test the actual Brain API and provider-neutral client against that one
project: bounded compact dossier and citation-verified Markdown must agree
on project, event, commitment, fact and file occurrence. A source-scoped
assistant missing one of the project's direct source grants must not receive
the project or its dossier. Retain the existing known-answer Email/FileOS
counts, second-tenant canary, no-source-mutation and browser security checks.
Update the operator walkthrough with the exact new reviewed counts and the
explicit source-stated/untrusted caveat. Do not quietly label the resulting
project as current business truth, a full Librarian round trip, or a working
investment analysis.

## Verification and rollback

Run fictional PostgreSQL/API/client tests, actual local launcher self-test,
full repository and browser gates, static/docs checks, hosted CI/strict runtime
and populated restore. The seeder's temporary database and files retain their
existing per-run cleanup. Rollback removes only this fictional seed and its
acceptance tests/docs; no production data or FOS-Master checkout is changed.
