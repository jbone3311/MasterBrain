"use strict";
(() => {
  const tokenField = document.getElementById("brain-token");
  const questionField = document.getElementById("brain-question");
  const focusField = document.getElementById("brain-source-focus");
  const askButton = document.getElementById("ask-button");
  const searchButton = document.getElementById("search-button");
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
  const focusGroups = {
    all: new Set(groups.map(([key]) => key)),
    email: new Set(["email_messages", "email_attachments", "email_documents"]),
    fileos: new Set(["fileos", "archive_members", "archive_documents", "archive_images"]),
  };
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
  function updateButton() {
    askButton.disabled = busy || !usable();
    searchButton.disabled = busy || !usable();
  }
  function invalidate(clearToken = false) {
    epoch += 1;
    for (const controller of pending) controller.abort();
    pending.clear();
    busy = false;
    if (clearToken) tokenField.value = "";
    questionField.value = "";
    turns.replaceChildren();
    node("p", "Ask with distinctive source words, such as “Find the insurance certificate.” Ask shows source quotes and separate reviewed matches; Search only uses your literal words and groups results by source.", turns, "empty");
    status.textContent = usable() ? "Ready for a read-only question." : "Enter an authorized credential to begin.";
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

  function renderResults(data, parent, capturedEpoch, token, focus) {
    if (!data || data.mode !== "grouped_current_sources" || !data.layers ||
        !data.coverage || typeof data.coverage.complete !== "boolean" ||
        (data.coverage.source_focus || "all") !== focus ||
        groups.some(([key]) => !Array.isArray(data.layers[key]) ||
          (!focusGroups[focus].has(key) && data.layers[key].length))) {
      throw new Error("Search response could not be verified.");
    }
    node("h3", "Indexed evidence, not an AI-generated answer", parent);
    node("p", data.coverage.complete ? "Coverage reported complete." :
      "Partial coverage: only indexed current sources and reviewed knowledge appear here.", parent, "notice");
    if (focus !== "all") node("p", focus === "email" ?
      "Email only. Files and reviewed knowledge were not searched." :
      "Files only. Email and reviewed knowledge were not searched.", parent, "notice");
    let total = 0;
    for (const [key, label] of groups) {
      if (!focusGroups[focus].has(key)) continue;
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

  function renderAnswer(data, parent, capturedEpoch, token, focus) {
    const reviewed = data && data.reviewed_knowledge === undefined ? [] : data?.reviewed_knowledge;
    if (!data || data.mode !== "grounded_extractive_v1" ||
        !["quoted_evidence", "no_supported_evidence", "no_supported_answer"].includes(data.status) ||
        typeof data.answer !== "string" || !Array.isArray(data.citations) ||
        !data.coverage || data.coverage.complete !== false || data.untrusted_content !== true ||
        (data.coverage.source_focus || "all") !== focus ||
        data.citations.length > 4 || (data.status === "quoted_evidence") !== (data.citations.length > 0) ||
        !Array.isArray(reviewed) || reviewed.length > 4 || (focus !== "all" && reviewed.length)) {
      throw new Error("Answer response could not be verified.");
    }
    for (const citation of data.citations) {
      if (!citation || typeof citation.evidence_id !== "string" || !citation.evidence_id ||
          typeof citation.document_id !== "string" || typeof citation.source_id !== "string" ||
          typeof citation.source_kind !== "string" || typeof citation.quote !== "string" ||
          (focus !== "all" && citation.source_kind !== focus) ||
          !citation.quote.trim() || citation.quote.length > 400 ||
          !Number.isInteger(citation.start) || citation.start < 0 ||
          citation.end !== citation.start + citation.quote.length ||
          !/^[a-f0-9]{64}$/.test(citation.body_sha256)) {
        throw new Error("Answer citation could not be verified.");
      }
    }
    for (const hit of reviewed) {
      if (!hit || !["entity", "relationship", "claim", "event", "project", "commitment", "correction"].includes(hit.object_kind) ||
          typeof hit.object_id !== "string" || !new RegExp(`^${hit.object_kind}_[a-f0-9]{32}$`).test(hit.object_id) ||
          typeof hit.title !== "string" || !hit.title.length || hit.title.length > 300 || hit.title.includes("\0") ||
          typeof hit.excerpt !== "string" || !hit.excerpt.length || hit.excerpt.length > 1200 || hit.excerpt.includes("\0") ||
          !Array.isArray(hit.evidence_ids) || !hit.evidence_ids.length || hit.evidence_ids.length > 5 ||
          new Set(hit.evidence_ids).size !== hit.evidence_ids.length ||
          hit.evidence_ids.some(id => typeof id !== "string" || !/^evidence_[a-f0-9]{32}$/.test(id)) ||
          !Number.isInteger(hit.linked_evidence_count) ||
          hit.linked_evidence_count < hit.evidence_ids.length || hit.linked_evidence_count > 20) {
        throw new Error("Reviewed knowledge response could not be verified.");
      }
    }
    if (data.citations.length) node("h3", "Verified source quotes", parent);
    node("p", data.answer, parent);
    node("p", "Partial coverage: only authorized indexed sources and reviewed matches appear here, not a complete account.", parent, "notice");
    if (focus !== "all") node("p", focus === "email" ?
      "Email only. Files and reviewed knowledge were not searched." :
      "Files only. Email and reviewed knowledge were not searched.", parent, "notice");
    for (const citation of data.citations) {
      const card = node("article", "", parent, "hit");
      node("p", citation.quote, card);
      node("p", `${citation.source_kind} · ${citation.source_id} · characters ${citation.start}–${citation.end}`, card, "locator");
      addEvidenceButton(card, capturedEpoch, token, citation.evidence_id);
    }
    if (reviewed.length) {
      node("h3", "Reviewed knowledge matches", parent);
      node("p", "These are reviewed interpretations, not exact source quotes or a synthesized answer.", parent, "notice");
      for (const hit of reviewed) {
        const card = node("article", "", parent, "hit");
        node("p", `${hit.object_kind} · ${hit.title}`, card);
        node("p", hit.excerpt, card);
        node("p", `${hit.evidence_ids.length} of ${hit.linked_evidence_count} linked evidence IDs shown`, card, "locator");
        for (const id of hit.evidence_ids) addEvidenceButton(card, capturedEpoch, token, id);
      }
    }
    return {quotes: data.citations.length, reviewed: reviewed.length};
  }

  async function runQuestion(searchOnly) {
    const question = questionField.value.trim();
    const token = tokenField.value;
    const focus = focusField.value;
    if (!question || !usable() || busy || !focusGroups[focus]) return;
    const capturedEpoch = epoch;
    busy = true;
    updateButton();
    if (turns.querySelector(".empty")) turns.replaceChildren();
    const asked = node("article", "", turns, "turn question");
    node("h3", `${searchOnly ? "You searched" : "You asked"} · ${focus === "all" ? "All sources" : focus === "email" ? "Email only" : "Files only"}`, asked);
    node("p", question, asked);
    const answer = node("article", "", turns, "turn response");
    node("p", "Checking authorized current sources…", answer);
    questionField.value = "";
    trimTurns();
    status.textContent = "Checking sources…";
    try {
      let data;
      let searchFallback = searchOnly;
      const searchBody = focus === "all" ? {query: question} : {query: question, source_focus: focus};
      const answerBody = focus === "all" ? {question} : {question, source_focus: focus};
      if (searchOnly) {
        data = await api("/v1/brain/current-search", searchBody, token);
      } else {
        try {
          data = await api("/v1/brain/answers", answerBody, token);
        } catch (error) {
          if (error.status !== 503) throw error;
          if (epoch !== capturedEpoch || tokenField.value !== token) return;
          searchFallback = true;
          data = await api("/v1/brain/current-search", searchBody, token);
        }
      }
      if (epoch !== capturedEpoch || tokenField.value !== token) return;
      answer.replaceChildren();
      if (searchFallback) {
        if (!searchOnly) node("p", "Answer selection is not configured; showing indexed search results.", answer, "notice");
        const count = renderResults(data, answer, capturedEpoch, token, focus);
        status.textContent = `${count} indexed results. Source coverage is partial; no action was taken.`;
      } else {
        const count = renderAnswer(data, answer, capturedEpoch, token, focus);
        status.textContent = `${count.quotes} verified source quotes · ${count.reviewed} reviewed knowledge matches. Source coverage is partial; no action was taken.`;
      }
    } catch (error) {
      if (epoch === capturedEpoch && tokenField.value === token) {
        answer.replaceChildren();
        node("p", Number.isInteger(error?.status) ?
          `Request refused (${error.status}). Check your access.` : "Answer unavailable. Please retry.", answer, "notice");
        status.textContent = "Question did not complete.";
      }
    } finally {
      if (epoch === capturedEpoch) { busy = false; updateButton(); }
    }
  }
  document.getElementById("ask-form").addEventListener("submit", event => {
    event.preventDefault();
    return runQuestion(false);
  });
  searchButton.addEventListener("click", () => runQuestion(true));
  tokenField.addEventListener("input", () => invalidate());
  focusField.addEventListener("change", () => invalidate());
  document.getElementById("clear-session").addEventListener("click", () => invalidate(true));
  document.getElementById("clear-turns").addEventListener("click", () => invalidate());
  updateButton();
})();
