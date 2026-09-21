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
function response(data, status = 200) { return {ok: status >= 200 && status < 300, status, json: async () => data}; }
function descendants(element) {
  return element.children.flatMap((child) => child instanceof Element ? [child, ...descendants(child)] : []);
}
function button(element, text) {
  const found = descendants(element).find((child) => child.textContent === text && typeof child.onclick === "function");
  assert.ok(found, `missing button: ${text}`);
  return found;
}
function approvedRule() {
  return {id: "00000000-0000-4000-8000-000000000101", kind: "rule", status: "approved", version: 7,
    payload: {kind: "rule", sender_domain: "example.invalid", category: "investment", canonical_mailbox: "review"},
    reason: "Synthetic owner instruction"};
}
function simulation() {
  return {id: "00000000-0000-4000-8000-000000000102", expires_at: "2026-09-20T15:00:00Z",
    sample: [{subject: "Synthetic sample", category: "investment"}]};
}

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

test("approved rule simulation requires a separate explicit activation click", async () => {
  const calls = [];
  const proposal = approvedRule(), receipt = simulation();
  const app = harness(async (url, options) => {
    calls.push({url, method: options.method, body: options.body === undefined ? undefined : JSON.parse(options.body)});
    if (url === "/v1/proposals") return response({results: [proposal]});
    if (url === `/v1/proposals/${proposal.id}/simulation`) return response(receipt);
    if (url === "/v1/rules/activations") return response({revision: 3});
    if (url === "/v1/rules") return response({revision: 3, rules: [{category: "investment"}]});
    assert.fail(`unexpected request: ${url}`);
  });
  app.element("token").value = "synthetic-owner";
  await app.element("refresh").onclick();
  assert.equal(calls.length, 1, "loading approval must not simulate or activate");
  const preview = button(app.element("proposals"), "Preview rule on a bounded sample");
  await preview.onclick();
  assert.deepEqual(calls[1], {url: `/v1/proposals/${proposal.id}/simulation`, method: "POST", body: {expected_version: 7}});
  assert.equal(calls.length, 2, "simulation must not activate automatically");
  assert.equal(preview.disabled, true);
  const activate = button(app.element("proposals"), "Activate this rule — labels only");
  app.element("results").append("labels from old revision");
  await activate.onclick();
  assert.deepEqual(calls[2], {url: "/v1/rules/activations", method: "POST", body: {simulation_id: receipt.id}});
  assert.equal(calls[3].url, "/v1/rules");
  assert.equal(activate.disabled, true);
  assert.equal(app.element("results").children.length, 0);
  assert.match(app.element("status").textContent, /revision 3.*Mailbox unchanged/);
});

test("a late simulation after clearing the session reveals no sample or activation", async () => {
  const pending = deferred();
  const proposal = approvedRule();
  const calls = [];
  const app = harness(async (url) => {
    calls.push(url);
    if (url === "/v1/proposals") return response({results: [proposal]});
    if (url === `/v1/proposals/${proposal.id}/simulation`) return pending.promise;
    assert.fail("no activation or additional request permitted");
  });
  app.element("token").value = "old-owner";
  await app.element("refresh").onclick();
  const oldCard = app.element("proposals").children[0];
  const preview = button(app.element("proposals"), "Preview rule on a bounded sample");
  const work = preview.onclick();
  app.element("disconnect").onclick();
  app.element("token").value = "new-owner";
  pending.resolve(response(simulation()));
  await work;
  assert.equal(calls.length, 2);
  assert.equal(app.element("proposals").children.length, 0);
  assert.equal(app.element("rules").children.length, 0);
  assert.equal(preview.disabled, undefined);
  assert.ok(!descendants(oldCard).some((node) => node.textContent.includes("Synthetic sample")));
  assert.ok(!descendants(oldCard).some((node) => node.textContent.includes("Activate this rule")));
  assert.match(app.element("status").textContent, /Session changed/);
});

test("late simulation also cannot cross a credential edit", async () => {
  const pending = deferred();
  const app = harness(async (url) => url === "/v1/proposals"
    ? response({results: [approvedRule()]}) : pending.promise);
  app.element("token").value = "old-owner";
  await app.element("refresh").onclick();
  const work = button(app.element("proposals"), "Preview rule on a bounded sample").onclick();
  app.element("token").value = "new-owner";
  app.element("token").oninput();
  pending.resolve(response(simulation()));
  await work;
  assert.equal(app.element("proposals").children.length, 0);
  assert.equal(app.element("rules").children.length, 0);
});

