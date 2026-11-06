// Approved v0.12 interactions. No API, model, tokenizer or deployment is executed.
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
const dom=new JSDOM(fs.readFileSync(path.join(__dirname,'../01_ui_prototype.html'),'utf8'),{runScripts:'dangerously',url:'https://prototype.local',virtualConsole:vc,beforeParse(w){w.structuredClone=structuredClone;w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};}});
const w=dom.window,d=w.document,run=s=>w.eval(s),json=s=>JSON.parse(JSON.stringify(run(s))),q=s=>{const el=d.querySelector(s);assert(el,'Missing '+s);return el;};
const change=(selector,value)=>{const el=q(selector);el.type==='checkbox'?el.checked=value:el.value=value;el.dispatchEvent(new w.Event('change',{bubbles:true}));};
let count=0;function test(name,fn){run('openCreate()');fn();count++;console.log('PASS '+name);}
test('composition is opt-in, previews exact substitution, preserves sources and updates downstream pickers',()=>{
 run("selectMod('embedding')");assert(!q('#compositionAdvanced').open);assert(!run('compositionOn(config)'));q('#compositionAdvanced').open=true;
 run("config.parsing.field_rules.fields.push(schemaField('title','string',true));config.chunking.copy=['title'];selectMod('embedding')");
 change('[data-path="embedding.composition.enabled"]',true);assert(q('#compositionAdvanced').open);change('[data-path="embedding.mappings.0.source"]','embedding_text');
 const chunk=json('previewChunks(config,exampleDocument(config))[0]');assert.equal(chunk.fields.embedding_text,'標題：設備保養規範\n內容：設備每月需清潔散熱孔。');assert.equal(chunk.fields.text,'設備每月需清潔散熱孔。');assert.equal(chunk.vectors.text.source_field,'embedding_text');assert(!chunk.metadata._rag);
 run("selectMod('indexing')");assert(q('[data-pick="indexing.fulltext"][value="embedding_text"]'));assert(q('[data-pick="indexing.filters"][value="fields.embedding_text"]'));run("selectMod('rerank')");assert(!q('[data-rerank-content] option[value="embedding_text"]').disabled);
 run('showCompositionExample()');assert(q('#helpBody').textContent.includes('組合前'));assert(q('#helpBody').textContent.includes('組合後'));run("$('helpDialog').close()");
});
test('template errors, missing task fields, unknown vars and output collisions block saving',()=>{
 run("demoCase(8);config.embedding.composition.output_field='text';valid()");assert(q('#createButton').disabled);assert(q('#validation').textContent.includes('不可覆寫'));
 run("config.embedding.composition.output_field='embedding_text';config.embedding.composition.template='{{fields.unknown}}';valid()");assert(q('#createButton').disabled);
 run("config.embedding.composition.template='{{fields.text}';valid()");assert(q('#createButton').disabled);
 run("config.embedding.composition.template='{{fields.title}}';config.chunking.copy=[];valid()");assert(q('#createButton').disabled);
});
test('inactive template draft is retained but excluded from effective impact and export',()=>{
 const before=run('JSON.stringify(effectiveConfig(config))');run("config.embedding.composition.template='invalid{{';config.embedding.composition.output_field='text'");assert.equal(run('JSON.stringify(effectiveConfig(config))'),before);assert.deepEqual(json('validate(config)'),[]);
 run("config.embedding.composition.enabled=true");assert(json('validate(config)').length);
});
test('original field copy and extra original chunk are independent, only same unit/task full slice dedups',()=>{
 run("config.embedding.composition.enabled=false;config.chunking.tasks=[{task_id:'text',split_field:'text',output_field:'text',copy_fields:[{source_field:'page',output_field:'page'}]}]");
 w.doc={document_id:'d',source_revision:'v1',units:[{text:'清潔前先斷電。',page:1},{text:'每月清潔散熱孔並檢查風扇運轉。',page:2}],metadata:{}};
 assert.equal(run('previewChunks(config,doc,{characterSize:10,embed:false}).length'),3);
 run('config.chunking.include_original_chunk=true');let chunks=json('previewChunks(config,doc,{characterSize:10,embed:false})');assert.equal(chunks.length,4);assert.equal(chunks.at(-1).fields.text,w.doc.units[1].text);assert.deepEqual(chunks.map(c=>c.fields.page),[1,2,2,2]);assert(chunks.every(c=>Object.keys(c.vectors).length===0));assert.equal(new Set(chunks.map(c=>c.chunk_id)).size,4);
 run("doc.metadata.chunking_mode='passthrough'");assert.equal(run('previewChunks(config,doc,{characterSize:10,embed:false}).length'),2);
 run("doc.units=[{text:'同一段',page:1},{text:'同一段',page:2}];delete doc.metadata.chunking_mode");assert.equal(run('previewChunks(config,doc,{characterSize:10,embed:false}).length'),2);
 run('delete config.chunking.tasks;config.chunking.preserve_original=true');assert.equal(json('previewChunks(config,exampleDocument(config),{embed:false})')[0].fields.original_text,'設備每月需清潔散熱孔。');
});
test('Developer Local form follows schema and validates parameters without another pod',()=>{
 run("selectMod('chunking')");change('#componentPicker','developer.paragraph_chunker@1.0.0');assert(q('[data-path="components.chunking.params.max_chars"]'));assert(!d.querySelector('[data-path="chunking.size"]'));assert(q('#dynamicfields').textContent.includes('不另起 Pod'));
 change('[data-path="components.chunking.params.max_chars"]',1);assert(q('#createButton').disabled);assert(q('#validation').textContent.includes('max_chars'));
 change('[data-path="components.chunking.params.max_chars"]',600);assert(!q('#createButton').disabled);assert.equal(run('effectiveConfig(config).chunking.component_id'),'developer.paragraph_chunker');
});
test('remote pipeline is picked at first module, locks covered modules, suppresses local config and resources',()=>{
 run("config.chunking.size=321;selectMod('parsing')");change('#componentPicker','remote.document_pipeline@1.0.0');assert(!q('#createButton').disabled);run("selectMod('chunking')");assert(q('#dynamicfields fieldset').disabled);assert(q('#dynamicfields').textContent.includes('管理'));assert(!q('[data-owner]').disabled);
 const c=json('effectiveConfig(config)');assert.deepEqual(c.chunking,{managed_by:'parsing'});assert.deepEqual(c.embedding,{managed_by:'parsing'});assert(!json('resources(config)').some(r=>r.path==='embedding'));
 run("selectMod('parsing')");change('#componentPicker','builtin');assert.equal(run('config.chunking.size'),321);assert.equal(run('effectiveConfig(config).chunking.size'),321);
});
test('fixed external service has no parameter or endpoint input; invalid refs and index capabilities remain visible',()=>{
 run("selectMod('parsing')");change('#componentPicker','remote.fixed_parser@2.0.0');assert(!d.querySelector('[data-path^="components.parsing.params"]'));assert(!d.querySelector('#dynamicfields input'));assert(q('#dynamicfields').textContent.includes('共用'));
 run("config.components.parsing.version='deleted';selectMod('parsing')");assert(q('#componentPicker').textContent.includes('已失效'));assert(q('#createButton').disabled);
 run("config=defaults();selectMod('indexing')");assert(q('#componentPicker option[value="remote.indexing@1.0.0"]').disabled);
 run("config.indexing.backend='Local Search';selectMod('retrieval')");assert(q('#componentPicker option[value="remote.retrieval@1.0.0"]').disabled);
});
test('overlapping selections and unavailable service block saving with module errors',()=>{
 run("chooseComponent('chunking','remote.chunking@1.0.0');chooseComponent('parsing','remote.document_pipeline@1.0.0')");assert(q('#createButton').disabled);assert(q('#validation').textContent.includes('重疊'));
 run("config=defaults();config.components.parsing={id:'remote.unavailable_parser',version:'1.0.0',params:{}};selectMod('parsing')");assert(q('#createButton').disabled);assert(q('#componentPicker option[value="remote.unavailable_parser@1.0.0"]').disabled);
});
test('Image and External exports differ, instance/data refs are per system and no space selector is introduced',()=>{
 run("chooseComponent('parsing','remote.document_pipeline@1.0.0');active={id:'A',group:0,name:'remote',collection:'remote-A',revision:1,config:clone(config)}");const y=run('yaml(config,true)');assert(y.includes('remote-service'));assert(y.includes('parameters.json'));assert(y.includes('readinessProbe'));assert.equal((y.match(/kind: Deployment/g)||[]).length,2);assert(!y.includes('data_space_id'));
 assert.notEqual(run("remoteBindings(config,'A')[0].instance_name"),run("remoteBindings(config,'B')[0].instance_name"));assert.notEqual(run("remoteBindings(config,'A')[0].data_binding_ref"),run("remoteBindings(config,'B')[0].data_binding_ref"));
 run("chooseComponent('parsing','remote.fixed_parser@2.0.0')");const x=run('yaml(config,true)');assert.equal((x.match(/kind: Deployment/g)||[]).length,1);assert(x.includes('admin-binding/remote.fixed_parser/TARGET_ENV'));
});
test('Query API and UI use root array, filters/metadata copied with no historical wrapper or ranks',()=>{
 run("$('createDialog').close();openOperation(systems[0].id,'inference')");q('#question').value='保養？';q('#queryMetadata').value='{"language":"zh-TW"}';q('#queryMetadata').dispatchEvent(new w.Event('input',{bubbles:true}));q('#inferenceRun').click();const data=JSON.parse(q('#opResult').textContent);assert(Array.isArray(data));assert.equal(data[0].metadata.language,'zh-TW');assert.deepEqual(Object.keys(data[0]),['ori_query','query','filters','result_sets','metadata']);
 assert.deepEqual(Object.keys(data[0].result_sets[0]),['key','items']);assert.deepEqual(Object.keys(data[0].result_sets[0].items[0]),['chunk','score']);
 q('#queryMetadata').value='[]';q('#queryMetadata').dispatchEvent(new w.Event('input',{bubbles:true}));assert(q('#inferenceRun').disabled);
 const api=json("runtimeApiSample(active,'inference')");assert(Array.isArray(api.response));assert.deepEqual(api.response[0].metadata,api.request.metadata);assert(api.response.every(x=>Array.isArray(x.filters)));
});
test('new settings survive Save/Edit; Cancel preserves saved config and changes prompt reingestion',()=>{
 run("demoCase(8);config.chunking.include_original_chunk=true;$('systemName').value='v12';createSystem();openEdit(systems.at(-1).id)");assert(run('config.embedding.composition.enabled'));assert(run('config.chunking.include_original_chunk'));const saved=run('JSON.stringify(systems.at(-1).config)');run("config.embedding.composition.template='changed {{fields.text}}';$('createDialog').close()");assert.equal(run('JSON.stringify(systems.at(-1).config)'),saved);
 assert(run("(()=>{const c=clone(systems.at(-1).config);c.chunking.include_original_chunk=false;return impact(systems.at(-1).config,c).ingestion})()"));
});
test('AI mock proposes new configuration only as a validated draft',()=>{
 q('#helperRequest').value='欄位組合，額外保留原文 Chunk';run('propose()');assert(!q('#applySuggestion').disabled);assert(!run('config.embedding.composition.enabled'));run('applySuggestion()');assert(run('config.embedding.composition.enabled'));assert(run('config.chunking.include_original_chunk'));assert.equal(run('config.embedding.mappings[0].source'),'embedding_text');
});
assert.deepEqual(errors,[]);dom.window.close();console.log(`${count} v0.12 DOM flows passed. All services remain simulated.`);
