"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../src/masterbrain/web/brain.js"), "utf8");
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
function walk(element) { return [element, ...element.children.flatMap(walk)]; }
const flush = async () => { for (let i = 0; i < 6; i++) await new Promise(resolve => setImmediate(resolve)); };
function harness(customFetch) {
  const ids = ["brain-token", "brain-question", "ask-button", "turns", "brain-status",
    "ask-form", "clear-session", "clear-turns"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(id)]));
  const calls = [];
  vm.runInNewContext(script, {
    document: {getElementById: id => elements[id], createElement: tag => new Element(tag)},
    fetch: async (url, options) => {
      calls.push({url, options});
      if (customFetch) return customFetch(url, options);
      const value = url === "/v1/brain/current-search" ? searchData() :
        url.endsWith("/content") ? {evidence_id: "ev_email", content: "<script>untrusted</script>", truncated: false} :
          {id: "ev_email", source_kind: "email", observed_at: "2026-09-24", sha256: "a".repeat(64)};
      return {ok: true, status: 200, json: async () => value};
    },
    AbortController, setTimeout, clearTimeout,
  });
  const enterToken = value => { elements["brain-token"].value = value; elements["brain-token"].events.input(); };
  const ask = async value => {
    elements["brain-question"].value = value;
    await elements["ask-form"].events.submit({preventDefault() {}});
    await flush();
  };
  return {elements, calls, enterToken, ask};
}

test("static shell makes no request and refuses a missing credential", async () => {
  const h = harness();
  assert.equal(h.calls.length, 0);
  assert.equal(h.elements["ask-button"].disabled, true);
  await h.ask("Cedar Harbor");
  assert.equal(h.calls.length, 0);
});

test("read-only conversation uses the scoped API and renders hostile content as text", async () => {
  const h = harness();
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, "/v1/brain/current-search");
  assert.equal(JSON.parse(h.calls[0].options.body).query, "Cedar Harbor");
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

test("evidence metadata and text use separate authorized calls; denied text stays hidden", async () => {
  const h = harness(async url => {
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
  const h = harness(async () => ({ok: true, json: async () =>
    ({mode: "grouped_current_sources", layers: {fileos: []}, coverage: {complete: false}})}));
  h.enterToken("owner-token");
  await h.ask("Cedar Harbor");
  const rendered = walk(h.elements.turns).map(item => item.textContent).join("\n");
  assert.match(rendered, /Search unavailable/);
  assert.doesNotMatch(rendered, /Partial coverage/);
});

test("changing the credential clears content and prevents a late response from returning", async () => {
  let release;
  const h = harness(async url => {
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
