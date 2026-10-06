# Pinned FOS-Master scanner test snapshot

These two files are **byte-for-byte, unmodified** copies from private
`jbone3311/FOS-Master` commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`:

| File | SHA-256 |
|---|---|
| `_SYSTEM/tools/scan_domains.py` | `bf4a9bb46275bb3d9ae429335520b333541dfbbddbd0c2ec4ddef2d9873d1073` |
| `_SYSTEM/tools/junk_filter.py` | `12110b1b5404c31172d65878a9327bf8f415f8d343b668aa5982948c840da437` |

They are test fixtures, not MasterBrain runtime code or an adopted scanner
policy. The parity loader verifies both hashes before import and allows this
snapshot only at its fixed checked-in path. Tests patch the domain root to a
fictional temporary tree and use an in-memory SQLite database; they never run
the donor command-line entry point, read a live root or write its registry.
The files are outside the installable `src` package and outside all runtime
Dockerfile copy lists. The original FOS-Master repository and its history
remain unchanged. When a local pinned checkout is available, the test suite
also compares these bytes and scanner outputs directly with it.

Do not edit the copied source to appease lint or a platform test. Investigate
a difference, update the pinned donor reference in a separate review, and
rebuild the golden corpus with explicit provenance.
