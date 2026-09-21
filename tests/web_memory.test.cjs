"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const vm = require("node:vm"), fs = require("node:fs"), crypto = require("node:crypto");
const {Element, response, deferred, button} = require("./web_harness.cjs");
const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12,"0")}`;
function setup(fetch) {
  const elements = new Map();
  const el = (id) => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({document: {getElementById: el, createElement: (tag) => new Element(tag)}, crypto, fetch});
  vm.runInContext(fs.readFileSync("src/email_brain/web/memory.js", "utf8"), context);
  const e = (name) => el(`memory-${name}`);
  e("token").value = "synthetic-only"; e("account").value = id(1);
  return {e, evaluate: (code) => vm.runInContext(code, context)};
}
const record = {record_id:id(2), evidence_id:id(3), revision:1, payload:{kind:"trip",title:"<script>bad()</script>",status:"planned"}, source_quote:"synthetic", source_current:true, recorded_at:"2026-09-21T00:00:00Z", parent_trip_id:null};
const summary = {last_checked_at:null, needs_refresh:true, buckets:[{bucket:"travel",revision:1,last_changed_at:null}]};
test("read-only refresh uses inert text and discloses partial coverage", async () => {
  const calls=[];
  const {e} = setup(async (url, options) => { calls.push(options); return response(url.endsWith("summary") ? summary : {results:[record],next_after:null}); });
  await e("refresh").onclick();
  assert.match(e("records").textContent, /<script>bad/);
  assert.match(e("summary").textContent, /partial\/manual/);
  assert.ok(calls.every(o => !o.method && o.credentials === "omit"));
});
for (const change of ["token","account","clear"]) test(`late refresh discarded after ${change}`, async () => {
  const wait=deferred(); const {e}=setup(() => wait.promise);
  const pending=e("refresh").onclick();
  if(change === "clear") e("clear").onclick(); else { e(change).value="changed"; e(change).oninput(); }
  wait.resolve(response(summary)); await pending;
  assert.equal(e("summary").textContent, ""); assert.equal(e("records").textContent, "");
});
test("detached edit button cannot restore cleared private fields", async () => {
  const {e}=setup(async url => response(url.endsWith("summary") ? summary : {results:[record],next_after:null}));
  await e("refresh").onclick(); const edit=button(e("records"),"Review / correct this record");
  e("clear").onclick(); edit.onclick(); assert.equal(e("payload").value,"");
});
test("save requires explicit review, not extraction alone", async () => {
  let calls=0; const {e}=setup(async()=>{calls++;return response({});});
  await e("save").onclick(); assert.equal(calls,0);
  assert.match(e("status").textContent,/acknowledge/);
});
test("uncertain save retains idempotency key on exact retry", async () => {
  const keys=[]; const {e}=setup(async(url,opts)=>{keys.push(opts.headers["Idempotency-Key"]);throw new Error("offline");});
  e("payload").value=JSON.stringify(record.payload);e("evidence").value=id(3);e("quote").value="synthetic";e("reviewed").checked=true;
  await e("save").onclick();await e("save").onclick();
  assert.equal(keys.length,2);assert.equal(keys[0],keys[1]);
  e("quote").value="different";e("quote").oninput();e("reviewed").checked=true;
  await e("save").onclick();assert.notEqual(keys[2],keys[1]);
});
test("changing fields revokes review", () => {
  const {e}=setup();e("reviewed").checked=true;e("payload").oninput();assert.equal(e("reviewed").checked,false);
});
test("candidate is never automatically published", async () => {
  const calls=[];const {e}=setup(async(url,opts)=>{calls.push(url);return response({candidate:record.payload,source_quote:"synthetic"});});
  e("evidence").value=id(3);await e("extract").onclick();
  assert.equal(calls.length,1);assert.match(calls[0],/candidates/);assert.equal(e("reviewed").checked,false);
});
test("late suggestion does not overwrite user correction", async () => {
  const wait=deferred();const {e}=setup(()=>wait.promise);e("evidence").value=id(3);
  const pending=e("extract").onclick();e("payload").value="my correction";e("payload").oninput();
  wait.resolve(response({candidate:record.payload,source_quote:"synthetic"}));await pending;
  assert.equal(e("payload").value,"my correction");
});
test("change cursor is private to page and continues without consuming", async () => {
  const calls=[];const {e}=setup(async url=>{calls.push(url);return response({changes:[],next_cursor:id(7),has_more:false});});
  await e("changes").onclick();await e("changes").onclick();
  assert.match(calls[1],new RegExp(`after=${id(7)}`));e("clear").onclick();
  e("token").value="synthetic";await e("changes").onclick();assert.ok(!calls[2].includes("after="));
});
test("access denial clears rendered data", async () => {
  const {e}=setup(async()=>response({},403));e("records").textContent="private";
  await e("refresh").onclick();assert.equal(e("records").textContent,"");assert.match(e("status").textContent,/Access denied/);
});
