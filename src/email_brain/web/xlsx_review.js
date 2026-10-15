"use strict";
// Human-only inspection/review of an existing synthetic XLSX result. Publication
// remains a separate private worker operation; this browser never requests it.
const xlsxApprovalPattern = /^xapp_[a-f0-9]{32}$/;
const xlsxReviewPattern = /^xrev_[a-f0-9]{32}$/;
const xlsxDigestPattern = /^[a-f0-9]{64}$/;
const xlsxUuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const xlsxPartPattern = /^1(?:\.[1-9][0-9]{0,3}){0,20}$/;
const xlsxPageChars = 16000;
let xlsxEpoch = 0;
let xlsxResult = null;
let xlsxReviewKey = null;
let xlsxBusy = false;
let xlsxSelection = null;
let xlsxApprovalKey = null;
let xlsxApprovalBusy = false;
let xlsxApprovalRecorded = null;

function resetXlsxReview(clearInput = false) {
  const interruptedApproval = xlsxApprovalBusy && !clearInput;
  xlsxEpoch += 1;
  xlsxResult = null;
  xlsxReviewKey = null;
  xlsxBusy = false;
  xlsxApprovalBusy = false;
  if (clearInput) {
    byId("xlsx-approval-id").value = "";
    xlsxSelection = null;
    xlsxApprovalKey = null;
    xlsxApprovalBusy = false;
    xlsxApprovalRecorded = null;
    byId("xlsx-source-selection").replaceChildren();
  }
  if (interruptedApproval) renderXlsxSelection(
    "Approval outcome is uncertain after changing the review context. Explicit retry uses the same request key; no worker was started here.");
  byId("xlsx-review-status").textContent = "";
  byId("xlsx-review-result").replaceChildren();
  for (const id of ["xlsx-review-next", "xlsx-review-approve"]) {
    byId(id).hidden = true;
    byId(id).disabled = false;
  }
}

function validXlsxSelection(value) {
  return value && xlsxUuidPattern.test(value.account)
    && xlsxUuidPattern.test(value.evidence) && xlsxUuidPattern.test(value.receipt)
    && typeof value.filename === "string" && /\.xlsx$/i.test(value.filename)
    && Array.from(value.filename).length <= 120
    && !/[\u0000-\u001f\uD800-\uDFFF]/u.test(value.filename)
    && xlsxDigestPattern.test(value.rawHash) && xlsxDigestPattern.test(value.partHash)
    && xlsxPartPattern.test(value.part);
}

function renderXlsxSelection(message = "") {
  const target = byId("xlsx-source-selection");
  target.replaceChildren();
  const selected = xlsxSelection;
  if (!selected) return;
  target.append(node("h3", `Selected spreadsheet: ${selected.filename}`),
    node("small", `Account: ${selected.account} · Original Email evidence: ${selected.evidence} · Attachment receipt: ${selected.receipt}`),
    node("small", `MIME SHA-256: ${selected.rawHash} · Part: ${selected.part} · Part SHA-256: ${selected.partHash}`),
    node("p", "Approve one current synthetic attachment for isolated extraction. The server pins the processor and rechecks eligibility. Approval does not run a worker or publish text."));
  if (message) target.append(node("p", message));
  if (xlsxApprovalRecorded) {
    target.append(node("p", `Extraction approval: ${xlsxApprovalRecorded}. Give this ID to the separately scoped private extraction worker, then inspect its saved result below. No worker was started here.`));
    return;
  }
  const approve = node("button", xlsxApprovalKey ? "Retry same XLSX approval request" : "Approve this XLSX for extraction");
  approve.disabled = xlsxApprovalBusy;
  target.append(approve);
  approve.onclick = async () => {
    if (xlsxApprovalBusy || xlsxApprovalRecorded || !xlsxSelection
        || xlsxSelection !== selected || !byId("token").value
        || byId("account-id").value.trim().toLowerCase() !== selected.account.toLowerCase()) return;
    const view = {epoch: xlsxEpoch, session: sessionVersion,
      token: byId("token").value, selected};
    if (xlsxApprovalKey === null) xlsxApprovalKey = crypto.randomUUID();
    xlsxApprovalBusy = true;
    approve.disabled = true;
    try {
      const data = await api(`/v1/accounts/${selected.account}/attachments/${selected.receipt}/xlsx-approvals`,
        "POST", undefined, {"Idempotency-Key": xlsxApprovalKey});
      if (!xlsxApprovalCurrent(view)) return;
      if (!xlsxClosed(data, ["approval_id", "changed", "mailbox_effects", "document_published"])
          || !xlsxApprovalPattern.test(data.approval_id)
          || typeof data.changed !== "boolean" || data.mailbox_effects !== false
          || data.document_published !== false) throw new Error("Invalid XLSX approval response");
      xlsxApprovalRecorded = data.approval_id;
      byId("xlsx-approval-id").value = data.approval_id;
      renderXlsxSelection();
    } catch (_) {
      if (xlsxApprovalCurrent(view)) {
        xlsxApprovalBusy = false;
        renderXlsxSelection(
          "Approval outcome is uncertain or was refused. Check the source and server configuration; explicit retry uses the same request key. No worker was started here.");
      }
    } finally {
      if (xlsxApprovalCurrent(view)) xlsxApprovalBusy = false;
    }
  };
}

