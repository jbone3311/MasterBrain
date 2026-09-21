"use strict";
// Separate developer preview. Text-only DOM, session fencing and explicit publication.
const el = (id) => document.getElementById(`memory-${id}`);
const textNode = (tag, text) => { const n = document.createElement(tag); n.textContent = text; return n; };
const uuid = (value) => /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value);
let epoch = 0, editorEpoch = 0, recordId = crypto.randomUUID(), revision = 0;
let cursor = null, after = null, intent = null, saving = false, refreshVersion = 0;
function report(message) { el("status").textContent = message; }
function newRecord() {
  editorEpoch++; recordId = crypto.randomUUID(); revision = 0; intent = null;
  for (const id of ["evidence", "quote", "parent", "payload"]) el(id).value = "";
  el("reviewed").checked = false; el("editing").textContent = "New record";
}
function reset() {
  epoch++; refreshVersion++; cursor = null; after = null; newRecord();
  for (const id of ["summary", "records", "events"]) el(id).replaceChildren();
  el("more").hidden = true;
}
function context() { return {epoch, token: el("token").value.trim(), account: el("account").value.trim()}; }
function current(c) { return c.epoch === epoch && c.token === el("token").value.trim() && c.account === el("account").value.trim(); }
async function request(c, suffix, options = {}) {
  if (!uuid(c.account) || !c.token) throw new Error("Enter an account ID and owner token.");
  const response = await fetch(`/v1/accounts/${c.account}/memory/${suffix}`, {
    ...options, credentials: "omit", cache: "no-store",
    headers: {Authorization: `Bearer ${c.token}`, "Content-Type": "application/json", ...options.headers}
  });
  if (!current(c)) throw new Error("Session changed.");
  if (!response.ok) {
    if ([401, 403, 404].includes(response.status)) { reset(); report("Access denied. Private records cleared; check the connection."); }
    throw new Error(response.status === 409 ? "Record or evidence changed. Reload and review before saving." : "Request denied or unavailable.");
  }
  return response.json();
}
function showRecord(row, c) {
  if (!uuid(row.record_id) || !uuid(row.evidence_id) || !Number.isSafeInteger(row.revision)
      || row.revision < 1 || (row.parent_trip_id && !uuid(row.parent_trip_id))) throw new Error("Invalid record response.");
  const card = textNode("article", "");
  card.append(textNode("h3", `${row.payload.title} · ${row.payload.status}`),
    textNode("p", `Record ${row.record_id} · revision ${row.revision} · ${row.recorded_at}`),
    textNode("p", row.source_current ? "Owner-reviewed email claim. Not live verified." : "Source changed or was removed. Review this retained claim."),
    textNode("pre", JSON.stringify(row.payload, null, 2)), textNode("p", `Evidence ${row.evidence_id}`));
  const edit = textNode("button", "Review / correct this record");
  edit.onclick = () => {
    if (!current(c) || saving) return;
    editorEpoch++; recordId = row.record_id; revision = row.revision; intent = null;
    el("evidence").value = row.evidence_id; el("quote").value = row.source_quote;
    el("parent").value = row.parent_trip_id || "";
    el("payload").value = JSON.stringify(row.payload, null, 2); el("reviewed").checked = false;
    el("editing").textContent = `Updating ${recordId}, expected revision ${revision}`;
  };
  card.append(edit); el("records").append(card);
}
async function refresh(more = false) {
  const c = context(), version = ++refreshVersion;
  try {
    const summary = await request(c, "summary");
    if (!current(c) || version !== refreshVersion) return;
    el("summary").replaceChildren(textNode("p", `Last successful mailbox check: ${summary.last_checked_at || "unknown"}. ${summary.needs_refresh ? "Refresh needed or source unavailable." : "Source checked recently."} Interpretation remains partial/manual.`));
    for (const b of summary.buckets) el("summary").append(textNode("p", `${b.bucket}: revision ${b.revision}, changed ${b.last_changed_at || "never"}`));
    const data = await request(c, "records" + (more && after ? `?after=${after}` : ""));
    if (!current(c) || version !== refreshVersion) return;
    if (data.next_after !== null && !uuid(data.next_after)) throw new Error("Invalid page response.");
    if (!more) el("records").replaceChildren();
    for (const row of data.results) showRecord(row, c);
    after = data.next_after; el("more").hidden = !after;
    report("Loaded reviewed records. Missing records do not mean all email has been interpreted.");
  } catch (error) { if (current(c) && version === refreshVersion) report(error.message); }
}
el("refresh").onclick = () => refresh(); el("more").onclick = () => refresh(true);
el("clear").onclick = () => { el("token").value = ""; reset(); report("Session cleared."); };
for (const id of ["token", "account"]) el(id).oninput = () => { reset(); report("Connection changed. Refresh to load records."); };
for (const id of ["evidence", "quote", "parent", "payload"]) el(id).oninput = () => { editorEpoch++; el("reviewed").checked = false; };
el("new").onclick = () => { if (!saving) newRecord(); };
el("changes").onclick = async () => {
  const c = context(), previous = cursor;
  try {
    const data = await request(c, "changes" + (previous ? `?after=${previous}` : ""));
    if (!current(c) || cursor !== previous) return;
    if (data.next_cursor !== null && !uuid(data.next_cursor)) throw new Error("Invalid change cursor.");
    el("events").replaceChildren();
    for (const row of data.changes) el("events").append(textNode("p", `${row.kind} · record ${row.record_id} · revision ${row.revision}`));
    cursor = data.next_cursor;
    report(data.has_more ? "More changes remain. Check again for the next page." : "Caught up with reviewed memory—not necessarily all incoming email.");
  } catch (error) { if (current(c)) report(error.message); }
};
el("extract").onclick = async () => {
  const c = context(), version = ++editorEpoch, evidence = el("evidence").value.trim();
  el("reviewed").checked = false;
  try {
    if (!uuid(evidence)) throw new Error("Enter an evidence ID.");
    const data = await request(c, `candidates/${evidence}`, {method: "POST"});
    if (!current(c) || version !== editorEpoch) return;
    if (!data.candidate) { report("Unsupported or ambiguous email. No fields were inferred or saved."); return; }
    el("payload").value = JSON.stringify(data.candidate, null, 2); el("quote").value = data.source_quote;
    report("Suggestion only. Review every field and explicitly save if correct.");
  } catch (error) { if (current(c)) report(error.message); }
};
el("save").onclick = async () => {
  if (saving || !el("reviewed").checked) { report("Review and acknowledge the fields before saving."); return; }
  const c = context(), version = editorEpoch;
  try {
    const body = JSON.stringify({expected_revision: revision, evidence_id: el("evidence").value.trim(),
      source_quote: el("quote").value, parent_trip_id: el("parent").value.trim() || null,
      payload: JSON.parse(el("payload").value), reviewed: true});
    const fingerprint = `${recordId}:${body}`;
    if (!intent || intent.fingerprint !== fingerprint) intent = {fingerprint, key: crypto.randomUUID()};
    saving = true; el("save").disabled = true;
    const result = await request(c, `records/${recordId}`, {method: "PUT", body, headers: {"Idempotency-Key": intent.key}});
    if (!current(c) || version !== editorEpoch) return;
    revision = result.record.revision; intent = null; el("reviewed").checked = false;
    el("editing").textContent = `Updating ${recordId}, expected revision ${revision}`;
    report(result.changed ? "Reviewed record saved. Refresh the list to see it." : "No change; existing revision retained.");
  } catch (error) { if (current(c)) report(error.message); }
  finally { saving = false; el("save").disabled = false; }
};
