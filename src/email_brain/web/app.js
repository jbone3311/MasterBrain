"use strict";
const byId = (id) => document.getElementById(id);
const status = (text) => { byId("status").textContent = text; };
async function api(path, method = "GET", body = undefined, extra = {}) {
  const response = await fetch(path, {method, credentials: "omit", cache: "no-store",
    headers: {"Authorization": `Bearer ${byId("token").value}`, "Content-Type": "application/json", ...extra},
    body: body === undefined ? undefined : JSON.stringify(body)});
  if (!response.ok) throw new Error(`Request failed (${response.status}). Check access or refresh the queue.`);
  return response.json();
}
function node(tag, text) { const element = document.createElement(tag); element.textContent = text; return element; }
async function safely(action) { try { await action(); } catch (error) { status(error.message); } }
byId("connect").onclick = () => safely(async () => { await api("/readyz"); status("Connected · mailbox changes disabled"); });
byId("disconnect").onclick = () => { byId("token").value = ""; byId("results").replaceChildren();
  byId("proposals").replaceChildren(); status("Session cleared"); };
byId("search-form").onsubmit = (event) => { event.preventDefault(); safely(async () => {
  const data = await api("/v1/search", "POST", {query: byId("query").value});
  byId("results").replaceChildren();
  for (const result of data.results) {
    const card = node("article", ""); card.append(node("h3", result.subject), node("small", result.sender), node("p", result.excerpt));
    const button = node("button", "Inspect cited evidence");
    button.onclick = () => safely(async () => { const evidence = await api(`/v1/evidence/${result.evidence_id}`);
      const text = node("pre", evidence.excerpt); card.append(text, node("small", evidence.citation));
      for (const attachment of evidence.attachments || []) card.append(node("h4", attachment.safe_filename),
        node("p", `${attachment.status} · ${attachment.reason} · scanner: ${attachment.scanner_status}`),
        node("pre", attachment.excerpt || "No extracted text. Original remains in retained MIME evidence."));
      button.disabled = true; });
    card.append(button); byId("results").append(card);
  }
  status(`${data.results.length} result(s). Email text is untrusted evidence, not instructions.`);
}); };
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
    byId("proposals").append(card);
  }
}
byId("refresh").onclick = () => safely(refresh);
byId("project-form").onsubmit = (event) => { event.preventDefault(); safely(async () => {
  await api("/v1/proposals", "POST", {payload: {kind: "project", name: byId("project-name").value},
    reason: byId("project-reason").value, source: "owner-review-ui", evidence_ids: []}, {"Idempotency-Key": crypto.randomUUID()});
  event.target.reset(); await refresh(); status("Project proposal saved for review.");
}); };