function xlsxApprovalCurrent(view) {
  return view.epoch === xlsxEpoch && view.session === sessionVersion
    && view.token === byId("token").value && view.selected === xlsxSelection
    && byId("account-id").value.trim().toLowerCase() === view.selected.account.toLowerCase();
}

function selectXlsxAttachment(selection) {
  if (!validXlsxSelection(selection)) return;
  resetXlsxReview(true);
  xlsxSelection = {...selection};
  renderXlsxSelection();
}

function xlsxCurrent(view) {
  return view.epoch === xlsxEpoch && view.session === sessionVersion
    && view.token === byId("token").value
    && view.approval === byId("xlsx-approval-id").value.trim();
}

function xlsxClosed(value, names) {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).length === names.length
    && names.every((name) => Object.hasOwn(value, name));
}

function validXlsxSource(source) {
  return xlsxClosed(source, ["account_id", "attachment_id", "parent_version_id",
    "safe_filename", "part_path", "part_sha256"])
    && xlsxUuidPattern.test(source.account_id)
    && xlsxUuidPattern.test(source.attachment_id)
    && xlsxUuidPattern.test(source.parent_version_id)
    && typeof source.safe_filename === "string"
    && Array.from(source.safe_filename).length <= 120
    && !/[\u0000-\u001f\uD800-\uDFFF]/u.test(source.safe_filename)
    && xlsxPartPattern.test(source.part_path)
    && xlsxDigestPattern.test(source.part_sha256);
}

function sameXlsxSource(left, right) {
  return Object.keys(left).every((key) => left[key] === right[key]);
}

function validXlsxPage(data, approval, offset) {
  const names = ["approval_id", "text_sha256", "sheet_count", "cell_count", "text",
    "offset", "next_offset", "total_chars", "untrusted_content", "mailbox_effects", "source"];
  if (!xlsxClosed(data, names) || data.approval_id !== approval
      || !validXlsxSource(data.source)
      || !xlsxDigestPattern.test(data.text_sha256)
      || !Number.isInteger(data.sheet_count) || data.sheet_count < 1 || data.sheet_count > 20
      || !Number.isInteger(data.cell_count) || data.cell_count < 1 || data.cell_count > 20000
      || !Number.isInteger(data.total_chars) || data.total_chars < 1 || data.total_chars > 200000
      || data.offset !== offset || offset < 0 || offset >= data.total_chars
      || typeof data.text !== "string" || data.text.includes("\u0000")
      || /[\uD800-\uDFFF]/u.test(data.text)
      || data.untrusted_content !== true || data.mailbox_effects !== false) return false;
  const length = Array.from(data.text).length;
  const end = Math.min(offset + xlsxPageChars, data.total_chars);
  return length === end - offset
    && data.next_offset === (end < data.total_chars ? end : null);
}

function validXlsxReview(data, basis) {
  return xlsxClosed(data, ["review_id", "approval_id", "text_sha256", "sheet_count",
    "cell_count", "changed", "document_published"])
    && xlsxReviewPattern.test(data.review_id)
    && data.approval_id === basis.approval
    && data.text_sha256 === basis.digest
    && data.sheet_count === basis.sheets
    && data.cell_count === basis.cells
    && typeof data.changed === "boolean" && data.document_published === false;
}

