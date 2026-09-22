# Security Policy

This repository handles highly sensitive email and file data. Do not open a public
issue containing a vulnerability, credential, message/file content, tenant identifier,
path, provenance record, or production log.

Until a private reporting channel is configured, report suspected security issues directly to the repository owner through an already-established private channel. Include only the minimum reproduction details and synthetic data.

The binding threat model and controls are in [`docs/SECURITY.md`](docs/SECURITY.md).
Production deployment is not approved until the gates in
[`docs/RELEASE_ACCEPTANCE.md`](docs/RELEASE_ACCEPTANCE.md) pass.
