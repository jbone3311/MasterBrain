"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {harness, deferred, response, buttons, button} = require("./web_harness.cjs");

const ACCOUNT = "00000000-0000-4000-8000-000000000201";
const RECEIPT = "00000000-0000-4000-8000-000000000202";
const JOB = "00000000-0000-4000-8000-000000000203";
const OTHER = "00000000-0000-4000-8000-000000000204";
const ATTEMPT = "00000000-0000-4000-8000-000000000205";
const VERSION = "sandbox-mime-v1-" + "a".repeat(64);
const ROOT = `/v1/accounts/${ACCOUNT}`;
const ENQUEUE = `${ROOT}/quarantine/${RECEIPT}/jobs`;
const CREATED = new Date(Date.now() - 60000).toISOString();
const EXPIRES = new Date(Date.parse(CREATED) + 3600000).toISOString();
const COMPLETED = new Date(Date.parse(CREATED) + 5000).toISOString();
function caps(extra = {}) {
  return {enabled: true, parser_version: VERSION, worker_online: null, mailbox_effects: false, ...extra};
}
function job(extra = {}) {
  return {id: JOB, account_id: ACCOUNT, receipt_id: RECEIPT, parser_version: VERSION,
    status: "queued", attempts: 0, created_at: CREATED, expires_at: EXPIRES,
    retry_at: null, completed_at: null, attempt_id: null, outcome: null, mailbox_effects: false, ...extra};
}
function terminal(status, outcome) {
  return job({status, outcome, attempts: status === "completed" ? 1 : status === "failed" ? 3 : 0,
    attempt_id: status === "completed" ? ATTEMPT : null, completed_at: COMPLETED});
}
function history(results = [], extra = {}) {
  return {results, next_after: null, limit: 50, mailbox_effects: false, ...extra};
}
function held() {
  return {results: [{id: RECEIPT, provider_id: "synthetic-source", parser_version: "stdlib-mime-v4",
    reason: "mime_too_large", raw_sha256: "a".repeat(64), recorded_at: CREATED}], next_after: null,
    limit: 50, raw_access: false, reprocessing: true, retry_parser_version: "stdlib-mime-v4"};
}
function scenario(override = () => undefined) {
  const calls = [];
  const app = harness(async (url, options) => {
    const request = {url, method: options.method, headers: {...options.headers},
      body: options.body === undefined ? undefined : JSON.parse(options.body)};
    calls.push(request);
    const custom = override(request, calls);
    if (custom !== undefined) return custom;
    if (url === `${ROOT}/quarantine`) return response(held());
    if (url === `${ROOT}/sync-status`) return response({message_counts: {ready: 0, quarantined: 1, deleted: 0}, worker: null});
    if (url === `${ROOT}/processing`) return response(caps());
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history());
    if (url === ENQUEUE) return response(job(), 202);
    if (url === `${ROOT}/processing/${JOB}`) return response(job());
    assert.fail(`unexpected request ${url}`);
  });
  app.element("token").value = "synthetic-owner";
  app.element("account-id").value = ACCOUNT;
  return {app, calls};
}
async function ready(app) {
  await app.evaluate(`heldMessages('${ACCOUNT}')`);
  await app.element("processing-refresh").onclick();
  return button(app.element("quarantine"), "Approve isolated parsing");
}
function posts(calls) { return calls.filter((call) => call.method === "POST"); }
function cards(app) { return app.element("processing-jobs").children.filter((n) => n.tagName === "ARTICLE"); }
function visible(app) {
  return ["status", "processing-health", "processing-jobs", "quarantine"].map((id) => app.element(id).textContent).join("\n");
}

test("processing refresh is read-only and explicit approval binds full displayed context", async () => {
  const {app, calls} = scenario();
  const approve = await ready(app);
  assert.equal(posts(calls).length, 0);
  assert.match(visible(app), new RegExp(VERSION));
  assert.match(visible(app), /hour|60 minute/i);
  assert.match(visible(app), /unknown|not.*online|not.*running|not.*proof/i);
  await approve.onclick();
  assert.equal(posts(calls).length, 1);
  const sent = posts(calls)[0];
  assert.equal(sent.url, ENQUEUE);
  assert.deepEqual(sent.body, {expected_parser_version: VERSION});
  assert.equal(sent.headers["Idempotency-Key"], app.uuids[0]);
  assert.equal(app.uuids.length, 1);
  assert.match(visible(app), /mailbox.*unchanged|no mailbox|mailbox.*false/i);
});

