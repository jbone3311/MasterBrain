"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {createHash} = require("node:crypto");
const {harness, response, deferred} = require("./web_harness.cjs");

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