test("active rules refresh is read-only and rollback binds the displayed revision", async () => {
  const calls = [];
  let revision = 4;
  const app = harness(async (url, options) => {
    const body = options.body === undefined ? undefined : JSON.parse(options.body);
    calls.push({url, method: options.method, body});
    if (url === "/v1/rules") return response({revision, rules: [{category: "business"}]});
    if (url === "/v1/rules/rollback") { revision = 5; return response({revision}); }
    assert.fail(`unexpected request: ${url}`);
  });
  await app.element("rules-refresh").onclick();
  assert.deepEqual(calls, [{url: "/v1/rules", method: "GET", body: undefined}]);
  app.element("results").append("old virtual labels");
  await button(app.element("rules"), "Restore revision 3 labels").onclick();
  assert.deepEqual(calls[1], {url: "/v1/rules/rollback", method: "POST", body: {expected_revision: 4, target_revision: 3}});
  assert.equal(calls[2].url, "/v1/rules");
  assert.equal(app.element("results").children.length, 0);
  assert.ok(button(app.element("rules"), "Restore revision 4 labels"));
  assert.match(app.element("status").textContent, /revision 5.*Mailbox unchanged/);
});

test("revision zero has no rollback button", async () => {
  const app = harness(async () => response({revision: 0, rules: []}));
  await app.element("rules-refresh").onclick();
  assert.ok(!descendants(app.element("rules")).some((node) => typeof node.onclick === "function"));
});

test("stale rollback sends its original expected revision and does not retry a conflict", async () => {
  const calls = [];
  let revision = 2;
  const app = harness(async (url, options) => {
    calls.push({url, body: options.body === undefined ? undefined : JSON.parse(options.body)});
    if (url === "/v1/rules") return response({revision, rules: []});
    if (url === "/v1/rules/rollback") return response({detail: "revision conflict"}, 409);
    assert.fail(`unexpected request: ${url}`);
  });
  await app.element("rules-refresh").onclick();
  const stale = button(app.element("rules"), "Restore revision 1 labels");
  revision = 3;
  await app.element("rules-refresh").onclick();
  await stale.onclick();
  assert.deepEqual(calls[2], {url: "/v1/rules/rollback", body: {expected_revision: 2, target_revision: 1}});
  assert.equal(calls.length, 3, "conflicts must not silently retry against a newer revision");
  assert.ok(button(app.element("rules"), "Restore revision 2 labels"));
  assert.match(app.element("status").textContent, /Request failed \(409\)/);
});

test("late active-rule refresh cannot reveal labels after clearing a session", async () => {
  const pending = deferred();
  const app = harness(() => pending.promise);
  app.element("token").value = "old-owner";
  const work = app.element("rules-refresh").onclick();
  app.element("disconnect").onclick();
  pending.resolve(response({revision: 8, rules: [{category: "private label"}]}));
  await work;
  assert.equal(app.element("rules").children.length, 0);
});

test("disconnect clears rules, form text, and the previous review-delete choice", () => {
  const app = harness(() => assert.fail("disconnect must not request anything"));
  for (const id of ["results", "proposals", "import-health", "quarantine", "rules"]) app.element(id).append("private");
  const fields = ["token", "query", "account-id", "project-name", "project-reason", "rule-domain", "rule-category", "rule-reason"];
  for (const id of fields) app.element(id).value = "private value";
  app.element("rule-mailbox").value = "review_delete";
  app.element("disconnect").onclick();
  for (const id of fields) assert.equal(app.element(id).value, "", `${id} retained private form text`);
  for (const id of ["results", "proposals", "import-health", "quarantine", "rules"]) assert.equal(app.element(id).children.length, 0);
  assert.equal(app.element("rule-mailbox").value, "review", "virtual label must reset to safe default");
});

test("rule simulation and active-rule contents render as text, not HTML", async () => {
  const payload = "<img src=x onerror=steal()>";
  const app = harness(async (url) => {
    if (url === "/v1/proposals") return response({results: [approvedRule()]});
    if (url === "/v1/rules") return response({revision: 1, rules: [{category: payload}]});
    return response({...simulation(), sample: [{subject: payload}]});
  });
  await app.element("refresh").onclick();
  await button(app.element("proposals"), "Preview rule on a bounded sample").onclick();
  await app.element("rules-refresh").onclick();
  const rendered = [...descendants(app.element("proposals")), ...descendants(app.element("rules"))]
    .filter((node) => node.textContent.includes(payload));
  assert.equal(rendered.length, 2);
  for (const node of rendered) assert.equal(node.innerHTML, undefined);
});

