# ADR-166: Explicit synthetic-trial workspace credential handoff

Status: accepted for the fictional local trial only.

## Context

The disposable `/trial` page receives a short-lived, read-only bearer code in
its initial URL fragment and immediately removes the fragment. The separate
`/brain` workspace deliberately accepts a code only in its access field. The
trial guide previously said to copy the code from the launcher terminal, but
the launcher does not print secrets. That made the documented cross-source Ask
walkthrough unavailable after the initial fragment disappeared.

## Decision

The trial page provides an explicit **Show temporary access code** control and
an ordinary link to `/brain`. A valid code remains in the trial page's memory;
its text is inserted into the page only after a user click and is cleared from
the page when hidden. The code is not printed, copied to the clipboard
automatically, placed in the `/brain` URL, stored in browser storage, sent to a
new endpoint, or treated as a broader grant. A missing or malformed code keeps
the reveal control disabled. The user manually transfers the displayed code to
the separate workspace's existing access field.

This is a convenience for fictional, loopback-only data. It is not a hosted
identity or assistant enrollment pattern, and it does not enable real mail,
file roots, model calls or source effects. Anyone who can see the revealed
code can use its existing read scopes until it expires or the trial stops;
hide it when finished.

## Verification and rollback

Browser tests require no code text before the click, explicit reveal/hide,
missing-code refusal and immediate removal of the initial URL fragment. The
real PostgreSQL-backed launcher self-test and existing Brain API authorization
tests remain required. Rollback removes only the trial-page handoff section and
handler; no database, credential issuance or production route changes.
