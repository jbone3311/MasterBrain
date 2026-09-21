"use strict";
// Owner-only reader. No HTML, URL navigation, storage, automatic exports or parsing.
let readerVersion = 0;
const readerUrls = new Set();
function resetReader() {
  readerVersion += 1;
  for (const url of readerUrls) URL.revokeObjectURL(url);
  readerUrls.clear();
  byId("message-reader-content").replaceChildren();
  byId("message-reader").hidden = true;
}
function invalidReader() { throw new Error("Email response could not be verified."); }
function validateReader(data, hit) {
  const fields = ["id", "message_id", "account_id", "raw_sha256", "raw_size", "subject", "sender",
    "received_at", "body", "body_source", "body_complete", "headers", "headers_truncated",
    "attachments", "untrusted_content", "mailbox_effects"];
  if (!closed(data, fields) || !sameId(data.id, hit.evidence_id) || !sameId(data.message_id, hit.id)
      || !sameId(data.account_id, hit.account_id) || !validHash(data.raw_sha256)
      || !Number.isInteger(data.raw_size) || data.raw_size < 1 || data.raw_size > 16777216
      || !boundedText(data.subject, 2000) || !boundedText(data.sender, 320) || !validDate(data.received_at)
      || !boundedText(data.body, 2097152) || typeof data.body_complete !== "boolean"
      || typeof data.headers_truncated !== "boolean" || data.untrusted_content !== true
      || data.mailbox_effects !== false || !Array.isArray(data.headers) || data.headers.length > 100
      || !Array.isArray(data.attachments) || data.attachments.length > 64) invalidReader();
  const small = data.raw_size <= 1048576;
  if (small ? data.body_source !== "original_mime" || !data.body_complete
    : data.body_source !== "stored_projection" || !boundedText(data.body, 100000)
      || data.headers.length !== 0 || !data.headers_truncated) invalidReader();
  let headerChars = 0;
  for (const header of data.headers) {
    if (!closed(header, ["name", "value"]) || !boundedText(header.name, 100)
        || !boundedText(header.value, 4000)) invalidReader();
    headerChars += [...header.value].length;
  }
  if (headerChars > 65536) invalidReader();
  const ids = new Set(), paths = new Set();
  for (const part of data.attachments) {
    if (!closed(part, ["id", "part_id", "safe_filename", "media_type", "sha256", "byte_size", "status",
      "reason", "scanner_status", "download_available"]) || !validUuid(part.id) || ids.has(part.id.toLowerCase())
        || typeof part.part_id !== "string" || !partPattern.test(part.part_id) || paths.has(part.part_id)
        || !boundedText(part.safe_filename, 120) || !boundedText(part.media_type, 255) || !validHash(part.sha256)
        || !Number.isInteger(part.byte_size) || part.byte_size < 0 || part.byte_size > 16777216
        || !["extracted", "deferred", "failed", "skipped", "pending"].includes(part.status)
        || !boundedText(part.reason, 120) || part.scanner_status !== "not_scanned"
        || typeof part.download_available !== "boolean"
        || (part.download_available && (!small || /^(message|multipart)\//.test(part.media_type)))) invalidReader();
    ids.add(part.id.toLowerCase()); paths.add(part.part_id);
  }
}
async function readDownload(response, size, current) {
  if (response.headers.get("Content-Type") !== "application/octet-stream"
      || response.headers.get("Content-Length") !== String(size)
      || !response.body || size > 16777216) {
    if (response.body) await response.body.cancel();
    invalidReader();
  }
  const stream = response.body.getReader(), chunks = [];
  let total = 0;
  try {
    while (true) {
      const {done, value} = await stream.read();
      if (!current()) invalidReader();
      if (done) break;
      total += value.byteLength;
      if (total > size) invalidReader();
      chunks.push(value);
    }
    if (total !== size) invalidReader();
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return bytes;
  } finally { await stream.cancel(); stream.releaseLock(); }
}
async function openReader(hit, context) {
  if (!currentSearch(context)) return;
  resetReader();
  const generation = readerVersion, selectedAccount = byId("account-id").value.trim();
  const current = () => generation === readerVersion && currentSearch(context)
    && selectedAccount === byId("account-id").value.trim();
  const target = byId("message-reader-content");
  byId("message-reader").hidden = false;
  target.replaceChildren(node("p", "Loading retained email…"));
  try {
    const data = await api(`/v1/reader/${hit.evidence_id}`);
    if (!current()) return;
    validateReader(data, hit);
    const body = node("pre", data.body || "No readable selected body. The original may contain other MIME parts.");
    body.className = "reader-body"; body.tabIndex = 0; body.setAttribute("aria-label", "Email body");
    target.replaceChildren(node("h3", data.subject || "(No subject)"),
      node("p", `From: ${data.sender || "Ambiguous or unavailable sender — see headers"} · Received: ${data.received_at}`),
      node("p", data.body_source === "original_mime"
        ? "Complete selected body as text. Quoted replies are retained. HTML formatting and remote images are disabled."
        : `Large original: showing its stored text projection${data.body_complete ? " (not marked truncated)" : " — truncated"}. Download the original for all MIME contents and headers.`),
      body,
      node("small", `Evidence: ${data.id} · Original SHA-256: ${data.raw_sha256}`));
    const headerDetails = node("details", "");
    headerDetails.append(node("summary", `Headers${data.headers_truncated ? " (bounded or unavailable)" : ""}`));
    for (const header of data.headers) headerDetails.append(node("p", `${header.name}: ${header.value}`));
    target.append(headerDetails, node("h4", "Attachments and original"),
      node("p", "Files are unscanned. Downloading does not make them safe. Do not open files you do not trust. Individual attachments are saved as .bin; the original .eml includes all MIME parts."));
    const acknowledge = node("input", ""); acknowledge.type = "checkbox";
    const label = node("label", ""); label.className = "check-label";
    label.append(acknowledge, node("span", "I understand these files are unscanned and want to enable downloads."));
    target.append(label);
    const controls = [];
    let downloading = false;
    let saveLink = null;
    function clearPreparedDownload() {
      for (const url of readerUrls) URL.revokeObjectURL(url);
      readerUrls.clear();
      if (saveLink) { saveLink.remove(); saveLink = null; }
    }
    const update = () => { for (const control of controls) control.disabled = downloading || acknowledge.checked !== true; };
    acknowledge.onchange = () => { if (acknowledge.checked !== true) clearPreparedDownload(); update(); };
    function downloadButton(text, suffix, size, sha, filename) {
      const button = node("button", text); button.disabled = true; controls.push(button);
      button.onclick = async () => {
        if (downloading || acknowledge.checked !== true || !current()) return;
        downloading = true; update();
        try {
          const response = await fetch(`/v1/reader/${data.id}/${suffix}`, {method: "POST", credentials: "omit", cache: "no-store",
            headers: {"Authorization": `Bearer ${context.token}`, "Content-Type": "application/json"},
            body: JSON.stringify({acknowledge_unscanned: true})});
          if (!current()) { if (response.body) await response.body.cancel(); return; }
          if (!response.ok) {
            if (response.body) await response.body.cancel();
            if ([401, 403, 404].includes(response.status)) {
              resetReader(); status("Download denied. Email cleared; reconnect and search again."); return;
            }
            throw new Error("Download denied or unavailable.");
          }
          if (response.headers.get("X-Content-SHA256") !== sha
              || response.headers.get("Content-Disposition") !== `attachment; filename="${filename}"`) {
            if (response.body) await response.body.cancel();
            invalidReader();
          }
          const bytes = await readDownload(response, size, current);
          const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
            (n) => n.toString(16).padStart(2, "0")).join("");
          if (!current() || acknowledge.checked !== true) return;
          if (digest !== sha) invalidReader();
          clearPreparedDownload();
          const url = URL.createObjectURL(new Blob([bytes], {type: "application/octet-stream"}));
          readerUrls.add(url);
          const link = node("a", `Save verified file: ${filename}`); link.href = url; link.download = filename;
          saveLink = link;
          link.onclick = (event) => {
            if (!current() || acknowledge.checked !== true || saveLink !== link) { event.preventDefault(); return; }
            status("Save requested. Check your browser's downloads; the file remains unscanned.");
          };
          target.append(link);
          status("File verified. Click the Save verified file link below to save it. File remains unscanned.");
        } catch (_) { if (current()) status("Download could not be verified. Check access and try again; no file was saved by this page."); }
        finally { downloading = false; if (current()) update(); }
      };
      return button;
    }
    target.append(downloadButton("Download original email (.eml)", "original", data.raw_size, data.raw_sha256, `message-${data.id}.eml`));
    if (!data.attachments.length) target.append(node("p", "No attachment receipts for this message."));
    for (const part of data.attachments) {
      const card = node("article", "");
      card.append(node("h4", part.safe_filename), node("p", `${part.media_type} · ${part.byte_size} bytes · ${part.status} · unscanned`));
      if (part.download_available) card.append(downloadButton("Download attachment (.bin)", `attachments/${part.id}`,
        part.byte_size, part.sha256, `attachment-${part.id}.bin`));
      else card.append(node("p", "Use the original email download for this part; separate export requires restricted processing."));
      target.append(card);
    }
    status("Retained email opened. No mailbox changes or external image requests.");
    byId("message-reader").scrollIntoView?.({block: "start"});
  } catch (_) {
    if (current()) {
      resetReader(); status("Email could not be read. Check owner access and retained storage, then search again.");
    }
  }
}
byId("message-reader-close").onclick = resetReader;