const heldAccount = "00000000-0000-4000-8000-000000000201";
const heldReceipt = "00000000-0000-4000-8000-000000000202";
const heldPath = `/v1/accounts/${heldAccount}/quarantine`;
const retryPath = `${heldPath}/${heldReceipt}/retry`;
function heldPage(extra = {}) {
  return {results: [{id: heldReceipt, provider_id: "synthetic-source", parser_version: "old-parser",
    reason: "mime_rejected", raw_sha256: "a".repeat(64)}], next_after: null,
    reprocessing: true, retry_parser_version: "current-parser", ...extra};
}
function importHealth() { return {message_counts: {ready: 1, quarantined: 0, deleted: 0}, worker: null}; }
function retryOutcome(outcome = "recovered") {
  return {historical_outcome: true, outcome, mailbox_effects: false, evidence_id: "synthetic-evidence"};
}
async function prepareHeld(app) {
  app.element("token").value = "synthetic-owner";
  app.element("account-id").value = heldAccount;
  await app.evaluate(`heldMessages('${heldAccount}')`);
  return button(app.element("quarantine"), "Retry parsing");
}

test("held-message retry requires an explicit click and binds receipt, account and displayed parser", async () => {
  const calls = [];
  let retried = false;
  const app = harness(async (url, options) => {
    calls.push({url, method: options.method, body: options.body === undefined ? undefined : JSON.parse(options.body)});
    if (url === heldPath) return response(heldPage(retried ? {results: []} : {}));
    if (url === retryPath) { retried = true; return response(retryOutcome()); }
    if (url.endsWith("/sync-status")) return response(importHealth());
    assert.fail(`unexpected request: ${url}`);
  });
  const retry = await prepareHeld(app);
  assert.equal(calls.length, 1, "review must not automatically retry");
  assert.ok(descendants(app.element("quarantine")).some((n) => /No mailbox changes.*cached/.test(n.textContent)));
  app.element("results").append("outdated search results");
  await retry.onclick();
  assert.deepEqual(calls[1], {url: retryPath, method: "POST", body: {expected_parser_version: "current-parser"}});
  assert.deepEqual(calls.slice(2).map((c) => c.url), [`/v1/accounts/${heldAccount}/sync-status`, heldPath]);
  assert.equal(app.element("quarantine").children.length, 0);
  assert.equal(app.element("results").children.length, 0);
  assert.match(app.element("status").textContent, /Historical retry outcome: recovered.*current state.*Mailbox unchanged/);
});

test("legacy or unsupported quarantine responses expose no retry control", async () => {
  for (const extra of [{reprocessing: false}, {retry_parser_version: null}, {retry_parser_version: ""}]) {
    const app = harness(async () => response(heldPage(extra)));
    app.element("account-id").value = heldAccount;
    await app.evaluate(`heldMessages('${heldAccount}')`);
    assert.ok(!descendants(app.element("quarantine")).some((n) => typeof n.onclick === "function"));
  }
});

test("recovery failures stay held, refresh current status, and explain cached outcomes without raw content", async () => {
  for (const outcome of ["mime_rejected", "integrity_failed"]) {
    const calls = [];
    const app = harness(async (url) => {
      calls.push(url);
      if (url === heldPath) return response(heldPage());
      if (url === retryPath) return response({...retryOutcome(outcome), raw_mime: "PRIVATE RAW", exception: "PRIVATE EXCEPTION"});
      return response(importHealth());
    });
    await (await prepareHeld(app)).onclick();
    assert.equal(app.element("quarantine").children.length, 1);
    assert.deepEqual(calls, [heldPath, retryPath, `/v1/accounts/${heldAccount}/sync-status`, heldPath]);
    const text = app.element("status").textContent;
    assert.match(text, /Historical retry outcome:.*cached.*Mailbox unchanged/);
    assert.ok(!text.includes("PRIVATE"));
    if (outcome === "integrity_failed") assert.match(text, /Operator review is required/);
    else assert.match(text, /parser upgrade/);
  }
});

