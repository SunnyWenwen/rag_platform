// Dependency-free prototype behavior checks. DOM is stubbed; not a browser/layout test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2]||require('node:path').join(__dirname,'../01_ui_prototype.html'),'utf8');
const elements=new Map(),errors=[];
function el(id){if(!elements.has(id))elements.set(id,{id,value:'',textContent:'',innerHTML:'',disabled:false,hidden:false,files:[],style:{},listeners:{},classList:{toggle(){}},addEventListener(type,fn){this.listeners[type]=fn;},showModal(){this.open=true;},close(){this.open=false;},focus(){},click(){}});return elements.get(id);}
const context={document:{getElementById:el,createElement:()=>({click(){}})},crypto:require('node:crypto').webcrypto,URL,Blob,structuredClone,console,setTimeout,clearTimeout,window:{}};
vm.createContext(context);vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const run=s=>vm.runInContext(s,context),copy=x=>JSON.parse(JSON.stringify(x));let count=0;
function test(name,fn){try{fn();count++;console.log('PASS '+name);}catch(e){errors.push(name+': '+e.stack);}}
function change(path,value,type='text'){el('dynamicfields').listeners.change({target:{dataset:{path},value:String(value),type,checked:!!value}});}
function fresh(){run("openCreate();config=exampleConfig();selectMod('schema')");}

test('single-document JSON transport and CSV conversion',()=>{run('config=defaults()');const d=copy(run("runtimeApiSample({config,revision:1},'ingest').request"));assert(d.content.text);assert(!d.fields&&!d.records);assert.equal(run('validateRecords(config,[{document_id:"x",content:{text:"hello"}}]).errors.length'),0);assert(run('validateRecords(config,[{document_id:"x",content:{text:"hello"},uri:"https://example.com"}]).errors.length'));assert(run('validateRecords(config,[{document_id:"x",uri:"https://example.com"}]).errors.some(x=>x.includes("尚未接入"))'));});
test('default fields, all metadata, named vector objects',()=>{run('config=exampleConfig();validate(config)');const chunks=copy(run('previewChunks(config,exampleDocument(config))'));assert.equal(chunks[0].metadata.department,'manufacturing');assert(chunks[0].metadata._rag.source_refs.length);assert(Array.isArray(chunks[0].vectors.text.values));assert.equal(chunks[0].vectors.text.source_field,'text');});
test('advanced split/copy mapping and conflicts',()=>{run('config=defaults();config.chunking.tasks=[{task_id:"a",split_field:"text",output_field:"text",copy_fields:[{source_field:"text",output_field:"original_text"}]}]');assert.equal(run('taskErrors(config).length'),0);assert(run('previewChunks(config,exampleDocument(config))[0].fields.original_text'));run('config.chunking.tasks[0].copy_fields[0].output_field="text"');assert(run('taskErrors(config).length'));});
test('fixed-size hides and omits inactive separators',()=>{run('config=defaults();config.chunking.method="Fixed-size";selectMod("chunking")');assert(!el('dynamicfields').innerHTML.includes('data-separators'));assert(!run('Object.hasOwn(effectiveConfig(config).chunking,"separators")'));assert(run('valid()'));});
test('structure examples and all modules render',()=>{run('config=defaults();showStructureExamples()');assert(el('helpBody').innerHTML.includes('text-spans/0.1-draft'));for(const id of ['schema','import','parsing','chunking','embedding','indexing','transform','retrieval','rerank','generation'])run(`selectMod('${id}')`);assert(run('valid()'));});
if(errors.length){console.error(errors.join('\n'));process.exit(1);}console.log(count+' schema migration checks passed');
