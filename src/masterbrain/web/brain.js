"use strict";
(() => {
  const MAX_ANSWER_TEXT_BYTES = 8192; // Keep aligned with masterbrain.schemas.
  const tokenField = document.getElementById("brain-token");
  const questionField = document.getElementById("brain-question");
  const focusField = document.getElementById("brain-source-focus");
  const askButton = document.getElementById("ask-button");
  const searchButton = document.getElementById("search-button");
  const scheduleStart = document.getElementById("schedule-start");
  const scheduleEnd = document.getElementById("schedule-end");
  const eventsButton = document.getElementById("schedule-events-button");
  const dueButton = document.getElementById("schedule-due-button");
  const scheduleResults = document.getElementById("schedule-results");
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
  let scheduleBusy = false;
  let scheduleEpoch = 0;
  const pending = new Set();
  const schedulePending = new Set();

  function node(tag, value, parent, className = "") {
    const item = document.createElement(tag);
    item.textContent = value;
    if (className) item.className = className;
    parent.appendChild(item);
    return item;
  }

  function usable() { return tokenField.value.trim().length > 0; }
  function utcDate(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
        value.startsWith("0000-")) return null;
    const millis = Date.parse(`${value}T00:00:00Z`);
    return Number.isFinite(millis) && new Date(millis).toISOString().slice(0, 10) === value ? millis : null;
  }
  function scheduleWindow() {
    const start = utcDate(scheduleStart.value);
    const end = utcDate(scheduleEnd.value);
    if (start === null || end === null || end <= start || end - start > 366 * 86400000) return null;
    return {start: `${scheduleStart.value}T00:00:00Z`, end: `${scheduleEnd.value}T00:00:00Z`};
  }
  function updateButton() {
    askButton.disabled = busy || scheduleBusy || !usable();
    searchButton.disabled = busy || scheduleBusy || !usable();
    const scheduleDisabled = busy || scheduleBusy || !usable() || focusField.value !== "all" || !scheduleWindow();
    eventsButton.disabled = scheduleDisabled;
    dueButton.disabled = scheduleDisabled;
  }
  function clearSchedule() {
    scheduleEpoch += 1;
    for (const controller of schedulePending) controller.abort();
    schedulePending.clear();
    scheduleBusy = false;
    scheduleResults.replaceChildren();
    updateButton();
  }
  function invalidate(clearToken = false) {
    epoch += 1;
    for (const controller of pending) controller.abort();
    pending.clear();
    busy = false;
    clearSchedule();
    if (clearToken) tokenField.value = "";
    questionField.value = "";
    turns.replaceChildren();
    node("p", "Ask with distinctive source words, such as “Find the insurance certificate.” Ask shows source quotes and separate reviewed matches; Search only uses your literal words and groups results by source.", turns, "empty");
    status.textContent = usable() ? "Ready for a read-only question." : "Enter an authorized credential to begin.";
    updateButton();
  }

  async function api(path, body, token, controller = new AbortController()) {
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

  const projectId = value => typeof value === "string" && /^project_[a-f0-9]{32}$/.test(value);
  const evidenceId = value => typeof value === "string" && /^evidence_[a-f0-9]{32}$/.test(value);
  const entityId = value => typeof value === "string" && /^entity_[a-f0-9]{32}$/.test(value);
  const eventId = value => typeof value === "string" && /^event_[a-f0-9]{32}$/.test(value);
  const commitmentId = value => typeof value === "string" && /^commitment_[a-f0-9]{32}$/.test(value);
  const memberId = value => typeof value === "string" && /^member_[a-f0-9]{32}$/.test(value);
  const projectArtifactId = value => typeof value === "string" && /^partifact_[a-f0-9]{32}$/.test(value);
  const safeText = (value, min, max) => typeof value === "string" &&
    value.length <= max * 2 && Array.from(value).length >= min &&
    Array.from(value).length <= max && !value.includes("\0") && (() => {
      try { encodeURIComponent(value); return true; } catch { return false; }
    })();
  const awareTime = value => typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value));
  const links = value => Array.isArray(value) && value.length >= 1 && value.length <= 20 &&
    value.every(evidenceId) && new Set(value).size === value.length;
  const record = value => value && typeof value === "object" && !Array.isArray(value);

  function validDossier(data, id) {
    if (!record(data) || !record(data.project) || !record(data.coverage) ||
        data.untrusted_content !== true || data.visibility !== "unsuperseded" ||
        data.event_limit !== 5 || data.commitment_limit !== 5 || data.member_limit !== 5 ||
        data.artifact_limit !== 5 ||
        typeof data.events_truncated !== "boolean" || typeof data.commitments_truncated !== "boolean" ||
        typeof data.members_truncated !== "boolean" || typeof data.artifacts_truncated !== "boolean" ||
        !awareTime(data.recorded_cutoff_at) || !Array.isArray(data.events) ||
        !Array.isArray(data.commitments) || !Array.isArray(data.members) || !Array.isArray(data.artifacts) ||
        data.events.length > 5 || data.commitments.length > 5 || data.members.length > 5 ||
        data.artifacts.length > 5 ||
        (data.events_truncated && data.events.length !== 5) ||
        (data.commitments_truncated && data.commitments.length !== 5) ||
        (data.members_truncated && data.members.length !== 5) ||
        (data.artifacts_truncated && data.artifacts.length !== 5) ||
        data.coverage.order !== "recorded_at_descending" ||
        data.coverage.undated_links !== "included" ||
        data.coverage.source_freshness !== "not_asserted" ||
        data.coverage.interpretation !== "reviewed_assertions_not_current_state" ||
        data.coverage.artifact_visibility !== "retained_reviewed_link_history") return false;
    const project = data.project;
    if (project.object_kind !== "project" || project.object_id !== id ||
        !safeText(project.title, 1, 300) || !safeText(project.summary, 0, 300) ||
        typeof project.summary_truncated !== "boolean" ||
        !["proposed", "active", "blocked", "completed", "cancelled", "unknown"].includes(project.state) ||
        !awareTime(project.recorded_at) || Date.parse(project.recorded_at) > Date.parse(data.recorded_cutoff_at) ||
        !links(project.evidence_ids)) return false;
    const validRow = (row, kind) => {
      if (!record(row) || row.object_kind !== kind || row.project_id !== id ||
          !awareTime(row.recorded_at) || Date.parse(row.recorded_at) > Date.parse(data.recorded_cutoff_at) ||
          !links(row.evidence_ids)) return false;
      if (kind === "event") return eventId(row.object_id) &&
        typeof row.event_type === "string" &&
        /^[a-z][a-z0-9_.-]{0,99}$/.test(row.event_type) && safeText(row.title, 1, 300) &&
        (row.starts_at === null || awareTime(row.starts_at)) &&
        (row.ends_at === null || (awareTime(row.ends_at) && awareTime(row.starts_at) &&
          Date.parse(row.ends_at) > Date.parse(row.starts_at)));
      if (kind === "member") return memberId(row.object_id) && entityId(row.entity_id) &&
        safeText(row.entity_name, 1, 300) && ["person", "organization"].includes(row.entity_type) &&
        typeof row.role === "string" && /^[a-z][a-z0-9_.-]{0,99}$/.test(row.role) &&
        ["asserted", "disputed", "retracted"].includes(row.assertion_status) &&
        (row.valid_from === null || awareTime(row.valid_from)) &&
        (row.valid_to === null || (awareTime(row.valid_from) && awareTime(row.valid_to) &&
          Date.parse(row.valid_to) > Date.parse(row.valid_from)));
      return commitmentId(row.object_id) && safeText(row.summary, 1, 300) &&
        typeof row.summary_truncated === "boolean" &&
        ["proposed", "open", "completed", "cancelled", "overdue", "unknown"].includes(row.state) &&
        (row.due_at === null || awareTime(row.due_at)) &&
        (row.owner_entity_id === null || entityId(row.owner_entity_id)) &&
        (row.counterparty_entity_id === null || entityId(row.counterparty_entity_id));
    };
    for (const [rows, kind] of [[data.events, "event"], [data.commitments, "commitment"], [data.members, "member"]]) {
      if (!rows.every(row => validRow(row, kind)) ||
          new Set(rows.map(row => row.object_id)).size !== rows.length ||
          rows.some((row, index) => index > 0 &&
            (Date.parse(rows[index - 1].recorded_at) < Date.parse(row.recorded_at) ||
              (Date.parse(rows[index - 1].recorded_at) === Date.parse(row.recorded_at) &&
                rows[index - 1].object_id < row.object_id)))) return false;
    }
    const artifactKeys = ["object_kind", "object_id", "project_id", "artifact_evidence_id",
      "basis_evidence_id", "artifact_source_kind", "relation", "assertion_status",
      "observed_at", "recorded_at"].sort().join(",");
    if (!data.artifacts.every(row => record(row) &&
        Object.keys(row).sort().join(",") === artifactKeys &&
        row.object_kind === "project_artifact" &&
        projectArtifactId(row.object_id) && row.project_id === id &&
        evidenceId(row.artifact_evidence_id) && evidenceId(row.basis_evidence_id) &&
        ["email", "fileos"].includes(row.artifact_source_kind) &&
        typeof row.relation === "string" && /^[a-z][a-z0-9_.-]{0,99}$/.test(row.relation) &&
        ["asserted", "retracted"].includes(row.assertion_status) &&
        awareTime(row.observed_at) && awareTime(row.recorded_at) &&
        Date.parse(row.recorded_at) <= Date.parse(data.recorded_cutoff_at)) ||
        new Set(data.artifacts.map(row => row.object_id)).size !== data.artifacts.length ||
        data.artifacts.some((row, index) => index > 0 &&
          (Date.parse(data.artifacts[index - 1].recorded_at) < Date.parse(row.recorded_at) ||
            (Date.parse(data.artifacts[index - 1].recorded_at) === Date.parse(row.recorded_at) &&
              data.artifacts[index - 1].object_id < row.object_id)))) return false;
    return true;
  }

  async function showProject(id, target, capturedEpoch, token) {
    if (epoch !== capturedEpoch || tokenField.value !== token) return;
    target.replaceChildren();
    node("p", "Opening separately authorized reviewed project…", target);
    try {
      const data = await api(`/v1/knowledge/projects/${id}/dossier?event_limit=5&commitment_limit=5&member_limit=5&artifact_limit=5`, undefined, token);
      if (epoch !== capturedEpoch || tokenField.value !== token) return;
      if (!validDossier(data, id)) throw new Error("Project response could not be verified.");
      target.replaceChildren();
      node("h4", data.project.title, target);
      node("p", `Reviewed project state: ${data.project.state}. This is not a live status check.`, target, "notice");
      if (data.project.summary) node("p", data.project.summary, target);
      if (data.project.summary_truncated) node("p", "Project preview shortened.", target, "notice");
      for (const source of data.project.evidence_ids) addEvidenceButton(target, capturedEpoch, token, source);
      for (const [name, rows, truncated] of [
        ["Reviewed events", data.events, data.events_truncated],
        ["Reviewed commitments", data.commitments, data.commitments_truncated],
        ["Reviewed people and organizations", data.members, data.members_truncated],
      ]) {
        const group = node("div", "", target, "project-group");
        node("h5", `${name} · ${rows.length}${truncated ? "+" : ""}`, group);
        if (!rows.length) node("p", "No linked reviewed records in this bounded view.", group);
        for (const row of rows) {
          const card = node("article", "", group, "hit");
          node("p", row.object_kind === "event" ? row.title :
            row.object_kind === "member" ? row.entity_name : row.summary, card);
          node("p", row.object_kind === "event" ?
            `Reviewed event · ${row.starts_at || "undated"}` :
            row.object_kind === "member" ?
              `Reviewed role · ${row.role} · ${row.assertion_status}` :
              `Reviewed commitment · ${row.state} · ${row.due_at || "undated"}`, card, "locator");
          for (const source of row.evidence_ids) addEvidenceButton(card, capturedEpoch, token, source);
        }
      }
      const artifactGroup = node("div", "", target, "project-group");
      node("h5", `Reviewed related evidence · ${data.artifacts.length}${data.artifacts_truncated ? "+" : ""}`, artifactGroup);
      if (!data.artifacts.length) node("p", "No linked reviewed evidence in this bounded view.", artifactGroup);
      for (const row of data.artifacts) {
        const card = node("article", "", artifactGroup, "hit");
        node("p", `${row.artifact_source_kind} evidence · ${row.relation} · ${row.assertion_status}`, card);
        node("p", "Artifact evidence", card, "locator");
        addEvidenceButton(card, capturedEpoch, token, row.artifact_evidence_id);
        node("p", "Quoted basis evidence", card, "locator");
        addEvidenceButton(card, capturedEpoch, token, row.basis_evidence_id);
      }
      node("p", "Latest recorded reviewed links only. Source freshness and current project truth are not established.", target, "notice");
    } catch (error) {
      if (epoch === capturedEpoch && tokenField.value === token) {
        target.replaceChildren();
        node("p", Number.isInteger(error?.status) ?
          `Project request refused (${error.status}). Check your access.` :
          "Project details unavailable.", target, "notice");
      }
    }
  }

  function addProjectButton(parent, capturedEpoch, token, hit) {
    if (hit?.object_kind !== "project" || !projectId(hit.object_id)) return;
    const button = node("button", "Open reviewed project", parent, "project-button");
    button.type = "button";
    const target = node("div", "", parent, "project-panel");
    button.addEventListener("click", () => showProject(hit.object_id, target, capturedEpoch, token));
  }

  function validSchedule(data, kind, window, after, cutoff) {
    const events = kind === "events";
    const rows = data?.results;
    const coverage = data?.coverage;
    const rowId = events ? eventId : commitmentId;
    const dateField = events ? "starts_at" : "due_at";
    if (!record(data) || !Array.isArray(rows) || rows.length > 10 ||
        data.limit !== 10 || data.visibility !== "unsuperseded" ||
        data.untrusted_content !== true || !record(coverage) ||
        coverage.source_freshness !== "not_asserted" ||
        coverage.interpretation !== "reviewed_assertions" ||
        coverage[events ? "undated_events" : "undated_commitments"] !== "excluded" ||
        (!events && data.state_filter !== null) ||
        !awareTime(data.recorded_cutoff_at) ||
        (cutoff !== null && Date.parse(data.recorded_cutoff_at) !== Date.parse(cutoff)) ||
        (data.next_cursor !== null &&
          (!rowId(data.next_cursor) || rows.length !== 10 ||
            data.next_cursor !== rows[rows.length - 1].object_id || data.next_cursor === after))) return false;
    const start = Date.parse(window.start);
    const end = Date.parse(window.end);
    for (const row of rows) {
      if (!record(row) || row.object_kind !== (events ? "event" : "commitment") ||
          !rowId(row.object_id) || !awareTime(row[dateField]) ||
          Date.parse(row[dateField]) < start || Date.parse(row[dateField]) >= end ||
          (row.project_id !== null && !projectId(row.project_id)) || !links(row.evidence_ids)) return false;
      if (events) {
        if (typeof row.event_type !== "string" ||
            !/^[a-z][a-z0-9_.-]{0,99}$/.test(row.event_type) ||
            !safeText(row.title, 1, 300) ||
            (row.ends_at !== null &&
              (!awareTime(row.ends_at) || Date.parse(row.ends_at) <= Date.parse(row.starts_at)))) return false;
      } else if (!safeText(row.summary, 1, 300) ||
          typeof row.summary_truncated !== "boolean" ||
          !["proposed", "open", "completed", "cancelled", "overdue", "unknown"].includes(row.state) ||
          (row.owner_entity_id !== null && !entityId(row.owner_entity_id)) ||
          (row.counterparty_entity_id !== null && !entityId(row.counterparty_entity_id))) return false;
    }
    if (new Set(rows.map(row => row.object_id)).size !== rows.length ||
        rows.some(row => row.object_id === after) ||
        rows.some((row, index) => index > 0 &&
          (Date.parse(rows[index - 1][dateField]) > Date.parse(row[dateField]) ||
            (Date.parse(rows[index - 1][dateField]) === Date.parse(row[dateField]) &&
              rows[index - 1].object_id > row.object_id)))) return false;
    return true;
  }

  async function showSchedule(kind, window, after, cutoff, capturedEpoch, capturedScheduleEpoch, token) {
    const current = () => epoch === capturedEpoch && scheduleEpoch === capturedScheduleEpoch &&
      tokenField.value === token && focusField.value === "all" &&
      scheduleWindow()?.start === window.start && scheduleWindow()?.end === window.end;
    if (!current() || busy || scheduleBusy) return;
    scheduleBusy = true;
    updateButton();
    const controller = new AbortController();
    schedulePending.add(controller);
    scheduleResults.replaceChildren();
    node("p", "Opening separately authorized reviewed schedule…", scheduleResults);
    try {
      const route = kind === "events" ? "timeline" : "commitments-due";
      let path = `/v1/knowledge/${route}?start=${encodeURIComponent(window.start)}` +
        `&end=${encodeURIComponent(window.end)}&visibility=unsuperseded&limit=10`;
      if (after !== null) path += `&recorded_cutoff_at=${encodeURIComponent(cutoff)}&after=${after}`;
      const data = await api(path, undefined, token, controller);
      if (!current()) return;
      if (!validSchedule(data, kind, window, after, cutoff)) throw new Error("Invalid schedule response");
      scheduleResults.replaceChildren();
      node("h3", kind === "events" ? "Reviewed events" : "Reviewed commitments due", scheduleResults);
      node("p", `${window.start.slice(0, 10)} to ${window.end.slice(0, 10)} (end exclusive, UTC). ` +
        "Undated records excluded. Source freshness and current truth are not established.",
      scheduleResults, "notice");
      if (!data.results.length) node("p", "No dated reviewed records on this page.", scheduleResults);
      for (const row of data.results) {
        const card = node("article", "", scheduleResults, "hit");
        node("p", kind === "events" ? row.title : row.summary, card);
        node("p", kind === "events" ?
          `Reviewed event · ${row.event_type} · ${row.starts_at}` :
          `Reviewed commitment · ${row.state} · ${row.due_at}`, card, "locator");
        if (kind !== "events" && row.summary_truncated) node("p", "Preview shortened.", card, "notice");
        for (const evidence of row.evidence_ids) addEvidenceButton(card, capturedEpoch, token, evidence);
      }
      if (data.next_cursor !== null) {
        const next = node("button", "Next 10 reviewed records", scheduleResults, "project-button");
        next.type = "button";
        next.addEventListener("click", () => showSchedule(kind, window, data.next_cursor,
          data.recorded_cutoff_at, capturedEpoch, capturedScheduleEpoch, token));
      }
    } catch (error) {
      if (current()) {
        scheduleResults.replaceChildren();
        node("p", Number.isInteger(error?.status) ?
          `Schedule request refused (${error.status}). Check your access.` :
          "Reviewed schedule unavailable.", scheduleResults, "notice");
      }
    } finally {
      schedulePending.delete(controller);
      if (current()) { scheduleBusy = false; updateButton(); }
    }
  }

  function beginSchedule(kind) {
    const window = scheduleWindow();
    if (!window || !usable() || focusField.value !== "all" || busy || scheduleBusy) return;
    clearSchedule();
    return showSchedule(kind, window, null, null, epoch, scheduleEpoch, tokenField.value);
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
          addProjectButton(card, capturedEpoch, token, hit);
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
    const validUnicode = text => {
      try { encodeURIComponent(text); return true; } catch { return false; }
    };
    const reviewed = data && data.reviewed_knowledge === undefined ? [] : data?.reviewed_knowledge;
    if (!data || data.mode !== "grounded_extractive_v1" ||
        !["quoted_evidence", "no_supported_evidence", "no_supported_answer"].includes(data.status) ||
        typeof data.answer !== "string" || !Array.isArray(data.citations) ||
        !data.coverage || data.coverage.complete !== false || data.untrusted_content !== true ||
        (data.coverage.answer_context_truncated !== undefined &&
          typeof data.coverage.answer_context_truncated !== "boolean") ||
        (data.coverage.answer_output_truncated !== undefined &&
          typeof data.coverage.answer_output_truncated !== "boolean") ||
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
          !citation.quote.trim() || !validUnicode(citation.quote) || Array.from(citation.quote).length > 400 ||
          !Number.isInteger(citation.start) || citation.start < 0 ||
          citation.end !== citation.start + Array.from(citation.quote).length ||
          !/^[a-f0-9]{64}$/.test(citation.body_sha256)) {
        throw new Error("Answer citation could not be verified.");
      }
    }
    for (const hit of reviewed) {
      if (!hit || !["entity", "relationship", "claim", "event", "project", "commitment", "member", "correction"].includes(hit.object_kind) ||
          typeof hit.object_id !== "string" || !new RegExp(`^${hit.object_kind}_[a-f0-9]{32}$`).test(hit.object_id) ||
          typeof hit.title !== "string" || !hit.title.length || !validUnicode(hit.title) || Array.from(hit.title).length > 300 || hit.title.includes("\0") ||
          typeof hit.excerpt !== "string" || !hit.excerpt.length || !validUnicode(hit.excerpt) || Array.from(hit.excerpt).length > 1200 || hit.excerpt.includes("\0") ||
          !Array.isArray(hit.evidence_ids) || !hit.evidence_ids.length || hit.evidence_ids.length > 5 ||
          new Set(hit.evidence_ids).size !== hit.evidence_ids.length ||
          hit.evidence_ids.some(id => typeof id !== "string" || !/^evidence_[a-f0-9]{32}$/.test(id)) ||
          !Number.isInteger(hit.linked_evidence_count) ||
          hit.linked_evidence_count < hit.evidence_ids.length || hit.linked_evidence_count > 20) {
        throw new Error("Reviewed knowledge response could not be verified.");
      }
    }
    const encoder = new TextEncoder();
    const answerTextBytes = data.citations.reduce((total, item) =>
      total + encoder.encode(item.quote).length, 0) + reviewed.reduce((total, item) =>
      total + encoder.encode(item.title).length + encoder.encode(item.excerpt).length, 0);
    if (answerTextBytes > MAX_ANSWER_TEXT_BYTES) throw new Error("Answer text budget exceeded.");
    if (data.citations.length) node("h3", "Verified source quotes", parent);
    node("p", data.answer, parent);
    node("p", "Partial coverage: only authorized indexed sources and reviewed matches appear here, not a complete account.", parent, "notice");
    if (data.coverage.answer_context_truncated) node("p",
      "Answer context was shortened by read limits. Other indexed source text may support this question.", parent, "notice");
    if (data.coverage.answer_output_truncated) node("p",
      "Answer results were shortened by the output limit. Open evidence or narrow the question for more detail.", parent, "notice");
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
        addProjectButton(card, capturedEpoch, token, hit);
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
  scheduleStart.addEventListener("input", () => clearSchedule());
  scheduleEnd.addEventListener("input", () => clearSchedule());
  eventsButton.addEventListener("click", () => beginSchedule("events"));
  dueButton.addEventListener("click", () => beginSchedule("due"));
  document.getElementById("clear-session").addEventListener("click", () => invalidate(true));
  document.getElementById("clear-turns").addEventListener("click", () => invalidate());
  updateButton();
})();