test("recovery 403, 409 and 503 errors are generic and never trigger automatic retries", async () => {
  for (const code of [403, 409, 503]) {
    const calls = [];
    const app = harness(async (url) => {
      calls.push(url);
      return url === heldPath ? response(heldPage()) : response({detail: "PRIVATE EXCEPTION"}, code);
    });
    const retry = await prepareHeld(app);
    await retry.onclick();
    assert.deepEqual(calls, [heldPath, retryPath]);
    assert.equal(retry.disabled, false);
    assert.match(app.element("status").textContent, new RegExp(`Request failed \\(${code}\\)`));
    assert.ok(!app.element("status").textContent.includes("PRIVATE"));
  }
});

test("a pending retry ignores double clicks and does not refresh after credentials change", async () => {
  const pending = deferred(), calls = [];
  const app = harness(async (url) => { calls.push(url); return url === heldPath ? response(heldPage()) : pending.promise; });
  const retry = await prepareHeld(app);
  const work = retry.onclick();
  assert.equal(retry.disabled, true);
  await retry.onclick();
  app.element("token").value = "new-owner";
  app.element("token").oninput();
  pending.resolve(response(retryOutcome()));
  await work;
  assert.deepEqual(calls, [heldPath, retryPath]);
  assert.equal(app.element("quarantine").children.length, 0);
  assert.equal(app.element("import-health").children.length, 0);
  assert.match(app.element("status").textContent, /Session changed/);
});

test("a pending retry ignores switching accounts away and back", async () => {
  const pending = deferred(), calls = [];
  const app = harness(async (url) => { calls.push(url); return url === heldPath ? response(heldPage()) : pending.promise; });
  const retry = await prepareHeld(app);
  const work = retry.onclick();
  app.element("account-id").value = "other-account"; app.element("account-id").oninput();
  app.element("account-id").value = heldAccount; app.element("account-id").oninput();
  pending.resolve(response(retryOutcome()));
  await work;
  assert.deepEqual(calls, [heldPath, retryPath]);
  assert.equal(app.element("quarantine").children.length, 0);
  assert.equal(app.element("import-health").children.length, 0);
  assert.ok(!app.element("status").textContent.includes("recovered"));
});

test("a retry control from an old review context cannot issue a request", async () => {
  const calls = [];
  const app = harness(async (url) => { calls.push(url); return response(heldPage()); });
  const retry = await prepareHeld(app);
  app.element("disconnect").onclick();
  app.element("token").value = "new-owner";
  app.element("account-id").value = heldAccount;
  await retry.onclick();
  assert.deepEqual(calls, [heldPath]);
  assert.match(app.element("status").textContent, /Review context changed/);
});

test("recovery refresh cannot reveal results after disconnect", async () => {
  const pending = deferred(), calls = [];
  const refreshStarted = deferred();
  const app = harness(async (url) => {
    calls.push(url);
    if (url === heldPath) return response(heldPage());
    if (url === retryPath) return response(retryOutcome());
    refreshStarted.resolve(); return pending.promise;
  });
  const retry = await prepareHeld(app);
  const work = retry.onclick();
  await refreshStarted.promise;
  app.element("disconnect").onclick();
  pending.resolve(response(importHealth()));
  await work;
  assert.deepEqual(calls, [heldPath, retryPath, `/v1/accounts/${heldAccount}/sync-status`]);
  assert.equal(app.element("quarantine").children.length, 0);
  assert.equal(app.element("import-health").children.length, 0);
  assert.ok(!app.element("status").textContent.includes("recovered"));
});

test("unknown recovery response fields never render as success or raw text", async () => {
  const calls = [];
  const app = harness(async (url) => {
    calls.push(url);
    return url === heldPath ? response(heldPage()) : response({...retryOutcome(), outcome: "<script>PRIVATE</script>"});
  });
  await (await prepareHeld(app)).onclick();
  assert.deepEqual(calls, [heldPath, retryPath]);
  assert.equal(app.element("status").textContent, "Unexpected retry response. Refresh the queue.");
});

test("same-account refresh supersedes an older import response", async () => {
  const pending = deferred();
  let reads = 0;
  const app = harness(async (url) => {
    if (url === heldPath) return response(heldPage({results: []}));
    return ++reads === 1 ? pending.promise : response(importHealth());
  });
  app.element("account-id").value = heldAccount;
  const old = app.evaluate("loadImport()");
  await app.evaluate("loadImport()");
  pending.resolve(response({message_counts: {ready: 999, quarantined: 999, deleted: 999}, worker: null}));
  await old;
  assert.ok(!descendants(app.element("import-health")).some((n) => n.textContent.includes("999")));
});
