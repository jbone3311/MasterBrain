"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {harness, deferred, response, buttons, button} = require("./web_harness.cjs");

const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const ACCOUNT = id(401), RECEIPT = id(402), JOB = id(403), DOCUMENT = id(404), EVIDENCE = id(405), MESSAGE = id(406), OTHER = id(407);
const PROCESSOR = "sandbox-pdf-v1-" + "a".repeat(64), POLICY = "synthetic-unscanned-pdf-v1";
const ROOT = `/v1/accounts/${ACCOUNT}`, ENQUEUE = `${ROOT}/attachments/${RECEIPT}/jobs`;
const CREATED = "2026-09-21T10:00:00Z", EXPIRES = "2026-09-21T11:00:00Z", DONE = "2026-09-21T10:01:00Z";
function caps(extra = {}) {
  return {enabled: true, processor_version: PROCESSOR, policy_version: POLICY, scanner_status: "unscanned", worker_online: null, mailbox_effects: false, ...extra};
}
function job(extra = {}) {
  return {id: JOB, account_id: ACCOUNT, receipt_id: RECEIPT, processor_version: PROCESSOR, policy_version: POLICY,
    status: "queued", attempts: 0, created_at: CREATED, expires_at: EXPIRES, retry_at: null, completed_at: null,
    extraction_id: null, outcome: null, mailbox_effects: false, ...extra};
}
function completed(extra = {}) {
  return job({status: "completed", outcome: "result_saved", attempts: 1, completed_at: DONE, extraction_id: DOCUMENT, ...extra});
}
function history(results = [], extra = {}) { return {results, next_after: null, limit: 50, mailbox_effects: false, ...extra}; }
function hit(extra = {}) {
  return {id: MESSAGE, account_id: ACCOUNT, evidence_id: EVIDENCE, subject: "Fictional Melron", sender: "alex@example.invalid",
    excerpt: "See the attached fictional PDF.", result_type: "message", citation: `emailbrain://evidence/${EVIDENCE}`, ...extra};
}
function pdfHit(extra = {}) {
  return hit({result_type: "document", document_id: DOCUMENT, attachment_id: RECEIPT, safe_filename: "fictional.pdf",
    processor_version: PROCESSOR, policy_version: POLICY, revision: 1, status: "extracted", reason: "bounded_pdf_v1",
    scanner_status: "unscanned", untrusted_content: true, citation: `emailbrain://document/${DOCUMENT}`, ...extra});
}
function search(results = [hit()]) { return {mode: "lexical", untrusted_content: true, results}; }
function part(extra = {}) {
  return {id: RECEIPT, part_id: "1.2", safe_filename: "fictional.pdf", media_type: "application/pdf", sha256: "b".repeat(64),
    byte_size: 1000, status: "deferred", reason: "isolated_extractor_required", scanner_status: "unscanned", duplicate_of: null, excerpt: "", ...extra};
}
function message(extra = {}) {
  return {id: EVIDENCE, account_id: ACCOUNT, message_id: MESSAGE, raw_sha256: "c".repeat(64), excerpt: "Fictional body",
    untrusted_content: true, citation: `emailbrain://evidence/${EVIDENCE}`, attachments: [part()], ...extra};
}
function page(excerpt = "pdfonlyproof fictional text", extra = {}) {
  return {number: 1, excerpt, excerpt_sha256: "d".repeat(64), offsets: [0, [...excerpt].length], truncated: false, ...extra};
}
function evidence(extra = {}) {
  return {id: DOCUMENT, account_id: ACCOUNT, receipt_id: RECEIPT, processor_version: PROCESSOR, policy_version: POLICY,
    revision: 1, created_at: DONE, status: "extracted", reason: "bounded_pdf_v1", scanner_status: "unscanned",
    evidence_id: EVIDENCE, safe_filename: "fictional.pdf", page_count: 1, pages: [page()],
    source: {raw_sha256: "c".repeat(64), part_path: "1.2", part_sha256: "b".repeat(64)},
    untrusted_content: true, citation: `emailbrain://document/${DOCUMENT}`, ...extra};
}
function scenario(override = () => undefined) {
  const calls = [], state = {jobs: []};
  const app = harness(async (url, options) => {
    const request = {url, method: options.method, headers: {...options.headers}, body: options.body === undefined ? undefined : JSON.parse(options.body)};
    calls.push(request);
    const custom = override(request, calls, state);
    if (custom !== undefined) return custom;
    if (url === "/v1/search") return response(search(request.body.include_documents ? [pdfHit()] : [hit()]));
    if (url === `/v1/evidence/${EVIDENCE}`) return response(message());
    if (url === `${ROOT}/documents`) return response(caps());
    if (url === `${ROOT}/documents/jobs?limit=50`) return response(history(state.jobs));
    if (url === ENQUEUE) { state.jobs = [job()]; return response(job(), 202); }
    if (url === `${ROOT}/documents/jobs/${JOB}`) return response(state.jobs[0] || job());
    if (url === `${ROOT}/documents/jobs/${JOB}/cancel`) {
      const next = state.jobs[0]?.status === "completed" ? state.jobs[0] : job({status: "cancelled", outcome: "cancelled", completed_at: DONE});
      state.jobs = [next]; return response(next);
    }
    if (url === `/v1/documents/${DOCUMENT}`) return response(evidence());
    assert.fail(`unexpected request ${url}`);
  });
  app.element("token").value = "synthetic-owner"; app.element("query").value = "fictional";
  app.element("account-id").value = ACCOUNT;
  return {app, calls, state};
}
async function find(app) { return app.element("search-form").onsubmit({preventDefault() {}}); }
async function select(app) {
  await find(app);
  await button(app.element("results"), "Inspect cited evidence").onclick();
  await button(app.element("results"), "Review this PDF").onclick();
}
async function ready(app) { await select(app); return button(app.element("document-selection"), "Approve this PDF"); }
function approvals(calls) { return calls.filter((call) => call.url === ENQUEUE); }
function visible(app) {
  return ["status", "results", "documents-health", "document-selection", "document-jobs"].map((name) => app.element(name).textContent).join("\n");
}

