# FileOS Read-Only Extraction

The first working FileOS adapter path is:

`snapshot → transactional import → re-hash source bytes → extract → normalize → chunk → index → search`

The in-process extractor supports plain text, Markdown, HTML and CSV. The adapter reads each file at most
once per attempt, caps input at 1 MiB, refuses symlinks and path escapes, compares
size/mtime before and after the read, and verifies the immutable snapshot SHA-256.
Only then can text enter DataCore. Files remain untouched.

Every observed item is accounted as `extracted`, `empty`, `unsupported`, `deferred`,
`changed` or `failed`. A sibling failure does not roll back valid published siblings.
An extracted result is still untrusted source content; indexing does not make it an
instruction or grant it authority.

The encoding and HTML/CSV semantics are adapted from FOS-Master `doc_extract.py` at
the pinned donor commit. The live parity harness exercises UTF-8/CRLF, UTF-16 BOM,
Latin-1 uncertainty, HTML structural/table text and quoted CSV newlines against that
checkout. MasterBrain intentionally adds strict byte limits, source-root confinement,
source-version hashing and explicit outcome states around the donor behavior.

PDF, DOCX and XLSX now have a separate, opt-in isolated-worker tranche described in
[FileOS document extraction](FILEOS_DOCUMENT_EXTRACTION.md). They remain deferred when
that processor is not configured; legacy XLS, general archives, images and OCR remain
deferred in all cases. FOS-Master stays operational and unchanged while these adapters
run in shadow mode.