test("approval controls stay absent without configured capabilities", async () => {
  for (const capability of [caps({enabled: false, parser_version: null}), caps({enabled: false})]) {
    const {app, calls} = scenario(({url}) => url === `${ROOT}/processing` ? response(capability) : undefined);
    await app.evaluate(`heldMessages('${ACCOUNT}')`);
    assert.equal(buttons(app.element("quarantine")).filter((b) => /isolated/i.test(b.textContent)).length, 0);
    await app.element("processing-refresh").onclick();
    assert.equal(buttons(app.element("quarantine")).filter((b) => /Approve isolated/.test(b.textContent)).length, 0);
    assert.equal(posts(calls).length, 0);
  }
});

test("uncertain submission retains one request key and never automatically reapproves", async () => {
  let attempts = 0;
  const {app, calls} = scenario(({url}) => {
    if (url === ENQUEUE && ++attempts === 1) return Promise.reject(new Error("PRIVATE NETWORK DETAIL"));
  });
  const approve = await ready(app);
  await approve.onclick();
  assert.equal(posts(calls).length, 1);
  assert.ok(!visible(app).includes("PRIVATE"));
  assert.match(visible(app), /uncertain|unknown|same approval request/i);
  await button(app.element("quarantine"), "Retry same approval request").onclick();
  assert.equal(posts(calls).length, 2);
  assert.equal(posts(calls)[0].headers["Idempotency-Key"], posts(calls)[1].headers["Idempotency-Key"]);
  assert.deepEqual(posts(calls)[0].body, posts(calls)[1].body);
  assert.equal(app.uuids.length, 1);
});

test("pending approval ignores double clicks", async () => {
  const pending = deferred();
  const {app, calls} = scenario(({url}) => url === ENQUEUE ? pending.promise : undefined);
  const approve = await ready(app);
  const first = approve.onclick();
  assert.equal(approve.disabled, true);
  await approve.onclick();
  assert.equal(posts(calls).length, 1);
  pending.resolve(response(job(), 202));
  await first;
  assert.equal(posts(calls).length, 1);
});

test("scope, conflict and unavailable errors never render source diagnostics or auto-retry", async () => {
  for (const code of [401, 403, 409, 503]) {
    const {app, calls} = scenario(({url}) => url === ENQUEUE ? response({detail: "PRIVATE DIAGNOSTIC"}, code) : undefined);
    await (await ready(app)).onclick();
    assert.equal(posts(calls).length, 1);
    assert.ok(!visible(app).includes("PRIVATE"));
    assert.match(app.element("status").textContent, /could not be confirmed|failed|access|denied/i);
    assert.ok(!/approval recorded|approval saved/i.test(app.element("status").textContent));
  }
});

test("untrusted approval responses cannot change account, receipt, parser or status contract", async () => {
  const malformed = [
    job({account_id: OTHER}), job({receipt_id: OTHER}), job({parser_version: "sandbox-mime-v1-" + "b".repeat(64)}),
    job({id: "../PRIVATE"}), job({status: "<script>PRIVATE</script>"}), job({outcome: "recovered"}),
    job({mailbox_effects: true}), job({attempts: true}), job({raw_mime: "PRIVATE RAW"}),
    job({status: "completed", attempt_id: ATTEMPT, completed_at: CREATED, outcome: null}),
  ];
  for (const value of malformed) {
    const {app, calls} = scenario(({url}) => url === ENQUEUE ? response(value, 202) : undefined);
    await (await ready(app)).onclick();
    assert.equal(posts(calls).length, 1);
    assert.ok(!visible(app).includes("PRIVATE"));
    assert.match(app.element("status").textContent, /unexpected|invalid|uncertain|could not be confirmed/i);
    assert.ok(!/approval recorded|approval saved/i.test(app.element("status").textContent));
  }
});

