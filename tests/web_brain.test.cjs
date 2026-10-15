"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../src/masterbrain/web/brain.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "../src/masterbrain/web/brain.html"), "utf8");
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.parent = null; this.events = {};
    this.textContent = ""; this.value = ""; this.className = ""; this.disabled = false;
    this.scrollTop = 0; this.scrollHeight = 0;
  }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  replaceChildren(...children) {
    for (const old of this.children) old.parent = null;
    this.children = [];
    for (const child of children) this.appendChild(child);
  }
  addEventListener(type, listener) { this.events[type] = listener; }
  get childElementCount() { return this.children.length; }
  get firstElementChild() { return this.children[0]; }
  remove() { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; }
  querySelector(selector) {
    if (selector.startsWith(".") && this.className.split(" ").includes(selector.slice(1))) return this;
    for (const child of this.children) { const found = child.querySelector(selector); if (found) return found; }
    return null;
  }
  set innerHTML(_) { throw new Error("Untrusted HTML must never be parsed"); }
}

const emptyLayers = () => Object.fromEntries([
  "email_messages", "email_attachments", "email_documents", "fileos", "archive_members",
  "archive_documents", "archive_images", "knowledge",
].map(key => [key, []]));
function searchData() {
  const layers = emptyLayers();
  layers.email_messages = [{evidence_id: "ev_email", excerpt: "<img src=x onerror=alert(1)>"}];
  layers.fileos = [{evidence_id: "ev_file", locator: "private/path.txt", excerpt: "Cedar Harbor"}];
  layers.knowledge = [{title: "Reviewed commitment", excerpt: "Due Friday", evidence_ids: ["ev_email"]}];
  return {mode: "grouped_current_sources", layers, coverage: {complete: false}};
}
const PROJECT_ID = "project_" + "a".repeat(32);
const EVIDENCE_ID = "evidence_" + "b".repeat(32);
const EVENT_ID = "event_" + "c".repeat(32);
const COMMITMENT_ID = "commitment_" + "d".repeat(32);
const MEMBER_ID = "member_" + "e".repeat(32);
const ENTITY_ID = "entity_" + "f".repeat(32);
const ARTIFACT_LINK_ID = "partifact_" + "1".repeat(32);
const PROJECT_FACT_ID = "pfact_" + "2".repeat(32);
const DOSSIER_PATH = `/v1/knowledge/projects/${PROJECT_ID}/dossier?event_limit=5&commitment_limit=5&member_limit=5&artifact_limit=5&fact_limit=5`;
const SCHEDULE_START = "2026-10-01";
const SCHEDULE_END = "2026-10-08";
const scheduleQuery = `start=2026-10-01T00%3A00%3A00Z&end=2026-10-08T00%3A00%3A00Z&visibility=unsuperseded&limit=10`;
const TIMELINE_PATH = `/v1/knowledge/timeline?${scheduleQuery}`;
const DUE_PATH = `/v1/knowledge/commitments-due?${scheduleQuery}`;
function timelineData() {
  return {results: [{object_kind: "event", object_id: EVENT_ID, event_type: "review",
    title: "<script>review</script>", starts_at: "2026-10-04T09:00:00Z",
    ends_at: null, project_id: PROJECT_ID, evidence_ids: [EVIDENCE_ID]}],
  next_cursor: null, recorded_cutoff_at: "2026-10-05T00:00:00Z", limit: 10,
  visibility: "unsuperseded", untrusted_content: true,
  coverage: {undated_events: "excluded", source_freshness: "not_asserted",
    interpretation: "reviewed_assertions"}};
}
function dueData() {
  return {results: [{object_kind: "commitment", object_id: COMMITMENT_ID,
    summary: "Send <img> report", summary_truncated: true, state: "open",
    due_at: "2026-10-06T12:00:00Z", project_id: PROJECT_ID,
    owner_entity_id: null, counterparty_entity_id: null, evidence_ids: [EVIDENCE_ID]}],
  next_cursor: null, recorded_cutoff_at: "2026-10-05T00:00:00Z", limit: 10,
  visibility: "unsuperseded", state_filter: null, untrusted_content: true,
  coverage: {undated_commitments: "excluded", source_freshness: "not_asserted",
    interpretation: "reviewed_assertions"}};
}
function projectSearchData() {
  const data = searchData();
  data.layers.knowledge = [{object_kind: "project", object_id: PROJECT_ID,
    title: "Fictional project", excerpt: "Reviewed plan", evidence_ids: [EVIDENCE_ID]}];
  return data;
}
function dossierData() {
  return {
    project: {object_kind: "project", object_id: PROJECT_ID,
      title: "<img src=x onerror=alert(1)>", summary: "Fictional reviewed notes",
      summary_truncated: false, state: "active", recorded_at: "2026-10-04T00:00:00Z",
      evidence_ids: [EVIDENCE_ID]},
    events: [{object_kind: "event", object_id: EVENT_ID, project_id: PROJECT_ID,
      event_type: "review", title: "Undated <script>event</script>",
      starts_at: null, ends_at: null, recorded_at: "2026-10-04T00:00:00Z",
      evidence_ids: [EVIDENCE_ID]}],
    commitments: [{object_kind: "commitment", object_id: COMMITMENT_ID,
      project_id: PROJECT_ID, summary: "Send <img> package", summary_truncated: false,
      state: "open", due_at: null, owner_entity_id: null, counterparty_entity_id: null,
      recorded_at: "2026-10-04T00:00:00Z", evidence_ids: [EVIDENCE_ID]}],
    members: [{object_kind: "member", object_id: MEMBER_ID, project_id: PROJECT_ID,
      entity_id: ENTITY_ID, entity_name: "Pat <Example>", entity_type: "person",
      role: "broker", assertion_status: "asserted", valid_from: null, valid_to: null,
      recorded_at: "2026-10-04T00:00:00Z", evidence_ids: [EVIDENCE_ID]}],
    artifacts: [{object_kind: "project_artifact", object_id: ARTIFACT_LINK_ID,
      project_id: PROJECT_ID, artifact_evidence_id: EVIDENCE_ID,
      basis_evidence_id: EVIDENCE_ID, artifact_source_kind: "fileos",
      relation: "related", assertion_status: "asserted",
      observed_at: "2026-10-04T00:00:00Z", recorded_at: "2026-10-04T00:00:00Z"}],
    facts: [{object_kind: "project_fact", object_id: PROJECT_FACT_ID,
      project_id: PROJECT_ID, predicate: "capital.amount", value_preview: "Fictional <img> units",
      value_truncated: false, value_type: "text", assertion_status: "asserted",
      derivation: "source_stated", confidence: 1, evidence_ids: [EVIDENCE_ID],
      quote_evidence_id: EVIDENCE_ID, observed_at: "2026-10-04T00:00:00Z",
      valid_from: null, valid_to: null, recorded_at: "2026-10-04T00:00:00Z"}],
    recorded_cutoff_at: "2026-10-05T00:00:00Z", visibility: "unsuperseded",
    event_limit: 5, commitment_limit: 5, member_limit: 5, artifact_limit: 5, fact_limit: 5,
    events_truncated: false, commitments_truncated: false, members_truncated: false,
    artifacts_truncated: false, facts_truncated: false, untrusted_content: true,
    coverage: {order: "recorded_at_descending", undated_links: "included",
      source_freshness: "not_asserted", interpretation: "reviewed_assertions_not_current_state",
      artifact_visibility: "retained_reviewed_link_history",
      fact_visibility: "current_authorized_source_stated_reviewed_facts"},
  };
}
function walk(element) { return [element, ...element.children.flatMap(walk)]; }
const flush = async () => { for (let i = 0; i < 6; i++) await new Promise(resolve => setImmediate(resolve)); };
test("reviewed schedule controls exist once in the served static page", () => {
  for (const id of ["schedule-start", "schedule-end", "schedule-events-button",
    "schedule-due-button", "schedule-results"]) {
    assert.equal(html.split(`id="${id}"`).length - 1, 1, id);
  }
  assert.match(html, /id="schedule-start" type="date"/);
  assert.match(html, /id="schedule-end" type="date"/);
  assert.match(html, /id="schedule-results"[^>]*aria-live="polite"/);
});
function harness(customFetch) {
  const ids = ["brain-token", "brain-question", "brain-source-focus", "ask-button", "search-button", "turns", "brain-status",
    "ask-form", "clear-session", "clear-turns", "schedule-start", "schedule-end",
    "schedule-events-button", "schedule-due-button", "schedule-results"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(id)]));
  elements["brain-source-focus"].value = "all";
  const calls = [];
  vm.runInNewContext(script, {
    document: {getElementById: id => elements[id], createElement: tag => new Element(tag)},
    fetch: async (url, options) => {
      calls.push({url, options});
      if (customFetch) return customFetch(url, options);
      if (url === "/v1/brain/answers") return {ok: false, status: 503};
      const value = url === "/v1/brain/current-search" ? searchData() :
        url.endsWith("/content") ? {evidence_id: "ev_email", content: "<script>untrusted</script>", truncated: false} :
          {id: "ev_email", source_kind: "email", observed_at: "2026-09-24", sha256: "a".repeat(64)};
      return {ok: true, status: 200, json: async () => value};
    },
    AbortController, TextEncoder, setTimeout, clearTimeout,
  });
  const enterToken = value => { elements["brain-token"].value = value; elements["brain-token"].events.input(); };
  const chooseFocus = value => {
    elements["brain-source-focus"].value = value;
    elements["brain-source-focus"].events.change();
  };
  const setSchedule = (start, end) => {
    elements["schedule-start"].value = start;
    elements["schedule-start"].events.input();
    elements["schedule-end"].value = end;
    elements["schedule-end"].events.input();
  };
  const ask = async value => {
    elements["brain-question"].value = value;
    await elements["ask-form"].events.submit({preventDefault() {}});
    await flush();
  };
  const searchOnly = async value => {
    elements["brain-question"].value = value;
    await elements["search-button"].events.click();
    await flush();
  };
  return {elements, calls, enterToken, chooseFocus, setSchedule, ask, searchOnly};
}