test("owner selects, explicitly approves, inspects saved PDF and opts into document search", async () => {
  const {app, calls, state} = scenario();
  const approve = await ready(app);
  assert.equal(approvals(calls).length, 0);
  assert.match(visible(app), /one hour/); assert.match(visible(app), /unscanned/);
  for (const value of [ACCOUNT, EVIDENCE, RECEIPT, PROCESSOR, POLICY, "b".repeat(64), "c".repeat(64)]) assert.ok(visible(app).includes(value));
  await approve.onclick();
  assert.deepEqual(approvals(calls)[0].body, {expected_processor_version: PROCESSOR, policy_version: POLICY});
  assert.equal(approvals(calls)[0].headers["Idempotency-Key"], app.uuids[0]);
  assert.equal(app.element("document-jobs").children.length, 1, "approval does not splice an unpositioned row into keyset history");
  state.jobs = [completed()];
  await app.element("documents-refresh").onclick();
  await button(app.element("document-jobs"), "Inspect PDF result").onclick();
  assert.match(visible(app), /pdfonlyproof/); assert.ok(visible(app).includes(`emailbrain://document/${DOCUMENT}`));
  app.element("include-documents").checked = true; app.element("include-documents").onchange();
  await find(app); await button(app.element("results"), "Inspect cited PDF pages").onclick();
  assert.equal(calls.filter((call) => call.url === `/v1/documents/${DOCUMENT}`).length, 2);
  assert.equal(calls.filter((call) => call.url === `/v1/evidence/${EVIDENCE}`).length, 1);
  assert.equal(approvals(calls).length, 1);
  assert.ok(calls.every((call) => !call.url.includes("/processing")), "MIME channel is untouched");
});

test("PDF search defaults off and clears on disconnect", async () => {
  const {app, calls} = scenario();
  await find(app); assert.equal(calls[0].body.include_documents, false);
  app.element("include-documents").checked = true;
  await find(app); assert.equal(calls.at(-1).body.include_documents, true);
  app.element("disconnect").onclick(); assert.equal(app.element("include-documents").checked, false);
  for (const name of ["results", "documents-health", "document-jobs", "document-selection"]) assert.equal(app.element(name).children.length, 0);
  assert.equal(app.element("documents-more").hidden, true);
});