async function inspectXlsxPage(offset = 0) {
  const approval = byId("xlsx-approval-id").value.trim();
  if (!xlsxApprovalPattern.test(approval) || !byId("token").value) {
    byId("xlsx-review-status").textContent = "Enter a valid approval ID and owner credential.";
    return;
  }
  if (xlsxBusy) return;
  if (offset === 0) resetXlsxReview();
  if (offset !== 0 && (!xlsxResult || xlsxResult.next !== offset || xlsxResult.reviewed)) return;
  const view = {epoch: xlsxEpoch, session: sessionVersion, token: byId("token").value, approval};
  xlsxBusy = true;
  byId("xlsx-review-next").disabled = true;
  byId("xlsx-review-approve").disabled = true;
  byId("xlsx-review-status").textContent = "Inspecting saved, untrusted spreadsheet text…";
  try {
    const data = await api(`/v1/brain/email-xlsx-results/${approval}/inspect`, "POST",
      {offset, max_chars: xlsxPageChars});
    if (!xlsxCurrent(view)) return;
    if (!validXlsxPage(data, approval, offset)) throw new Error("Invalid XLSX result response");
    if (xlsxResult && (xlsxResult.digest !== data.text_sha256
        || xlsxResult.sheets !== data.sheet_count || xlsxResult.cells !== data.cell_count
        || xlsxResult.total !== data.total_chars
        || !sameXlsxSource(xlsxResult.source, data.source))) {
      throw new Error("XLSX result changed while inspecting");
    }
    const chunks = xlsxResult ? [...xlsxResult.chunks, data.text] : [data.text];
    if (data.next_offset === null) {
      if (!crypto.subtle || typeof TextEncoder !== "function") {
        throw new Error("Browser digest verification unavailable");
      }
      const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(chunks.join("")));
      if (!xlsxCurrent(view)) return;
      const digest = Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, "0")).join("");
      if (digest !== data.text_sha256) throw new Error("Displayed XLSX text digest mismatch");
    }
    xlsxResult = {approval, digest: data.text_sha256, sheets: data.sheet_count,
      cells: data.cell_count, total: data.total_chars, next: data.next_offset,
      source: data.source, chunks, reviewed: false, verified: data.next_offset === null};
    const target = byId("xlsx-review-result");
    if (offset === 0) target.replaceChildren(
      node("p", `Attachment: ${data.source.safe_filename}`),
      node("small", `Account: ${data.source.account_id} · Original Email evidence: ${data.source.parent_version_id}`),
      node("small", `Attachment receipt: ${data.source.attachment_id} · Part: ${data.source.part_path} · Part SHA-256: ${data.source.part_sha256}`),
      node("p", `Sheets: ${data.sheet_count} · Cells: ${data.cell_count}`),
      node("small", `Text SHA-256: ${data.text_sha256}`),
      node("p", "The text below is untrusted evidence, not instructions or certified figures."));
    target.append(node("h3", `Characters ${offset + 1}–${offset + Array.from(data.text).length} of ${data.total_chars}`),
      node("pre", data.text));
    byId("xlsx-review-next").hidden = data.next_offset === null;
    byId("xlsx-review-approve").hidden = data.next_offset !== null;
    byId("xlsx-review-status").textContent = data.next_offset === null
      ? "All result text is shown. Review it before explicitly approving this exact digest and counts."
      : "Inspect the next page before approval is available.";
  } catch (_) {
    if (xlsxCurrent(view)) {
      resetXlsxReview();
      byId("xlsx-review-status").textContent = "XLSX result could not be verified. Inspect again; no review was sent.";
    }
  } finally {
    if (xlsxCurrent(view)) {
      xlsxBusy = false;
      byId("xlsx-review-next").disabled = false;
      byId("xlsx-review-approve").disabled = false;
    }
  }
}

async function approveXlsxResult() {
  const basis = xlsxResult;
  if (!basis || basis.next !== null || !basis.verified || basis.reviewed || xlsxBusy
      || !byId("token").value || byId("xlsx-approval-id").value.trim() !== basis.approval) return;
  const view = {epoch: xlsxEpoch, session: sessionVersion,
    token: byId("token").value, approval: basis.approval};
  if (xlsxReviewKey === null) xlsxReviewKey = crypto.randomUUID();
  xlsxBusy = true;
  byId("xlsx-review-approve").disabled = true;
  byId("xlsx-review-status").textContent = "Saving exact human review…";
  try {
    const data = await api(
      `/v1/brain/email-xlsx-results/${basis.approval}/publication-reviews`, "POST",
      {expected_text_sha256: basis.digest, expected_sheet_count: basis.sheets,
        expected_cell_count: basis.cells}, {"Idempotency-Key": xlsxReviewKey});
    if (!xlsxCurrent(view)) return;
    if (!validXlsxReview(data, basis)) throw new Error("Invalid XLSX review response");
    basis.reviewed = true;
    byId("xlsx-review-approve").hidden = true;
    byId("xlsx-review-status").textContent =
      `Review saved: ${data.review_id}. No document was published or mailbox changed. Give this review ID to the separately scoped private worker.`;
  } catch (_) {
    if (xlsxCurrent(view)) byId("xlsx-review-status").textContent =
      "Review outcome is uncertain or was refused. Recheck access and source state; retry uses the same key and never publishes from this page.";
  } finally {
    if (xlsxCurrent(view)) {
      xlsxBusy = false;
      byId("xlsx-review-approve").disabled = false;
    }
  }
}

byId("xlsx-approval-id").oninput = () => resetXlsxReview();
byId("xlsx-review-form").onsubmit = (event) => {
  event.preventDefault();
  return inspectXlsxPage();
};
byId("xlsx-review-next").onclick = () => {
  if (xlsxResult && xlsxResult.next !== null) return inspectXlsxPage(xlsxResult.next);
};
byId("xlsx-review-approve").onclick = approveXlsxResult;