test("static shell makes no request and refuses a missing credential", async () => {
  const h = harness();
  assert.equal(h.calls.length, 0);
  assert.equal(h.elements["ask-button"].disabled, true);
  await h.ask("Cedar Harbor");
  assert.equal(h.calls.length, 0);
  assert.equal(h.elements["schedule-events-button"].disabled, true);
});

test("reviewed schedule requires an explicit valid UTC window and All focus", async () => {
  const h = harness();
  h.enterToken("owner-token");
  h.setSchedule("2026-01-01", "2027-01-03");
  assert.equal(h.elements["schedule-events-button"].disabled, true, "367 days is refused");
  await h.elements["schedule-events-button"].events.click();
  assert.equal(h.calls.length, 0);
  h.setSchedule(SCHEDULE_START, SCHEDULE_END);
  assert.equal(h.elements["schedule-events-button"].disabled, false);
  h.chooseFocus("email");
  assert.equal(h.elements["schedule-events-button"].disabled, true);
  await h.elements["schedule-due-button"].events.click();
  assert.equal(h.calls.length, 0);
});

test("explicit timeline and due reads use scoped GETs and inert evidence-linked text", async () => {
  const h = harness(async url => ({ok: true, status: 200,
    json: async () => url === TIMELINE_PATH ? timelineData() : dueData()}));
  h.enterToken("owner-token");
  h.setSchedule(SCHEDULE_START, SCHEDULE_END);
  assert.equal(h.calls.length, 0, "entering dates must not fetch");
  await h.elements["schedule-events-button"].events.click(); await flush();
  assert.equal(h.calls[0].url, TIMELINE_PATH);
  assert.equal(h.calls[0].options.method, "GET");
  assert.equal(h.calls[0].options.credentials, "omit");
  assert.equal(h.calls[0].options.cache, "no-store");
  let rendered = walk(h.elements["schedule-results"]).map(item => item.textContent).join("\n");
  assert.match(rendered, /<script>review<\/script>/);
  assert.match(rendered, /Undated records excluded.*Source freshness/);
  assert.equal(walk(h.elements["schedule-results"]).filter(item => item.textContent === "Open evidence").length, 1);
  await h.elements["schedule-due-button"].events.click(); await flush();
  assert.equal(h.calls[1].url, DUE_PATH);
  rendered = walk(h.elements["schedule-results"]).map(item => item.textContent).join("\n");
  assert.match(rendered, /Send <img> report/);
  assert.match(rendered, /Preview shortened/);
  assert.equal(h.calls.some(call => /proposals|move|rename|delete/.test(call.url)), false);
});

