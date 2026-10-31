// Dependency-free tests of the UI's logical plan, not a search/RAG Engine implementation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2]||require('node:path').join(__dirname,'../01_ui_prototype.html'),'utf8');
const elements=new Map();
function el(id){if(!elements.has(id))elements.set(id,{id,value:'',textContent:'',innerHTML:'',files:[],style:{},listeners:{},classList:{toggle(){}},addEventListener(t,f){this.listeners[t]=f;},showModal(){this.open=true;},close(){this.open=false;},focus(){},click(){}});return elements.get(id);}
const context={document:{getElementById:el,createElement:()=>({click(){}})},crypto:require('node:crypto').webcrypto,URL,Blob,structuredClone,console,setTimeout,clearTimeout,window:{}};
vm.createContext(context);vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const run=s=>vm.runInContext(s,context),copy=v=>JSON.parse(JSON.stringify(v));let count=0;
const fresh=()=>run('openCreate()'),plan=()=>copy(run('resultPlan(config)')),effective=()=>copy(run('effectiveConfig(config)'));
function test(name,fn){fresh();fn();count++;console.log('PASS '+name);}
test('Create defaults and no-op ES single Query',()=>{
  assert(run('config.retrieval.processing.same_query.enabled'));assert(run('config.retrieval.processing.cross_query.enabled'));
  assert.equal(run('config.retrieval.processing.same_query.at'),'after_retrieval');assert.equal(run('config.retrieval.processing.cross_query.at'),'after_retrieval');
  assert.equal(run('resultAdvancedOpen'),false);assert.deepEqual(copy(run('config.rerank.content')),['text']);assert.equal(run('config.rerank.top_n'),3);
  const p=plan();assert.equal(p.initial.length,1);assert.equal(p.rerankInputs.length,1);assert(!p.before.enabled);assert.equal(p.upper,3);
  assert(!effective().retrieval.processing.same_query);assert(!effective().retrieval.processing.cross_query);
});
test('multi Query ES Hybrid merges only across queries',()=>{
  run("config.transform.method='Multi-query';config.transform.count=3");const p=plan();assert.equal(p.initial.length,4);assert(!p.before.same);assert(p.before.cross);assert.equal(p.rerankInputs.length,1);assert.equal(p.upper,3);assert.equal(run('validate(config).length'),0);
});
test('two queries by two routes preserve two grouping dimensions',()=>{
  run("config.indexing.backend='Local Search';config.transform.method='Rewrite'");let p=plan();assert.equal(p.initial.length,4);assert.equal(p.rerankInputs.length,1);
  run("config.retrieval.processing.cross_query.at='after_rerank'");p=plan();assert.equal(p.rerankInputs.length,2);assert(p.rerankInputs.every(x=>x.queries.length===1&&x.routes.length===2));assert.equal(p.final.length,1);
  run("config.retrieval.processing.same_query.at='after_rerank';config.retrieval.processing.cross_query.at='after_retrieval'");p=plan();assert.equal(p.rerankInputs.length,2);assert(p.rerankInputs.every(x=>x.queries.length===2&&x.routes.length===1));assert.equal(p.final.length,1);
  run("config.retrieval.processing.cross_query.at='after_rerank'");assert.equal(plan().rerankInputs.length,4);assert.equal(plan().final.length,1);
});
test('all four placement combinations work across ES independent and Local',()=>{
  for(const backend of ['Elasticsearch','Local Search'])for(const same of ['after_retrieval','after_rerank'])for(const cross of ['after_retrieval','after_rerank']){
    run(`config.indexing.backend=${JSON.stringify(backend)};config.retrieval.output_mode='independent';config.transform.method='Rewrite';config.retrieval.processing.same_query.at=${JSON.stringify(same)};config.retrieval.processing.cross_query.at=${JSON.stringify(cross)}`);
    assert.equal(plan().initial.length,4);assert.equal(plan().final.length,1);assert.equal(run('validate(config).length'),0);
  }
});
test('four limits independently shape output, not a monotone sequence',()=>{
  run("config.indexing.backend='Local Search';config.transform.method='Rewrite';config.retrieval.per_route_k=2;config.retrieval.processing.after_retrieval_top_n=7;config.retrieval.processing.cross_query.at='after_rerank';config.rerank.top_n=4;config.retrieval.processing.after_rerank_top_n=8");
  const p=plan();assert.equal(p.before.lists[0].upper,4);assert.equal(p.scored[0].upper,4);assert.equal(p.upper,8);assert.equal(run('validate(config).length'),0);
});
test('insufficient candidates are bounded, never filled to Top N',()=>{run('config.retrieval.per_route_k=1;config.rerank.top_n=3');assert.equal(plan().upper,1);assert.equal(run('validate(config).length'),0);});
test('only active action limits validate/export; raw draft preserved',()=>{
  run('config.retrieval.processing.after_retrieval_top_n=0;config.retrieval.processing.after_rerank_top_n=-1');assert.equal(run('validate(config).length'),0);const e=effective();assert(!Object.hasOwn(e.retrieval.processing,'after_retrieval_top_n'));assert(!Object.hasOwn(e.retrieval.processing,'after_rerank_top_n'));assert.equal(run('config.retrieval.processing.after_retrieval_top_n'),0);
  run("config.indexing.backend='Local Search'");assert(run('validate(config)').some(x=>x.includes('Retrieval 後 Top N')));
});
test('None does not drop post-rerank merging or validate hidden rerank values',()=>{
  run("config.transform.method='Rewrite';config.retrieval.processing.cross_query.at='after_rerank';config.rerank.mode='None';config.rerank.top_n=0;config.rerank.content=['missing']");const p=plan();assert(p.after.cross);assert.equal(p.upper,3);assert.equal(run('validate(config).length'),0);assert.deepEqual(effective().rerank,{mode:'None'});assert.equal(effective().retrieval.processing.cross_query.at,'after_rerank');assert(run('planText(config)').includes('不評分，仍執行後置處理'));
});
test('single-result document grouping is independent of list merging',()=>{
  run("config.retrieval.processing.merge_key='document_id'");const p=plan();assert(p.before.document);assert(!p.before.same&&!p.before.cross);assert.equal(effective().retrieval.processing.merge_key,'document_id');assert.equal(effective().retrieval.processing.after_retrieval_top_n,5);assert.equal(run('validate(config).length'),0);
});
test('document grouping must follow the final merge to avoid duplicate documents',()=>{
  run("config.transform.method='Rewrite';config.retrieval.processing.merge_key='document_id';config.retrieval.processing.cross_query.at='after_rerank'");assert(run('validate(config)').some(x=>x.includes('[Retrieval／文件去重]')));run("config.retrieval.processing.document_at='after_rerank'");assert.equal(run('validate(config).length'),0);assert(plan().after.document);
});
test('only chunk_id/document_id supported and inactive document timing omitted',()=>{run("config.retrieval.processing.document_at='bad'");assert.equal(run('validate(config).length'),0);assert(!Object.hasOwn(effective().retrieval.processing,'document_at'));run("config.retrieval.processing.merge_key='doc_id'");assert(run('validate(config)').some(x=>x.includes('merge_key')));});
test('current-query draft preserved but original query used after cross merge',()=>{
  run("config.transform.method='Rewrite';config.rerank.query_source='current'");assert(!plan().queryAllowed);assert.equal(effective().rerank.query_source,'original');assert.equal(run('config.rerank.query_source'),'current');run("config.retrieval.processing.cross_query.at='after_rerank'");assert(plan().queryAllowed);assert.equal(effective().rerank.query_source,'current');
});
test('Reranker fields must exist, be strings, be inherited and stored',()=>{
  run("config=exampleConfig();config.rerank.content=['summary'];config.chunking.copy=config.chunking.copy.filter(x=>x!=='summary')");assert(run('resultErrors(config)').some(x=>x.includes('fields.summary')));assert.deepEqual(copy(run('config.rerank.content')),['summary']);
  run("config.chunking.copy.push('summary');config.document_schema.fields.find(f=>f.name==='summary').type='number'");assert(run('resultErrors(config)').some(x=>x.includes('fields.summary')));
  run("config.document_schema.fields.find(f=>f.name==='summary').type='string';config.chunking.copy=[]");assert(run('resultErrors(config)').some(x=>x.includes('fields.summary')));
});
test('selected routes retain identities and stale refs fail without substitution',()=>{
  run("config=exampleConfig();config.indexing.backend='Local Search';config.transform.method='Rewrite';config.retrieval.processing.same_query.route_scope='selected';config.retrieval.processing.same_query.routes=['fulltext:text','vector:text']");const p=plan();assert.equal(p.final.length,2);assert(p.final.some(x=>x.routes.length===2));assert(run('resultErrors(config)').some(x=>x.includes('Generation 需一份')));
  run("config.retrieval.vectors=['summary_vector']");assert(run('resultErrors(config)').some(x=>x.includes('至少兩個有效')));assert(run("config.retrieval.processing.same_query.routes.includes('vector:text')"));
});
test('single Query/route toggles preserve unchecked preferences',()=>{
  run("config.retrieval.processing.same_query.enabled=false;config.retrieval.processing.cross_query.enabled=false;config.retrieval.processing.same_query.rrf_k=0;config.retrieval.processing.cross_query.rrf_k=0");assert.equal(run('validate(config).length'),0);run("config.indexing.backend='Local Search';config.transform.method='Rewrite'");assert(!run('config.retrieval.processing.same_query.enabled'));assert(!run('config.retrieval.processing.cross_query.enabled'));assert(!run('resultErrors(config)').some(x=>x.includes('RRF k')));assert(run('resultErrors(config)').some(x=>x.includes('Generation 需一份')));
});
test('RRF and Sum Score validate/export only selected parameters',()=>{
  run("config.indexing.backend='Local Search';config.retrieval.processing.same_query.method='Sum Score'");assert(run('resultErrors(config)').some(x=>x.includes('分數可比')));run("config.retrieval.processing.same_query.normalization='min_max';config.retrieval.processing.same_query.rrf_k=0");assert.equal(run('validate(config).length'),0);let x=effective().retrieval.processing.same_query;assert(!Object.hasOwn(x,'rrf_k'));assert.deepEqual(x.weights,{'fulltext:text':1,'vector:text':1});
  run("config.retrieval.processing.same_query.weights['fulltext:text']=0;config.retrieval.processing.same_query.weights['vector:text']=0");assert(run('resultErrors(config)').some(x=>x.includes('權重')));run("config.retrieval.processing.same_query.method='RRF';config.retrieval.processing.same_query.rrf_k=60");assert.equal(run('validate(config).length'),0);x=effective().retrieval.processing.same_query;assert(!Object.hasOwn(x,'weights'));assert(!Object.hasOwn(x,'normalization'));
});
test('weights attach to stable query identities, not list indices',()=>{
  run("config.transform.method='Multi-query';config.retrieval.processing.cross_query.method='Sum Score';config.retrieval.processing.cross_query.normalization='min_max';config.retrieval.processing.cross_query.weights.original=0.7;config.retrieval.processing.cross_query.weights['rewrite-1']=0.2");assert.equal(effective().retrieval.processing.cross_query.weights.original,0.7);run('config.transform.include_original=false');const w=effective().retrieval.processing.cross_query.weights;assert(!Object.hasOwn(w,'original'));assert.equal(w['rewrite-1'],0.2);assert.equal(run('config.retrieval.processing.cross_query.weights.original'),0.7);
});
test('disabled ES draft parameters never affect Local effective plan',()=>{
  run("config.indexing.backend='Local Search';config.retrieval.fusion='unsupported';config.retrieval.score_weights.vector=-1");assert.equal(run('validate(config).length'),0);assert.equal(effective().retrieval.output_mode,'independent');assert(!Object.hasOwn(effective().retrieval,'fusion'));run("config.indexing.backend='Elasticsearch'");assert(run('validate(config).length')>0);
});
test('invalid actions, query counts, limits and capabilities are blocked',()=>{
  for(const stmt of ["config.retrieval.per_route_k=0","config.retrieval.per_route_k=1.5","config.retrieval.output_mode='unknown'","config.rerank.mode='unknown'","config.rerank.top_n=NaN","config.transform.method='Multi-query';config.transform.count=33","config.indexing.backend='Local Search';config.retrieval.processing.same_query.at='unknown'","config.indexing.backend='Local Search';config.retrieval.processing.same_query.method='unknown'"]){fresh();run(stmt);assert(run('validate(config).length')>0,stmt);}
});
test('only inference impact; inactive settings do not invalidate results',()=>{
  assert(run("(()=>{const c=clone(config);c.retrieval.output_mode='independent';const x=impact(config,c);return !x.ingestion&&x.changed.includes('retrieval')})()"));
  assert(!run("(()=>{const c=clone(config);c.retrieval.processing.same_query.rrf_k=99;return impact(config,c).changed.length})()"));
});
test('Edit/Cancel preserves saved options and effective deployment parity',()=>{
  run("config.retrieval.processing.same_query.enabled=false;config.retrieval.processing.cross_query.enabled=false;$('systemName').value='Result edit';createSystem();openEdit(systems.at(-1).id)");assert(!run('config.retrieval.processing.same_query.enabled'));run("config.retrieval.processing.same_query.enabled=true;$('createDialog').close();openEdit(systems.at(-1).id)");assert(!run('config.retrieval.processing.same_query.enabled'));
  run("exportSystem(systems.at(-1).id);for(const r of resources(exportDraft)){get(r.path,exportDraft).url=r.kind==='Elasticsearch'?'https://es.example:9200':'https://api.example/v1';}");assert.deepEqual(copy(run('blueprint(active.config,true).pipelines.inference.retrieval.processing')),copy(run('blueprint(deploymentConfig(),false).pipelines.inference.retrieval.processing')));
});
test('AI proposal retains existing processing settings and applies as a draft',()=>{
  run('config.retrieval.processing.same_query.rrf_k=77');el('helperRequest').value='改用 Local Search';run('propose()');assert.equal(run('config.indexing.backend'),'Elasticsearch');run('applySuggestion()');assert.equal(run('config.indexing.backend'),'Local Search');assert.equal(run('config.retrieval.processing.same_query.rrf_k'),77);assert.equal(run('validate(config).length'),0);
});
test('all new demonstration cases have valid plans, except intended error demo',()=>{
  for(const n of [5,6,7]){run('demoCase('+n+')');assert.equal(run('validate(config).length'),0);assert.equal(plan().final.length,1);}run('demoCase(4)');assert(run('validate(config)').some(x=>x.includes('正整數')));
});
console.log(`${count} inference processing checks passed. UI planning only; no actual services called.`);
