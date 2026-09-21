"use strict";
// Actual API/SQL response bridge, invoked by pytest with synthetic JSON only.
// This is a DOM contract check, not a browser or real-worker execution test.
const fs = require("node:fs"), assert = require("node:assert/strict");
const {harness, response, button} = require("./web_harness.cjs");
async function main() {
  const data = JSON.parse(fs.readFileSync(0, "utf8"));
  const calls = [], root = `/v1/accounts/${data.account}`;
  let finished = false;
  const app = harness(async (url, options) => {
    calls.push({url, method: options.method});
    if (url === "/v1/search") return response(JSON.parse(options.body).include_documents ? data.pdf_search : data.body_search);
    if (url === `/v1/evidence/${data.message.id}`) return response(data.message);
    if (url === `${root}/documents`) return response(data.capabilities);
    if (url === `${root}/documents/jobs?limit=50`) return response(finished ? data.completed_history : data.queued_history);
    if (url === `/v1/documents/${data.document.id}`) return response(data.document);
    assert.fail(`unexpected synthetic request: ${url}`);
  });
  app.element("token").value = "synthetic-contract-only";
  app.element("query").value = "bodyproof";
  await app.element("search-form").onsubmit({preventDefault() {}});
  await button(app.element("results"), "Inspect cited evidence").onclick();
  await button(app.element("results"), "Review this PDF").onclick();
  assert.ok(button(app.element("document-selection"), "Approve this PDF"));
  assert.equal(calls.filter((call) => call.method === "POST" && call.url !== "/v1/search").length, 0);
  finished = true; await app.element("documents-refresh").onclick();
  await button(app.element("document-jobs"), "Inspect PDF result").onclick();
  assert.ok(app.element("document-jobs").textContent.includes(data.document.citation));
  assert.ok(app.element("document-jobs").textContent.includes(data.document.reason));
  for (const page of data.document.pages) assert.ok(app.element("document-jobs").textContent.includes(page.excerpt));
  app.element("include-documents").checked = true;
  app.element("query").value = "pdfonlyproof";
  await app.element("search-form").onsubmit({preventDefault() {}});
  if (data.pdf_search.results.length) {
    await button(app.element("results"), "Inspect cited PDF pages").onclick();
    assert.ok(app.element("results").textContent.includes(data.document.citation));
  } else assert.equal(app.element("results").children.length, 0);
  assert.ok(!app.element("status").textContent.includes("could not be verified"));
  process.stdout.write("PASS: real API shapes rendered with source-bound document controls\n");
}
main().catch((error) => { process.stderr.write(String(error)); process.exitCode = 1; });
