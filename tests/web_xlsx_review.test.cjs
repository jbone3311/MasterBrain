"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {createHash} = require("node:crypto");
const {harness, response, deferred, button} = require("./web_harness.cjs");

const approval = `xapp_${"a".repeat(32)}`;
const review = `xrev_${"b".repeat(32)}`;
const digest = createHash("sha256").update("A".repeat(16000) + "<x>").digest("hex");
const prefix = `/v1/brain/email-xlsx-results/${approval}`;
const source = {account_id: "00000000-0000-4000-8000-000000000001",
  attachment_id: "00000000-0000-4000-8000-000000000002",
  parent_version_id: "00000000-0000-4000-8000-000000000003",
  safe_filename: "rent.xlsx", part_path: "1.2", part_sha256: "e".repeat(64)};
const page = (offset, text, next, total, hash = digest) => ({
  approval_id: approval, text_sha256: hash, sheet_count: 1, cell_count: 8,
  text, offset, next_offset: next, total_chars: total,
  untrusted_content: true, mailbox_effects: false, source,
});
const saved = (hash = digest) => ({review_id: review, approval_id: approval, text_sha256: hash,
  sheet_count: 1, cell_count: 8, changed: true, document_published: false});
function prepare(fetch) {
  const app = harness(fetch);
  app.element("token").value = "synthetic-owner";
  app.element("xlsx-approval-id").value = approval;
  return app;
}

test("inspects every bounded page before exact human review; browser never publishes", async () => {
  const calls = [];
  const app = prepare(async (url, options) => {
    calls.push({url, options});
    if (url === `${prefix}/inspect`) {
      const body = JSON.parse(options.body);
      return response(body.offset === 0
        ? page(0, "A".repeat(16000), 16000, 16003)
        : page(16000, "<x>", null, 16003));
    }
    if (url === `${prefix}/publication-reviews`) return response(saved(), 201);
    assert.fail(`unexpected request: ${url}`);
  });
  assert.equal(calls.length, 0);
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  assert.equal(calls.length, 1);
  assert.equal(app.element("xlsx-review-approve").hidden, true);
  await app.element("xlsx-review-next").onclick();
  assert.equal(app.element("xlsx-review-next").hidden, true);
  assert.equal(app.element("xlsx-review-approve").hidden, false);
  assert.ok(app.element("xlsx-review-result").textContent.includes("rent.xlsx"));
  assert.ok(app.element("xlsx-review-result").textContent.includes("<x>"));
  await app.element("xlsx-review-approve").onclick();
  assert.equal(calls.length, 3);
  assert.equal(calls[2].url, `${prefix}/publication-reviews`);
  assert.deepEqual(JSON.parse(calls[2].options.body), {
    expected_text_sha256: digest, expected_sheet_count: 1, expected_cell_count: 8,
  });
  assert.equal(calls[2].options.headers["Idempotency-Key"], app.uuids[0]);
  assert.ok(app.element("xlsx-review-status").textContent.includes(review));
  assert.equal(app.element("xlsx-review-approve").hidden, true);
  assert.ok(calls.every((call) => !call.url.includes("publish")));
});

test("invisible formatting characters are shown as markers and still digest-verified", async () => {
  const text = "USD \u202e0001\u202c\u200b";
  const hash = createHash("sha256").update(text).digest("hex");
  const app = prepare(async (url) => {
    if (url.endsWith("/inspect")) return response(page(0, text, null, Array.from(text).length, hash));
    assert.fail(`unexpected request: ${url}`);
  });
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  const shown = app.element("xlsx-review-result").textContent;
  assert.ok(shown.includes("USD ⟨U+202E⟩0001⟨U+202C⟩⟨U+200B⟩"));
  assert.ok(shown.includes("3 invisible formatting character(s)"));
  assert.ok(!/[\u202e\u202c\u200b]/u.test(shown));
  assert.equal(app.element("xlsx-review-approve").hidden, false);
});

