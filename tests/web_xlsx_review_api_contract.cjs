"use strict";
// Render real synthetic PostgreSQL/API response shapes through the owner UI.
const fs = require("node:fs");
const assert = require("node:assert/strict");
const {harness, response} = require("./web_harness.cjs");

async function main() {
  const packet = JSON.parse(fs.readFileSync(0, "utf8"));
  const calls = [];
  const route = `/v1/brain/email-xlsx-results/${packet.approval}`;
  const app = harness(async (url, options) => {
    calls.push({url, options});
    if (url === `${route}/inspect`) return response(packet.inspection);
    if (url === `${route}/publication-reviews`) return response(packet.review, 201);
    assert.fail(`unexpected owner request: ${url}`);
  });
  app.element("token").value = "fictional-owner";
  app.element("xlsx-approval-id").value = packet.approval;
  await app.element("xlsx-review-form").onsubmit({preventDefault() {}});
  assert.equal(app.element("xlsx-review-approve").hidden, false);
  assert.ok(app.element("xlsx-review-result").textContent.includes(packet.inspection.text));
  await app.element("xlsx-review-approve").onclick();
  assert.ok(app.element("xlsx-review-status").textContent.includes(packet.review.review_id));
  assert.deepEqual(calls.map((call) => call.url), [
    `${route}/inspect`, `${route}/publication-reviews`,
  ]);
  assert.deepEqual(JSON.parse(calls[1].options.body), {
    expected_text_sha256: packet.inspection.text_sha256,
    expected_sheet_count: packet.inspection.sheet_count,
    expected_cell_count: packet.inspection.cell_count,
  });
  process.stdout.write("PASS: real XLSX API shapes rendered with exact human review only\n");
}
main().catch((error) => { process.stderr.write(String(error)); process.exitCode = 1; });
