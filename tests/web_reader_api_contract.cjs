"use strict";
// Real SQL/API response -> actual UI validation/rendering, separate from browser proof.
const fs = require("node:fs");
const assert = require("node:assert/strict");
const {harness, response, button} = require("./web_harness.cjs");
const packet = JSON.parse(fs.readFileSync(0, "utf8"));
const app = harness(async (url) => {
  if (url === "/v1/search") return response(packet.search);
  if (url === `/v1/reader/${packet.reader.id}`) return response(packet.reader);
  assert.fail("unexpected request");
});
app.element("token").value = "synthetic-owner";
app.element("query").value = "Readerproof";
(async () => {
  await app.element("search-form").onsubmit({preventDefault() {}});
  await button(app.element("results"), "Read email").onclick();
  assert.match(app.element("message-reader-content").textContent, /FINALTAIL/);
  assert.match(app.element("message-reader-content").textContent, /unscanned/);
  assert.equal(app.element("message-reader").hidden, false);
  console.log("PASS: actual reader API shapes in owner UI");
})().catch((error) => { console.error(error); process.exitCode = 1; });