test("reviewed timeline pages with the exact returned cutoff and bounded cursor", async () => {
  const firstRows = Array.from({length: 10}, (_, index) => ({...timelineData().results[0],
    object_id: "event_" + String(index).repeat(32),
    starts_at: `2026-10-04T09:00:0${index}Z`,
  }));
  const first = {...timelineData(), results: firstRows, next_cursor: firstRows[9].object_id};
  const second = {...timelineData(), results: [{...timelineData().results[0],
    object_id: "event_" + "a".repeat(32), starts_at: "2026-10-04T09:00:10Z"}]};
  const h = harness(async url => ({ok: true, status: 200,
    json: async () => url === TIMELINE_PATH ? first : second}));
  h.enterToken("owner-token"); h.setSchedule(SCHEDULE_START, SCHEDULE_END);
  await h.elements["schedule-events-button"].events.click(); await flush();
  const next = walk(h.elements["schedule-results"]).find(item => item.textContent === "Next 10 reviewed records");
  assert.ok(next);
  await next.events.click(); await flush();
  assert.equal(h.calls[1].url, `${TIMELINE_PATH}&recorded_cutoff_at=2026-10-05T00%3A00%3A00Z&after=${firstRows[9].object_id}`);
  assert.match(walk(h.elements["schedule-results"]).map(item => item.textContent).join("\n"), /Reviewed events/);
  assert.equal(walk(h.elements["schedule-results"]).filter(item => item.textContent === "Open evidence").length, 1);
});

test("reviewed schedule refuses a next page that changes its recorded cutoff", async () => {
  const rows = Array.from({length: 10}, (_, index) => ({...timelineData().results[0],
    object_id: "event_" + String(index).repeat(32),
    starts_at: `2026-10-04T09:00:0${index}Z`,
  }));
  const first = {...timelineData(), results: rows, next_cursor: rows[9].object_id};
  const shifted = {...timelineData(), recorded_cutoff_at: "2026-10-06T00:00:00Z"};
  const h = harness(async url => ({ok: true, status: 200,
    json: async () => url === TIMELINE_PATH ? first : shifted}));
  h.enterToken("owner-token"); h.setSchedule(SCHEDULE_START, SCHEDULE_END);
  await h.elements["schedule-events-button"].events.click(); await flush();
  await walk(h.elements["schedule-results"]).find(item => item.textContent === "Next 10 reviewed records").events.click();
  await flush();
  assert.match(walk(h.elements["schedule-results"]).map(item => item.textContent).join("\n"),
    /Reviewed schedule unavailable/);
});

