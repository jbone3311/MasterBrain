"use strict";
(() => {
  const token = location.hash.slice(1);
  history.replaceState(null, "", location.pathname);
  const status = document.getElementById("status");
  const results = document.getElementById("results");
  const evidence = document.getElementById("evidence");
  const input = document.getElementById("query");
  let searchVersion = 0;
  let evidenceVersion = 0;
  function element(tag, text, parent) {
    const node = document.createElement(tag);
    node.textContent = text;
    parent.appendChild(node);
    return node;
  }
  async function api(path, body) {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "omit", cache: "no-store", redirect: "error",
    });
    if (!response.ok) throw new Error(`Request refused (${response.status}).`);
    return response.json();
  }
  async function showEvidence(id) {
    const version = ++evidenceVersion;
    evidence.replaceChildren();
    element("p", "Loading authorized evidence…", evidence);
    try {
      const path = `/v1/brain/evidence/${encodeURIComponent(id)}`;
      const metadata = await api(path);
      const content = await api(`${path}/content`, {max_chars: 4000});
      if (version !== evidenceVersion) return;
      if (!metadata || metadata.id !== id || !content ||
          content.evidence_id !== id || typeof content.content !== "string") {
        throw new Error("Evidence response could not be verified.");
      }
      evidence.replaceChildren();
      element("h3", "Bounded source text", evidence);
      element("pre", content.content, evidence);
      if (content.truncated === true) element("p", "Preview truncated at 4,000 characters.", evidence);
      const details = document.createElement("details");
      evidence.appendChild(details);
      element("summary", "Citation identity and provenance", details);
      element("pre", JSON.stringify(metadata, null, 2), details);
    } catch (error) {
      if (version !== evidenceVersion) return;
      evidence.replaceChildren();
      element("p", error.message, evidence);
    }
  }
  async function search() {
    const query = input.value.trim();
    if (!query) return;
    const version = ++searchVersion;
    ++evidenceVersion;
    results.replaceChildren();
    evidence.replaceChildren();
    status.textContent = "Searching current indexed evidence…";
    try {
      const data = await api("/v1/brain/current-search", {query});
      if (version !== searchVersion) return;
      let total = 0;
      const groups = [["email_messages", "Emails"], ["fileos", "Files"]];
      for (const [key, label] of groups) {
        const hits = data.layers[key];
        total += hits.length;
        const group = document.createElement("section");
        results.appendChild(group);
        element("h2", `${label} · ${hits.length}`, group);
        if (!hits.length) element("p", "No matching indexed evidence in this group.", group);
        for (const hit of hits) {
          const card = document.createElement("article");
          group.appendChild(card);
          element("h3", key === "fileos" ? hit.locator : "Email evidence", card);
          element("p", hit.excerpt, card);
          const button = element("button", "Open evidence", card);
          button.type = "button";
          button.addEventListener("click", () => showEvidence(hit.evidence_id));
          element("small", hit.evidence_id, card);
        }
      }
      status.textContent = `${total} results. Partial source coverage; no generated answer.`;
      document.getElementById("coverage").textContent = JSON.stringify(data.coverage, null, 2);
    } catch (error) {
      if (version === searchVersion) status.textContent = error.message;
    }
  }
  document.getElementById("search-form").addEventListener("submit", event => {
    event.preventDefault();
    search();
  });
  document.querySelectorAll(".example").forEach(button => {
    button.addEventListener("click", () => {input.value = button.dataset.query; search();});
  });
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token)) {
    status.textContent = "Trial credential missing. Restart the launcher to open a new authenticated browser tab. Do not enter a real token.";
    document.getElementById("search-button").disabled = true;
    return;
  }
  Promise.all([
    api("/v1/brain/current-coverage"),
    api("/v1/brain/sources/trial_files/freshness"),
  ]).then(([coverage, freshness]) => {
    document.getElementById("freshness").textContent = JSON.stringify({coverage, freshness}, null, 2);
  }).catch(error => {document.getElementById("freshness").textContent = error.message;});
  search();
})();
