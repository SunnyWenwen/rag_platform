'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');

const html = fs.readFileSync(path.join(__dirname, '..', '01_ui_prototype.html'), 'utf8');
const elements = new Map();
function element(id) {
  return {
    id, value: '', innerHTML: '', textContent: '', style: {}, open: false,
    classList: {toggle() {}},
    addEventListener() {},
    insertAdjacentHTML(where, markup) {
      this.innerHTML = where === 'afterbegin' ? markup + this.innerHTML : this.innerHTML + markup;
    },
    showModal() { this.open = true; },
    close() { this.open = false; }
  };
}
for (const [, id] of html.matchAll(/\bid="([A-Za-z][A-Za-z0-9]+)"/g)) {
  elements.set(id, element(id));
}
const context = vm.createContext({
  document: {getElementById: id => elements.get(id) || null},
  assert, structuredClone, crypto: webcrypto, URL, window: {}, setTimeout() {}, clearTimeout() {}
});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
vm.runInContext(`
  const same = (actual, expected) => assert.equal(stableJSON(actual), stableJSON(expected));

  // A batch supplies one parameter set, and each document receives its own call plan.
  loadRemoteDemo('parsing_chunking_embedding');
  same(validate(config), []);
  const first = exampleIngestion(config);
  const second = {...first, document_id: 'manual-2'};
  const parameters = {remote_api_secret_ref: 'sample/api-token', language: 'zh-TW'};
  const state = validateRecords(config, [first, second], [], parameters);
  same(state.errors, []);
  same(state.request, {documents:[first, second], parameters});
  same(schemaIssues(state.request, ingestionRequestSchema(config), 'request'), []);
  assert.equal(state.remoteCalls.length, 2);
  for (const row of state.remoteCalls) {
    assert.equal(row.calls.length, 1);
    assert.equal(row.calls[0].secret_ref, 'sample/api-token');
    same(row.calls[0].parameters, {language:'zh-TW', chunk_size:512});
  }
  assert(validateRecords(config, [{...first, parameters}], [], parameters).errors.length);
  assert(validateRecords(config, [first], [], {}).errors.length);
  assert(validateRecords(config, [first, first], [], parameters).errors.length);
  assert(validateRecords(config, [], [], parameters).errors.length);
  assert(schemaIssues([first], ingestionRequestSchema(config), 'request').length);

  // The external search fixture follows Ingestion's effective candidate fields.
  loadInferenceRemoteDemo(false);
  const preview = remoteBoundary(config, 'retrieval');
  same(remoteResponseIssues(config, 'retrieval', preview.response), []);
  const invalid = clone(preview.response);
  invalid.output[0].result_sets[0].items[0].data.structdata.text = 42;
  assert(remoteResponseIssues(config, 'retrieval', invalid).some(issue => issue.includes('structdata.text')));
  assert.equal(inferenceReady({config, docs:0, needsIngest:true}), true);

  // Template selection copies defaults into the draft, keeping the published version reusable.
  assert.equal(typeof registerRemoteTemplate, 'undefined');
  for (let i = 0; i < adminTemplates.length; i++) {
    applySharedTemplate(i);
    same(validate(config), []);
    const applied = stableJSON(config);
    config.chunking.size = 9999;
    applySharedTemplate(i);
    assert.equal(stableJSON(config), applied);
  }
`, context);
assert(!html.includes('手動登錄 Remote API 模板'));
console.log('PASS: batch fan-out, Remote credentials, candidate validation, and versioned template selection');