test("reviewed schedule rejects malformed, mismatched and denied pages without partial content", async () => {
  const invalid = [
    {...timelineData(), limit: 50},
    {...timelineData(), results: [{...timelineData().results[0], starts_at: "2026-10-08T00:00:00Z"}]},
    {...timelineData(), results: [{...timelineData().results[0], starts_at: "2026-10-04 09:00:00Z"}]},
    {...timelineData(), results: [{...timelineData().results[0], evidence_ids: ["evidence_bad"]}]},
    {...timelineData(), results: [
      {...timelineData().results[0], object_id: "event_" + "e".repeat(32), starts_at: "2026-10-05T09:00:00Z"},
      {...timelineData().results[0], object_id: "event_" + "f".repeat(32)},
    ]},
    {...timelineData(), next_cursor: EVENT_ID},
    {...timelineData(), coverage: {...timelineData().coverage, undated_events: "included"}},
  ];
  for (const data of invalid) {
    const h = harness(async () => ({ok: true, status: 200, json: async () => data}));
    h.enterToken("owner-token"); h.setSchedule(SCHEDULE_START, SCHEDULE_END);
    await h.elements["schedule-events-button"].events.click(); await flush();
    const rendered = walk(h.elements["schedule-results"]).map(item => item.textContent).join("\n");
    assert.match(rendered, /Reviewed schedule unavailable/);
    assert.doesNotMatch(rendered, /<script>review<\/script>/);
  }
  const denied = harness(async () => ({ok: false, status: 403}));
  denied.enterToken("owner-token"); denied.setSchedule(SCHEDULE_START, SCHEDULE_END);
  await denied.elements["schedule-events-button"].events.click(); await flush();
  assert.match(walk(denied.elements["schedule-results"]).map(item => item.textContent).join("\n"),
    /Schedule request refused \(403\)/);
});

test("commitment due pages refuse unrelated filters, invalid links and hidden cursors", async () => {
  for (const data of [
    {...dueData(), state_filter: "open"},
    {...dueData(), results: [{...dueData().results[0], project_id: "project_bad"}]},
    {...dueData(), results: [{...dueData().results[0], owner_entity_id: "entity_bad"}]},
    {...dueData(), results: [{...dueData().results[0], state: "approved"}]},
    {...dueData(), results: [{...dueData().results[0], summary: "x".repeat(301)}]},
  ]) {
    const h = harness(async () => ({ok: true, status: 200, json: async () => data}));
    h.enterToken("owner-token"); h.setSchedule(SCHEDULE_START, SCHEDULE_END);
    await h.elements["schedule-due-button"].events.click(); await flush();
    assert.match(walk(h.elements["schedule-results"]).map(item => item.textContent).join("\n"),
      /Reviewed schedule unavailable/);
  }
  const hidden = harness(async () => ({ok: false, status: 404}));
  hidden.enterToken("owner-token"); hidden.setSchedule(SCHEDULE_START, SCHEDULE_END);
  await hidden.elements["schedule-due-button"].events.click(); await flush();
  assert.match(walk(hidden.elements["schedule-results"]).map(item => item.textContent).join("\n"),
    /Schedule request refused \(404\)/);
});

test("date, focus and credential changes discard late reviewed schedule pages", async () => {
  for (const change of ["date", "focus", "token", "clear"]) {
    let release;
    const h = harness(async () => new Promise(resolve => { release = () => resolve({ok: true, status: 200,
      json: async () => timelineData()}); }));
    h.enterToken("owner-token"); h.setSchedule(SCHEDULE_START, SCHEDULE_END);
    const inFlight = h.elements["schedule-events-button"].events.click();
    await flush();
    if (change === "date") h.setSchedule("2026-10-02", SCHEDULE_END);
    else if (change === "focus") h.chooseFocus("fileos");
    else if (change === "token") h.enterToken("new-token");
    else h.elements["clear-session"].events.click();
    release(); await inFlight; await flush();
    const rendered = walk(h.elements["schedule-results"]).map(item => item.textContent).join("\n");
    assert.doesNotMatch(rendered, /<script>review<\/script>|Reviewed events/);
  }
});

test("read-only conversation uses the scoped API and renders hostile content as text", async () => {
  const h = harness();
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  assert.equal(h.calls.length, 2);
  assert.equal(h.calls[0].url, "/v1/brain/answers");
  assert.equal(JSON.parse(h.calls[0].options.body).question, "Cedar Harbor");
  assert.equal(h.calls[1].url, "/v1/brain/current-search");
  assert.equal(JSON.parse(h.calls[1].options.body).query, "Cedar Harbor");
  assert.equal(h.calls[0].options.credentials, "omit");
  assert.equal(h.calls[0].options.cache, "no-store");
  assert.equal(h.calls[0].options.redirect, "error");
  assert.equal(h.calls[0].options.headers.Authorization, "Bearer owner-token");
  assert.match(h.elements["brain-status"].textContent, /3 indexed results/);
  const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(rendered, /Partial coverage/);
  assert.match(rendered, /<img src=x onerror=alert\(1\)>/);
  assert.match(rendered, /Reviewed commitment/);
  assert.equal(h.calls.some(call => /proposals|move|rename|delete/.test(call.url)), false);
});

test("explicit project drill-down uses the scoped read route and renders bounded hostile text inertly", async () => {
  const h = harness(async url => ({ok: true, status: 200,
    json: async () => url === DOSSIER_PATH ? dossierData() : projectSearchData()}));
  h.enterToken("owner-token");
  await h.searchOnly("Fictional project");
  assert.equal(h.calls.length, 1, "search must not fetch project context automatically");
  const button = walk(h.elements.turns).find(item => item.textContent === "Open reviewed project");
  assert.ok(button);
  await button.events.click(); await flush();
  assert.equal(h.calls.length, 2);
  assert.equal(h.calls[1].url, DOSSIER_PATH);
  assert.equal(h.calls[1].options.method, "GET");
  assert.equal(h.calls[1].options.credentials, "omit");
  assert.equal(h.calls[1].options.cache, "no-store");
  const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(rendered, /Reviewed project state: active.*not a live status check/);
  assert.match(rendered, /<img src=x onerror=alert\(1\)>/);
  assert.match(rendered, /Undated <script>event<\/script>/);
  assert.match(rendered, /Send <img> package/);
  assert.match(rendered, /Pat <Example>/);
  assert.match(rendered, /Reviewed role · broker · asserted/);
  assert.match(rendered, /Reviewed related evidence · 1/);
  assert.match(rendered, /fileos evidence · related · asserted/);
  assert.match(rendered, /Source freshness and current project truth are not established/);
  assert.ok(walk(h.elements.turns).filter(item => item.textContent === "Open evidence").length >= 4);
  assert.equal(h.calls.some(call => /proposals|move|rename|delete/.test(call.url)), false);
});

