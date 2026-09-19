# Security Policy

This repository handles designs for highly sensitive email data. Do not open a public issue containing a vulnerability, credential, message content, tenant identifier, or production log.

Until a private reporting channel is configured, report suspected security issues directly to the repository owner through an already-established private channel. Include only the minimum reproduction details and synthetic data.

The binding threat model and controls are in [`docs/SECURITY.md`](docs/SECURITY.md). Production deployment is not approved until restore, tenant-isolation, prompt-injection, provider-scope, and mailbox-action controls have passed the gates in [`docs/TESTING_AND_EVALS.md`](docs/TESTING_AND_EVALS.md).
