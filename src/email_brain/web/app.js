"use strict";
const byId = (id) => document.getElementById(id);
const status = (text) => { byId("status").textContent = text; };
let sessionVersion = 0;
let quarantineAfter = null;
let quarantineAccount = null;
function clearEvidence() {
  sessionVersion += 1;
  for (const id of ["results", "proposals", "import-health", "quarantine", "rules"]) byId(id).replaceChildren();
  quarantineAfter = null; quarantineAccount = null; byId("quarantine-more").hidden = true;
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
byId("search-form").onsubmit = (event) => { event.preventDefault(); safely(async () => {
  const data = await api("/v1/search", "POST", {query: byId("query").value});
  byId("results").replaceChildren();
  for (const result of data.results) {
    const card = node("article", ""); card.append(node("h3", result.subject), node("small", result.sender), node("p", result.excerpt));
    if (result.classification) card.append(node("small", `Email Brain labels · revision ${result.classification.rules_revision} · ${JSON.stringify(result.classification.effects)} · virtual only`));
    const button = node("button", "Inspect cited evidence");
    button.onclick = () => safely(async () => { const evidence = await api(`/v1/evidence/${result.evidence_id}`);
      const text = node("pre", evidence.excerpt); card.append(text, node("small", evidence.citation));
      for (const attachment of evidence.attachments || []) card.append(node("h4", attachment.safe_filename),
        node("p", `${attachment.status} · ${attachment.reason} · scanner: ${attachment.scanner_status}`),
        node("pre", attachment.excerpt || "No extracted text. Original remains in retained MIME evidence."));
      button.disabled = true; });
    const accountButton = node("button", "Check this account's import");
    accountButton.onclick = () => { byId("account-id").value = result.account_id; safely(loadImport); };
    card.append(button, accountButton); byId("results").append(card);
  }
  status(`${data.results.length} result(s). Email text is untrusted evidence, not instructions.`);
}); };
async function heldMessages(account, after = null) {
  const query = after ? `?after=${encodeURIComponent(after)}` : "";
  const data = await api(`/v1/accounts/${encodeURIComponent(account)}/quarantine${query}`);
  if (byId("account-id").value.trim() !== account) return;
  if (!after) byId("quarantine").replaceChildren();
  for (const receipt of data.results) {
    const card = node("article", "");
    card.append(node("h3", "Message held for parser review"), node("p", `Reason: ${receipt.reason}`),
      node("small", `Source ID: ${receipt.provider_id} · Parser: ${receipt.parser_version}`),
      node("pre", `Preserved SHA-256: ${receipt.raw_sha256}`));
    byId("quarantine").append(card);
  }
  quarantineAccount = account; quarantineAfter = data.next_after;
  byId("quarantine-more").hidden = !data.next_after;
}
async function loadImport() {
  const account = byId("account-id").value.trim();
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(account)) throw new Error("Enter a valid account ID.");
  byId("quarantine").replaceChildren(); byId("quarantine-more").hidden = true;
  const data = await api(`/v1/accounts/${encodeURIComponent(account)}/sync-status`);
  if (byId("account-id").value.trim() !== account) return;
  const counts = data.message_counts;
  byId("import-health").replaceChildren(node("p", `${counts.ready} indexed · ${counts.quarantined} held · ${counts.deleted} no longer current`),
    node("p", `Worker: ${data.worker ? data.worker.last_outcome || "not started" : "not enrolled"}. This is not proof of complete attachment extraction.`));
  await heldMessages(account);
}
byId("account-form").onsubmit = (event) => { event.preventDefault(); safely(loadImport); };
byId("account-id").oninput = () => { byId("import-health").replaceChildren(); byId("quarantine").replaceChildren();
  quarantineAfter = null; quarantineAccount = null; byId("quarantine-more").hidden = true; };
byId("quarantine-more").onclick = () => { if (quarantineAccount && quarantineAfter) safely(() => heldMessages(quarantineAccount, quarantineAfter)); };
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
          activate.disabled = true; byId("results").replaceChildren();
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
      byId("results").replaceChildren(); await refreshRules();
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