test("Ask reviewed project matches can open the same read-only dossier", async () => {
  const h = harness(async url => ({ok: true, status: 200, json: async () =>
    url === "/v1/brain/answers" ? {
      mode: "grounded_extractive_v1", status: "no_supported_evidence",
      answer: "No exact source quote was selected.", citations: [],
      reviewed_knowledge: [{object_kind: "project", object_id: PROJECT_ID,
        title: "Fictional project", excerpt: "Reviewed project assertion",
        evidence_ids: [EVIDENCE_ID], linked_evidence_count: 1}],
      coverage: {complete: false}, untrusted_content: true,
    } : dossierData()}));
  h.enterToken("owner-token");
  await h.ask("Fictional project");
  assert.equal(h.calls.length, 1);
  const button = walk(h.elements.turns).find(item => item.textContent === "Open reviewed project");
  assert.ok(button);
  await button.events.click(); await flush();
  assert.equal(h.calls[1].url, DOSSIER_PATH);
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Reviewed project state: active/);
});

test("project drill-down refuses mismatched data and hidden project responses", async () => {
  for (const reply of [
    {ok: true, status: 200, json: async () => ({...dossierData(),
      project: {...dossierData().project, object_id: "project_" + "e".repeat(32)}})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      commitments: [{...dossierData().commitments[0], project_id: "project_" + "e".repeat(32)}]})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      events_truncated: true})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      events: [{...dossierData().events[0], recorded_at: "2026-10-06T00:00:00Z"}]})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      project: {...dossierData().project, evidence_ids: ["evidence_bad"]}})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      members: [{...dossierData().members[0], entity_id: "entity_bad"}]})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      members: [{...dossierData().members[0], role: "admin permission"}]})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      artifacts: [{...dossierData().artifacts[0], project_id: "project_bad"}]})},
    {ok: true, status: 200, json: async () => ({...dossierData(),
      artifacts: [{...dossierData().artifacts[0], source_quote: "private"}]})},
    {ok: false, status: 404},
  ]) {
    const h = harness(async url => url === DOSSIER_PATH ? reply :
      {ok: true, status: 200, json: async () => projectSearchData()});
    h.enterToken("owner-token");
    await h.searchOnly("Fictional project");
    const button = walk(h.elements.turns).find(item => item.textContent === "Open reviewed project");
    await button.events.click(); await flush();
    const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
    assert.match(rendered, /Project details unavailable|Project request refused \(404\)/);
    assert.doesNotMatch(rendered, /Fictional reviewed notes|Send <img> package/);
  }
});

test("project drill-down labels independently truncated lists and rejects row reordering", async () => {
  const fiveEvents = Array.from({length: 5}, (_, index) => ({...dossierData().events[0],
    object_id: "event_" + String(9 - index).repeat(32),
    recorded_at: `2026-10-04T00:00:0${5 - index}Z`,
  }));
  const valid = {...dossierData(), events: fiveEvents, events_truncated: true};
  const h = harness(async url => ({ok: true, status: 200,
    json: async () => url === DOSSIER_PATH ? valid : projectSearchData()}));
  h.enterToken("owner-token");
  await h.searchOnly("Fictional project");
  await walk(h.elements.turns).find(item => item.textContent === "Open reviewed project").events.click();
  await flush();
  const shown = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(shown, /Reviewed events · 5\+/);
  assert.match(shown, /Reviewed commitments · 1/);

  const reordered = {...valid, events: [...fiveEvents].reverse()};
  const bad = harness(async url => ({ok: true, status: 200,
    json: async () => url === DOSSIER_PATH ? reordered : projectSearchData()}));
  bad.enterToken("owner-token");
  await bad.searchOnly("Fictional project");
  await walk(bad.elements.turns).find(item => item.textContent === "Open reviewed project").events.click();
  await flush();
  assert.match(walk(bad.elements.turns).map(item => item.textContent).join("\n"),
    /Project details unavailable/);
});

test("project artifact history has its own bound and rejects malformed ordering", async () => {
  const fiveArtifacts = Array.from({length: 5}, (_, index) => ({...dossierData().artifacts[0],
    object_id: "partifact_" + String(9 - index).repeat(32),
    recorded_at: `2026-10-04T00:00:0${5 - index}Z`,
  }));
  const valid = {...dossierData(), artifacts: fiveArtifacts, artifacts_truncated: true};
  const h = harness(async url => ({ok: true, status: 200,
    json: async () => url === DOSSIER_PATH ? valid : projectSearchData()}));
  h.enterToken("owner-token");
  await h.searchOnly("Fictional project");
  await walk(h.elements.turns).find(item => item.textContent === "Open reviewed project").events.click();
  await flush();
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"),
    /Reviewed related evidence · 5\+/);

  const bad = harness(async url => ({ok: true, status: 200,
    json: async () => url === DOSSIER_PATH ?
      {...valid, artifacts: [...fiveArtifacts].reverse()} : projectSearchData()}));
  bad.enterToken("owner-token");
  await bad.searchOnly("Fictional project");
  await walk(bad.elements.turns).find(item => item.textContent === "Open reviewed project").events.click();
  await flush();
  assert.match(walk(bad.elements.turns).map(item => item.textContent).join("\n"),
    /Project details unavailable/);
});

