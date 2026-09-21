"use strict";
// Separate document channel over the existing API. No browser storage or polling.
const documentPolicy = "synthetic-unscanned-pdf-v1";
const pdfPattern = /^sandbox-pdf-v1-[a-f0-9]{64}$/;
const hashPattern = /^[a-f0-9]{64}$/;
const partPattern = /^1(?:\.[1-9][0-9]{0,3}){0,20}$/;
const pdfOutcomes = {bounded_pdf_v1: "extracted", pages_without_text: "partial",
  no_text: "deferred", encrypted: "deferred", unsupported_features: "deferred",
  pdf_byte_limit: "deferred", page_limit: "deferred", stream_limit: "deferred",
  text_limit: "deferred", invalid_pdf: "failed"};
const documentJobOutcomes = {...jobOutcomes, completed: ["result_saved"]};
const documentJobFields = ["id", "account_id", "receipt_id", "processor_version", "policy_version",
  "status", "attempts", "created_at", "expires_at", "retry_at", "completed_at", "extraction_id", "outcome", "mailbox_effects"];
let documentVersion = 0, documentCardVersion = 0, selectionVersion = 0, searchVersion = 0;
let documentAccount = null, documentCaps = null, documentAfter = null, documentRows = [], documentSelection = null;
const documentCards = new Map(), documentIntents = new Map();
function validPdf(value) { return typeof value === "string" && pdfPattern.test(value); }
function validHash(value) { return typeof value === "string" && hashPattern.test(value); }
function boundedText(value, limit) {
  return typeof value === "string" && value.length <= limit * 2 && [...value].length <= limit
    && !/[\u0000\uD800-\uDFFF]/u.test(value);
}
function invalidDocument() { throw new Error("Invalid document response"); }
function invalidateDocumentApprovals() {
  for (const intent of documentIntents.values()) if (intent.pending) {
    intent.pending = false; intent.uncertain = true; intent.serial += 1;
  }
}
function clearDocumentSelection() {
  invalidateDocumentApprovals(); selectionVersion += 1; documentSelection = null;
  byId("document-selection").replaceChildren();
}
function resetDocuments(clear = false) {
  documentVersion += 1; selectionVersion += 1; documentCards.clear(); invalidateDocumentApprovals();
  documentCaps = null; documentAfter = null; documentRows = [];
  if (clear) { documentAccount = null; documentSelection = null; documentIntents.clear(); }
  for (const id of ["documents-health", "document-selection", "document-jobs"]) byId(id).replaceChildren();
  byId("documents-more").hidden = true; byId("documents-more").disabled = false;
}
function documentContext(account = documentAccount) {
  return {account, session: sessionVersion, token: byId("token").value, view: documentVersion};
}
function currentDocument(context) {
  return context.session === sessionVersion && context.token === byId("token").value
    && context.view === documentVersion && sameId(context.account, byId("account-id").value.trim());
}
function validateDocumentCaps(data) {
  if (!closed(data, ["enabled", "processor_version", "policy_version", "scanner_status", "worker_online", "mailbox_effects"])
      || typeof data.enabled !== "boolean" || (data.processor_version !== null && !validPdf(data.processor_version))
      || (data.enabled && data.processor_version === null) || data.policy_version !== documentPolicy
      || data.scanner_status !== "unscanned" || data.worker_online !== null || data.mailbox_effects !== false) invalidDocument();
}
function validateDocumentJob(job, account, expected = null) {
  if (!closed(job, documentJobFields) || !validUuid(job.id) || !sameId(job.account_id, account)
      || !validUuid(job.receipt_id) || !validPdf(job.processor_version) || job.policy_version !== documentPolicy
      || job.mailbox_effects !== false || !Object.hasOwn(documentJobOutcomes, job.status)
      || !documentJobOutcomes[job.status].includes(job.outcome) || !Number.isInteger(job.attempts)
      || job.attempts < 0 || job.attempts > 3 || (job.status === "queued" && job.attempts !== 0)
      || (["running", "retry_wait", "completed"].includes(job.status) && job.attempts < 1)
      || (job.status === "retry_wait" && job.attempts > 2)
      || !validDate(job.created_at) || !validDate(job.expires_at)
      || Date.parse(job.expires_at) - Date.parse(job.created_at) !== 3600000
      || (job.status === "retry_wait" ? !validDate(job.retry_at) : job.retry_at !== null)
      || (terminalJob(job) ? !validDate(job.completed_at) : job.completed_at !== null)
      || (job.status === "completed" ? !validUuid(job.extraction_id) : job.extraction_id !== null)) invalidDocument();
  if (expected && (!sameId(job.id, expected.id) || !sameId(job.receipt_id, expected.receipt_id)
      || job.processor_version !== expected.processor_version || job.policy_version !== expected.policy_version
      || job.created_at !== expected.created_at || job.expires_at !== expected.expires_at || job.attempts < expected.attempts
      || (terminalJob(expected) && (job.status !== expected.status || job.outcome !== expected.outcome
          || job.extraction_id !== expected.extraction_id || job.completed_at !== expected.completed_at)))) invalidDocument();
}
function validateDocumentPage(page, account, after) {
  if (!closed(page, ["results", "next_after", "limit", "mailbox_effects"]) || page.limit !== 50
      || page.mailbox_effects !== false || !Array.isArray(page.results) || page.results.length > 50
      || (page.next_after !== null && (!validUuid(page.next_after) || !page.results.length || sameId(page.next_after, after)))) invalidDocument();
  const ids = new Set();
  for (const job of page.results) {
    validateDocumentJob(job, account);
    if (ids.has(job.id.toLowerCase())) invalidDocument();
    ids.add(job.id.toLowerCase());
  }
  if (page.next_after !== null && !sameId(page.next_after, page.results[page.results.length - 1].id)) invalidDocument();
}
function validateDocumentEvidence(data, expected) {
  const fields = ["id", "account_id", "receipt_id", "processor_version", "policy_version", "revision", "created_at",
    "status", "reason", "scanner_status", "evidence_id", "safe_filename", "pages", "page_count", "source", "untrusted_content", "citation"];
  if (!closed(data, fields) || !sameId(data.id, expected.document_id) || !sameId(data.account_id, expected.account_id)
      || !sameId(data.receipt_id, expected.receipt_id) || !validUuid(data.evidence_id)
      || (expected.evidence_id && !sameId(data.evidence_id, expected.evidence_id))
      || !validPdf(data.processor_version) || data.processor_version !== expected.processor_version
      || data.policy_version !== documentPolicy || !Number.isInteger(data.revision) || data.revision < 1
      || (expected.revision !== undefined && data.revision !== expected.revision)
      || !validDate(data.created_at) || !boundedText(data.safe_filename, 120)
      || !Object.hasOwn(pdfOutcomes, data.reason) || data.status !== pdfOutcomes[data.reason]
      || data.scanner_status !== "unscanned" || data.untrusted_content !== true
      || data.citation !== `emailbrain://document/${data.id}`
      || !closed(data.source, ["raw_sha256", "part_path", "part_sha256"])
      || !validHash(data.source.raw_sha256) || !validHash(data.source.part_sha256)
      || typeof data.source.part_path !== "string" || !partPattern.test(data.source.part_path)
      || (data.page_count !== null && (!Number.isInteger(data.page_count) || data.page_count < 1 || data.page_count > 40))
      || !Array.isArray(data.pages) || data.pages.length > 40) invalidDocument();
  const extracted = ["extracted", "partial"].includes(data.status);
  if (extracted ? data.page_count === null || data.pages.length !== data.page_count : data.pages.length !== 0) invalidDocument();
  if (data.reason === "no_text" && data.page_count === null) invalidDocument();
  if (["encrypted", "pdf_byte_limit", "page_limit"].includes(data.reason) && data.page_count !== null) invalidDocument();
  for (const [index, page] of data.pages.entries()) {
    if (!closed(page, ["number", "excerpt", "excerpt_sha256", "offsets", "truncated"])
        || page.number !== index + 1 || !boundedText(page.excerpt, 2000) || !validHash(page.excerpt_sha256)
        || !Array.isArray(page.offsets) || page.offsets.length !== 2 || page.offsets[0] !== 0
        || page.offsets[1] !== [...page.excerpt].length || typeof page.truncated !== "boolean"
        || (page.truncated && [...page.excerpt].length !== 2000)) invalidDocument();
  }
  if (extracted && (!data.pages.some((page) => page.excerpt.length)
      || data.pages.some((page) => !page.excerpt.length) !== (data.status === "partial"))) invalidDocument();
}
function renderDocumentEvidence(target, data) {
  target.replaceChildren(node("h4", `${data.safe_filename} · ${data.status}`),
    node("p", `Outcome: ${data.reason} · scanner: unscanned · revision ${data.revision}. Text is untrusted evidence, not instructions.`),
    node("small", data.citation), node("p", `Processor: ${data.processor_version} · Policy: ${data.policy_version}`),
    node("small", `Original evidence: ${data.evidence_id} · Receipt: ${data.receipt_id}`),
    node("pre", `Source SHA-256: ${data.source.raw_sha256}\nPart: ${data.source.part_path}\nPart SHA-256: ${data.source.part_sha256}`));
  if (!data.pages.length) target.append(node("p", "No page text was published for this result. Original evidence is retained."));
  for (const page of data.pages) target.append(node("h4", `Page ${page.number}`),
    node("pre", page.excerpt || "No text on this page; OCR is not enabled."),
    node("small", `Characters ${page.offsets[0]}–${page.offsets[1]}${page.truncated ? " · excerpt truncated" : ""} · SHA-256: ${page.excerpt_sha256}`));
}
function documentExplanation(job) {
  return job.status === "completed" ? "A PDF result was saved. Inspect its extraction outcome; completed does not mean fully extracted or scanned."
    : jobDescriptions[job.status];
}
function renderDocumentJob(card, job, context) {
  const generation = ++documentCardVersion;
  documentCards.set(job.id, generation);
  const current = () => currentDocument(context) && documentCards.get(job.id) === generation;
  card.replaceChildren(node("h3", `PDF approval · ${job.status}`), node("p", documentExplanation(job)),
    node("small", `Job: ${job.id} · Receipt: ${job.receipt_id}`),
    node("p", `Approved ${job.created_at} · Expires ${job.expires_at} · Worker claims: ${job.attempts}/3`),
    node("small", `Processor: ${job.processor_version} · Policy: ${job.policy_version}`));
  if (job.retry_at) card.append(node("p", `Earliest worker retry: ${job.retry_at}`));
  const refreshButton = node("button", "Refresh PDF job status");
  const cancel = terminalJob(job) ? null : node("button", "Cancel PDF approval");
  let pending = false;
  async function update(method) {
    if (pending || !current()) return;
    pending = true; refreshButton.disabled = true; if (cancel) cancel.disabled = true;
    try {
      const next = await api(`/v1/accounts/${context.account}/documents/jobs/${job.id}${method === "POST" ? "/cancel" : ""}`, method);
      if (!current()) return;
      validateDocumentJob(next, context.account, job);
      if (method === "POST" && !terminalJob(next)) invalidDocument();
      documentRows = documentRows.map((row) => sameId(row.id, job.id) ? next : row);
      renderDocumentJob(card, next, context); status(`${documentExplanation(next)} Mailbox unchanged.`);
    } catch (_) {
      if (current()) status(method === "POST" ? "PDF cancellation could not be confirmed. Refresh job status; no automatic retry was sent."
        : "PDF job status could not be verified. Check access and refresh history.");
    } finally { pending = false; if (current()) { refreshButton.disabled = false; if (cancel) cancel.disabled = false; } }
  }
  refreshButton.onclick = () => update("GET"); card.append(refreshButton);
  if (cancel) { cancel.onclick = () => update("POST"); card.append(cancel); }
  if (job.extraction_id) {
    const inspect = node("button", "Inspect PDF result"), result = node("div", "");
    inspect.onclick = async () => {
      if (inspect.disabled || !current()) return;
      inspect.disabled = true;
      try {
        const data = await api(`/v1/documents/${job.extraction_id}`);
        if (!current()) return;
        validateDocumentEvidence(data, {document_id: job.extraction_id, account_id: context.account,
          receipt_id: job.receipt_id, processor_version: job.processor_version});
        renderDocumentEvidence(result, data);
      } catch (_) { if (current()) { inspect.disabled = false; status("PDF evidence could not be verified. Refresh history and check access."); } }
    };
    card.append(inspect, result);
  }
}
function renderDocumentJobs(context) {
  documentCards.clear(); byId("document-jobs").replaceChildren();
  if (!documentRows.length) byId("document-jobs").append(node("p", "No PDF approvals on this page."));
  for (const job of documentRows) {
    const card = node("article", ""); renderDocumentJob(card, job, context); byId("document-jobs").append(card);
  }
  const after = documentAfter;
  byId("documents-more").hidden = after === null; byId("documents-more").disabled = false;
  byId("documents-more").onclick = () => {
    if (!byId("documents-more").disabled && currentDocument(context) && after === documentAfter) return loadDocumentPage(after);
  };
}
async function loadDocuments() {
  const account = byId("account-id").value.trim();
  if (!validUuid(account)) { status("Enter a valid account ID or select a PDF from message evidence."); return; }
  resetDocuments(documentAccount !== null && !sameId(documentAccount, account));
  documentAccount = account;
  const context = documentContext(account);
  byId("documents-health").replaceChildren(node("p", "Loading PDF configuration and saved approvals…"));
  try {
    const caps = await api(`/v1/accounts/${account}/documents`);
    if (!currentDocument(context)) return;
    validateDocumentCaps(caps);
    const page = await api(`/v1/accounts/${account}/documents/jobs?limit=50`);
    if (!currentDocument(context)) return;
    validateDocumentPage(page, account, null);
    documentCaps = caps; documentRows = page.results; documentAfter = page.next_after;
    byId("documents-health").replaceChildren(
      node("p", caps.enabled ? "Synthetic PDF approval is configured. Worker availability is unknown." : "New PDF approvals are disabled. Saved history remains available."),
      node("small", `Processor: ${caps.processor_version || "none"} · Policy: ${caps.policy_version} · scanner: unscanned`));
    renderDocumentJobs(context); renderDocumentSelection();
    status("PDF history refreshed. No processing was approved or started by this refresh.");
  } catch (_) {
    if (currentDocument(context)) {
      documentCaps = null; documentRows = []; documentAfter = null;
      byId("documents-health").replaceChildren(node("p", "PDF information could not be verified. Check access and refresh before approving."));
      renderDocumentJobs(context); renderDocumentSelection();
      status("PDF information unavailable. No automatic retry was sent.");
    }
  }
}
async function loadDocumentPage(after) {
  if (!documentCaps || !validUuid(after) || !sameId(documentAccount, byId("account-id").value.trim())) return;
  documentVersion += 1; documentCards.clear(); invalidateDocumentApprovals();
  const context = documentContext();
  byId("document-jobs").replaceChildren(node("p", "Loading the next PDF history page…"));
  byId("documents-more").disabled = true; renderDocumentSelection();
  try {
    const page = await api(`/v1/accounts/${context.account}/documents/jobs?limit=50&after=${after}`);
    if (!currentDocument(context)) return;
    validateDocumentPage(page, context.account, after);
    documentRows = page.results; documentAfter = page.next_after; renderDocumentJobs(context);
  } catch (_) {
    if (currentDocument(context)) {
      documentRows = []; documentAfter = null; byId("documents-more").hidden = true;
      byId("document-jobs").replaceChildren(node("p", "PDF history page could not be verified. Refresh from the beginning."));
    }
  } finally { if (currentDocument(context)) byId("documents-more").disabled = false; }
}
function renderDocumentSelection() {
  invalidateDocumentApprovals(); const rendered = ++selectionVersion;
  const target = byId("document-selection"); target.replaceChildren();
  const selected = documentSelection;
  if (!selected || !sameId(selected.account, documentAccount)) return;
  target.append(node("h3", `Selected PDF: ${selected.filename}`),
    node("small", `Account: ${selected.account} · Evidence: ${selected.evidence} · Receipt: ${selected.receipt}`),
    node("pre", `Source SHA-256: ${selected.rawHash}\nPart: ${selected.part}\nPart SHA-256: ${selected.partHash}`),
    node("p", "Approval lasts one hour, survives closing this page, and applies only to this PDF under the displayed processor/policy. Source eligibility is rechecked by the server. This file remains unscanned."));
  if (!documentCaps || !documentCaps.enabled) {
    target.append(node("p", "Approval unavailable. Refresh PDF history to verify configuration and access.")); return;
  }
  const context = documentContext(), processor = documentCaps.processor_version;
  const identity = `${selected.account.toLowerCase()}/${selected.receipt.toLowerCase()}/${processor}/${documentPolicy}`;
  let intent = documentIntents.get(identity);
  if (!intent) { intent = {key: null, pending: false, uncertain: false, job: null, serial: 0}; documentIntents.set(identity, intent); }
  target.append(node("small", `Approve processor: ${processor} · Policy: ${documentPolicy}`));
  const approve = node("button", intent.uncertain ? "Retry same PDF approval request" : "Approve this PDF");
  approve.disabled = intent.pending || intent.job !== null;
  if (intent.job) target.append(node("p", `Approval request recorded as ${intent.job.id}. Refresh PDF history for current state; no new grant is created here.`));
  if (intent.uncertain) target.append(node("p", "The request may already be saved. Refresh history or explicitly repeat the same request key; do not assume it failed."));
  target.append(approve);
  const current = () => currentDocument(context) && rendered === selectionVersion && documentCaps?.processor_version === processor;
  approve.onclick = async () => {
    if (approve.disabled || intent.pending || intent.job || !current()) return;
    intent.pending = true; approve.disabled = true; const serial = ++intent.serial;
    try {
      if (intent.key === null) intent.key = crypto.randomUUID();
      if (!validUuid(intent.key)) invalidDocument();
      const job = await api(`/v1/accounts/${selected.account}/attachments/${selected.receipt}/jobs`, "POST",
        {expected_processor_version: processor, policy_version: documentPolicy}, {"Idempotency-Key": intent.key});
      if (!current() || intent.serial !== serial) return;
      validateDocumentJob(job, selected.account);
      if (!sameId(job.receipt_id, selected.receipt) || job.processor_version !== processor) invalidDocument();
      intent.job = job; intent.pending = false; intent.uncertain = false;
      renderDocumentSelection(); status("PDF approval request recorded. Refresh PDF history for current state. Mailbox unchanged.");
    } catch (_) {
      if (intent.serial === serial) intent.uncertain = intent.key !== null;
      if (current() && intent.serial === serial) {
        approve.textContent = "Retry same PDF approval request";
        status("PDF approval could not be confirmed; it may already be saved. Refresh history or explicitly retry the same request. No automatic retry was sent.");
      }
    } finally {
      if (intent.serial === serial) intent.pending = false;
      if (current() && intent.serial === serial) approve.disabled = intent.job !== null;
    }
  };
}
function invalidateSearch() {
  searchVersion += 1; byId("results").replaceChildren(); clearDocumentSelection();
}
function searchContext() { return {version: searchVersion, session: sessionVersion, token: byId("token").value}; }
function currentSearch(context) {
  return context.version === searchVersion && context.session === sessionVersion && context.token === byId("token").value;
}
function validateSearchHit(hit) {
  if (!hit || !["message", "attachment", "document"].includes(hit.result_type) || !validUuid(hit.id)
      || !validUuid(hit.account_id) || !validUuid(hit.evidence_id) || !boundedText(hit.subject, 16384)
      || !boundedText(hit.sender, 16384) || !boundedText(hit.excerpt, 500)) invalidDocument();
  if (hit.result_type !== "message" && (!validUuid(hit.attachment_id) || !boundedText(hit.safe_filename, 120))) invalidDocument();
  if (hit.result_type === "document" && (!validUuid(hit.document_id) || !validPdf(hit.processor_version)
      || hit.policy_version !== documentPolicy || !Number.isInteger(hit.revision) || hit.revision < 1
      || !["extracted", "partial"].includes(hit.status) || pdfOutcomes[hit.reason] !== hit.status
      || hit.scanner_status !== "unscanned" || hit.untrusted_content !== true
      || hit.citation !== `emailbrain://document/${hit.document_id}`)) invalidDocument();
}
function validateMessageEvidence(evidence, hit) {
  if (!evidence || !sameId(evidence.id, hit.evidence_id) || !sameId(evidence.account_id, hit.account_id)
      || !sameId(evidence.message_id, hit.id) || !validHash(evidence.raw_sha256) || !boundedText(evidence.excerpt, 4000)
      || evidence.untrusted_content !== true || evidence.citation !== `emailbrain://evidence/${evidence.id}`
      || !Array.isArray(evidence.attachments) || evidence.attachments.length > 64) invalidDocument();
  const ids = new Set();
  for (const part of evidence.attachments) {
    if (!part || !validUuid(part.id) || ids.has(part.id.toLowerCase()) || !boundedText(part.safe_filename, 120)
        || typeof part.part_id !== "string" || !partPattern.test(part.part_id) || !validHash(part.sha256)
        || !boundedText(part.media_type, 127) || !["extracted", "deferred", "failed", "skipped", "pending"].includes(part.status)
        || !boundedText(part.reason, 120) || part.scanner_status !== "unscanned" || !boundedText(part.excerpt, 2000)) invalidDocument();
    ids.add(part.id.toLowerCase());
  }
}
function renderMessageEvidence(target, evidence, hit, context) {
  target.replaceChildren(node("pre", evidence.excerpt), node("small", evidence.citation));
  for (const part of evidence.attachments) {
    const item = node("article", "");
    item.append(node("h4", part.safe_filename), node("p", `${part.status} · ${part.reason} · scanner: ${part.scanner_status}`),
      node("pre", part.excerpt || "No extracted text. Original remains in retained MIME evidence."));
    if (part.media_type === "application/pdf" && part.status === "deferred"
        && ["isolated_extractor_required", "extraction_byte_limit"].includes(part.reason)) {
      const select = node("button", "Review this PDF");
      select.onclick = async () => {
        if (!currentSearch(context)) return;
        if (!sameId(byId("account-id").value.trim(), hit.account_id)) {
          byId("account-id").value = hit.account_id; byId("account-id").oninput();
        }
        clearDocumentSelection();
        documentSelection = {account: hit.account_id, evidence: evidence.id, receipt: part.id,
          rawHash: evidence.raw_sha256, part: part.part_id, partHash: part.sha256, filename: part.safe_filename};
        await loadDocuments();
      };
      item.append(select);
    }
    target.append(item);
  }
}
async function loadSearch() {
  invalidateSearch(); const context = searchContext(), include = byId("include-documents").checked === true;
  try {
    const data = await api("/v1/search", "POST", {query: byId("query").value, include_documents: include});
    if (!currentSearch(context)) return;
    if (!closed(data, ["mode", "untrusted_content", "results"]) || data.mode !== "lexical" || data.untrusted_content !== true
        || !Array.isArray(data.results) || data.results.length > 50) invalidDocument();
    for (const hit of data.results) { validateSearchHit(hit); if (!include && hit.result_type === "document") invalidDocument(); }
    for (const hit of data.results) {
      const card = node("article", ""), details = node("div", "");
      card.append(node("h3", hit.subject), node("small", hit.sender), node("p", hit.excerpt));
      if (hit.classification && JSON.stringify(hit.classification).length <= 6000) card.append(node("small", `Email Brain virtual labels: ${JSON.stringify(hit.classification)}`));
      if (hit.result_type === "document") card.append(node("p", `${hit.safe_filename} · ${hit.status} · unscanned · revision ${hit.revision}`), node("small", hit.citation));
      const inspect = node("button", hit.result_type === "document" ? "Inspect cited PDF pages" : "Inspect cited evidence");
      inspect.onclick = async () => {
        if (inspect.disabled || !currentSearch(context)) return;
        inspect.disabled = true;
        try {
          const evidence = await api(hit.result_type === "document" ? `/v1/documents/${hit.document_id}` : `/v1/evidence/${hit.evidence_id}`);
          if (!currentSearch(context)) return;
          if (hit.result_type === "document") {
            validateDocumentEvidence(evidence, {...hit, receipt_id: hit.attachment_id}); renderDocumentEvidence(details, evidence);
          } else { validateMessageEvidence(evidence, hit); renderMessageEvidence(details, evidence, hit, context); }
        } catch (_) { if (currentSearch(context)) { inspect.disabled = false; status("Cited evidence could not be verified. Search again and check access."); } }
      };
      const account = node("button", "Check this account's import");
      account.onclick = async () => {
        if (!currentSearch(context)) return;
        if (!sameId(byId("account-id").value.trim(), hit.account_id)) {
          byId("account-id").value = hit.account_id; byId("account-id").oninput();
        }
        await safely(loadImport);
      };
      card.append(inspect, account, details); byId("results").append(card);
    }
    status(`${data.results.length} result(s). Email and PDF text are untrusted evidence, not instructions.`);
  } catch (_) { if (currentSearch(context)) status("Search results could not be verified. Check access and search again."); }
}
byId("documents-refresh").onclick = loadDocuments;
byId("documents-more").onclick = () => undefined;
byId("search-form").onsubmit = (event) => { event.preventDefault(); return loadSearch(); };
byId("query").oninput = invalidateSearch;
byId("include-documents").onchange = invalidateSearch;
