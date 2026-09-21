"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {webcrypto, createHash} = require("node:crypto");
const {harness, Element, deferred, response, descendants, button} = require("./web_harness.cjs");
const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const EVIDENCE = id(1), MESSAGE = id(2), ACCOUNT = id(3), RECEIPT = id(4);
const raw = Buffer.from("fictional original email"), partBytes = Buffer.from("fictional part");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
function hit() { return {id: MESSAGE, evidence_id: EVIDENCE, account_id: ACCOUNT, result_type: "message",
  subject: "Fictional reader", sender: "alice@example.invalid", excerpt: "Readerproof"}; }
function part() { return {id: RECEIPT, part_id: "1.2", safe_filename: "costs.csv", media_type: "text/csv",
  sha256: sha(partBytes), byte_size: partBytes.length, status: "extracted", reason: "bounded_text_v1",
  scanner_status: "not_scanned", download_available: true}; }
function message(extra = {}) { return {id: EVIDENCE, message_id: MESSAGE, account_id: ACCOUNT,
  raw_sha256: sha(raw), raw_size: raw.length, subject: "Fictional reader", sender: "alice@example.invalid",
  received_at: "2026-09-21T12:00:00+00:00", body: "<script>inert</script>\n" + "x".repeat(130000) + " FINALTAIL 😀",
  body_source: "original_mime", body_complete: true, headers: [{name: "From", value: "Alice <alice@example.invalid>"}],
  headers_truncated: false, attachments: [part()], untrusted_content: true, mailbox_effects: false, ...extra}; }
function download(bytes = raw, filename = `message-${EVIDENCE}.eml`, headers = {}) {
  return new Response(bytes, {headers: {"Content-Type": "application/octet-stream", "Content-Length": String(bytes.length),
    "Content-Disposition": `attachment; filename="${filename}"`, "X-Content-SHA256": sha(bytes), ...headers}});
}
function scenario(override = () => undefined) {
  const calls = [], saved = [], revoked = [], timers = [];
  const app = harness(async (url, options) => {
    calls.push({url, options});
    const custom = override(url, options);
    if (custom !== undefined) return custom;
    if (url === "/v1/search") return response({mode: "lexical", untrusted_content: true, results: [hit()]});
    if (url === `/v1/reader/${EVIDENCE}`) return response(message());
    if (url.endsWith("/original")) return download();
    if (url.endsWith(`/attachments/${RECEIPT}`)) return download(partBytes, `attachment-${RECEIPT}.bin`);
    assert.fail(`unexpected request ${url}`);
  }, {crypto: webcrypto, Blob, Uint8Array, URL: {
    createObjectURL(blob) { saved.push(blob); return `blob:synthetic-${saved.length}`; },
    revokeObjectURL(url) { revoked.push(url); },
  }, setTimeout(fn) { timers.push(fn); }});
  // Click is observed independently of browser download acceptance.
  Element.prototype.click = function () { this.clicked = true; };
  app.element("token").value = "synthetic-owner";
  app.element("query").value = "Readerproof";
  return {app, calls, saved, revoked, timers};
}
async function open(app) {
  await app.element("search-form").onsubmit({preventDefault() {}});
  await button(app.element("results"), "Read email").onclick();
}
function consent(app) {
  const box = descendants(app.element("message-reader-content")).find((n) => n.type === "checkbox");
  assert.ok(box); box.checked = true; box.onchange();
  return box;
}
const view = (app) => app.element("message-reader-content");

test("reader displays complete long text safely, with no automatic download", async () => {
  const {app, calls, saved} = scenario(); await open(app);
  assert.match(view(app).textContent, /FINALTAIL 😀/);
  assert.match(view(app).textContent, /<script>inert<\/script>/);
  assert.equal(descendants(view(app)).some((e) => ["SCRIPT", "IMG", "IFRAME"].includes(e.tagName)), false);
  assert.equal(saved.length, 0); assert.equal(calls.length, 2);
  const exportButton = button(view(app), "Download original email (.eml)");
  assert.equal(exportButton.disabled, true);
  await exportButton.onclick(); assert.equal(calls.length, 2);
});