test("history renders every terminal state without cancellation controls", async () => {
  const states = [
    ["completed", "recovered"], ["completed", "mime_rejected"], ["completed", "integrity_failed"],
    ["cancelled", "cancelled"], ["expired", "approval_expired"],
    ["failed", "attempts_exhausted"], ["stale", "source_changed"], ["revoked", "authorization_revoked"],
  ];
  for (const [status, outcome] of states) {
    const value = terminal(status, outcome);
    const {app, calls} = scenario(({url}) => url.startsWith(`${ROOT}/processing/jobs`) ? response(history([value])) : undefined);
    await app.element("processing-refresh").onclick();
    assert.equal(app.element("processing-jobs").children.length, 1);
    assert.ok(!buttons(app.element("processing-jobs")).some((b) => b.textContent === "Cancel approval"));
    assert.equal(posts(calls).length, 0);
    assert.match(app.element("processing-jobs").textContent, new RegExp(status, "i"));
  }
});

test("cancellation race displays completed server state rather than claiming cancellation", async () => {
  const completed = terminal("completed", "recovered");
  const {app, calls} = scenario(({url}) => {
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history([job()]));
    if (url === `${ROOT}/processing/${JOB}/cancel`) return response(completed);
  });
  await app.element("processing-refresh").onclick();
  await button(app.element("processing-jobs"), "Cancel approval").onclick();
  assert.equal(posts(calls).length, 1);
  assert.equal(posts(calls)[0].url, `${ROOT}/processing/${JOB}/cancel`);
  assert.match(app.element("status").textContent, /completed|processing finished/i);
  assert.ok(!/approval cancelled|successfully cancelled/i.test(app.element("status").textContent));
});

test("manual status refresh remains read-only and validates returned job identity", async () => {
  const {app, calls} = scenario(({url}) => {
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history([job()]));
    if (url === `${ROOT}/processing/${JOB}`) return response(job({id: OTHER}));
  });
  await app.element("processing-refresh").onclick();
  await button(app.element("processing-jobs"), "Refresh job status").onclick();
  assert.equal(posts(calls).length, 0);
  assert.match(app.element("status").textContent, /unexpected|invalid|could not be verified/i);
  assert.ok(!app.element("processing-jobs").textContent.includes(OTHER));
});

test("malformed capabilities and history never create actionable controls", async () => {
  const cases = [
    {cap: caps({worker_online: true})}, {cap: caps({parser_version: "private-image:latest"})},
    {cap: caps({enabled: true, parser_version: null})}, {cap: caps({mailbox_effects: true})},
    {page: history([job({account_id: OTHER})])}, {page: history([], {next_after: "../PRIVATE"})},
    {page: history(Array.from({length: 51}, () => job()))}, {page: history([job(), job()])},
    {page: history([], {limit: 500})}, {page: history([job({status: "queued", attempts: 3})])},
  ];
  for (const value of cases) {
    const {app, calls} = scenario(({url}) => {
      if (url === `${ROOT}/processing` && value.cap) return response(value.cap);
      if (url.startsWith(`${ROOT}/processing/jobs`) && value.page) return response(value.page);
    });
    await app.element("processing-refresh").onclick();
    assert.equal(buttons(app.element("processing-jobs")).length, 0);
    assert.equal(posts(calls).length, 0);
    assert.ok(!visible(app).includes("PRIVATE"));
    assert.match(app.element("status").textContent, /unexpected|invalid|unavailable/i);
  }
});

test("pagination follows returned account-bound cursor and reset replaces old pages", async () => {
  let firstReads = 0;
  const {app, calls} = scenario(({url}) => {
    if (url.startsWith(`${ROOT}/processing/jobs`) && url.includes(`after=${JOB}`)) return response(history([job({id: OTHER})]));
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history([job()], {next_after: ++firstReads === 1 ? JOB : null}));
  });
  await app.element("processing-refresh").onclick();
  assert.equal(app.element("processing-more").hidden, false);
  await app.element("processing-more").onclick();
  assert.equal(cards(app).length, 1);
  assert.ok(app.element("processing-jobs").textContent.includes(OTHER));
  assert.ok(!app.element("processing-jobs").textContent.includes(JOB));
  assert.equal(app.element("processing-more").hidden, true);
  assert.ok(calls.some((c) => c.url.includes(`after=${JOB}`)));
  await app.element("processing-refresh").onclick();
  assert.equal(app.element("processing-jobs").children.length, 1);
});