test("refresh is read-only even when PDF approval is disabled", async () => {
  for (const capability of [caps({enabled: false}), caps({enabled: false, processor_version: null})]) {
    const {app, calls, state} = scenario(({url}) => url === `${ROOT}/documents` ? response(capability) : undefined);
    state.jobs = [job()]; await select(app);
    assert.equal(buttons(app.element("document-selection")).length, 0);
    assert.ok(button(app.element("document-jobs"), "Cancel PDF approval"));
    assert.equal(approvals(calls).length, 0);
  }
});

test("uncertain PDF approval retries the same key, including after refresh or reselection", async () => {
  let count = 0;
  const {app, calls} = scenario(({url}) => url === ENQUEUE && ++count < 3 ? Promise.reject(new Error("PRIVATE ERROR")) : undefined);
  await (await ready(app)).onclick();
  assert.ok(!visible(app).includes("PRIVATE ERROR"));
  await app.element("documents-refresh").onclick();
  await button(app.element("document-selection"), "Retry same PDF approval request").onclick();
  await select(app);
  await button(app.element("document-selection"), "Retry same PDF approval request").onclick();
  assert.equal(approvals(calls).length, 3);
  assert.equal(new Set(approvals(calls).map((call) => call.headers["Idempotency-Key"])).size, 1);
  assert.equal(app.uuids.length, 1);
});

test("pending approval ignores double clicks and refresh preserves its uncertain intent", async () => {
  const pending = deferred(); let count = 0;
  const {app, calls} = scenario(({url}) => url === ENQUEUE && ++count === 1 ? pending.promise : undefined);
  const approve = await ready(app), request = approve.onclick();
  await approve.onclick(); assert.equal(approvals(calls).length, 1);
  await app.element("documents-refresh").onclick();
  pending.resolve(response(job(), 202)); await request;
  await button(app.element("document-selection"), "Retry same PDF approval request").onclick();
  assert.equal(approvals(calls)[0].headers["Idempotency-Key"], approvals(calls)[1].headers["Idempotency-Key"]);
});

test("credential, account, query and selection changes invalidate detached approval controls", async () => {
  const changes = [
    (app) => app.element("token").oninput(),
    (app) => app.element("disconnect").onclick(),
    (app) => { app.element("account-id").value = OTHER; app.element("account-id").oninput(); app.element("account-id").value = ACCOUNT; app.element("account-id").oninput(); },
    (app) => app.element("query").oninput(),
    (app) => app.element("include-documents").onchange(),
    (app) => app.evaluate("clearDocumentSelection()"),
    (app) => app.element("documents-refresh").onclick(),
  ];
  for (const change of changes) {
    const {app, calls} = scenario(), approve = await ready(app);
    await change(app); const count = calls.length;
    await approve.onclick(); assert.equal(calls.length, count);
  }
});

test("late approval cannot reveal source or job data after context changes", async () => {
  for (const change of [(app) => app.element("disconnect").onclick(), (app) => app.element("account-id").oninput(), (app) => app.element("query").oninput()]) {
    const pending = deferred();
    const {app} = scenario(({url}) => url === ENQUEUE ? pending.promise : undefined);
    const work = (await ready(app)).onclick(); change(app);
    pending.resolve(response(job(), 202)); await work;
    assert.equal(app.element("document-selection").children.length, 0);
    assert.ok(!app.element("status").textContent.includes("request recorded"));
  }
});

test("approval errors including deleted source and missing scopes stay scrubbed and never retry automatically", async () => {
  for (const code of [401, 403, 404, 409, 422, 503]) {
    const {app, calls} = scenario(({url}) => url === ENQUEUE ? response({detail: "PRIVATE DIAGNOSTIC"}, code) : undefined);
    await (await ready(app)).onclick();
    assert.equal(approvals(calls).length, 1); assert.ok(!visible(app).includes("PRIVATE DIAGNOSTIC"));
    assert.match(app.element("status").textContent, /could not be confirmed/);
  }
});

test("malformed capabilities cannot create approval controls", async () => {
  for (const value of [caps({processor_version: "sandbox-mime-v1-" + "a".repeat(64)}), caps({enabled: true, processor_version: null}),
    caps({policy_version: "live-policy"}), caps({scanner_status: "clean"}), caps({worker_online: true}), caps({mailbox_effects: true}),
    caps({private: "PRIVATE"}), caps({enabled: "true"})]) {
    const {app, calls} = scenario(({url}) => url === `${ROOT}/documents` ? response(value) : undefined);
    await select(app); assert.equal(buttons(app.element("document-selection")).length, 0);
    assert.equal(approvals(calls).length, 0); assert.ok(!visible(app).includes("PRIVATE"));
  }
});

