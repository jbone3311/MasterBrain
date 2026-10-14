"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "cross_source_assets/trial.js"), "utf8");
class Element {
  constructor(tag) {this.tag = tag; this.children = []; this.events = {}; this.dataset = {}; this.value = ""; this.textContent = ""; this.attributes = {};}
  appendChild(node) {this.children.push(node); return node;}
  replaceChildren(...nodes) {this.children = nodes;}
  addEventListener(event, fn) {this.events[event] = fn;}
  setAttribute(name, value) {this.attributes[name] = value;}
  set innerHTML(value) {throw new Error("Source HTML execution is forbidden");}
}
function harness(token = "a".repeat(54), customFetch) {
  const nodes = {};
  for (const id of ["status", "results", "evidence", "query", "coverage", "freshness", "search-form", "search-button", "access-toggle", "access-code", "statement-button", "statement"]) nodes[id] = new Element(id);
  nodes["access-toggle"].disabled = true;
  nodes["statement-button"].disabled = true;
  nodes["access-code"].hidden = true;
  nodes.query.value = "Cedar Harbor";
  const examples = ["insurance", "nonexistentcanary"].map(query => {const e = new Element("button"); e.dataset.query = query; return e;});
  const calls = [];
  const replacements = [];
  const data = {layers: {email_messages: [{evidence_id: "ev_email", excerpt: "<script>untrusted text</script>"}], fileos: [{evidence_id: "ev_file", locator: "cedar.txt", excerpt: "Insurance outstanding"}]}, coverage: {complete: false}};
  vm.runInNewContext(script, {
    location: {hash: "#" + token, pathname: "/trial"},
    history: {replaceState: (...args) => replacements.push(args)},
    document: {getElementById: id => nodes[id], createElement: tag => new Element(tag), querySelectorAll: () => examples},
    fetch: async (url, options) => {
      calls.push({url, options});
      if (customFetch) return customFetch(url, options, data);
      const body = url === "/v1/brain/current-search" ? data :
        url.endsWith("/content") ? {evidence_id: "ev_email", content: "Insurance outstanding", truncated: false} :
          {id: "ev_email", source_kind: "email"};
      return {ok: true, status: 200, json: async () => body};
    },
  });
  return {nodes, calls, replacements, examples};
}
const flush = async () => {for (let n = 0; n < 5; n++) await new Promise(resolve => setImmediate(resolve));};
test("missing fragment never makes an initial authenticated request", async () => {
  const h = harness(""); await flush();
  assert.equal(h.calls.length, 0);
  assert.equal(h.nodes["search-button"].disabled, true);
  assert.equal(h.nodes["access-toggle"].disabled, true);
  assert.equal(h.nodes["statement-button"].disabled, true);
  assert.equal(h.nodes["access-code"].textContent, "");
  assert.match(h.nodes.status.textContent, /credential missing/);
});
test("fictional proposal is fetched only on click and renders source text inertly", async () => {
  const id = "stmt_fictional123";
  const h = harness("a".repeat(54), async (url, _options, data) => {
    const body = url === "/v1/brain/current-search" ? data :
      url === "/trial/statement-id" ? {proposal_id: id} :
      url.endsWith(id) ? {
        proposal_id: id, source_id: "trial_files", source_kind: "fileos", source_current: true,
        reviewed: false, source_effects: false, row_count: 1, status: "reconciled",
        reconciliation: {delta: "0"}, page: {next_after: null, truncated: false},
        rows: [{ordinal: 0, assertion_status: "proposed_extraction", description: "<script>fictional</script>",
          quote: "<img src=x onerror=alert(1)>", quote_truncated: false}],
      } : {};
    return {ok: true, json: async () => body};
  });
  await flush();
  assert.equal(h.calls.some(call => call.url.includes("statement")), false);
  assert.equal(h.nodes["statement-button"].disabled, false);
  await h.nodes["statement-button"].events.click(); await flush();
  assert.deepEqual(h.calls.filter(call => call.url.includes("statement")).map(call => call.url),
    ["/trial/statement-id", `/v1/knowledge/statement-proposals/${id}`]);
  assert.equal(h.nodes.statement.children[1].textContent, "<script>fictional</script>");
  assert.equal(h.nodes.statement.children[2].textContent, "<img src=x onerror=alert(1)>");
});
test("incomplete proposal response never renders a row", async () => {
  const h = harness("a".repeat(54), async (url, _options, data) => ({ok: true, json: async () =>
    url === "/v1/brain/current-search" ? data :
      url === "/trial/statement-id" ? {proposal_id: "stmt_fictional123"} :
        {proposal_id: "stmt_fictional123", rows: [{quote: "private text"}]}}));
  await flush();
  await h.nodes["statement-button"].events.click(); await flush();
  assert.equal(h.nodes.statement.children.length, 1);
  assert.match(h.nodes.statement.children[0].textContent, /could not be verified/);
});
test("trial access code is visible only after explicit reveal and is cleared on hide", async () => {
  const token = "a".repeat(54);
  const h = harness(token); await flush();
  assert.equal(h.nodes["access-toggle"].disabled, false);
  assert.equal(h.nodes["access-code"].hidden, true);
  assert.equal(h.nodes["access-code"].textContent, "");
  h.nodes["access-toggle"].events.click();
  assert.equal(h.nodes["access-code"].hidden, false);
  assert.equal(h.nodes["access-code"].textContent, token);
  assert.equal(h.nodes["access-toggle"].attributes["aria-expanded"], "true");
  h.nodes["access-toggle"].events.click();
  assert.equal(h.nodes["access-code"].hidden, true);
  assert.equal(h.nodes["access-code"].textContent, "");
  assert.equal(h.nodes["access-toggle"].attributes["aria-expanded"], "false");
  assert.deepEqual(h.replacements[0], [null, "", "/trial"]);
});
test("search renders untrusted text and uses memory-only non-redirected authorization", async () => {
  const h = harness(); await flush();
  assert.equal(h.nodes.results.children.length, 2);
  assert.match(h.nodes.status.textContent, /2 results/);
  const card = h.nodes.results.children[0].children[1];
  assert.equal(card.children[1].textContent, "<script>untrusted text</script>");
  assert.equal(h.replacements[0][2], "/trial");
  for (const call of h.calls) {
    assert.equal(call.options.credentials, "omit");
    assert.equal(call.options.redirect, "error");
    assert.match(call.options.headers.Authorization, /^Bearer a+$/);
  }
  await card.children[2].events.click(); await flush();
  assert.ok(h.calls.some(call => call.url === "/v1/brain/evidence/ev_email"));
  const content = h.calls.find(call => call.url.endsWith("/content"));
  assert.deepEqual(JSON.parse(content.options.body), {max_chars: 4000});
  assert.equal(h.nodes.evidence.children[1].textContent, "Insurance outstanding");
  assert.equal(h.nodes.evidence.children[2].tag, "details");
});
test("mismatched evidence identity cannot be displayed as source text", async () => {
  const h = harness("a".repeat(54), async (url, _options, data) => {
    const body = url === "/v1/brain/current-search" ? data :
      url.endsWith("/content") ? {evidence_id: "another_evidence", content: "Not this source"} :
        {id: "ev_email", source_kind: "email"};
    return {ok: true, status: 200, json: async () => body};
  });
  await flush();
  const card = h.nodes.results.children[0].children[1];
  await card.children[2].events.click(); await flush();
  assert.match(h.nodes.evidence.children[0].textContent, /could not be verified/);
  assert.equal(h.nodes.evidence.children.length, 1);
});
test("late search responses cannot replace the newer result", async () => {
  let release;
  const h = harness("a".repeat(54), async (url, options, data) => {
    if (url === "/v1/brain/current-search" && JSON.parse(options.body).query === "Cedar Harbor") {
      return new Promise(resolve => {release = () => resolve({ok: true, json: async () => data});});
    }
    return {ok: true, json: async () => url === "/v1/brain/current-search" ? {layers: {email_messages: [], fileos: []}, coverage: {complete: false}} : {}};
  });
  await flush();
  h.examples[1].events.click(); await flush();
  assert.match(h.nodes.status.textContent, /^0 results/);
  release(); await flush();
  assert.match(h.nodes.status.textContent, /^0 results/);
});