test("credential, account and refresh changes invalidate detached approval callbacks", async () => {
  for (const change of ["credential", "disconnect", "account", "processing", "import"]) {
    const {app, calls} = scenario();
    const approve = await ready(app);
    if (change === "credential") { app.element("token").value = "other-owner"; app.element("token").oninput(); }
    if (change === "disconnect") app.element("disconnect").onclick();
    if (change === "account") { app.element("account-id").value = OTHER; app.element("account-id").oninput(); app.element("account-id").value = ACCOUNT; app.element("account-id").oninput(); }
    if (change === "processing") await app.element("processing-refresh").onclick();
    if (change === "import") await app.evaluate("loadImport()");
    await approve.onclick();
    assert.equal(posts(calls).length, 0, `${change} left an old mutation callback live`);
  }
});

test("pending approval cannot repopulate private state after session or view change", async () => {
  for (const change of ["credential", "disconnect", "account", "processing", "import"]) {
    const pending = deferred();
    const {app, calls} = scenario(({url}) => url === ENQUEUE ? pending.promise : undefined);
    const approve = await ready(app), work = approve.onclick();
    if (change === "credential") { app.element("token").value = "new-owner"; app.element("token").oninput(); }
    if (change === "disconnect") app.element("disconnect").onclick();
    if (change === "account") { app.element("account-id").value = OTHER; app.element("account-id").oninput(); }
    if (change === "processing") await app.element("processing-refresh").onclick();
    if (change === "import") await app.evaluate("loadImport()");
    const count = calls.length;
    pending.resolve(response(job(), 202)); await work;
    assert.equal(calls.length, count, `${change} allowed stale response to issue follow-ups`);
    assert.ok(!/approval recorded|approval saved/i.test(app.element("status").textContent));
    assert.equal(cards(app).length, 0);
    assert.ok(!visible(app).includes(JOB));
  }
});

test("superseding same-account refresh rejects late capabilities and history", async () => {
  for (const delayed of ["capabilities", "history"]) {
    const pending = deferred(), started = deferred();
    let reads = 0;
    const {app} = scenario(({url}) => {
      const match = delayed === "capabilities" ? url === `${ROOT}/processing` : url.startsWith(`${ROOT}/processing/jobs`);
      if (match && ++reads === 1) { started.resolve(); return pending.promise; }
    });
    const old = app.element("processing-refresh").onclick(); await started.promise;
    await app.element("processing-refresh").onclick();
    pending.resolve(response(delayed === "capabilities" ? caps({parser_version: "sandbox-mime-v1-" + "b".repeat(64)}) : history([job()])));
    await old;
    assert.equal(cards(app).length, 0);
    assert.ok(!visible(app).includes("sandbox-mime-v1-" + "b".repeat(64)));
  }
});

test("processing-page callbacks cannot append after account change", async () => {
  const pending = deferred();
  const {app} = scenario(({url}) => {
    if (url.includes("after=")) return pending.promise;
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history([job()], {next_after: JOB}));
  });
  await app.element("processing-refresh").onclick();
  const work = app.element("processing-more").onclick();
  app.element("account-id").value = OTHER; app.element("account-id").oninput();
  pending.resolve(response(history([job({id: OTHER})]))); await work;
  assert.equal(app.element("processing-jobs").children.length, 0);
  assert.equal(app.element("processing-more").hidden, true);
});

test("uncertain approval keeps its key across a same-account processing refresh", async () => {
  let attempts = 0;
  const {app, calls} = scenario(({url}) => {
    if (url === ENQUEUE && ++attempts === 1) return Promise.reject(new Error("connection lost"));
  });
  await (await ready(app)).onclick();
  const key = posts(calls)[0].headers["Idempotency-Key"];
  await app.element("processing-refresh").onclick();
  await button(app.element("quarantine"), "Retry same approval request").onclick();
  assert.equal(posts(calls).length, 2);
  assert.equal(posts(calls)[1].headers["Idempotency-Key"], key);
  assert.equal(app.uuids.length, 1);
});