test("source-stated project facts render inertly and reject inferred or hidden-basis shapes", async () => {
  const h = harness(async url => ({ok: true, status: 200,
    json: async () => url === DOSSIER_PATH ? dossierData() : projectSearchData()}));
  h.enterToken("owner-token");
  await h.searchOnly("Fictional project");
  await walk(h.elements.turns).find(item => item.textContent === "Open reviewed project").events.click();
  await flush();
  const shown = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(shown, /Reviewed project facts · 1/);
  assert.match(shown, /Fictional <img> units/);
  assert.equal(walk(h.elements.turns).some(item => item.tag === "img"), false);

  for (const fact of [
    {...dossierData().facts[0], derivation: "inferred"},
    {...dossierData().facts[0], quote_evidence_id: "evidence_" + "9".repeat(32)},
    {...dossierData().facts[0], source_quote: "private"},
  ]) {
    const bad = harness(async url => ({ok: true, status: 200,
      json: async () => url === DOSSIER_PATH ? {...dossierData(), facts: [fact]} : projectSearchData()}));
    bad.enterToken("owner-token");
    await bad.searchOnly("Fictional project");
    await walk(bad.elements.turns).find(item => item.textContent === "Open reviewed project").events.click();
    await flush();
    assert.match(walk(bad.elements.turns).map(item => item.textContent).join("\n"),
      /Project details unavailable/);
  }
});

test("clearing access or changing focus prevents a late project dossier from reappearing", async () => {
  for (const change of ["token", "focus", "clear"]) {
    let release;
    const h = harness(async url => url === DOSSIER_PATH ? new Promise(resolve => {
      release = () => resolve({ok: true, status: 200, json: async () => dossierData()});
    }) : {ok: true, status: 200, json: async () => projectSearchData()});
    h.enterToken("owner-token");
    await h.searchOnly("Fictional project");
    const button = walk(h.elements.turns).find(item => item.textContent === "Open reviewed project");
    const inFlight = button.events.click();
    await flush();
    if (change === "token") h.enterToken("new-token");
    else if (change === "focus") h.chooseFocus("email");
    else h.elements["clear-session"].events.click();
    release(); await inFlight; await flush();
    const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
    assert.doesNotMatch(rendered, /Fictional reviewed notes|Send <img> package/);
    assert.equal(h.elements.turns.firstElementChild.className, "empty");
  }
});

test("explicit Email focus narrows Ask and Search only without fetching Files", async () => {
  const h = harness(async url => {
    if (url === "/v1/brain/answers") return {ok: true, json: async () => ({
      mode: "grounded_extractive_v1", status: "quoted_evidence",
      answer: "Relevant passages from current indexed evidence are quoted below.",
      citations: [{evidence_id: "ev_email", document_id: "doc_email", source_id: "source_email",
        source_kind: "email", quote: "Insurance is pending.", start: 0, end: 21,
        body_sha256: "a".repeat(64)}],
      reviewed_knowledge: [], coverage: {complete: false, source_focus: "email"},
      untrusted_content: true,
    })};
    const data = searchData();
    data.coverage.source_focus = "email";
    data.layers.fileos = [];
    data.layers.knowledge = [];
    return {ok: true, json: async () => data};
  });
  h.enterToken("owner-token");
  h.chooseFocus("email");
  await h.ask("insurance");
  assert.equal(h.calls.length, 1);
  assert.equal(JSON.parse(h.calls[0].options.body).source_focus, "email");
  let rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(rendered, /Files and reviewed knowledge were not searched/);
  assert.doesNotMatch(rendered, /private\/path.txt/);
  await h.searchOnly("insurance");
  assert.equal(JSON.parse(h.calls[1].options.body).source_focus, "email");
  rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.doesNotMatch(rendered, /Files ·/);
  assert.doesNotMatch(rendered, /Reviewed knowledge ·/);
});

test("changing source focus clears prior results and rejects a late response", async () => {
  let release;
  const h = harness(async () => new Promise(resolve => {
    release = () => resolve({ok: true, json: async () => searchData()});
  }));
  h.enterToken("owner-token");
  h.elements["brain-question"].value = "Cedar Harbor";
  const inFlight = h.elements["ask-form"].events.submit({preventDefault() {}});
  await flush();
  h.chooseFocus("fileos");
  release(); await inFlight; await flush();
  assert.equal(h.elements.turns.childElementCount, 1);
  assert.equal(h.elements.turns.firstElementChild.className, "empty");
  assert.equal(h.elements["brain-question"].value, "");
});