test("malformed approval identity and state never produce a saved-approval claim", async () => {
  for (const value of [job({account_id: OTHER}), job({receipt_id: OTHER}), job({processor_version: "sandbox-pdf-v1-" + "b".repeat(64)}),
    job({policy_version: "live"}), job({id: "../../PRIVATE"}), job({mailbox_effects: true}), job({status: "PRIVATE"}),
    job({attempts: true}), job({outcome: "result_saved"}), job({expires_at: DONE}), job({raw_mime: "PRIVATE"}),
    completed({extraction_id: null}), job({retry_at: DONE}), job({completed_at: DONE})]) {
    const {app, calls} = scenario(({url}) => url === ENQUEUE ? response(value, 202) : undefined);
    await (await ready(app)).onclick();
    assert.equal(approvals(calls).length, 1); assert.ok(!visible(app).includes("PRIVATE"));
    assert.match(app.element("status").textContent, /could not be confirmed/);
  }
});

test("changing configured processor requires a fresh explicit approval without retargeting old controls", async () => {
  let processor = PROCESSOR;
  const {app, calls} = scenario(({url}) => url === `${ROOT}/documents` ? response(caps({processor_version: processor})) : undefined);
  const old = await ready(app);
  processor = "sandbox-pdf-v1-" + "e".repeat(64); await app.element("documents-refresh").onclick();
  await old.onclick(); assert.equal(approvals(calls).length, 0);
  await button(app.element("document-selection"), "Approve this PDF").onclick();
  assert.equal(approvals(calls)[0].body.expected_processor_version, processor);
});

test("failed capability refresh removes previously actionable PDF controls", async () => {
  let fail = false;
  const {app, calls} = scenario(({url}) => fail && url === `${ROOT}/documents` ? response({}, 503) : undefined);
  const old = await ready(app); fail = true; await app.element("documents-refresh").onclick();
  await old.onclick(); assert.equal(approvals(calls).length, 0);
  assert.equal(buttons(app.element("document-selection")).length, 0);
});

test("older capability and history responses cannot replace a newer document view", async () => {
  for (const endpoint of [`${ROOT}/documents`, `${ROOT}/documents/jobs?limit=50`]) {
    const pending = deferred(); let held = false;
    const {app, state} = scenario(({url}) => url === endpoint && !held && (held = true) ? pending.promise : undefined);
    const first = app.element("documents-refresh").onclick();
    while (!held) await Promise.resolve();
    state.jobs = [completed()]; await app.element("documents-refresh").onclick();
    pending.resolve(response(endpoint.endsWith("limit=50") ? history([job()]) : caps({enabled: false})));
    await first; assert.match(app.element("document-jobs").textContent, /completed/);
    assert.ok(!app.element("document-jobs").textContent.includes("queued"));
  }
});

test("invalid accounts cause no document requests", async () => {
  const {app, calls} = scenario(); app.element("account-id").value = "../PRIVATE";
  await app.element("documents-refresh").onclick(); assert.equal(calls.length, 0);
});

test("history shows terminal outcomes and only unfinished jobs can be cancelled", async () => {
  const statuses = {queued: null, running: null, retry_wait: "infrastructure_unavailable", completed: "result_saved",
    cancelled: "cancelled", expired: "approval_expired", failed: "attempts_exhausted", stale: "source_changed", revoked: "authorization_revoked"};
  for (const [status, outcome] of Object.entries(statuses)) {
    const unfinished = ["queued", "running", "retry_wait"].includes(status);
    const value = job({status, outcome, attempts: status === "queued" ? 0 : 1,
      retry_at: status === "retry_wait" ? DONE : null, completed_at: unfinished ? null : DONE,
      extraction_id: status === "completed" ? DOCUMENT : null});
    const {app, calls, state} = scenario(); state.jobs = [value]; await app.element("documents-refresh").onclick();
    assert.match(app.element("document-jobs").textContent, new RegExp(status));
    assert.equal(buttons(app.element("document-jobs")).some((b) => b.textContent === "Cancel PDF approval"), unfinished);
    assert.equal(calls.filter((call) => call.method === "POST").length, 0);
  }
});

