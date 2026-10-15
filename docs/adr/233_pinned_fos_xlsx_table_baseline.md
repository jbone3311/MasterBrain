# ADR-233 — Pinned FOS-Master XLSX table baseline and explicit gaps

Status: fictional, nonpublishing comparison on an open PR.

## Decision

Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15` and
`_SYSTEM/tools/doc_extract.py` SHA-256
`746932e5ce033a9b8f8bd7155a88dfbb6d1c57a9916aea2230e6afbe1a3ab269`.
The optional local replay loads only that verified donor `extract_xlsx` function
from its AST and compares authored fictional workbooks with the existing
DataCore XLSX worker. It never runs donor configuration, scanning, database or
file effects. A portable DataCore plain-workbook golden remains active even
when the separate donor checkout is unavailable in hosted CI.

The ordinary overlap is source cell values: both paths see all authored values
in a bounded workbook. At this baseline, result shapes were **not** parity-
equivalent: FOS returned per-sheet `headers`/`rows` tables and space-separated
text while DataCore returned tab-separated text. ADR-234 later adds a separate,
nonpublishing addressable row/cell projection and tests its ordinary values
against the same pinned donor. Neither path yet provides a reviewed cell
citation in Brain API. FOS reads cached formula values and can
silently represent an uncached formula as an empty cell; DataCore defers the
entire workbook without text. FOS returns a truncated partial table with an
explicit flag when its configured row limit is reached; DataCore either reads
its own bounded workbook completely or defers on a structural limit. FOS
accepts `.xlsm` by extension; DataCore's closed source contract refuses it.
FOS recognizes OLE2-wrapped encrypted workbooks distinctly; DataCore refuses
them as invalid documents without claiming extracted text. These are recorded
policy/feature differences, not discrepancies to normalize away in tests.

## Acceptance and next gate

The fictional corpus covers ordinary rows, 1,000-row tail retention, an
uncached formula, row truncation, encrypted/mislabeled bytes and `.xlsm`.
The FOS-Master donor stays unchanged. This comparison does not prove all
workbook features, authentic statement values, sheet/cell provenance, Email
attachment publication or FileOS replacement parity.

Before an Email XLSX can get a reviewed source-tier receipt, build a separate
approved XLSX extraction and occurrence-specific Email document bridge (the
existing PDF approval and bridge are PDF-only). Review the table/cell and
formula policy against this baseline, then add a final-currentness-checked,
tenant-fenced digest receipt and private command. No live account or financial
claim is authorized by this ADR.