test("evidence metadata and text use separate authorized calls; denied text stays hidden", async () => {
  const h = harness(async url => {
    if (url === "/v1/brain/answers") return {ok: false, status: 503};
    if (url === "/v1/brain/current-search") return {ok: true, json: async () => searchData()};
    if (url.endsWith("/content")) return {ok: false, status: 403};
    return {ok: true, json: async () => ({id: "ev_email", source_kind: "email", observed_at: "2026-09-24", sha256: "a".repeat(64)})};
  });
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  const button = walk(h.elements.turns).find(item => item.tag === "button");
  await button.events.click(); await flush();
  assert.ok(h.calls.some(call => call.url === "/v1/brain/evidence/ev_email"));
  assert.ok(h.calls.some(call => call.url === "/v1/brain/evidence/ev_email/content"));
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /separate content grant/);
});

test("authorized content stays inert and all calls remain read-only Brain API calls", async () => {
  const h = harness(async url => {
    if (url === "/v1/brain/answers") return {ok: false, status: 503};
    if (url === "/v1/brain/current-search") return {ok: true, json: async () => searchData()};
    if (url.endsWith("/content")) return {ok: true, json: async () =>
      ({evidence_id: "ev_email", content: "<script>not executable</script>", truncated: false})};
    return {ok: true, json: async () =>
      ({id: "ev_email", source_kind: "email", observed_at: "2026-09-24"})};
  });
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  const button = walk(h.elements.turns).find(item => item.tag === "button");
  await button.events.click(); await flush();
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /<script>not executable<\/script>/);
  assert.ok(h.calls.every(call => call.url.startsWith("/v1/brain/")));
});

test("malformed search response fails visibly without rendering partial results", async () => {
  const h = harness(async url => url === "/v1/brain/answers" ? {ok: false, status: 503} :
    {ok: true, json: async () =>
      ({mode: "grouped_current_sources", layers: {fileos: []}, coverage: {complete: false}})});
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(rendered, /Answer unavailable/);
  assert.doesNotMatch(rendered, /Partial coverage/);
});

test("changing the credential clears content and prevents a late response from returning", async () => {
  let release;
  const h = harness(async url => {
    if (url === "/v1/brain/answers") return {ok: false, status: 503};
    if (url === "/v1/brain/current-search") {
      return new Promise(resolve => { release = () => resolve({ok: true, json: async () => searchData()}); });
    }
    throw new Error("Unexpected request");
  });
  h.enterToken("first-token");
  h.elements["brain-question"].value = "Cedar Harbor";
  const inFlight = h.elements["ask-form"].events.submit({preventDefault() {}});
  await flush();
  h.enterToken("second-token");
  assert.equal(h.elements["brain-question"].value, "");
  release(); await inFlight; await flush();
  assert.equal(h.elements.turns.childElementCount, 1);
  assert.equal(h.elements.turns.firstElementChild.className, "empty");
  assert.doesNotMatch(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Cedar Harbor/);
  h.elements["clear-session"].events.click();
  assert.equal(h.elements["brain-token"].value, "");
  assert.equal(h.elements["ask-button"].disabled, true);
});

test("configured answer renders exact quotes as inert text and opens evidence", async () => {
  const h = harness(async url => {
    if (url === "/v1/brain/answers") return {ok: true, json: async () => ({
      mode: "grounded_extractive_v1", status: "quoted_evidence",
      answer: "Relevant passages from current indexed evidence are quoted below.",
      citations: [{evidence_id: "ev_email", document_id: "doc1", source_id: "email",
        source_kind: "email", quote: "<script>inert</script>", start: 0, end: 22,
        body_sha256: "a".repeat(64)}], coverage: {complete: false, answer_context_truncated: true}, untrusted_content: true,
    })};
    return {ok: true, json: async () => ({id: "ev_email", source_kind: "email"})};
  });
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  assert.equal(h.calls.length, 1);
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /<script>inert<\/script>/);
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Answer context was shortened/);
  assert.match(h.elements["brain-status"].textContent, /1 verified source quotes/);
});

test("Ask keeps reviewed knowledge distinct and renders it as inert text", async () => {
  const evidenceId = `evidence_${"a".repeat(32)}`;
  const h = harness(async url => {
    if (url === "/v1/brain/answers") return {ok: true, json: async () => ({
      mode: "grounded_extractive_v1", status: "no_supported_answer",
      answer: "No exact source quote selected; reviewed knowledge matches are listed below.",
      citations: [], reviewed_knowledge: [{object_kind: "commitment",
        object_id: `commitment_${"b".repeat(32)}`, title: "<script>inert</script>",
        excerpt: "Insurance certificate remains outstanding.",
        evidence_ids: [evidenceId], linked_evidence_count: 1}],
      coverage: {complete: false}, untrusted_content: true,
    })};
    return {ok: true, json: async () => ({id: evidenceId, source_kind: "fileos"})};
  });
  h.enterToken("owner-token");
  await h.ask("insurance");
  assert.equal(h.calls.length, 1);
  const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(rendered, /Reviewed knowledge matches/);
  assert.match(rendered, /interpretations, not exact source quotes/);
  assert.match(rendered, /<script>inert<\/script>/);
  assert.match(h.elements["brain-status"].textContent, /1 reviewed knowledge matches/);
  const button = walk(h.elements.turns).find(item => item.tag === "button");
  await button.events.click(); await flush();
  assert.ok(h.calls.some(call => call.url === `/v1/brain/evidence/${evidenceId}`));
  h.elements["clear-session"].events.click();
  assert.doesNotMatch(walk(h.elements.turns).map(item => item.textContent).join("\n"), /inert/);
});

