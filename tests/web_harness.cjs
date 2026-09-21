"use strict";
// Independent standard-library DOM contract harness, not a browser/accessibility proof.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase(); this.children = []; this.value = "";
    this._text = ""; this.hidden = false; this.disabled = false; this.attributes = {};
    this.dataset = {}; this.parentElement = null;
  }
  get textContent() { return this._text + this.children.map((n) => n.textContent ?? String(n)).join(""); }
  set textContent(value) { this.replaceChildren(); this._text = String(value); }
  set innerHTML(_) { assert.fail("UI must not render HTML"); }
  append(...nodes) {
    for (const node of nodes) { if (node instanceof Element) node.parentElement = this; this.children.push(node); }
  }
  replaceChildren(...nodes) {
    for (const node of this.children) if (node instanceof Element) node.parentElement = null;
    this.children = []; this._text = ""; this.append(...nodes);
  }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  remove() {
    if (this.parentElement) this.parentElement.children = this.parentElement.children.filter((n) => n !== this);
    this.parentElement = null;
  }
}

function harness(fetch) {
  const elements = new Map(), uuids = [];
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  const context = vm.createContext({
    document: {getElementById: element, createElement: (tag) => new Element(tag)},
    fetch,
    crypto: {randomUUID() {
      const id = `00000000-0000-4000-8000-${String(900 + uuids.length).padStart(12, "0")}`;
      uuids.push(id); return id;
    }},
  });
  const source = fs.readFileSync(path.join(__dirname, "../src/email_brain/web/app.js"), "utf8");
  vm.runInContext(source, context);
  return {element, uuids, evaluate: (code) => vm.runInContext(code, context)};
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
}
function response(data, status = 200) {
  return {ok: status >= 200 && status < 300, status, json: async () => data};
}
function descendants(element) {
  return element.children.flatMap((child) => child instanceof Element ? [child, ...descendants(child)] : []);
}
function buttons(element) {
  return descendants(element).filter((child) => child.tagName === "BUTTON" && typeof child.onclick === "function");
}
function button(element, text) {
  const found = buttons(element).find((child) => text instanceof RegExp ? text.test(child.textContent) : child.textContent === text);
  assert.ok(found, `missing button: ${text}`); return found;
}
module.exports = {Element, harness, deferred, response, descendants, buttons, button};