test("manual status refresh is read-only and cancellation renders the terminal server race outcome", async () => {
  const {app, calls, state} = scenario(); state.jobs = [job()]; await app.element("documents-refresh").onclick();
  await button(app.element("document-jobs"), "Refresh PDF job status").onclick();
  assert.equal(calls.at(-1).method, "GET");
  state.jobs = [completed()]; await button(app.element("document-jobs"), "Cancel PDF approval").onclick();
  assert.match(app.element("document-jobs").textContent, /completed/);
  assert.ok(!buttons(app.element("document-jobs")).some((b) => b.textContent === "Cancel PDF approval"));
});

test("pending cancellation ignores double clicks and rejects nonterminal or mismatched replies", async () => {
  for (const reply of [job(), completed({account_id: OTHER}), completed({id: OTHER}), completed({receipt_id: OTHER}),
    completed({processor_version: "sandbox-pdf-v1-" + "b".repeat(64)})]) {
    const pending = deferred();
    const {app, calls, state} = scenario(({url}) => url.endsWith("/cancel") ? pending.promise : undefined);
    state.jobs = [job()]; await app.element("documents-refresh").onclick();
    const cancel = button(app.element("document-jobs"), "Cancel PDF approval"), work = cancel.onclick();
    await cancel.onclick(); assert.equal(calls.filter((call) => call.url.endsWith("/cancel")).length, 1);
    pending.resolve(response(reply)); await work;
    assert.match(app.element("status").textContent, /could not be confirmed/);
    assert.match(app.element("document-jobs").textContent, /queued/);
  }
});

test("late job status, cancellation and page evidence cannot cross account or session changes", async () => {
  for (const action of ["Refresh PDF job status", "Cancel PDF approval", "Inspect PDF result"]) {
    const pending = deferred();
    const {app, state} = scenario(({url}) => [ `${ROOT}/documents/jobs/${JOB}`, `${ROOT}/documents/jobs/${JOB}/cancel`, `/v1/documents/${DOCUMENT}`].includes(url) ? pending.promise : undefined);
    state.jobs = [action === "Inspect PDF result" ? completed() : job()];
    await app.element("documents-refresh").onclick();
    const work = button(app.element("document-jobs"), action).onclick();
    app.element("account-id").value = OTHER; app.element("account-id").oninput();
    pending.resolve(response(action === "Inspect PDF result" ? evidence() : completed())); await work;
    assert.equal(app.element("document-jobs").children.length, 0);
    assert.ok(!visible(app).includes("pdfonlyproof"));
  }
});

test("job rerender invalidates the previous card's inspect and cancellation callbacks", async () => {
  const {app, calls, state} = scenario(); state.jobs = [job()]; await app.element("documents-refresh").onclick();
  const cancel = button(app.element("document-jobs"), "Cancel PDF approval");
  state.jobs = [completed()]; await button(app.element("document-jobs"), "Refresh PDF job status").onclick();
  const count = calls.length; await cancel.onclick(); assert.equal(calls.length, count);
});

test("bounded keyset pages replace history and reject detached older paging callbacks", async () => {
  const {app, calls} = scenario(({url}) => {
    if (url === `${ROOT}/documents/jobs?limit=50`) return response(history([job()], {next_after: JOB}));
    if (url === `${ROOT}/documents/jobs?limit=50&after=${JOB}`) return response(history([job({id: OTHER})], {next_after: OTHER}));
    if (url === `${ROOT}/documents/jobs?limit=50&after=${OTHER}`) return response(history([]));
  });
  await app.element("documents-refresh").onclick(); const older = app.element("documents-more").onclick;
  await older(); const count = calls.length; await older(); assert.equal(calls.length, count);
  assert.ok(app.element("document-jobs").textContent.includes(OTHER));
  assert.ok(!app.element("document-jobs").textContent.includes(JOB));
  await app.element("documents-more").onclick(); assert.equal(app.element("documents-more").hidden, true);
});