test("uncertain review retries only the same exact idempotency key", async () => {
  const keys = [];
  const hash = createHash("sha256").update("fictional").digest("hex");
  const app = prepare(async (url, options) => {
    if (url.endsWith("/inspect")) return response(page(0, "fictional", null, 9, hash));
    keys.push(options.headers["Idempotency-Key"]);
    if (keys.length === 1) throw new Error("network interrupted after write");
    return response({...saved(hash), changed: false}, 201);
  });
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  await app.element("xlsx-review-approve").onclick();
  assert.ok(app.element("xlsx-review-status").textContent.includes("uncertain"));
  await app.element("xlsx-review-approve").onclick();
  assert.deepEqual(keys, [app.uuids[0], app.uuids[0]]);
  assert.ok(app.element("xlsx-review-status").textContent.includes(review));
});

test("changed digest or malformed page hides review and requires fresh inspection", async () => {
  const app = prepare(async (url, options) => {
    const body = JSON.parse(options.body);
    return response(body.offset === 0
      ? page(0, "A".repeat(16000), 16000, 16001)
      : page(16000, "B", null, 16001, "d".repeat(64)));
  });
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  await app.element("xlsx-review-next").onclick();
  assert.equal(app.element("xlsx-review-approve").hidden, true);
  assert.equal(app.element("xlsx-review-result").textContent, "");
  assert.ok(app.element("xlsx-review-status").textContent.includes("could not be verified"));
});

test("source occurrence changing between pages hides review", async () => {
  const app = prepare(async (url, options) => {
    const body = JSON.parse(options.body);
    return response(body.offset === 0
      ? page(0, "A".repeat(16000), 16000, 16001)
      : {...page(16000, "B", null, 16001),
        source: {...source, attachment_id: "00000000-0000-4000-8000-000000000099"}});
  });
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  await app.element("xlsx-review-next").onclick();
  assert.equal(app.element("xlsx-review-approve").hidden, true);
  assert.ok(app.element("xlsx-review-status").textContent.includes("could not be verified"));
});

test("credential change discards an in-flight inspection", async () => {
  const wait = deferred();
  const app = prepare(async () => wait.promise);
  const pending = app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  app.element("token").value = "different-owner";
  app.element("token").oninput();
  wait.resolve(response(page(0, "fictional", null, 9)));
  await pending;
  assert.equal(app.element("xlsx-approval-id").value, "");
  assert.equal(app.element("xlsx-review-result").textContent, "");
  assert.equal(app.element("xlsx-review-approve").hidden, true);
});

test("a complete page with a false claimed digest never enables review", async () => {
  const app = prepare(async () => response(page(0, "fictional", null, 9)));
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  assert.equal(app.element("xlsx-review-approve").hidden, true);
  assert.equal(app.element("xlsx-review-result").textContent, "");
  assert.ok(app.element("xlsx-review-status").textContent.includes("could not be verified"));
});

test("switching accounts clears the prior review and approval ID", async () => {
  const hash = createHash("sha256").update("fictional").digest("hex");
  const app = prepare(async () => response(page(0, "fictional", null, 9, hash)));
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  assert.equal(app.element("xlsx-review-approve").hidden, false);
  app.element("account-id").value = "00000000-0000-4000-8000-000000000001";
  app.element("account-id").oninput();
  assert.equal(app.element("xlsx-approval-id").value, "");
  assert.equal(app.element("xlsx-review-result").textContent, "");
  assert.equal(app.element("xlsx-review-approve").hidden, true);
});

test("search evidence selects one eligible XLSX; explicit approval never runs a worker", async () => {
  const calls = [];
  const app = harness(async (url, options) => {
    calls.push({url, options});
    return response({approval_id: approval, changed: true,
      mailbox_effects: false, document_published: false}, 201);
  });
  app.element("token").value = "synthetic-owner";
  const hit = {account_id: source.account_id};
  const evidence = {id: source.parent_version_id, raw_sha256: "d".repeat(64),
    excerpt: "fictional", citation: "emailbrain://evidence/fictional", attachments: [
      {id: source.attachment_id, safe_filename: source.safe_filename,
        part_id: source.part_path, sha256: source.part_sha256,
        media_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        status: "deferred", reason: "isolated_extractor_required", scanner_status: "not_scanned",
        excerpt: ""},
    ]};
  app.evaluate(`renderMessageEvidence(byId("results"), ${JSON.stringify(evidence)},
    ${JSON.stringify(hit)}, searchContext())`);
  assert.equal(calls.length, 0);
  button(app.element("results"), "Select XLSX for approval").onclick();
  assert.ok(app.element("xlsx-source-selection").textContent.includes("rent.xlsx"));
  assert.equal(calls.length, 0);
  await button(app.element("xlsx-source-selection"), "Approve this XLSX for extraction").onclick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url,
    `/v1/accounts/${source.account_id}/attachments/${source.attachment_id}/xlsx-approvals`);
  assert.equal(calls[0].options.headers["Idempotency-Key"], app.uuids[0]);
  assert.equal(app.element("xlsx-approval-id").value, approval);
  assert.ok(app.element("xlsx-source-selection").textContent.includes("No worker was started"));
});

