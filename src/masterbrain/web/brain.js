"use strict";
(() => {
  const tokenField = document.getElementById("brain-token");
  const questionField = document.getElementById("brain-question");
  const askButton = document.getElementById("ask-button");
  const turns = document.getElementById("turns");
  const status = document.getElementById("brain-status");
  const groups = [
    ["email_messages", "Email messages"],
    ["email_attachments", "Email attachments"],
    ["email_documents", "Email documents"],
    ["fileos", "Files"],
    ["archive_members", "Archive text"],
    ["archive_documents", "Archive documents"],
    ["archive_images", "Archive image OCR"],
    ["knowledge", "Reviewed knowledge"],
  ];
  let epoch = 0;
  let busy = false;
  const pending = new Set();

  function node(tag, value, parent, className = "") {
    const item = document.createElement(tag);
    item.textContent = value;
    if (className) item.className = className;
    parent.appendChild(item);
    return item;
  }

  function usable() { return tokenField.value.trim().length > 0; }
  function updateButton() { askButton.disabled = busy || !usable(); }
  function invalidate(clearToken = false) {
    epoch += 1;
    for (const controller of pending) controller.abort();
    pending.clear();
    busy = false;
    if (clearToken) tokenField.value = "";
    questionField.value = "";
    turns.replaceChildren();
    node("p", "Start with a distinctive name, topic, or phrase. Results are grouped by source; they are not an AI-generated answer.", turns, "empty");
    status.textContent = usable() ? "Ready for a read-only search." : "Enter an authorized credential to begin.";
    updateButton();
  }

  async function api(path, body, token) {
    const controller = new AbortController();
    pending.add(controller);
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(path, {
        method: body === undefined ? "GET" : "POST",
        headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"},
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: "omit", cache: "no-store", redirect: "error",
        referrerPolicy: "no-referrer", signal: controller.signal,
      });
      if (!response.ok) {
        const error = new Error(`Request refused (${response.status}). Check your access.`);
        error.status = response.status;
        throw error;
      }
      return await response.json();
    } finally {
      clearTimeout(timeout);
      pending.delete(controller);
    }
  }

  function trimTurns() {
    while (turns.childElementCount > 16) turns.firstElementChild.remove();
    turns.scrollTop = turns.scrollHeight;
  }

  async function showEvidence(evidenceId, target, capturedEpoch, token) {
    if (epoch !== capturedEpoch || tokenField.value !== token) return;
    target.replaceChildren();
    node("p", "Opening separately authorized evidence…", target);
    try {
      const id = encodeURIComponent(evidenceId);
      const metadata = await api(`/v1/brain/evidence/${id}`, undefined, token);
      if (epoch !== capturedEpoch || tokenField.value !== token) return;
      if (!metadata || metadata.id !== evidenceId || typeof metadata.source_kind !== "string") {
        throw new Error("Evidence response could not be verified.");
      }
      target.replaceChildren();
      node("p", `Source: ${metadata.source_kind} · Observed: ${metadata.observed_at || "unknown"}`, target);
      if (typeof metadata.locator === "string") node("p", metadata.locator, target, "locator");
      if (typeof metadata.sha256 === "string") node("p", `SHA-256: ${metadata.sha256}`, target, "locator");
      try {
        const content = await api(`/v1/brain/evidence/${id}/content`, {max_chars: 4000}, token);
        if (epoch !== capturedEpoch || tokenField.value !== token) return;
        if (!content || content.evidence_id !== evidenceId || typeof content.content !== "string") {
          throw new Error("Evidence text response could not be verified.");
        }
        node("pre", content.content, target, "evidence-panel");
        if (content.truncated === true) node("p", "Preview truncated at 4,000 characters.", target, "notice");
      } catch (error) {
        if (epoch === capturedEpoch && tokenField.value === token) {
          node("p", error.status === 403 ? "Text preview needs a separate content grant." : "Text preview unavailable.", target, "notice");
        }
      }
    } catch (error) {
      if (epoch === capturedEpoch && tokenField.value === token) {
        target.replaceChildren();
        node("p", Number.isInteger(error?.status) ?
          `Request refused (${error.status}). Check your access.` : "Evidence unavailable.", target, "notice");
      }
    }
  }

  function addEvidenceButton(parent, capturedEpoch, token, evidenceId) {
    if (typeof evidenceId !== "string" || !evidenceId) return;
    const button = node("button", "Open evidence", parent, "evidence-button");
    button.type = "button";
    const target = node("div", "", parent);
    button.addEventListener("click", () => showEvidence(evidenceId, target, capturedEpoch, token));
  }

  function renderResults(data, parent, capturedEpoch, token) {
    if (!data || data.mode !== "grouped_current_sources" || !data.layers ||
        !data.coverage || typeof data.coverage.complete !== "boolean" ||
        groups.some(([key]) => !Array.isArray(data.layers[key]))) {
      throw new Error("Search response could not be verified.");
    }
    node("h3", "Indexed evidence, not an AI-generated answer", parent);
    node("p", data.coverage.complete ? "Coverage reported complete." :
      "Partial coverage: only indexed current sources and reviewed knowledge appear here.", parent, "notice");
    let total = 0;
    for (const [key, label] of groups) {
      const hits = data.layers[key];
      total += hits.length;
      const group = node("section", "", parent, "group");
      node("h4", `${label} · ${hits.length}`, group);
      if (!hits.length) { node("p", "No matching indexed evidence in this group.", group); continue; }
      for (const hit of hits) {
        if (!hit || typeof hit !== "object") throw new Error("Search response could not be verified.");
        const card = node("article", "", group, "hit");
        if (key === "knowledge") {
          node("p", typeof hit.title === "string" ? hit.title : "Reviewed assertion", card);
          if (typeof hit.excerpt === "string") node("p", hit.excerpt, card);
          if (Array.isArray(hit.evidence_ids)) for (const id of hit.evidence_ids.slice(0, 5)) {
            addEvidenceButton(card, capturedEpoch, token, id);
          }
        } else {
          if (typeof hit.locator === "string") node("p", hit.locator, card, "locator");
          if (typeof hit.excerpt === "string") node("p", hit.excerpt, card);
          addEvidenceButton(card, capturedEpoch, token, hit.evidence_id);
        }
      }
    }
    return total;
  }

  document.getElementById("ask-form").addEventListener("submit", async event => {
    event.preventDefault();
    const question = questionField.value.trim();
    const token = tokenField.value;
    if (!question || !usable() || busy) return;
    const capturedEpoch = epoch;
    busy = true;
    updateButton();
    if (turns.querySelector(".empty")) turns.replaceChildren();
    const asked = node("article", "", turns, "turn question");
    node("h3", "You searched", asked);
    node("p", question, asked);
    const answer = node("article", "", turns, "turn response");
    node("p", "Searching authorized current sources…", answer);
    questionField.value = "";
    trimTurns();
    status.textContent = "Searching…";
    try {
      const data = await api("/v1/brain/current-search", {query: question}, token);
      if (epoch !== capturedEpoch || tokenField.value !== token) return;
      answer.replaceChildren();
      const count = renderResults(data, answer, capturedEpoch, token);
      status.textContent = `${count} indexed results. Source coverage is partial; no action was taken.`;
    } catch (error) {
      if (epoch === capturedEpoch && tokenField.value === token) {
        answer.replaceChildren();
        node("p", Number.isInteger(error?.status) ?
          `Request refused (${error.status}). Check your access.` : "Search unavailable. Please retry.", answer, "notice");
        status.textContent = "Search did not complete.";
      }
    } finally {
      if (epoch === capturedEpoch) { busy = false; updateButton(); }
    }
  });
  tokenField.addEventListener("input", () => invalidate());
  document.getElementById("clear-session").addEventListener("click", () => invalidate(true));
  document.getElementById("clear-turns").addEventListener("click", () => invalidate());
  updateButton();
})();
