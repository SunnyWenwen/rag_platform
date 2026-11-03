// npm dependencies: playwright; @sparticuz/chromium only for its bundled launch args.
// Optional CHROMIUM_EXECUTABLE points to a prepared Chromium binary.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');const {chromium}=require('playwright');
(async()=>{
 const args=process.env.CHROMIUM_EXECUTABLE?(await import(require.resolve('@sparticuz/chromium'))).default.args:[];
 const browser=await chromium.launch({headless:true,args,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{})});
 try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
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
 await page.setViewportSize({width:390,height:844});await fits();await screenshot('mobile-home');
 await page.getByRole('button',{name:'＋ Create Retrieval System'}).click();await fits();await screenshot('mobile-create');await run("selectMod('chunking')");await page.locator('#modtitle').scrollIntoViewIfNeeded();await fits();await screenshot('mobile-chunking');await page.locator('[data-path="chunking.size"]').fill('0');await page.locator('[data-path="chunking.size"]').blur();assert(await page.locator('#createButton').isDisabled());
 assert.deepEqual(errors,[]);console.log('PASS Chromium '+await browser.version()+': desktop/mobile, create/edit/cancel, CSV ingest, flat Units, Header-aware, grouped results, API help, export and no page errors.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
