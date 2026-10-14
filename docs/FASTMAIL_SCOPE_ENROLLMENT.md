# Private scoped Fastmail source enrollment

ADR-179 implements a local, administrator-assisted **synthetic/disposable**
enrollment and disconnect workflow. It is not permission to connect a real
Fastmail account. No command here contacts the provider, discovers a token,
changes mail, grants a hosted service identity or makes the account-wide
version-1 worker safe for a folder/date pilot.

## Authority and files

`email-brain fastmail-source` reads a private owner-only JSON file, a separate
version-2 [`sync-read` configuration](READ_CONTROLLER.md), a human owner
credential/token and the read worker's credential/token. The human credential
needs `email.source.manage`; the worker needs **exactly** `email.ingest`.
Both must name the same tenant as the enrollment file, and the human actor
must still have an `owner` database membership. Management scope is never
valid for assistants or workers. This bootstrap credential is not a hosted
issuer, and possession of the administrator DSN alone is outside this workflow.

Keep every file outside Git and Dropbox in an owner-only directory (`0700`),
with files `0600`. Paths are absolute and symlinks are refused. Supply the
administrator DSN only in `EMAIL_BRAIN_ADMIN_DSN`; do not put it in JSON,
the read-worker environment or an LLM prompt. The operator does **not** read
the provider token file or make an HTTP request. The later `sync-read --check`
must separately verify that file and all runtime bindings.

Fictional configuration shape:

```json
{
  "version": 1,
  "expected_tenant_id": "00000000-0000-4000-8000-000000000001",
  "expected_owner_actor_id": "00000000-0000-4000-8000-000000000002",
  "address": "owner@example.invalid",
  "read_config_file": "/private/operator-state/read.json",
  "owner_credentials_file": "/private/operator-state/owner-credentials.json",
  "owner_token_file": "/private/operator-state/owner-token"
}
```

## Check, enroll and disconnect

Inspect both private configurations and the exact mailbox ID and UTC date
window yourself. `--check` is a read-only SQL transaction and returns only an
account UUID, account state, canonical filter SHA-256 and full binding
SHA-256—not a provider login:

```sh
email-brain fastmail-source --config /private/operator-state/source.json --check
```

For a **new**, previously absent account, compare the returned account UUID
and both digests with the inspected private files. The binding digest includes
tenant, owner actor, address, account, provider account ID, secret reference
and scope; a change to any of them after `--check` invalidates approval.
`--enroll` requires all three values as separate explicit confirmations:

```sh
email-brain fastmail-source --config /private/operator-state/source.json \
  --enroll --confirm-account 00000000-0000-4000-8000-000000000003 \
  --confirm-scope 0000000000000000000000000000000000000000000000000000000000000000 \
  --confirm-binding 0000000000000000000000000000000000000000000000000000000000000000
```

The all-zero digest above is illustrative and will be rejected unless it is
the exact filter fingerprint. Enrollment inserts one new active Fastmail row
with its scope pin and a content-free audit record in a single transaction.
It refuses an existing account or duplicate address; it never converts an
unscoped account, writes a provider token to SQL, creates a lease or starts a
worker. Run the separate `sync-read --check` afterward; even that makes no
provider request. A real provider read needs separate owner authorization and
the disposable live-pilot acceptance plan.

`--disconnect` takes the same three confirmations. It serializes with worker
publication, marks that exact account disconnected and preserves its pin,
cursor, raw evidence and history. An exact repeat is a no-op. It does not
purge or hide previously retained evidence, revoke the Fastmail token or
guarantee that an already-started HTTP request never completes. Subsequent
guarded requests and page publication fail; revoke the token at Fastmail for
an immediate provider-side cutoff. Reactivation or repinning needs a separate
reviewed workflow; do not edit the database directly to bypass this boundary.

The tests use fictional credentials, HTTPS responses and disposable
PostgreSQL. They prove local behavior, not hosted identity, real provider
semantics, retention policy or operational acceptance.