test("changed configured image requires a fresh explicit click and never retargets old controls", async () => {
  let version = VERSION;
  const {app, calls} = scenario(({url}) => {
    if (url === `${ROOT}/processing`) return response(caps({parser_version: version}));
    if (url === ENQUEUE) return response(job({parser_version: version}), 202);
  });
  const old = await ready(app);
  version = "sandbox-mime-v1-" + "b".repeat(64);
  await app.element("processing-refresh").onclick();
  await old.onclick();
  assert.equal(posts(calls).length, 0);
  await button(app.element("quarantine"), "Approve isolated parsing").onclick();
  assert.deepEqual(posts(calls)[0].body, {expected_parser_version: version});
});

test("capability refresh failure invalidates previously authorized-looking controls", async () => {
  let denied = false;
  const {app, calls} = scenario(({url}) => url === `${ROOT}/processing` && denied
    ? response({detail: "PRIVATE"}, 403) : undefined);
  const old = await ready(app);
  denied = true;
  await app.element("processing-refresh").onclick();
  await old.onclick();
  assert.equal(posts(calls).length, 0);
  assert.ok(!buttons(app.element("quarantine")).some((b) => b.textContent === "Approve isolated parsing" && !b.disabled));
  assert.ok(!visible(app).includes("PRIVATE"));
});

test("queued, running and retry-wait jobs offer only explicit cancellation", async () => {
  for (const pending of [job(), job({status: "running", attempts: 1}),
    job({status: "retry_wait", attempts: 1, outcome: "infrastructure_unavailable", retry_at: COMPLETED})]) {
    const {app, calls} = scenario(({url}) => url.startsWith(`${ROOT}/processing/jobs`)
      ? response(history([pending])) : undefined);
    await app.element("processing-refresh").onclick();
    assert.ok(button(app.element("processing-jobs"), "Cancel approval"));
    assert.equal(posts(calls).length, 0);
  }
});

test("cancellation ignores double clicks and rejects mismatched success identity", async () => {
  const pending = deferred();
  const {app, calls} = scenario(({url}) => {
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history([job()]));
    if (url === `${ROOT}/processing/${JOB}/cancel`) return pending.promise;
  });
  await app.element("processing-refresh").onclick();
  const cancel = button(app.element("processing-jobs"), "Cancel approval");
  const work = cancel.onclick(); await cancel.onclick();
  assert.equal(posts(calls).length, 1);
  pending.resolve(response({...terminal("cancelled", "cancelled"), id: OTHER})); await work;
  assert.match(app.element("status").textContent, /unexpected|invalid|could not be confirmed/i);
  assert.ok(!/approval cancelled|successfully cancelled/i.test(app.element("status").textContent));
});

test("late cancellation and status responses cannot overwrite a newer page or account", async () => {
  for (const action of ["Cancel approval", "Refresh job status"]) for (const change of ["refresh", "account", "disconnect"]) {
    const pending = deferred(); let pageReads = 0;
    const {app, calls} = scenario(({url}) => {
      if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history(++pageReads === 1 ? [job()] : []));
      if (url === `${ROOT}/processing/${JOB}` || url === `${ROOT}/processing/${JOB}/cancel`) return pending.promise;
    });
    await app.element("processing-refresh").onclick();
    const work = button(app.element("processing-jobs"), action).onclick();
    if (change === "refresh") await app.element("processing-refresh").onclick();
    if (change === "account") { app.element("account-id").value = OTHER; app.element("account-id").oninput(); }
    if (change === "disconnect") app.element("disconnect").onclick();
    const count = calls.length;
    pending.resolve(response(terminal("completed", "recovered"))); await work;
    assert.equal(calls.length, count);
    assert.equal(cards(app).length, 0);
    assert.ok(!visible(app).includes(JOB));
    assert.ok(!/processing finished/i.test(app.element("status").textContent));
  }
});

test("invalid held receipt identities never gain isolated approval controls", async () => {
  for (const change of [{id: "../PRIVATE"}, {id: null}, {reason: "unknown"}, {raw_sha256: "PRIVATE"}]) {
    const page = held(); page.results[0] = {...page.results[0], ...change};
    const {app, calls} = scenario(({url}) => url === `${ROOT}/quarantine` ? response(page) : undefined);
    await app.evaluate(`heldMessages('${ACCOUNT}')`);
    await app.element("processing-refresh").onclick();
    assert.ok(!buttons(app.element("quarantine")).some((b) => /Approve isolated/.test(b.textContent)));
    assert.equal(posts(calls).length, 0);
  }
});

