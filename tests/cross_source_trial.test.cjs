"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "cross_source_assets/trial.js"), "utf8");
class Element {
  constructor(tag) {this.tag = tag; this.children = []; this.events = {}; this.dataset = {}; this.value = ""; this.textContent = "";}
  appendChild(node) {this.children.push(node); return node;}
  replaceChildren(...nodes) {this.children = nodes;}
  addEventListener(event, fn) {this.events[event] = fn;}
  set innerHTML(value) {throw new Error("Source HTML execution is forbidden");}
}
function harness(token = "a".repeat(54), customFetch) {
  const nodes = {};
  for (const id of ["status", "results", "evidence", "query", "coverage", "freshness", "search-form", "search-button"]) nodes[id] = new Element(id);
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
      const body = url === "/v1/brain/current-search" ? data : {text: "Insurance outstanding", complete: false};
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
  assert.match(h.nodes.status.textContent, /credential missing/);
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
  assert.match(h.nodes.evidence.children[1].textContent, /Insurance outstanding/);
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
