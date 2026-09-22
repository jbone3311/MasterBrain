# FileOS PDF and Office extraction

This is the first isolated document tranche for shared DataCore. It accepts only
source-bound `.pdf`, `.docx` and `.xlsx` files whose media type, size and SHA-256 match
the FileOS snapshot. Source files are opened read-only and are never moved, renamed,
rewritten or deleted.

## Components

- `document_contract.py` defines the closed request/result envelope and all bounds.
- `document_processor.py` is the privileged parent that invokes only an inspected
  immutable image ID.
- `document_worker.py` runs inside the locked-down image and owns optional readers.
- `Dockerfile.documents` builds that image independently from the API runtime.
- `FileOSAdapter` revalidates each source, isolates sibling failures and publishes
  only complete extracted text through `DataCoreStore`.

## Bounds and outcomes

| Constraint | Bound |
|---|---:|
| Source bytes | 8 MiB |
| Returned normalized text | 200,000 characters |
| PDF pages | 40 |
| DOCX paragraphs / tables | 2,000 / 100 |
| XLSX sheets / rows per sheet / columns | 20 / 2,000 / 100 |
| OOXML members / expanded bytes / compression ratio | 500 / 64 MiB / 200:1 |

`extracted` content is complete within the contract and may be published. `deferred`
means a known policy boundary such as encryption, active/external features, no text or
a size/structure cap. `changed` means the source no longer matches its snapshot.
`failed` means invalid input, unavailable source or unavailable isolated processor.
No outcome grants authority to alter the source.

## Security boundary

The worker has no network, mounts, Docker socket, inherited credentials, logs,
capabilities or writable root. The parent verifies Docker's isolation state before
sending content, caps both pipes, verifies child exit/OOM state and removes only the
exact container it created. Unexpected diagnostics are suppressed so filenames,
content and host paths do not reach logs.

OOXML active/external relationships, macros, DTD/entities, duplicate/escaping members,
symlinks, encrypted members and archive expansion are refused before library parsing.
PDF actions, forms, annotations, attached files and encryption are refused. Outputs
remain `scanner_status: unscanned`; extraction is not a malware-safety verdict.

## Current limits

No legacy `.doc`/`.xls`, XLSM, archives, images, OCR, PDF tables, password recovery,
formula calculation or embedded-object recursion. XLSX uses cached values only. Image-
only PDFs are deferred for the later opt-in OCR worker. There is no public upload or
source-write endpoint.

## Verification

Run the offline contracts and pinned donor comparison:

```sh
uv run pytest -q tests/test_datacore_documents.py tests/test_document_processor.py
uv run python scripts/datacore_parity.py --fos-repo ../FOS-Master --stress-files 3000
```

The actual container suite is intentionally separate and requires the prebuilt image:

```sh
docker build -f Dockerfile.documents -t masterbrain-documents-ci .
MASTERBRAIN_DOCUMENT_IMAGE_ID="$(docker image inspect masterbrain-documents-ci --format '{{.Id}}')" \
  uv run pytest -q tests/container_document_checks.py
```

CI is the authoritative container gate when the local host has no Docker executable.
The first full gate passed at revision `a6488c6`: **2,379 Python tests**, five real
document-container cases and a populated PostgreSQL restore.
