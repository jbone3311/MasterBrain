"use strict";
const byId = (id) => document.getElementById(id);
const status = (text) => { byId("status").textContent = text; };
let sessionVersion = 0;
let quarantineAfter = null;
let quarantineAccount = null;
let importVersion = 0;
let heldRenderVersion = 0;
let heldPages = [];
let processingVersion = 0;
let processingAccount = null;
let processingCaps = null;
let processingAfter = null;
let processingRows = [];
let processingCardVersion = 0;
const processingCards = new Map();
const approvalIntents = new Map();
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isolatedParserPattern = /^sandbox-mime-v1-[a-f0-9]{64}$/;
function invalidatePendingApprovals() {
  for (const intent of approvalIntents.values()) {
    if (intent.pending) { intent.pending = false; intent.uncertain = true; intent.serial += 1; }
  }
}
function resetProcessing(clearApprovals = false) {
  processingVersion += 1;
  processingAccount = null; processingCaps = null; processingAfter = null; processingRows = [];
  processingCards.clear();
  invalidatePendingApprovals();
  if (clearApprovals) approvalIntents.clear();
  byId("processing-health").replaceChildren(); byId("processing-jobs").replaceChildren();
  byId("processing-more").hidden = true; byId("processing-more").disabled = false;
}
function clearEvidence() {
  sessionVersion += 1;
  importVersion += 1;
  for (const id of ["results", "proposals", "import-health", "quarantine", "rules"]) byId(id).replaceChildren();
  quarantineAfter = null; quarantineAccount = null; byId("quarantine-more").hidden = true;
  heldPages = []; heldRenderVersion += 1; resetProcessing(true);
  resetDocuments(true); invalidateSearch(); byId("include-documents").checked = false;
}
async function api(path, method = "GET", body = undefined, extra = {}) {
  const version = sessionVersion, token = byId("token").value;
  const response = await fetch(path, {method, credentials: "omit", cache: "no-store",
    headers: {"Authorization": `Bearer ${token}`, "Content-Type": "application/json", ...extra},
    body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (version !== sessionVersion || token !== byId("token").value) throw new Error("Session changed. Please retry.");
  if (!response.ok) throw new Error(`Request failed (${response.status}). Check access or refresh the queue.`);
  return data;
}
function node(tag, text) { const element = document.createElement(tag); element.textContent = text; return element; }
async function safely(action) { try { await action(); } catch (error) { status(error.message); } }
byId("connect").onclick = () => safely(async () => { await api("/readyz"); status("Connected · mailbox changes disabled"); });
byId("token").oninput = () => { clearEvidence(); status("Credential changed. Reconnect to load evidence."); };
byId("disconnect").onclick = () => { byId("token").value = ""; clearEvidence();
  for (const id of ["query", "account-id", "project-name", "project-reason", "rule-domain", "rule-category", "rule-reason"]) byId(id).value = "";
  byId("rule-mailbox").value = "review";
  status("Session cleared"); };
async function heldMessages(account, after = null, version = importVersion) {
  const query = after ? `?after=${encodeURIComponent(after)}` : "";
  const data = await api(`/v1/accounts/${encodeURIComponent(account)}/quarantine${query}`);
  if (version !== importVersion || byId("account-id").value.trim() !== account) return;
  if (!after) heldPages = [];
  heldPages.push({data, account});
  quarantineAccount = account; quarantineAfter = data.next_after;
  renderHeldMessages(version);
  byId("quarantine-more").hidden = !data.next_after;
}
function renderHeldMessages(version = importVersion) {
  invalidatePendingApprovals();
  const rendered = ++heldRenderVersion;
  byId("quarantine").replaceChildren();
  for (const {data, account} of heldPages) for (const receipt of data.results) {
    const card = node("article", "");
    card.append(node("h3", "Message held for parser review"), node("p", `Reason: ${receipt.reason}`),
      node("small", `Source ID: ${receipt.provider_id} · Parser: ${receipt.parser_version}`));
    if (typeof receipt.raw_sha256 === "string") card.append(node("pre", `Preserved SHA-256: ${receipt.raw_sha256}`));
    else card.append(node("p", "Source bytes were not retained: the provider message exceeds the configured storage budget. Raise the budget and let synchronization revisit it; there is nothing to retry here."));
    if (typeof receipt.raw_sha256 === "string" && data.reprocessing === true && typeof data.retry_parser_version === "string" && data.retry_parser_version) {
      const retry = node("button", "Retry parsing");
      const session = sessionVersion, token = byId("token").value;
      card.append(node("small", `Retry parser: ${data.retry_parser_version}`));
      card.append(node("p", "Retry retained evidence inside Email Brain only. No mailbox changes, model calls, or raw-content display. A failed attempt is cached for this parser until a parser upgrade."));
      retry.onclick = () => safely(async () => {
        if (retry.disabled) return;
        if (session !== sessionVersion || token !== byId("token").value || version !== importVersion || rendered !== heldRenderVersion || byId("account-id").value.trim() !== account) throw new Error("Review context changed. Refresh held messages before retrying.");
        retry.disabled = true;
        try {
          const result = await api(`/v1/accounts/${encodeURIComponent(account)}/quarantine/${encodeURIComponent(receipt.id)}/retry`, "POST", {expected_parser_version: data.retry_parser_version});
          if (version !== importVersion || rendered !== heldRenderVersion || byId("account-id").value.trim() !== account) return;
          const outcomes = {
            recovered: "Historical retry outcome: recovered. Check refreshed import health for current state; search again for current evidence.",
            mime_rejected: "Historical retry outcome: parser still rejected this message. This result is cached for this parser; retry after a parser upgrade.",
            integrity_failed: "Historical retry outcome: retained evidence failed its integrity check. Operator review is required. This result is cached for this parser."
          };
          if (result.historical_outcome !== true || result.mailbox_effects !== false || !Object.hasOwn(outcomes, result.outcome)) throw new Error("Unexpected retry response. Refresh the queue.");
          if (result.outcome === "recovered") invalidateSearch();
          if (await loadImport()) status(`${outcomes[result.outcome]} Mailbox unchanged.`);
        } finally { retry.disabled = false; }
      });
      card.append(retry);
    }
    addIsolatedApproval(card, receipt, account, rendered);
    byId("quarantine").append(card);
  }
}
async function loadImport() {
  const account = byId("account-id").value.trim();
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(account)) throw new Error("Enter a valid account ID.");
  const version = ++importVersion;
  resetProcessing(quarantineAccount !== null && quarantineAccount !== account);
  heldPages = []; heldRenderVersion += 1;
  byId("quarantine").replaceChildren(); byId("quarantine-more").hidden = true;
  const data = await api(`/v1/accounts/${encodeURIComponent(account)}/sync-status`);
  if (version !== importVersion || byId("account-id").value.trim() !== account) return false;
  const counts = data.message_counts;
  byId("import-health").replaceChildren(node("p", `${counts.ready} indexed · ${counts.quarantined} held · ${counts.deleted} no longer current · ${counts.excluded || 0} excluded by policy`),
    node("p", `Worker: ${data.worker ? data.worker.last_outcome || "not started" : "not enrolled"}. This is not proof of complete attachment extraction.`));
  await heldMessages(account, null, version);
  return version === importVersion && byId("account-id").value.trim() === account;
}
byId("account-form").onsubmit = (event) => { event.preventDefault(); safely(loadImport); };
byId("account-id").oninput = () => { resetReader(); importVersion += 1; heldRenderVersion += 1; heldPages = []; resetProcessing(true); resetDocuments(true); byId("import-health").replaceChildren(); byId("quarantine").replaceChildren();
  quarantineAfter = null; quarantineAccount = null; byId("quarantine-more").hidden = true; };
byId("quarantine-more").onclick = () => { if (quarantineAccount && quarantineAfter) safely(() => heldMessages(quarantineAccount, quarantineAfter)); };

const jobDescriptions = {
  queued: "Approval saved. Waiting for a separately configured worker; availability is unknown.",
  running: "A worker has claimed this approval. Processing is not complete.",
  retry_wait: "The worker was unavailable or failed. A bounded retry is waiting; no parsing result was cached.",
  completed: "Processing finished. Binary attachments may still be unread; inspect current evidence.",
  cancelled: "Approval cancelled. No further publication is authorized by this job.",
  expired: "The one-hour approval expired. This job cannot authorize further processing.",
  failed: "The worker's bounded attempts ended without a completed processing result. Operator review is needed.",
  stale: "The provider's current message changed. This approval no longer matches the source.",
  revoked: "Account or owner authorization was revoked. This approval cannot proceed."
};
const jobOutcomes = {
  queued: [null], running: [null], retry_wait: ["infrastructure_unavailable"],
  completed: ["recovered", "mime_rejected", "integrity_failed"], cancelled: ["cancelled"],
  expired: ["approval_expired"], failed: ["attempts_exhausted", "infrastructure_unavailable"],
  stale: ["source_changed"], revoked: ["authorization_revoked"]
};
const jobFields = ["id", "account_id", "receipt_id", "parser_version", "status", "attempts", "created_at", "expires_at", "retry_at", "completed_at", "attempt_id", "outcome", "mailbox_effects"];
function closed(value, fields) {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).length === fields.length && fields.every((key) => Object.hasOwn(value, key));
}
function validUuid(value) { return typeof value === "string" && uuidPattern.test(value); }
function validParser(value) { return typeof value === "string" && isolatedParserPattern.test(value); }
function sameId(left, right) { return validUuid(left) && validUuid(right) && left.toLowerCase() === right.toLowerCase(); }
function validDate(value) {
  return typeof value === "string" && value.length <= 40
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function terminalJob(job) { return !["queued", "running", "retry_wait"].includes(job.status); }
function validateJob(job, account, expected = null) {
  if (!closed(job, jobFields) || !validUuid(job.id) || !sameId(job.account_id, account)
      || !validUuid(job.receipt_id) || !validParser(job.parser_version) || job.mailbox_effects !== false
      || typeof job.status !== "string" || !Object.hasOwn(jobOutcomes, job.status)
      || !jobOutcomes[job.status].includes(job.outcome) || !Number.isInteger(job.attempts)
      || job.attempts < 0 || job.attempts > 3 || (job.status === "queued" && job.attempts !== 0)
      || (["running", "retry_wait", "completed"].includes(job.status) && job.attempts < 1)
      || (job.status === "retry_wait" && job.attempts > 2)
      || !validDate(job.created_at) || !validDate(job.expires_at)
      || Date.parse(job.expires_at) - Date.parse(job.created_at) !== 3600000
      || (job.status === "retry_wait" ? !validDate(job.retry_at) : job.retry_at !== null)
      || (terminalJob(job) ? !validDate(job.completed_at) : job.completed_at !== null)
      || (job.status === "completed" ? !validUuid(job.attempt_id) : job.attempt_id !== null)) throw new Error("Invalid processing response");
  if (expected && (!sameId(job.id, expected.id) || !sameId(job.receipt_id, expected.receipt_id)
      || job.parser_version !== expected.parser_version || job.created_at !== expected.created_at
      || job.expires_at !== expected.expires_at || job.attempts < expected.attempts
      || (terminalJob(expected) && (job.status !== expected.status || job.outcome !== expected.outcome)))) throw new Error("Invalid processing response");
  return job;
}
function validateCapabilities(data) {
  if (!closed(data, ["enabled", "parser_version", "worker_online", "mailbox_effects"])
      || typeof data.enabled !== "boolean" || data.worker_online !== null || data.mailbox_effects !== false
      || (data.parser_version !== null && !validParser(data.parser_version))
      || (data.enabled && data.parser_version === null)) throw new Error("Invalid processing response");
  return data;
}
function validateJobsPage(data, account, after) {
  if (!closed(data, ["results", "next_after", "limit", "mailbox_effects"]) || data.limit !== 50
      || data.mailbox_effects !== false || !Array.isArray(data.results) || data.results.length > 50
      || (data.next_after !== null && (!validUuid(data.next_after) || !data.results.length
          || sameId(data.next_after, after)))) throw new Error("Invalid processing response");
  const ids = new Set();
  for (const job of data.results) {
    validateJob(job, account);
    if (ids.has(job.id.toLowerCase())) throw new Error("Invalid processing response");
    ids.add(job.id.toLowerCase());
  }
  if (data.next_after !== null && !sameId(data.next_after, data.results[data.results.length - 1].id)) throw new Error("Invalid processing response");
  return data;
}
function processingContext(account) {
  return {account, session: sessionVersion, token: byId("token").value, view: processingVersion, imported: importVersion};
}
function currentProcessing(context) {
  return context.session === sessionVersion && context.token === byId("token").value
    && context.view === processingVersion && context.imported === importVersion
    && byId("account-id").value.trim() === context.account;
}
function processingSummary() {
  byId("processing-health").replaceChildren(
    node("p", processingCaps.enabled ? "Isolated parsing is configured. Worker availability is unknown." : "New isolated approvals are disabled. Existing approval history is still available."),
    node("small", processingCaps.parser_version ? `Configured parser: ${processingCaps.parser_version}` : "No isolated parser is configured."),
    node("p", "Approval lasts one hour and survives token expiry or closing this page. Cancel an unfinished job to revoke that approval. Processing can finish with binary attachments still unread. No mailbox changes or model calls."));
}
async function loadProcessing() {
  const account = byId("account-id").value.trim();
  if (!validUuid(account)) throw new Error("Enter a valid account ID.");
  const changedAccount = processingAccount !== null && processingAccount !== account;
  resetProcessing(changedAccount);
  importVersion += 1;
  if (quarantineAccount !== account) heldPages = [];
  renderHeldMessages();
  const context = processingContext(account);
  byId("processing-health").replaceChildren(node("p", "Loading processing configuration and saved approvals…"));
  try {
    const caps = await api(`/v1/accounts/${encodeURIComponent(account)}/processing`);
    if (!currentProcessing(context)) return;
    validateCapabilities(caps);
    const page = await api(`/v1/accounts/${encodeURIComponent(account)}/processing/jobs?limit=50`);
    if (!currentProcessing(context)) return;
    validateJobsPage(page, account, null);
    processingAccount = account; processingCaps = caps; processingAfter = page.next_after; processingRows = page.results;
    processingSummary(); renderProcessingJobs(context); renderHeldMessages();
    status("Processing history refreshed. Worker availability is unknown. Mailbox unchanged.");
  } catch (_) {
    if (currentProcessing(context)) {
      processingCaps = null; processingAfter = null; processingRows = [];
      byId("processing-health").replaceChildren(node("p", "Processing information could not be verified. Refresh processing before approving."));
      byId("processing-jobs").replaceChildren(); byId("processing-more").hidden = true;
      renderHeldMessages(); status("Processing information unavailable. Check access and refresh processing.");
    }
  }
}
async function loadProcessingPage(after = processingAfter) {
  if (!processingCaps || !processingAccount || !validUuid(after)
      || byId("account-id").value.trim() !== processingAccount) return;
  const account = processingAccount;
  processingVersion += 1; importVersion += 1; processingCards.clear();
  invalidatePendingApprovals();
  const context = processingContext(account);
  byId("processing-jobs").replaceChildren(node("p", "Loading the next history page…"));
  byId("processing-more").disabled = true; renderHeldMessages();
  try {
    const page = await api(`/v1/accounts/${encodeURIComponent(account)}/processing/jobs?limit=50&after=${encodeURIComponent(after)}`);
    if (!currentProcessing(context)) return;
    validateJobsPage(page, account, after);
    processingRows = page.results; processingAfter = page.next_after;
    renderProcessingJobs(context);
  } catch (_) {
    if (currentProcessing(context)) {
      processingRows = []; processingAfter = null; byId("processing-more").hidden = true;
      byId("processing-jobs").replaceChildren(node("p", "This history page could not be verified. Refresh processing to start again."));
    }
  } finally { if (currentProcessing(context)) byId("processing-more").disabled = false; }
}
function jobExplanation(job) {
  if (job.status === "completed" && job.outcome === "mime_rejected") return "Processing finished, but the parser rejected this message. The rejection is cached for this parser version; original evidence is retained.";
  if (job.status === "completed" && job.outcome === "integrity_failed") return "Processing finished with an evidence-integrity failure. Operator review is required; this is not recovered mail.";
  return jobDescriptions[job.status];
}
function renderJob(card, job, context) {
  const cardVersion = ++processingCardVersion;
  processingCards.set(job.id, cardVersion);
  card.replaceChildren(node("h3", `Processing approval · ${job.status}`), node("p", jobExplanation(job)),
    node("small", `Job: ${job.id} · Receipt: ${job.receipt_id}`),
    node("p", `Approved ${job.created_at} · Expires ${job.expires_at} · Worker claims: ${job.attempts}/3`),
    node("small", `Parser: ${job.parser_version}`));
  if (job.retry_at !== null) card.append(node("p", `Earliest worker retry: ${job.retry_at}`));
  const refreshJob = node("button", "Refresh job status");
  const cancel = terminalJob(job) ? null : node("button", "Cancel approval");
  let pending = false;
  async function update(method) {
    if (pending || !currentProcessing(context) || processingCards.get(job.id) !== cardVersion) return;
    pending = true; refreshJob.disabled = true; if (cancel) cancel.disabled = true;
    try {
      const result = await api(`/v1/accounts/${encodeURIComponent(context.account)}/processing/${encodeURIComponent(job.id)}${method === "POST" ? "/cancel" : ""}`, method);
      if (!currentProcessing(context) || processingCards.get(job.id) !== cardVersion) return;
      validateJob(result, context.account, job);
      if (method === "POST" && !terminalJob(result)) throw new Error("Invalid cancellation response");
      processingRows = processingRows.map((row) => sameId(row.id, result.id) ? result : row);
      renderJob(card, result, context);
      status(`${jobExplanation(result)} Mailbox unchanged.`);
    } catch (_) {
      if (currentProcessing(context) && processingCards.get(job.id) === cardVersion) {
        status(method === "POST" ? "Cancellation could not be confirmed. Refresh job status before assuming it was cancelled. No automatic retry was sent." : "Job status could not be verified. Refresh processing and check access.");
      }
    } finally {
      pending = false;
      if (currentProcessing(context) && processingCards.get(job.id) === cardVersion) { refreshJob.disabled = false; if (cancel) cancel.disabled = false; }
    }
  }
  refreshJob.onclick = () => update("GET"); card.append(refreshJob);
  if (cancel) { cancel.onclick = () => update("POST"); card.append(cancel); }
}
function renderProcessingJobs(context) {
  byId("processing-jobs").replaceChildren(); processingCards.clear();
  if (!processingRows.length) byId("processing-jobs").append(node("p", "No saved approvals on this page."));
  for (const job of processingRows) {
    const card = node("article", ""); renderJob(card, job, context); byId("processing-jobs").append(card);
  }
  byId("processing-more").hidden = processingAfter === null;
  byId("processing-more").disabled = false;
  const after = processingAfter;
  byId("processing-more").onclick = () => {
    if (byId("processing-more").disabled || !currentProcessing(context) || after !== processingAfter) return;
    return loadProcessingPage(after);
  };
}
function addIsolatedApproval(card, receipt, account, rendered) {
  if (!processingCaps || !processingCaps.enabled || processingAccount !== account
      || !validUuid(receipt.id) || !["mime_rejected", "mime_too_large"].includes(receipt.reason)
      || typeof receipt.raw_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(receipt.raw_sha256)) return;
  const context = processingContext(account), parser = processingCaps.parser_version;
  const identity = `${account.toLowerCase()}/${receipt.id.toLowerCase()}/${parser}`;
  let intent = approvalIntents.get(identity);
  if (!intent) { intent = {key: null, pending: false, uncertain: false, job: null, serial: 0}; approvalIntents.set(identity, intent); }
  const approve = node("button", intent.uncertain ? "Retry same approval request" : "Approve isolated parsing");
  approve.disabled = intent.pending || intent.job !== null;
  card.append(node("p", "Approve this retained message for isolated parsing for one hour. The grant survives closing this page; unfinished work can be cancelled in processing history. Binary attachments may remain unread."),
    node("small", `Isolated parser to approve: ${parser}`), approve);
  if (intent.job) card.append(node("p", `Approval request recorded as ${intent.job.id} · ${intent.job.status}. Refresh processing history for its current state.`));
  if (intent.uncertain) card.append(node("p", "The previous request may already have been saved. This button repeats the same request key, not a new approval. Refresh processing history to reconcile it."));
  approve.onclick = async () => {
    if (approve.disabled || intent.pending || intent.job !== null || !currentProcessing(context)
        || rendered !== heldRenderVersion || processingCaps.parser_version !== parser) return;
    const serial = ++intent.serial;
    intent.pending = true; approve.disabled = true;
    try {
      if (intent.key === null) intent.key = crypto.randomUUID();
      if (!validUuid(intent.key)) throw new Error("Approval key unavailable");
      const job = await api(`/v1/accounts/${encodeURIComponent(account)}/quarantine/${encodeURIComponent(receipt.id)}/jobs`, "POST",
        {expected_parser_version: parser}, {"Idempotency-Key": intent.key});
      if (!currentProcessing(context) || rendered !== heldRenderVersion || intent.serial !== serial) return;
      validateJob(job, account);
      if (!sameId(job.receipt_id, receipt.id) || job.parser_version !== parser) throw new Error("Invalid approval response");
      intent.job = job; intent.uncertain = false; intent.pending = false;
      // Keep the keyset page intact: a new or idempotently returned old job does
      // not establish its position relative to the current history cursor.
      renderHeldMessages();
      status(`Approval request recorded. ${jobExplanation(job)} Mailbox unchanged.`);
    } catch (_) {
      if (intent.serial === serial) intent.uncertain = intent.key !== null;
      if (currentProcessing(context) && rendered === heldRenderVersion && intent.serial === serial) {
        approve.textContent = "Retry same approval request";
        status("Approval could not be confirmed; it may already be saved. Refresh processing history or explicitly retry the same request. No automatic retry was sent.");
      }
    } finally {
      if (intent.serial === serial) intent.pending = false;
      if (currentProcessing(context) && rendered === heldRenderVersion && intent.serial === serial) approve.disabled = intent.job !== null;
    }
  };
}
byId("processing-refresh").onclick = () => safely(loadProcessing);
byId("processing-more").onclick = () => undefined;
async function refresh() {
  const data = await api("/v1/proposals"); byId("proposals").replaceChildren();
  for (const proposal of data.results) {
    const card = node("article", ""); card.append(node("h3", `${proposal.kind} · ${proposal.status}`),
      node("pre", JSON.stringify(proposal.payload, null, 2)), node("p", proposal.reason));
    if (proposal.status === "pending") for (const decision of ["approved", "rejected"]) {
      const button = node("button", decision === "approved" ? "Approve for later implementation" : "Reject");
      button.onclick = () => safely(async () => { await api(`/v1/proposals/${proposal.id}/reviews`, "POST",
        {decision, expected_version: proposal.version}); await refresh(); status("Review recorded. No mailbox or rule changes applied."); });
      card.append(button);
    }
    if (proposal.kind === "rule" && proposal.status === "approved") {
      const preview = node("button", "Preview rule on a bounded sample");
      preview.onclick = () => safely(async () => {
        const receipt = await api(`/v1/proposals/${proposal.id}/simulation`, "POST", {expected_version: proposal.version});
        preview.disabled = true;
        card.append(node("p", `Sample: ${receipt.sample.length} current messages, at most 50. Not a whole-mailbox accuracy test. Expires ${receipt.expires_at}.`), node("pre", JSON.stringify(receipt.sample, null, 2)));
        const activate = node("button", "Activate this rule — labels only");
        activate.onclick = () => safely(async () => {
          const result = await api("/v1/rules/activations", "POST", {simulation_id: receipt.id});
          activate.disabled = true; invalidateSearch();
          await refreshRules(); status(`Rule activation recorded at revision ${result.revision}. Search again for current labels. Mailbox unchanged.`);
        });
        card.append(activate);
      });
      card.append(preview);
    }
    byId("proposals").append(card);
  }
}
byId("refresh").onclick = () => safely(refresh);
byId("project-form").onsubmit = (event) => { event.preventDefault(); safely(async () => {
  await api("/v1/proposals", "POST", {payload: {kind: "project", name: byId("project-name").value},
    reason: byId("project-reason").value, source: "owner-review-ui", evidence_ids: []}, {"Idempotency-Key": crypto.randomUUID()});
  event.target.reset(); await refresh(); status("Project proposal saved for review.");
}); };
async function refreshRules() {
  const data = await api("/v1/rules");
  byId("rules").replaceChildren(node("p", `Revision ${data.revision} · ${data.rules.length} active sender rules · labels only`), node("pre", JSON.stringify(data.rules, null, 2)));
  if (data.revision > 0) {
    const undo = node("button", `Restore revision ${data.revision - 1} labels`);
    undo.onclick = () => safely(async () => {
      const restored = await api("/v1/rules/rollback", "POST", {expected_revision: data.revision, target_revision: data.revision - 1});
      invalidateSearch(); await refreshRules();
      status(`Restored earlier labels as revision ${restored.revision}. Mailbox unchanged.`);
    });
    byId("rules").append(undo);
  }
}
byId("rules-refresh").onclick = () => safely(refreshRules);
byId("rule-form").onsubmit = (event) => { event.preventDefault(); safely(async () => {
  await api("/v1/proposals", "POST", {payload: {kind: "rule", sender_domain: byId("rule-domain").value.trim().toLowerCase(), category: byId("rule-category").value, canonical_mailbox: byId("rule-mailbox").value},
    reason: byId("rule-reason").value, source: "owner-review-ui", evidence_ids: []}, {"Idempotency-Key": crypto.randomUUID()});
  event.target.reset(); await refresh(); status("Rule proposal saved. Review, preview, and activation are separate steps.");
}); };