test("pending page fetch ignores double clicks and cannot append after account change", async () => {
  const pending = deferred();
  const {app, calls} = scenario(({url}) => {
    if (url === `${ROOT}/documents/jobs?limit=50`) return response(history([job()], {next_after: JOB}));
    if (url.includes("&after=")) return pending.promise;
  });
  await app.element("documents-refresh").onclick(); const work = app.element("documents-more").onclick();
  await app.element("documents-more").onclick(); assert.equal(calls.filter((call) => call.url.includes("&after=")).length, 1);
  app.element("account-id").oninput(); pending.resolve(response(history([completed()]))); await work;
  assert.equal(app.element("document-jobs").children.length, 0);
});

test("malformed, duplicated and over-limit history pages fail closed", async () => {
  for (const value of [history([job({account_id: OTHER})]), history([job(), job()]), history(Array(51).fill(job())),
    history([], {next_after: JOB}), history([job()], {next_after: OTHER}), history([], {limit: 100}), history([], {mailbox_effects: true})]) {
    const {app} = scenario(({url}) => url.endsWith("?limit=50") ? response(value) : undefined);
    await app.element("documents-refresh").onclick();
    assert.equal(buttons(app.element("document-jobs")).length, 0);
    assert.equal(app.element("documents-more").hidden, true);
  }
});

test("invalid message/source/receipt identities never produce PDF selection controls", async () => {
  for (const value of [message({id: OTHER}), message({account_id: OTHER}), message({message_id: OTHER}), message({raw_sha256: "PRIVATE"}),
    message({attachments: [part({id: "../../PRIVATE"})]}), message({attachments: [part(), part()]}),
    message({attachments: [part({part_id: "../../PRIVATE"})]}), message({attachments: [part({sha256: "PRIVATE"})]}),
    message({untrusted_content: false}), message({citation: "https://example.invalid/PRIVATE"})]) {
    const {app} = scenario(({url}) => url === `/v1/evidence/${EVIDENCE}` ? response(value) : undefined);
    await find(app); await button(app.element("results"), "Inspect cited evidence").onclick();
    assert.ok(!buttons(app.element("results")).some((b) => b.textContent === "Review this PDF"));
    assert.ok(!visible(app).includes("PRIVATE"));
  }
});

test("only deferred supported PDF receipts offer selection, not Office, text or active content", async () => {
  for (const value of [part({media_type: "text/plain"}), part({media_type: "application/msword"}), part({status: "extracted"}), part({reason: "active_content_quarantined"})]) {
    const {app} = scenario(({url}) => url === `/v1/evidence/${EVIDENCE}` ? response(message({attachments: [value]})) : undefined);
    await find(app); await button(app.element("results"), "Inspect cited evidence").onclick();
    assert.ok(!buttons(app.element("results")).some((b) => b.textContent === "Review this PDF"));
  }
});

test("new search supersedes old successes and errors; detached evidence controls cannot issue requests", async () => {
  for (const result of [response(search([hit({subject: "PRIVATE OLD"})])), response({}, 503)]) {
    const pending = deferred(); let first = true;
    const {app, calls} = scenario(({url}) => url === "/v1/search" && first && !(first = false) ? pending.promise : undefined);
    const old = find(app); await find(app); pending.resolve(result); await old;
    assert.ok(!visible(app).includes("PRIVATE OLD")); assert.match(app.element("status").textContent, /1 result/);
    const inspect = button(app.element("results"), "Inspect cited evidence"); app.element("query").oninput();
    const count = calls.length; await inspect.onclick(); assert.equal(calls.length, count);
  }
});

test("pending message or PDF evidence cannot render after query or session changes", async () => {
  for (const pdf of [false, true]) {
    const pending = deferred();
    const {app} = scenario(({url}) => url.startsWith(pdf ? "/v1/documents/" : "/v1/evidence/") ? pending.promise : undefined);
    app.element("include-documents").checked = pdf; await find(app);
    const work = button(app.element("results"), pdf ? "Inspect cited PDF pages" : "Inspect cited evidence").onclick();
    app.element("query").oninput(); pending.resolve(response(pdf ? evidence() : message())); await work;
    assert.equal(app.element("results").children.length, 0);
  }
});

test("search rejects invalid IDs, oversized result sets and unrequested PDF hits", async () => {
  for (const value of [search([hit({id: "../PRIVATE"})]), search([hit({account_id: "../PRIVATE"})]), search([hit({evidence_id: "../PRIVATE"})]),
    search(Array(51).fill(hit())), search([pdfHit()]), {...search(), untrusted_content: false}]) {
    const {app, calls} = scenario(({url}) => url === "/v1/search" ? response(value) : undefined);
    await find(app); assert.equal(app.element("results").children.length, 0); assert.equal(calls.length, 1);
    assert.ok(!visible(app).includes("PRIVATE"));
  }
});

