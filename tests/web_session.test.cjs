"use strict";
// Standard-library DOM contract harness, not a real browser/accessibility test.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class Element {
  constructor() { this.children = []; this.value = ""; this.textContent = ""; this.hidden = false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
}
function harness(fetch) {
  const elements = new Map();
  const element = (id) => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({document: {getElementById: element, createElement: () => new Element()}, fetch});
  const source = fs.readFileSync(path.join(__dirname, "../src/email_brain/web/app.js"), "utf8");
  vm.runInContext(source, context);
  return {element, evaluate: (code) => vm.runInContext(code, context)};
}
function deferred() { let resolve; const promise = new Promise((done) => { resolve = done; }); return {promise, resolve}; }

test("clearing session rejects an in-flight private response", async () => {
  const pending = deferred();
  const app = harness(() => pending.promise);
  app.element("token").value = "old-secret";
  const request = app.evaluate("api('/v1/search', 'POST', {query:'synthetic'})");
  app.element("disconnect").onclick();
  pending.resolve({ok: true, json: async () => ({results: ["private evidence"]})});
  await assert.rejects(request, /Session changed/);
  assert.equal(app.element("token").value, "");
  assert.equal(app.element("results").children.length, 0);
});

test("editing a credential clears visible evidence and review state", () => {
  const app = harness(() => assert.fail("no request expected"));
  for (const id of ["results", "proposals", "import-health", "quarantine"]) app.element(id).append("private");
  app.element("token").oninput();
  for (const id of ["results", "proposals", "import-health", "quarantine"]) assert.equal(app.element(id).children.length, 0);
  assert.equal(app.element("quarantine-more").hidden, true);
});

test("mail markup is assigned as text, never HTML", () => {
  const app = harness(() => assert.fail("no request expected"));
  const node = app.evaluate("node('p', '<img src=x onerror=steal()>')");
  assert.equal(node.textContent, "<img src=x onerror=steal()>");
  assert.equal(node.innerHTML, undefined);
});

test("switching accounts discards a late quarantine page", async () => {
  const pending = deferred();
  const app = harness(() => pending.promise);
  app.element("account-id").value = "old-account";
  const request = app.evaluate("heldMessages('old-account')");
  app.element("account-id").value = "new-account";
  app.element("account-id").oninput();
  pending.resolve({ok: true, json: async () => ({results: [{provider_id: "old-data"}], next_after: "next"})});
  await request;
  assert.equal(app.element("quarantine").children.length, 0);
  assert.equal(app.element("quarantine-more").hidden, true);
});

test("invalid account IDs cannot become API paths", async () => {
  const app = harness(() => assert.fail("no request expected"));
  app.element("account-id").value = "../../other/path";
  await assert.rejects(app.evaluate("loadImport()"), /valid account ID/);
});

test("API omits cookies and browser caching", async () => {
  const app = harness(async (url, options) => {
    assert.equal(url, "/v1/search");
    assert.equal(options.credentials, "omit");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers.Authorization, "Bearer scoped-token");
    return {ok: true, json: async () => ({results: []})};
  });
  app.element("token").value = "scoped-token";
  await app.evaluate("api('/v1/search')");
});