test("Ask accepts a reviewed role match without treating it as a permission", async () => {
  const h = harness(async url => ({ok: true, status: 200, json: async () =>
    url === "/v1/brain/answers" ? {
      mode: "grounded_extractive_v1", status: "no_supported_evidence",
      answer: "No exact source quote was selected.", citations: [],
      reviewed_knowledge: [{object_kind: "member", object_id: MEMBER_ID,
        title: "broker", excerpt: "Pat <Example> is the reviewed broker.",
        evidence_ids: [EVIDENCE_ID], linked_evidence_count: 1}],
      coverage: {complete: false}, untrusted_content: true,
    } : {id: EVIDENCE_ID}}));
  h.enterToken("owner-token");
  await h.ask("Who brokers the project?");
  const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(rendered, /Pat <Example> is the reviewed broker/);
  assert.match(rendered, /interpretations, not exact source quotes/);
  assert.equal(h.calls.length, 1);
});

test("malformed reviewed knowledge is rejected without search fallback", async () => {
  const h = harness(async () => ({ok: true, json: async () => ({
    mode: "grounded_extractive_v1", status: "no_supported_answer", answer: "Unsupported.",
    citations: [], reviewed_knowledge: [{object_kind: "claim", object_id: "bad",
      title: "private", excerpt: "private", evidence_ids: [], linked_evidence_count: 0}],
    coverage: {complete: false}, untrusted_content: true,
  })}));
  h.enterToken("owner-token");
  await h.ask("insurance");
  assert.deepEqual(h.calls.map(call => call.url), ["/v1/brain/answers"]);
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Answer unavailable/);
});

test("malformed answer is rejected and never falls back to search", async () => {
  const h = harness(async () => ({ok: true, json: async () => ({
    mode: "grounded_extractive_v1", status: "quoted_evidence", answer: "unsupported",
    citations: [{evidence_id: "ev", quote: "invented"}], coverage: {complete: false},
    untrusted_content: true,
  })}));
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  assert.equal(h.calls.length, 1);
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Answer unavailable/);
});

test("malformed Ask context-budget flag is rejected", async () => {
  const h = harness(async () => ({ok: true, json: async () => ({
    mode: "grounded_extractive_v1", status: "no_supported_evidence",
    answer: "No supported answer from current indexed evidence.", citations: [],
    reviewed_knowledge: [], coverage: {complete: false, answer_context_truncated: "false"},
    untrusted_content: true,
  })}));
  h.enterToken("owner-token");
  await h.ask("insurance");
  assert.deepEqual(h.calls.map(call => call.url), ["/v1/brain/answers"]);
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Answer unavailable/);
});

test("Ask marks shortened output and rejects an oversized untrusted answer body", async () => {
  const hit = number => ({object_kind: "claim", object_id: `claim_${number.toString(16).padStart(32, "0")}`,
    title: "📄".repeat(300), excerpt: "📄".repeat(1200),
    evidence_ids: [`evidence_${number.toString(16).padStart(32, "0")}`], linked_evidence_count: 1});
  const response = {mode: "grounded_extractive_v1", status: "no_supported_answer",
    answer: "No exact source quote selected; reviewed knowledge matches are listed below.",
    citations: [], reviewed_knowledge: [hit(1)],
    coverage: {complete: false, answer_output_truncated: true}, untrusted_content: true};
  const h = harness(async () => ({ok: true, json: async () => response}));
  h.enterToken("owner-token");
  await h.ask("insurance");
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Answer results were shortened/);
  response.reviewed_knowledge = [hit(1), hit(2)];
  await h.ask("insurance");
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Answer unavailable/);
});

test("Ask validates Unicode code-point citation offsets and rejects lone surrogates", async () => {
  const response = {mode: "grounded_extractive_v1", status: "quoted_evidence",
    answer: "Relevant passages from current indexed evidence are quoted below.",
    citations: [{evidence_id: "evidence_" + "a".repeat(32), document_id: "document_" + "b".repeat(32),
      source_id: "trial_files", source_kind: "fileos", quote: "📄 proof", start: 3, end: 10,
      body_sha256: "a".repeat(64)}], reviewed_knowledge: [],
    coverage: {complete: false, answer_output_truncated: false}, untrusted_content: true};
  const h = harness(async () => ({ok: true, json: async () => response}));
  h.enterToken("owner-token");
  await h.ask("proof");
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /📄 proof/);
  response.citations[0].quote = "bad\ud800";
  response.citations[0].end = 7;
  await h.ask("proof");
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Answer unavailable/);
});

test("an answer denial does not silently search, but explicit Search only remains usable", async () => {
  const h = harness(async url => url === "/v1/brain/answers" ? {ok: false, status: 403} :
    {ok: true, json: async () => searchData()});
  h.enterToken("search-only-token");
  await h.ask("Cedar Harbor");
  assert.deepEqual(h.calls.map(call => call.url), ["/v1/brain/answers"]);
  assert.match(walk(h.elements.turns).map(item => item.textContent).join("\n"), /Request refused \(403\)/);
  await h.searchOnly("Cedar Harbor");
  assert.deepEqual(h.calls.map(call => call.url),
    ["/v1/brain/answers", "/v1/brain/current-search"]);
  assert.match(h.elements["brain-status"].textContent, /3 indexed results/);
});