test("PDF evidence is bound to document/account/receipt/processor and searched source/revision", async () => {
  for (const value of [evidence({id: OTHER}), evidence({account_id: OTHER}), evidence({receipt_id: OTHER}), evidence({evidence_id: OTHER}),
    evidence({revision: 2}), evidence({processor_version: "sandbox-pdf-v1-" + "f".repeat(64)}), evidence({policy_version: "live"}),
    evidence({citation: "https://example.invalid/PRIVATE"}), evidence({untrusted_content: false}), evidence({scanner_status: "safe"}), evidence({raw_mime: "PRIVATE"})]) {
    const {app} = scenario(({url}) => url === `/v1/documents/${DOCUMENT}` ? response(value) : undefined);
    app.element("include-documents").checked = true; await find(app);
    await button(app.element("results"), "Inspect cited PDF pages").onclick();
    assert.ok(!visible(app).includes("pdfonlyproof")); assert.ok(!visible(app).includes("PRIVATE"));
    assert.match(app.element("status").textContent, /could not be verified/);
  }
});

test("PDF evidence rejects malformed pages, offsets, counts, hashes and contradictory extraction outcomes", async () => {
  for (const value of [evidence({pages: [page("PRIVATE", {number: 2})]}), evidence({pages: [page("PRIVATE", {offsets: [1, 8]})]}),
    evidence({pages: [page("PRIVATE", {truncated: true})]}), evidence({pages: [page("PRIVATE", {excerpt_sha256: "bad"})]}),
    evidence({pages: [page("x".repeat(2001))]}), evidence({page_count: 41}), evidence({page_count: null}),
    evidence({pages: [page("")]}), evidence({status: "partial", reason: "pages_without_text"}),
    evidence({status: "deferred", reason: "encrypted"}), evidence({source: {raw_sha256: "c".repeat(64), part_path: "../PRIVATE", part_sha256: "b".repeat(64)}})]) {
    const {app, state} = scenario(({url}) => url === `/v1/documents/${DOCUMENT}` ? response(value) : undefined);
    state.jobs = [completed()]; await app.element("documents-refresh").onclick();
    await button(app.element("document-jobs"), "Inspect PDF result").onclick();
    assert.match(app.element("status").textContent, /could not be verified/); assert.ok(!visible(app).includes("PRIVATE"));
  }
});

test("partial, deferred and failed PDF results remain explicit and unscanned", async () => {
  for (const value of [evidence({status: "partial", reason: "pages_without_text", page_count: 2, pages: [page(), page("", {number: 2})]}),
    evidence({status: "deferred", reason: "encrypted", page_count: null, pages: []}),
    evidence({status: "failed", reason: "invalid_pdf", page_count: null, pages: []})]) {
    const {app, state} = scenario(({url}) => url === `/v1/documents/${DOCUMENT}` ? response(value) : undefined);
    state.jobs = [completed()]; await app.element("documents-refresh").onclick();
    await button(app.element("document-jobs"), "Inspect PDF result").onclick();
    assert.ok(visible(app).includes(value.reason)); assert.match(visible(app), /unscanned/);
    assert.ok(!buttons(app.element("document-jobs")).some((b) => b.textContent === "Cancel PDF approval"));
  }
});

test("PDF markup renders only as text; Unicode offsets use code points; truncation stays visible", async () => {
  const prefix = "<img src=x onerror=steal()> 😀 ";
  const text = prefix + "z".repeat(2000 - [...prefix].length);
  assert.equal([...text].length, 2000);
  const {app, state} = scenario(({url}) => url === `/v1/documents/${DOCUMENT}` ? response(evidence({pages: [page(text, {truncated: true})]})) : undefined);
  state.jobs = [completed()]; await app.element("documents-refresh").onclick();
  await button(app.element("document-jobs"), "Inspect PDF result").onclick();
  assert.ok(visible(app).includes("<img src=x onerror=steal()>")); assert.match(visible(app), /excerpt truncated/);
  assert.match(visible(app), /Characters 0–2000/);
});
