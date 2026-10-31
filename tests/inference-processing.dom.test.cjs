// Real DOM events via jsdom; no browser layout or external service checks.
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('node:fs'),assert=require('node:assert/strict');
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
const dom=new JSDOM(fs.readFileSync(process.argv[2]||require('node:path').join(__dirname,'../01_ui_prototype.html'),'utf8'),{runScripts:'dangerously',url:'https://prototype.local',virtualConsole:vc,beforeParse(w){w.structuredClone=structuredClone;w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};}});
const w=dom.window,d=w.document,run=s=>w.eval(s),q=s=>{const el=d.querySelector(s);assert(el,'Missing '+s);return el;};
const ctl=path=>q('[data-path="'+path+'"]');
const change=(path,value)=>{const el=ctl(path);if(el.type==='checkbox')el.checked=value;else el.value=value;el.dispatchEvent(new w.Event('change',{bubbles:true}));};
const click=s=>q(s).click(),fresh=()=>run('openCreate()'),showModule=id=>run('selectMod('+JSON.stringify(id)+')');
const advanced=()=>{q('#resultAdvanced > summary').click();assert(q('#resultAdvanced').open);};
let count=0;
function test(name,fn){fresh();fn();count++;console.log('PASS '+name);}
test('basic UI and collapsed advanced defaults are one Config',()=>{
  showModule('retrieval');assert(!q('#resultAdvanced').open);assert.equal(ctl('retrieval.per_route_k').value,'10');
  const before=run('JSON.stringify(config)');advanced();assert.equal(run('JSON.stringify(config)'),before);
  for(const key of ['same_query','cross_query']){const el=ctl('retrieval.processing.'+key+'.enabled');assert(el.checked);assert(el.disabled);}
  assert(q('#resultAdvanced').textContent.includes('後端已融合'));assert(q('#resultAdvanced').textContent.includes('一個有效 Query'));
  assert(ctl('retrieval.processing.after_retrieval_top_n').disabled);assert(ctl('retrieval.processing.after_rerank_top_n').disabled);
  showModule('rerank');assert.equal(q('[data-rerank-content]').value,'text');assert.equal(ctl('rerank.top_n').value,'3');assert(!q('#rerankAdvanced').open);
});
test('details state persists through a change and resets for a new dialog',()=>{
  showModule('retrieval');advanced();change('retrieval.fusion','RRF');assert(q('#resultAdvanced').open);showModule('generation');showModule('retrieval');assert(q('#resultAdvanced').open);fresh();showModule('retrieval');assert(!q('#resultAdvanced').open);
});
test('upstream query and backend controls drive locked/active state',()=>{
  showModule('transform');change('transform.method','Multi-query');change('transform.count',2);showModule('retrieval');advanced();assert(!ctl('retrieval.processing.cross_query.enabled').disabled);assert(ctl('retrieval.processing.same_query.enabled').disabled);assert(!ctl('retrieval.processing.after_retrieval_top_n').disabled);assert(q('#resultPlanSummary').textContent.includes('3 Query × 1 份 ES Hybrid'));
  showModule('indexing');change('indexing.backend','Local Search');showModule('retrieval');assert(!ctl('retrieval.processing.same_query.enabled').disabled);assert(ctl('retrieval.output_mode').disabled);assert.equal(ctl('retrieval.output_mode').value,'independent');assert.equal(run('config.retrieval.output_mode'),'backend_fused');assert(!q('#createButton').disabled);
});
test('post-model merging keeps four limits and recomputes summary',()=>{
  showModule('indexing');change('indexing.backend','Local Search');showModule('transform');change('transform.method','Rewrite');showModule('retrieval');advanced();
  change('retrieval.per_route_k',2);change('retrieval.processing.after_retrieval_top_n',7);change('retrieval.processing.cross_query.at','after_rerank');change('retrieval.processing.after_rerank_top_n',8);
  assert(!ctl('retrieval.processing.after_rerank_top_n').disabled);showModule('rerank');change('rerank.top_n',4);assert(!q('#createButton').disabled);assert(q('#dynamicfields').textContent.includes('2 份 ResultSet'));
  q('#rerankAdvanced > summary').click();change('rerank.query_source','current');assert.equal(run('config.rerank.query_source'),'current');
  showModule('retrieval');change('retrieval.processing.cross_query.at','after_retrieval');assert(ctl('retrieval.processing.after_rerank_top_n').disabled);showModule('rerank');assert(ctl('rerank.query_source').disabled);assert.equal(ctl('rerank.query_source').value,'original');assert.equal(run('config.rerank.query_source'),'current');
  showModule('retrieval');change('retrieval.processing.cross_query.at','after_rerank');showModule('rerank');assert(!ctl('rerank.query_source').disabled);assert.equal(ctl('rerank.query_source').value,'current');
});
test('turning Rerank off disables its controls but preserves post processing',()=>{
  run('demoCase(6)');showModule('rerank');change('rerank.mode','None');assert(ctl('rerank.top_n').matches(':disabled'));assert(q('[data-rerank-content]').matches(':disabled'));assert(q('#dynamicfields').textContent.includes('不評分，仍執行後置處理'));assert(!q('#createButton').disabled);
  showModule('retrieval');assert(!ctl('retrieval.processing.after_rerank_top_n').disabled);assert(ctl('retrieval.processing.after_retrieval_top_n').disabled);
});
test('single-list document grouping enables its output limit',()=>{
  showModule('retrieval');advanced();change('retrieval.processing.merge_key','document_id');assert(!ctl('retrieval.processing.after_retrieval_top_n').disabled);assert(q('#dynamicfields').textContent.includes('原 chunk_id／引用不變'));change('retrieval.processing.document_at','after_rerank');assert(ctl('retrieval.processing.after_retrieval_top_n').disabled);assert(!ctl('retrieval.processing.after_rerank_top_n').disabled);assert(!q('#createButton').disabled);
});
test('invalid content field stays selected, error focuses the module and blocks save',()=>{
  run('config=exampleConfig()');showModule('rerank');const content=q('[data-rerank-content]');content.value='summary';content.dispatchEvent(new w.Event('change',{bubbles:true}));assert.equal(run('config.rerank.content[0]'),'summary');
  showModule('chunking');click('[data-pick="chunking.copy"][value="summary"]');assert(q('#createButton').disabled);const issue=Array.from(d.querySelectorAll('.validation-link')).find(x=>x.textContent.includes('[Rerank／評分內容]'));assert(issue);issue.click();assert.equal(run('selected'),'rerank');assert.equal(q('[data-rerank-content]').value,'summary');assert(q('[data-rerank-content] option[value="summary"]').disabled);assert.equal(d.activeElement,q('[data-rerank-content]'));
  q('[data-rerank-content]').value='text';q('[data-rerank-content]').dispatchEvent(new w.Event('change',{bubbles:true}));assert.equal(run('config.rerank.content[0]'),'text');assert(q('#createButton').disabled);showModule('chunking');click('[data-pick="chunking.copy"][value="summary"]');assert(!q('#createButton').disabled);
});
test('unused type/unindexed choices are visible disabled, not silently substituted',()=>{
  run("config.document_schema.fields.push(schemaField('price','number'));config.document_schema.fields.push(schemaField('summary'))");showModule('rerank');assert(q('[data-rerank-content] option[value="price"]').disabled);assert(q('[data-rerank-content] option[value="summary"]').disabled);showModule('retrieval');assert(q('[data-pick="retrieval.fulltext"][value="summary"]').disabled);assert.equal(run('config.rerank.content[0]'),'text');
});
test('advanced error remains visible collapsed and click opens correct section',()=>{
  showModule('indexing');change('indexing.backend','Local Search');showModule('retrieval');advanced();change('retrieval.processing.same_query.method','Sum Score');q('#resultAdvanced > summary').click();assert(!q('#resultAdvanced').open);assert(q('#createButton').disabled);
  const issue=Array.from(d.querySelectorAll('.validation-link')).find(x=>x.textContent.includes('[Retrieval／同 Query 合併]'));assert(issue);issue.click();assert(q('#resultAdvanced').open);assert.equal(run('selected'),'retrieval');assert(d.activeElement.dataset.path.startsWith('retrieval.processing.same_query'));
  change('retrieval.processing.same_query.normalization','min_max');assert(!q('#createButton').disabled);
});
test('Sum Score conditional weights, RRF and draft parameters survive toggles',()=>{
  showModule('indexing');change('indexing.backend','Local Search');showModule('retrieval');advanced();change('retrieval.processing.same_query.method','Sum Score');assert(!d.querySelector('[data-path="retrieval.processing.same_query.rrf_k"]'));change('retrieval.processing.same_query.normalization','min_max');change('retrieval.processing.same_query.weights.fulltext:text',0.4);change('retrieval.processing.same_query.method','RRF');assert(!d.querySelector('[data-path="retrieval.processing.same_query.weights.fulltext:text"]'));assert(!q('#createButton').disabled);change('retrieval.processing.same_query.method','Sum Score');assert.equal(ctl('retrieval.processing.same_query.weights.fulltext:text').value,'0.4');assert(!q('#createButton').disabled);
});
test('unchecked preferences survive inapplicability and reactivation',()=>{
  showModule('transform');change('transform.method','Rewrite');showModule('retrieval');advanced();change('retrieval.processing.cross_query.enabled',false);assert(q('#createButton').disabled);showModule('transform');change('transform.method','None');showModule('retrieval');assert(ctl('retrieval.processing.cross_query.enabled').disabled);assert(!ctl('retrieval.processing.cross_query.enabled').checked);assert(!q('#createButton').disabled);showModule('transform');change('transform.method','Rewrite');showModule('retrieval');assert(!ctl('retrieval.processing.cross_query.enabled').disabled);assert(!ctl('retrieval.processing.cross_query.enabled').checked);assert(q('#createButton').disabled);
});
test('invalid timing for final document dedup is actionable',()=>{
  run('demoCase(6)');change('retrieval.processing.merge_key','document_id');assert(q('#createButton').disabled);assert(q('#validation').textContent.includes('[Retrieval／文件去重]'));change('retrieval.processing.document_at','after_rerank');assert(!q('#createButton').disabled);
});
test('Create/Edit/Cancel, inference readiness, effective export and mock question',()=>{
  run('demoCase(5)');q('#systemName').value='Inference UI';click('#createButton');assert(!q('#createDialog').open);run("openOperation(systems.at(-1).id,'ingest');ingestDemoRecords();$('operationDialog').close();openEdit(systems.at(-1).id)");showModule('retrieval');advanced();change('retrieval.processing.cross_query.at','after_rerank');assert(q('#changeImpact').textContent.includes('不需重新 Ingestion'));click('#createButton');assert(!run('systems.at(-1).needsIngest'));
  run('openEdit(systems.at(-1).id)');showModule('retrieval');assert.equal(ctl('retrieval.processing.cross_query.at').value,'after_rerank');change('retrieval.processing.cross_query.enabled',false);q('#createDialog .close').click();assert(run('systems.at(-1).config.retrieval.processing.cross_query.enabled'));
  run("openOperation(systems.at(-1).id,'inference')");q('#question').value='設備多久保養？';click('#inferenceRun');assert(q('#opResult').textContent.includes('示意回答'));assert(q('#opResult').textContent.includes('評分提問（示例）：設備多久保養？'));assert(q('#opResult').textContent.includes('Reranker 後'));assert(q('#opResult').textContent.includes('非實際命中'));
  run("$('operationDialog').close();exportSystem(systems.at(-1).id)");assert(q('#exportReady').disabled);for(const el of d.querySelectorAll('[data-export$=".url"]')){el.value='https://api.example/v1';el.dispatchEvent(new w.Event('input',{bubbles:true}));}assert(!q('#exportReady').disabled);assert.equal(run('blueprint(deploymentConfig(),false).pipelines.inference.retrieval.processing.cross_query.at'),'after_rerank');
});
assert.deepEqual(errors,[]);dom.window.close();console.log(`${count} inference DOM flows passed; no page-script errors. Browser layout unverified.`);