test("uncertain extraction approval retries the same key, then account change clears selection", async () => {
  const keys = [];
  const app = harness(async (_, options) => {
    keys.push(options.headers["Idempotency-Key"]);
    if (keys.length === 1) throw new Error("response lost after write");
    return response({approval_id: approval, changed: false,
      mailbox_effects: false, document_published: false}, 201);
  });
  app.element("token").value = "synthetic-owner";
  app.element("account-id").value = source.account_id;
  app.evaluate(`selectXlsxAttachment(${JSON.stringify({account: source.account_id,
    evidence: source.parent_version_id, receipt: source.attachment_id,
    filename: source.safe_filename, rawHash: "d".repeat(64),
    part: source.part_path, partHash: source.part_sha256})})`);
  await button(app.element("xlsx-source-selection"), "Approve this XLSX for extraction").onclick();
  assert.ok(app.element("xlsx-source-selection").textContent.includes("uncertain"));
  await button(app.element("xlsx-source-selection"), "Retry same XLSX approval request").onclick();
  assert.deepEqual(keys, [app.uuids[0], app.uuids[0]]);
  assert.equal(app.element("xlsx-approval-id").value, approval);
  app.element("account-id").value = "00000000-0000-4000-8000-000000000099";
  app.element("account-id").oninput();
  assert.equal(app.element("xlsx-source-selection").textContent, "");
  assert.equal(app.element("xlsx-approval-id").value, "");
});

test("stale extraction approval response after credential change cannot populate result ID", async () => {
  const wait = deferred();
  const app = harness(async () => wait.promise);
  app.element("token").value = "synthetic-owner";
  app.element("account-id").value = source.account_id;
  app.evaluate(`selectXlsxAttachment(${JSON.stringify({account: source.account_id,
    evidence: source.parent_version_id, receipt: source.attachment_id,
    filename: source.safe_filename, rawHash: "d".repeat(64),
    part: source.part_path, partHash: source.part_sha256})})`);
  const pending = button(app.element("xlsx-source-selection"), "Approve this XLSX for extraction").onclick();
  app.element("token").value = "another-owner";
  app.element("token").oninput();
  wait.resolve(response({approval_id: approval, changed: true,
    mailbox_effects: false, document_published: false}, 201));
  await pending;
  assert.equal(app.element("xlsx-source-selection").textContent, "");
  assert.equal(app.element("xlsx-approval-id").value, "");
});

test("changing result input during an approval keeps a retryable key and ignores stale reply", async () => {
  const wait = deferred(), keys = [];
  const app = harness(async (_, options) => {
    keys.push(options.headers["Idempotency-Key"]);
    if (keys.length === 1) return wait.promise;
    return response({approval_id: approval, changed: false,
      mailbox_effects: false, document_published: false}, 201);
  });
  app.element("token").value = "synthetic-owner";
  app.element("account-id").value = source.account_id;
  app.evaluate(`selectXlsxAttachment(${JSON.stringify({account: source.account_id,
    evidence: source.parent_version_id, receipt: source.attachment_id,
    filename: source.safe_filename, rawHash: "d".repeat(64),
    part: source.part_path, partHash: source.part_sha256})})`);
  const pending = button(app.element("xlsx-source-selection"), "Approve this XLSX for extraction").onclick();
  app.element("xlsx-approval-id").value = `xapp_${"c".repeat(32)}`;
  app.element("xlsx-approval-id").oninput();
  wait.resolve(response({approval_id: approval, changed: true,
    mailbox_effects: false, document_published: false}, 201));
  await pending;
  assert.equal(app.element("xlsx-approval-id").value, `xapp_${"c".repeat(32)}`);
  await button(app.element("xlsx-source-selection"), "Retry same XLSX approval request").onclick();
  assert.deepEqual(keys, [app.uuids[0], app.uuids[0]]);
  assert.equal(app.element("xlsx-approval-id").value, approval);
});
