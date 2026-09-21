# Try the email reader

There are two distinct tests. Neither requires sharing your actual email here.
The [build receipt](BUILD_RECEIPT.md) records automated results separately.

## Quick fictional browser test — no database setup

From the checkout, after installing the locked development environment:

```sh
uv run python tests/reader_preview.py --synthetic-preview
```

Open the printed loopback URL on this computer. The page says **Fictional reader
test** and pre-fills a public, test-only token and the search word `Readerproof`.
It generates four messages in memory, not from your accounts. This preview uses
the actual reader display/decoding/download code but substitutes fixture storage;
it is **not PostgreSQL, tenant-isolation, browser-login or live-provider acceptance**.
Other product controls on this preview are not connected. Stop it with Ctrl-C.

1. Click **Search**. Four fictional results should appear.
2. Open **long conversation** with **Read email**. The bottom contains `FINALTAIL`
   and an emoji, beyond the old 100,000-character projection cutoff. Close it.
3. Open **HTML-only safety**. Read the text; no tracking image or HTML script appears.
4. Open **project documents**. Expect PDF, Excel, Word and CSV receipt entries.
5. Downloads must remain disabled until you check the unscanned-files acknowledgement.
   Try **Download original email (.eml)** and one **Download attachment (.bin)**.
   Then click **Save verified file**. The browser may prompt for a save location.
   These generated files are fictional;
   future real attachments remain untrusted. Saving is not document extraction.
6. Open **large original boundary**. Expect an explicit truncated projection warning,
   not a claim of full on-screen reading. The original download retains the rest.
7. Click **Clear session**. Message text, results and token should disappear.
   Searching without restoring the test token must not return mail.

Tell us which message/button failed, the generic status text and browser—not actual
email bodies, credentials or downloaded private files. Useful feedback: readability,
how easy it is to find a message, download clarity, and whether limits are obvious.

The in-app browser smoke verified preparation and the **Save verified file** link,
not a completed filesystem save. Please confirm that files actually appear in your
downloads during this trial; use your regular browser if the in-app browser blocks
the save. A save-request status is not proof that the browser saved the file.

## Database-backed synthetic product test

Follow [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) to provision a **disposable**
PostgreSQL instance, non-owner runtime role and generated demo owner credentials.
Use `seed-corpus` or the [known-answer mailbox](TEST_MAILBOX_PLAN.md), then `serve`.
Search `Melron` or the documented fixture markers, click **Read email**, and repeat
the normal reading/download/session-clearing checks. This exercises the real
ingestion, database, API and UI. Keep all database files and credentials outside Git
and Dropbox; never point the integration suite at a real database.

The current machine does not include PostgreSQL/Docker. CI runs the disposable
database/container/restore checks. The quick preview above remains usable without
installing them; do not mistake it for a locally database-backed deployment.

## Still not ready for live use

Real mailbox enrollment/acceptance, complete browser sign-in, managed hosting,
cloud object/KMS backup recovery, malware scanning, large-message full on-screen
rendering, team sharing and assistant integrations remain separate release gates.
No SMTP, sending, moving or deletion is enabled by this reader.
