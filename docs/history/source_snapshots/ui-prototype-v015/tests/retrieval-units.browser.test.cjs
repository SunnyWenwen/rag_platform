// npm dependencies: playwright; @sparticuz/chromium only for its bundled launch args.
// Optional CHROMIUM_EXECUTABLE points to a prepared Chromium binary.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');const {chromium}=require('playwright');
(async()=>{
 const args=process.env.CHROMIUM_ARGS_JSON?JSON.parse(process.env.CHROMIUM_ARGS_JSON):process.env.CHROMIUM_EXECUTABLE?(await import(require.resolve('@sparticuz/chromium'))).default.args:[];
 const browser=await chromium.launch({headless:true,args,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{})});
 try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.setDefaultTimeout(12000);
 const output=process.env.QA_OUTPUT_DIR||path.resolve(__dirname,'../browser-qa');fs.mkdirSync(output,{recursive:true});
 await page.goto(pathToFileURL(path.resolve(__dirname,'../01_ui_prototype.html')).href);
 if(process.env.QA_FONT_CSS){const font=path.resolve(process.env.QA_FONT_CSS);const css=fs.readFileSync(font,'utf8').replaceAll('./files/',pathToFileURL(path.join(path.dirname(font),'files')).href+'/');await page.addStyleTag({content:css+'body{font-family:"Noto Sans TC",sans-serif}'});await page.evaluate(()=>document.fonts.ready);}
 const run=code=>page.evaluate(code);
 const screenshot=async name=>page.screenshot({path:path.join(output,name+'.png')});
 const fits=async()=>assert(await run('document.documentElement.scrollWidth<=innerWidth'),'page overflows viewport');
 assert.equal(await page.title(),'Retrieval Builder · UI Prototype');await fits();await screenshot('desktop-home');
 await page.getByRole('button',{name:'＋ Create Retrieval System'}).click();
 assert(!await page.locator('#querynodes').textContent().then(s=>s.includes('Generation')));
 await run("selectMod('parsing')");await page.locator('#parsingAdvanced > summary').click();await page.getByRole('button',{name:'Units 契約範例'}).click();assert((await page.locator('#helpBody').textContent()).includes('2＋3＝5'));await page.locator('#helpDialog .close').click();
 await run("selectMod('chunking')");await page.locator('[data-path="chunking.method"]').selectOption('Header-aware');assert(!await page.locator('#createButton').isDisabled());await screenshot('desktop-chunking');
 await page.locator('#systemName').fill('Browser QA');await page.locator('#createButton').click();
 const id=await run('systems.at(-1).id');await run(`openEdit('${id}')`);await run("selectMod('chunking')");await page.locator('[data-path="chunking.size"]').fill('128');await page.locator('[data-path="chunking.size"]').blur();await page.locator('#createDialog .close').click();assert.equal(await run('systems.at(-1).config.chunking.size'),512);
 await run(`openOperation('${id}','ingest')`);
 await page.locator('#documents').setInputFiles({name:'test.csv',mimeType:'text/csv',buffer:Buffer.from('body\n清潔前先斷電。\n每月清潔散熱孔。')});
 await page.locator('[data-csv-target="fields.text"]').selectOption('body');assert(!await page.locator('#ingestRun').isDisabled());assert((await page.locator('#ingestParsed').textContent()).includes('units'));await page.locator('#ingestRun').click();assert.equal(await run('active.docs'),2);
 await page.locator('#operationDialog .close').click();await run(`openOperation('${id}','inference')`);await page.locator('#question').fill('清潔前要注意什麼？');await page.locator('#inferenceRun').click();assert((await page.locator('#opResult').textContent()).includes('result_sets'));await screenshot('desktop-retrieval');
 await page.locator('[data-api-help="inference"]').click();assert(!(await page.locator('#helpBody').textContent()).includes('citations'));await page.locator('#helpDialog .close').click();await page.locator('#operationDialog .close').click();
 await run(`openEdit('${id}');config.indexing.backend='Local Search';config.transform.method='Multi-query';config.retrieval.processing.same_query.enabled=false;config.retrieval.processing.cross_query.enabled=false;selectMod('retrieval')`);assert(await run('resultPlan(config).final.length')>1);assert(!await page.locator('#createButton').isDisabled());
 await page.locator('#createDialog .close').click();await run(`exportSystem('${id}')`);assert(await page.locator('#exportReady').isDisabled());
 for(const el of await page.locator('[data-export$=".url"]').all()){await el.fill('https://service.example/v1');await el.blur();}assert(!await page.locator('#exportReady').isDisabled());assert(!await run('Object.hasOwn(blueprint(active.config,true).pipelines.inference,"generation")'));await page.locator('#exportDialog .close').click();
 // v0.12: actual browser interactions for the new controls (services still mocked).
 await run("openCreate();demoCase(8)");await page.locator('#compositionAdvanced > summary').click();assert(await page.locator('[data-path="embedding.composition.enabled"]').isChecked());await page.locator('[data-path="embedding.composition.template"]').fill('標題：{{fields.title}}\n內容：{{fields.text}}');await page.locator('[data-path="embedding.composition.template"]').blur();assert(!await page.locator('#createButton').isDisabled());await fits();await screenshot('desktop-composition');
 await run("selectMod('indexing')");assert(await page.locator('[data-pick="indexing.fulltext"][value="embedding_text"]').count());
 await run("demoCase(10);selectMod('chunking')");assert(await page.locator('#dynamicfields input').isDisabled());await fits();await screenshot('desktop-remote-locked');await page.locator('[data-owner="parsing"]').click();assert((await page.locator('#dynamicfields').textContent()).includes('ready_mock'));
 await page.locator('#componentPicker').selectOption('remote.fixed_parser@2.0.0');assert.equal(await page.locator('#dynamicfields input').count(),0);await screenshot('desktop-external');
 await run("demoCase(9);showChunkExample()");const demo=JSON.parse(await page.locator('#helpBody pre').textContent());assert.equal(demo.length,4);await page.locator('#helpDialog .close').click();await page.locator('#createDialog .close').click();
 // v0.13: exercise the exact Schema walkthrough with actual browser controls.
 await page.getByRole('button',{name:'＋ Create Retrieval System'}).click();
 assert.equal(await page.locator('#modtitle').textContent(),'Parsing');assert.equal(await page.locator('#schemaNode').count(),0);
 await page.locator('.demo-cases > summary').click();await page.getByRole('button',{name:/Schema 相依：欄位改名/}).click();
 assert(!await page.locator('#createButton').isDisabled());
 assert((await page.locator('#schemaIO').textContent()).includes('fields.page · integer'));
 await page.locator('#ingestnodes button').filter({hasText:'Embedding'}).click();
 const source=page.locator('[data-path="embedding.mappings.0.source"]');
 assert.equal(await source.inputValue(),'body_text');
 assert(await source.locator('option[value="page"]').isDisabled());
 assert((await page.locator('#schemaIO').textContent()).includes('vectors.body_vec'));
 await page.locator('#schemaIO').scrollIntoViewIfNeeded();await screenshot('desktop-schema-embedding');
 await page.locator('#ingestnodes button').filter({hasText:'Chunking'}).click();
 await page.locator('[data-path="chunking.output_field"]').fill('content');
 await page.locator('[data-path="chunking.output_field"]').blur();
 assert(await page.locator('#createButton').isDisabled());
 const issue=page.locator('#validation button').filter({hasText:'/mappings/0/source_field'});
 await issue.click();assert.equal(await source.inputValue(),'body_text');
 assert(await source.locator('option[value="body_text"]').isDisabled());
 assert.equal(await run('document.activeElement.dataset.path'),'embedding.mappings.0.source');
 await screenshot('desktop-schema-invalid-reference');
 await source.selectOption('content');
 await page.locator('#ingestnodes button').filter({hasText:'Indexing'}).click();
 const vec=page.locator('[data-pick="indexing.vectors"][value="body_vec"]');
 assert(await vec.isChecked());assert(!await vec.isDisabled());
 await page.locator('[data-pick="indexing.fulltext"][value="body_text"]').click();
 assert(!await run("config.indexing.fulltext.includes('body_text')"));
 await page.locator('[data-pick="indexing.fulltext"][value="content"]').check();
 await page.locator('#querynodes button').filter({hasText:'Retrieval'}).click();
 await page.locator('[data-pick="retrieval.fulltext"][value="body_text"]').click();
 assert(!await run("config.retrieval.fulltext.includes('body_text')"));
 await page.locator('[data-pick="retrieval.fulltext"][value="content"]').check();
 await page.locator('#querynodes button').filter({hasText:'Rerank'}).click();
 await page.locator('[data-rerank-content]').selectOption('content');
 assert(!await page.locator('#createButton').isDisabled());
 await page.locator('#systemName').fill('Schema chain QA');await page.locator('#createButton').click();
 const chainId=await run('systems.at(-1).id');await run(`openEdit('${chainId}')`);
 assert.equal(await run('config.embedding.mappings[0].source'),'content');
 await page.locator('#createDialog .close').click();
 await page.setViewportSize({width:390,height:844});await fits();await screenshot('mobile-home');
 await page.getByRole('button',{name:'＋ Create Retrieval System'}).click();await fits();await screenshot('mobile-create');await run("selectMod('chunking')");await page.locator('#modtitle').scrollIntoViewIfNeeded();await fits();await screenshot('mobile-chunking');await page.locator('[data-path="chunking.size"]').fill('0');await page.locator('[data-path="chunking.size"]').blur();assert(await page.locator('#createButton').isDisabled());
 await run("demoCase(8)");await page.locator('#modtitle').scrollIntoViewIfNeeded();await fits();await screenshot('mobile-composition');await run("demoCase(10);selectMod('chunking')");await page.locator('#modtitle').scrollIntoViewIfNeeded();await fits();await screenshot('mobile-remote');
 assert.deepEqual(errors,[]);console.log('PASS Chromium '+await browser.version()+': desktop/mobile, create/edit/cancel, CSV ingest, flat Units, Header-aware, QueryContext array, API help, export, composition, original Chunk, Remote controls, Schema propagation with stale-reference recovery and no page errors.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