test("pending history-page fetch ignores double clicks and stale saved page callbacks", async () => {
  const pending = deferred();
  const {app, calls} = scenario(({url}) => {
    if (url.includes("after=")) return pending.promise;
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history([job()], {next_after: JOB}));
  });
  await app.element("processing-refresh").onclick();
  const staleCancel = button(app.element("processing-jobs"), "Cancel approval");
  const more = app.element("processing-more");
  const work = more.onclick(); await more.onclick(); await staleCancel.onclick();
  assert.equal(calls.filter((c) => c.url.includes("after=")).length, 1);
  assert.equal(posts(calls).length, 0);
  pending.resolve(response(history([job({id: OTHER})]))); await work;
  assert.ok(app.element("processing-jobs").textContent.includes(OTHER));
});

test("cancellation response must be terminal before cancellation can be reported", async () => {
  const {app} = scenario(({url}) => {
    if (url.startsWith(`${ROOT}/processing/jobs`)) return response(history([job()]));
    if (url === `${ROOT}/processing/${JOB}/cancel`) return response(job());
  });
  await app.element("processing-refresh").onclick();
  await button(app.element("processing-jobs"), "Cancel approval").onclick();
  assert.match(app.element("status").textContent, /could not be confirmed/i);
  assert.ok(button(app.element("processing-jobs"), "Cancel approval"));
});

test("held-page rerender during submission exposes retry of the same uncertain request", async () => {
  const pending = deferred(); let attempts = 0;
  const {app, calls} = scenario(({url}) => url === ENQUEUE && ++attempts === 1 ? pending.promise : undefined);
  const approve = await ready(app), work = approve.onclick();
  const key = posts(calls)[0].headers["Idempotency-Key"];
  await app.evaluate(`heldMessages('${ACCOUNT}')`);
  pending.resolve(response(job(), 202)); await work;
  const retry = button(app.element("quarantine"), "Retry same approval request");
  assert.equal(retry.disabled, false, "replacement control must not remain disabled forever");
  await retry.onclick();
  assert.equal(posts(calls).length, 2);
  assert.equal(posts(calls)[1].headers["Idempotency-Key"], key);
  assert.equal(app.uuids.length, 1);
});

test("approval result never evicts an unseen cursor-bound history row", async () => {
  const rows = Array.from({length: 50}, (_, index) => job({
    id: `00000000-0000-4000-8000-${String(349 - index).padStart(12, "0")}`,
  }));
  const anchor = rows.at(-1).id;
  const {app, calls} = scenario(({url}) => url.startsWith(`${ROOT}/processing/jobs`)
    ? response(history(rows, {next_after: anchor})) : undefined);
  const approve = await ready(app);
  assert.equal(cards(app).length, 50);
  assert.ok(app.element("processing-jobs").textContent.includes(anchor));
  await approve.onclick();
  assert.equal(posts(calls).length, 1);
  assert.equal(cards(app).length, 50);
  assert.ok(app.element("processing-jobs").textContent.includes(anchor), "a new confirmation must not drop the last unpaged row");
  assert.ok(!app.element("processing-jobs").textContent.includes(JOB));
  assert.ok(app.element("quarantine").textContent.includes(JOB), "confirmation belongs with the approved receipt until refresh");
});

test("detached older More callback cannot page using a newer history cursor", async () => {
  let pages = 0;
  const {app, calls} = scenario(({url}) => {
    if (url.includes("after=")) return response(history());
    if (url.startsWith(`${ROOT}/processing/jobs`)) {
      const id = ++pages === 1 ? JOB : OTHER;
      return response(history([job({id})], {next_after: id}));
    }
  });
  await app.element("processing-refresh").onclick();
  const oldMore = app.element("processing-more").onclick;
  await app.element("processing-refresh").onclick();
  const count = calls.length;
  await oldMore();
  assert.equal(calls.length, count);
  await app.element("processing-more").onclick();
  assert.ok(calls.at(-1).url.includes(`after=${OTHER}`));
});