for (const which of ["original", "attachment"]) test(`${which} download is explicit, hash-checked, temporary and inert`, async () => {
  const {app, calls, saved, revoked} = scenario(); await open(app); consent(app);
  await button(view(app), which === "original" ? "Download original email (.eml)" : "Download attachment (.bin)").onclick();
  assert.equal(saved.length, 1);
  assert.equal(saved[0].type, "application/octet-stream");
  assert.deepEqual(Buffer.from(await saved[0].arrayBuffer()), which === "original" ? raw : partBytes);
  const request = calls.at(-1).options;
  assert.equal(request.method, "POST"); assert.equal(request.credentials, "omit");
  assert.equal(request.cache, "no-store");
  assert.deepEqual(JSON.parse(request.body), {acknowledge_unscanned: true});
  const link = descendants(view(app)).find((e) => e.tagName === "A");
  assert.ok(link); assert.equal(link.clicked, undefined);
  link.onclick({preventDefault() { assert.fail("current save rejected"); }});
  assert.match(app.element("status").textContent, /Save requested/);
  app.element("message-reader-close").onclick();
  assert.deepEqual(revoked, ["blob:synthetic-1"]);
  let prevented = false; link.onclick({preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
});

for (const mutate of [
  (d) => { d.account_id = id(99); }, (d) => { d.id = id(99); }, (d) => { d.message_id = id(99); },
  (d) => { d.body_complete = false; }, (d) => { d.body_source = "html"; },
  (d) => { d.raw_size = 16777217; }, (d) => { d.mailbox_effects = true; },
  (d) => { d.untrusted_content = false; }, (d) => { d.headers.push({name: "X", value: "x".repeat(4001)}); },
  (d) => { d.attachments.push({...d.attachments[0]}); }, (d) => { d.attachments[0].scanner_status = "safe"; },
  (d) => { d.attachments[0].download_available = "true"; }, (d) => { d.extra = true; },
]) test(`invalid reader envelope ${mutate.toString()} is not rendered`, async () => {
  const data = message(); mutate(data);
  const {app} = scenario((url) => url === `/v1/reader/${EVIDENCE}` ? response(data) : undefined);
  await open(app); assert.equal(view(app).textContent, "");
  assert.equal(app.element("message-reader").hidden, true);
});

test("large projection is clearly labeled and does not offer per-part download", async () => {
  const data = message({raw_size: 2000000, body: "Stored excerpt", body_source: "stored_projection", body_complete: false,
    headers: [], headers_truncated: true, attachments: [{...part(), download_available: false}]});
  const {app} = scenario((url) => url === `/v1/reader/${EVIDENCE}` ? response(data) : undefined);
  await open(app); assert.match(view(app).textContent, /truncated/);
  assert.match(view(app).textContent, /Download the original/);
  assert.equal(descendants(view(app)).some((e) => e.textContent === "Download attachment (.bin)"), false);
});

for (const change of ["token", "query", "account", "close"]) test(`late reader response after ${change} is discarded`, async () => {
  const pending = deferred();
  const {app} = scenario((url) => url === `/v1/reader/${EVIDENCE}` ? pending.promise : undefined);
  const run = open(app); await new Promise(setImmediate);
  if (change === "token") { app.element("token").value = "new-owner"; app.element("token").oninput(); }
  if (change === "query") { app.element("query").value = "new-query"; app.element("query").oninput(); }
  if (change === "account") { app.element("account-id").value = id(99); app.element("account-id").oninput(); }
  if (change === "close") app.element("message-reader-close").onclick();
  pending.resolve(response(message())); await run;
  assert.equal(view(app).textContent, "");
});

test("detached download button cannot fetch after account or session changes", async () => {
  const {app, calls} = scenario(); await open(app); consent(app);
  const old = button(view(app), "Download original email (.eml)");
  app.element("token").value = "new-owner"; app.element("token").oninput();
  await old.onclick(); assert.equal(calls.length, 2);
});

test("late download is discarded and its response body cancelled", async () => {
  const pending = deferred(); let cancelled = false;
  const {app, saved} = scenario((url) => url.endsWith("/original") ? pending.promise : undefined);
  await open(app); consent(app);
  const run = button(view(app), "Download original email (.eml)").onclick();
  app.element("message-reader-close").onclick();
  pending.resolve({body: {cancel: async () => { cancelled = true; }}});
  await run; assert.equal(saved.length, 0); assert.equal(cancelled, true);
});

for (const mode of ["hash", "length", "type", "disposition", "bytes", "truncated", "excess", "denied"]) {
  test(`download rejects ${mode} failure`, async () => {
    const headers = {};
    if (mode === "hash") headers["X-Content-SHA256"] = "0".repeat(64);
    if (mode === "length") headers["Content-Length"] = "16777217";
    if (mode === "type") headers["Content-Type"] = "text/html";
    if (mode === "disposition") headers["Content-Disposition"] = "inline";
    let bytes = raw;
    if (mode === "bytes") bytes = Buffer.alloc(raw.length, 120);
    if (mode === "truncated") bytes = raw.subarray(0, 3);
    if (mode === "excess") bytes = Buffer.concat([raw, raw]);
    if (["bytes", "truncated", "excess"].includes(mode)) {
      headers["X-Content-SHA256"] = sha(raw); headers["Content-Length"] = String(raw.length);
    }
    const {app, saved} = scenario((url) => url.endsWith("/original")
      ? mode === "denied" ? new Response("denied", {status: 403}) : download(bytes, `message-${EVIDENCE}.eml`, headers) : undefined);
    await open(app); consent(app);
    await button(view(app), "Download original email (.eml)").onclick();
    assert.equal(saved.length, 0);
    if (mode === "denied") assert.equal(view(app).textContent, "");
  });
}

test("only one export request at a time and consent can be disabled", async () => {
  const pending = deferred();
  const {app, calls} = scenario((url) => url.endsWith("/original") ? pending.promise : undefined);
  await open(app); const box = consent(app);
  const original = button(view(app), "Download original email (.eml)");
  const other = button(view(app), "Download attachment (.bin)");
  const run = original.onclick(); await other.onclick(); assert.equal(calls.length, 3);
  pending.resolve(download()); await run;
  box.checked = false; box.onchange(); await other.onclick(); assert.equal(calls.length, 3);
});

for (const change of ["consent", "token", "query", "account"]) test(`prepared save link is revoked after ${change}`, async () => {
  const {app, revoked} = scenario(); await open(app); const box = consent(app);
  await button(view(app), "Download original email (.eml)").onclick();
  const old = descendants(view(app)).find((e) => e.tagName === "A"); assert.ok(old);
  if (change === "consent") { box.checked = false; box.onchange(); }
  if (change === "token") { app.element("token").value = "other"; app.element("token").oninput(); }
  if (change === "query") app.element("query").oninput();
  if (change === "account") { app.element("account-id").value = id(99); app.element("account-id").oninput(); }
  assert.deepEqual(revoked, ["blob:synthetic-1"]);
  assert.equal(descendants(view(app)).some((e) => e.tagName === "A"), false);
  let prevented = false; old.onclick({preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
});

test("a new verified file replaces the prior temporary link", async () => {
  const {app, saved, revoked} = scenario(); await open(app); consent(app);
  await button(view(app), "Download original email (.eml)").onclick();
  const old = descendants(view(app)).find((e) => e.tagName === "A");
  await button(view(app), "Download attachment (.bin)").onclick();
  assert.equal(saved.length, 2); assert.deepEqual(revoked, ["blob:synthetic-1"]);
  assert.equal(descendants(view(app)).filter((e) => e.tagName === "A").length, 1);
  let prevented = false; old.onclick({preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
});

test("withdrawn consent during a request never prepares a save link", async () => {
  const pending = deferred();
  const {app, saved} = scenario((url) => url.endsWith("/original") ? pending.promise : undefined);
  await open(app); const box = consent(app);
  const run = button(view(app), "Download original email (.eml)").onclick();
  box.checked = false; box.onchange(); pending.resolve(download()); await run;
  assert.equal(saved.length, 0);
  assert.equal(descendants(view(app)).some((e) => e.tagName === "A"), false);
});
