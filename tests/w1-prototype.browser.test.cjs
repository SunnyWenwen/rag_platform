'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

const url = pathToFileURL(path.join(__dirname,'../01_ui_prototype.html')).href;
const browserOptions = {};
if (process.env.CHROMIUM_EXECUTABLE) browserOptions.executablePath = process.env.CHROMIUM_EXECUTABLE;
if (process.env.CHROMIUM_ARGS) browserOptions.args = JSON.parse(process.env.CHROMIUM_ARGS);

async function main() {
  const browser = await chromium.launch(browserOptions);
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    page.setDefaultTimeout(5000);
    const errors = [];
    page.on('pageerror',error => errors.push(error.message));
    const button = name => page.getByRole('button',{name,exact:true});
    const module = name => page.getByRole('navigation',{name:'設定區域'}).getByRole('button',{name,exact:true});
    const impact = page.locator('#publish-impact');
    const dialog = page.locator('#system-dialog');
    const card = page.locator('.card').filter({has:page.getByRole('heading',{name:'W1 驗收',exact:true})});
    const openCardAction = name => card.getByRole('button',{name,exact:true}).click();
    const closeSystem = () => dialog.getByRole('button',{name:'關閉',exact:true}).click();
    await page.goto(url);
    const readFixture = name => JSON.parse(fs.readFileSync(path.join(__dirname,'../examples',name),'utf8'));
    const storedConfig = readFixture('system_config/local_memory.builtin.json').config;
    const candidate = readFixture('user_remote_api/effective_document.schema.json').allOf[1].properties.structdata;
    const derived = await page.evaluate(config => {
      const data = derive(config);
      return {
        properties:Object.fromEntries(Object.entries(data.indexed).map(([key,value]) => [key,fieldValueSchema(value.type)])),
        required:Object.keys(data.indexed).filter(key => data.indexed[key].required).sort(),
        fulltext:optionValues(config,'retrieval','/fulltext_fields/*'),
        vectors:optionValues(config,'retrieval','/vector_fields/*'),
        profile:data.vectorBindings.text
      };
    },storedConfig);
    assert.deepEqual(derived.properties,candidate.properties);
    assert.deepEqual(derived.required,[...candidate.required].sort());
    assert.deepEqual(derived.fulltext,['structdata.text']);
    assert.deepEqual(derived.vectors,['text']);
    assert.equal(derived.profile.dimensions,3);
    assert.equal(await page.getByRole('heading',{level:1}).innerText(),'Customer Support');
    assert.equal(await page.locator('.card').count(),3);
    assert.equal(await page.locator('.sidebar').evaluate(node => getComputedStyle(node).backgroundColor),'rgb(255, 255, 255)');
    assert.equal(await page.locator('.mark').evaluate(node => getComputedStyle(node).backgroundColor),'rgb(101, 85, 215)');
    await page.getByRole('button',{name:/Engineering/}).click();
    assert.equal(await page.locator('.card').count(),1);
    await page.getByRole('button',{name:/Customer Support/}).click();
    await button('＋ Create Retrieval System').click();
    await page.getByRole('dialog',{name:'Create Retrieval System'}).waitFor();
    await page.getByLabel('Retrieval System 名稱').fill('W1 驗收');
    const uuidV4 = new RegExp(JSON.parse(fs.readFileSync(
      path.join(__dirname,'../schemas/runtime_identity.schema.json'),'utf8'
    )).$defs.uuid_v4.pattern);
    const createdSystemId = await page.evaluate(() => current().id);
    assert.match(createdSystemId,uuidV4);
    assert.equal(await page.getByRole('navigation',{name:'設定區域'}).locator('.module-line').count(),2);

    await module('其他設定').click();
    const variableSettings = page.getByRole('region',{name:'Variable'});
    const secretSettings = page.getByRole('region',{name:'Secret'});
    const apiAuth = page.getByRole('region',{name:'System API 認證'});
    assert.equal(await apiAuth.getByLabel('Ingestion 帳號').inputValue(),'ingestion');
    assert.equal(await apiAuth.getByLabel('Inference 帳號').inputValue(),'inference');
    const ingestionPassword = apiAuth.getByLabel('Ingestion 密碼');
    const inferencePassword = apiAuth.getByLabel('Inference 密碼');
    assert.equal(await ingestionPassword.getAttribute('type'),'password');
    assert.equal(await inferencePassword.getAttribute('type'),'password');
    assert.match(await ingestionPassword.inputValue(),uuidV4);
    assert.match(await inferencePassword.inputValue(),uuidV4);
    assert.notEqual(await ingestionPassword.inputValue(),await inferencePassword.inputValue());
    await inferencePassword.fill('fixture-inference-password');
    await variableSettings.getByRole('button',{name:'新增 Variable'}).click();
    await variableSettings.getByLabel('Variable Key').fill('trace_label');
    await variableSettings.getByLabel('Variable Key').press('Tab');
    await variableSettings.getByLabel('trace_label DEV 測試值').fill('dev-parser');
    await secretSettings.getByRole('button',{name:'新增 Secret'}).click();
    assert.equal(await secretSettings.getByLabel('SECRET_1 DEV 測試值').getAttribute('type'),'password');
    assert.equal(await variableSettings.getByLabel('trace_label DEV 測試值').inputValue(),'dev-parser');
    assert.deepEqual(await page.evaluate(() => draft.variable),{trace_label:'dev-parser'});
    await secretSettings.getByRole('button',{name:'移除'}).click();
    await variableSettings.getByRole('button',{name:'移除'}).click();
    assert.equal(await variableSettings.getByLabel('Variable Key').count(),0);

    const template = page.getByLabel('模組設定模板');
    const loadTemplate = button('載入模組設定');
    assert.equal(await template.getByRole('option').count(),3);
    assert.equal(await loadTemplate.isDisabled(),true);
    await template.selectOption('faq');
    await loadTemplate.click();
    assert.deepEqual(await page.evaluate(() => ({
      maxTokens:params(draft,'chunking').max_tokens,
      topK:params(draft,'retrieval').per_route_k,
      fixedFilters:draft.pipelines.inference.fixed_filters ?? [],
      active:current().active
    })),{maxTokens:192,topK:6,fixedFilters:[],active:null});
    assert.equal(await page.getByLabel('Retrieval System 名稱').inputValue(),'W1 驗收');
    await template.selectOption('maintenance');
    page.once('dialog',dialog => dialog.accept());
    await loadTemplate.click();
    assert.equal(await page.evaluate(() => params(draft,'chunking').max_tokens),500);

    await module('Chunking').click();
    assert.equal(await page.getByLabel('Tokenizer',{exact:true}).inputValue(),'fixture');
    assert.equal(await page.getByRole('option',{name:'DEV Tokenizer'}).count(),1);
    assert.equal(await page.getByLabel('切分上限（tokens）').getAttribute('step'),'1');
    await page.evaluate(() => {
      descriptor('chunking',draft).parameters_schema.properties.test_ratio = {
        type:'number',title:'小數測試',minimum:0,maximum:1
      };
      render();
    });
    const ratio = dialog.getByRole('spinbutton',{name:'小數測試'});
    assert.equal(await ratio.getAttribute('step'),'any');
    assert.equal(await ratio.getAttribute('max'),'1');
    await ratio.fill('0.25');
    assert.equal(await page.evaluate(() => params(draft,'chunking').test_ratio),0.25);
    await page.evaluate(() => {
      delete descriptor('chunking',draft).parameters_schema.properties.test_ratio;
      delete params(draft,'chunking').test_ratio;
      render();
    });

    await page.getByLabel('輸出欄位',{exact:true}).fill('body_text');
    await module('Embedding').click();
    assert.equal(await page.getByLabel('向量映射 1：來源欄位',{exact:true}).inputValue(),'text');
    assert.match(await page.getByLabel('向量映射 1：來源欄位',{exact:true}).innerText(),/text（已失效）/);
    await button('驗證並發布').click();
    assert.match(await page.getByRole('alert').innerText(),/已失效/);
    assert.equal(await page.locator('#publish').evaluate(el => el.open),false);

    await page.getByRole('navigation',{name:'設定區域'}).getByRole('button',{name:/^Chunking/}).click();
    await page.getByLabel('輸出欄位',{exact:true}).fill('text');
    await button('保存草稿').click();
    await button('驗證並發布').click();
    assert.match(await impact.innerText(),/建立索引/);
    await button('確認發布').click();
    assert.equal(await page.evaluate(() => current().active.secret.INFERENCE_API_PASSWORD),'fixture-inference-password');
    assert.equal(await page.evaluate(() => localStorage.getItem(storageKey).includes('fixture-inference-password')),false);
    const deployedVersion = await page.evaluate(() => activeRevision(current()));
    await closeSystem();
    await openCardAction('↗ Export');
    await page.getByLabel('部署環境').selectOption('ent');
    assert.match(await dialog.innerText(),/env: ent/);
    assert.match(await dialog.innerText(),/PLED_ES_ACCOUNT/);
    assert.doesNotMatch(await dialog.innerText(),/fixture-inference-password/);
    const downloadEvent = page.waitForEvent('download');
    await button('下載部署 Config JSON').click();
    const download = await downloadEvent;
    assert.equal(download.suggestedFilename(),createdSystemId + '.ent.json');
    const exported = JSON.parse(fs.readFileSync(await download.path(),'utf8'));
    assert.equal(exported.system_id,createdSystemId);
    assert.equal(exported.config_revision,deployedVersion);
    const connection = exported.config.pipelines.ingestion.indexing.parameters;
    assert.equal(connection.service_source,'pled_es');
    for (const lane of ['INGESTION','INFERENCE']) {
      for (const field of ['USERNAME','PASSWORD']) {
        assert.equal(exported.config.secret[lane + '_API_' + field],null);
      }
    }
    for (const [field,key] of Object.entries({
      es_number:'PLED_ES_NUMBER',account:'PLED_ES_ACCOUNT',password:'PLED_ES_PASSWORD'
    })) {
      assert.equal(connection[field],'{{' + key + '}}');
      assert.equal(exported.config.secret[key],null);
    }
    assert.equal(await page.evaluate(() => params(current().active,'indexing').service_source),'dev_test');
    await closeSystem();
    await openCardAction('◇ Inference');
    assert.equal(await button('執行查詢').isDisabled(),true);

    await closeSystem();
    await openCardAction('↑ Ingest');
    await dialog.getByText('原始檔案 Request 預覽',{exact:true}).click();
    const raw = readFixture('system_config/file_ingestion.base64.request.json').documents[0];
    await page.getByLabel('選擇原始檔案').setInputFiles({
      name:raw.document_id,mimeType:raw.content.media_type,buffer:Buffer.from(raw.content.base64,'base64')
    });
    await dialog.locator('#original-file-request').waitFor();
    assert.deepEqual(JSON.parse(await dialog.locator('#original-file-request').textContent()),{documents:[raw]});
    assert.equal(await button('開始匯入').isDisabled(),true);
    await page.getByLabel('Ingestion Request').fill('{"documents":[]}');
    await button('預檢資料').click();
    assert.match(await page.getByRole('alert').innerText(),/至少一份文件/);
    const uploadCSV = async content => {
      await page.getByLabel('上傳 CSV 或 JSON').setInputFiles({
        name:'keys.csv',mimeType:'text/csv',buffer:Buffer.from(content)
      });
      const firstHeader = content.split(',')[0];
      await page.waitForFunction(header => csv?.headers[0] === header,firstHeader);
    };
    const compositeKey = page.getByLabel('組合主鍵（選至少兩欄）');
    await uploadCSV('site,record,body,title,price\nTW,001,內容,標題,350\n');
    await button('預檢資料').click();
    await page.getByRole('alert').filter({hasText:'請映射必填欄位 document_id'}).waitFor();
    await compositeKey.selectOption(['site']);
    await button('預檢資料').click();
    await page.getByRole('alert').filter({hasText:'組合主鍵至少需要兩個欄位'}).waitFor();
    await compositeKey.selectOption(['site','record']);
    await button('預檢資料').click();
    await page.locator('#batch-summary').waitFor();
    const firstCsvId = await page.evaluate(() => batchPreview.documents[0].document_id);
    assert.match(firstCsvId,/^csv:[0-9a-f]{64}$/);
    await uploadCSV('record,site,body,title,price\n001,TW,內容,標題,350\n');
    await compositeKey.selectOption(['record','site']);
    await button('預檢資料').click();
    await page.locator('#batch-summary').waitFor();
    assert.equal(await page.evaluate(() => batchPreview.documents[0].document_id),firstCsvId);
    await page.getByLabel('上傳 CSV 或 JSON').setInputFiles({
      name:'manual.csv',mimeType:'text/csv',
      buffer:Buffer.from('\uFEFFdocument_id,body,title,price,tags\r\nmanual-a,"定期清潔散熱孔。\n注意電源。",設備保養,350,"[""設備""]"\r\n')
    });
    await page.getByText('CSV 欄位映射 · 1 列',{exact:true}).waitFor();
    await button('預檢資料').click();
    await page.locator('#batch-summary').waitFor();
    assert.match(await page.locator('#batch-summary').innerText(),/1 份文件/);
    await button('開始匯入').click();
    const run = page.getByRole('region',{name:'匯入結果'});
    await run.getByText('已完成',{exact:true}).first().waitFor();
    assert.match(await run.innerText(),/manual-a/);
    await page.getByLabel('查詢 Run ID').fill('ing-expired');
    await button('查詢工作').click();
    assert.match(await run.innerText(),/狀態未知/);

    await closeSystem();
    await openCardAction('◇ Inference');
    await button('載入範例').click();
    await button('執行查詢').click();
    const result = page.getByRole('region',{name:'查詢結果'});
    assert.match(await result.innerText(),/設備保養/);
    assert.match(await result.innerText(),/manual-a/);
    await page.getByLabel('Filter 值').fill('300');
    await button('執行查詢').click();
    assert.match(await result.innerText(),/沒有符合條件/);
    await page.getByLabel('Filter 值').fill('"300"');
    await button('執行查詢').click();
    assert.match(await page.getByRole('alert').innerText(),/符合 number/);

    await closeSystem();
    await openCardAction('⚙ Edit Config');
    await module('Inference Input').click();
    const fixedFilter = dialog.locator('#advanced').getByText('固定 Filter',{exact:true});
    assert.equal(await fixedFilter.isVisible(),false);
    await dialog.locator('#advanced > summary').click();
    assert.equal(await fixedFilter.isVisible(),true);
    await button('＋ 新增條件').click();
    await page.getByLabel('Filter 欄位').last().selectOption('structdata.price');
    await page.getByLabel('Filter 條件').last().selectOption('gte');
    assert.equal(await page.getByLabel('Filter 條件').last().inputValue(),'gte');
    await button('移除條件').last().click();
    await module('Retrieval').click();
    assert.deepEqual(await dialog.locator('.builder .form-grid > .field').evaluateAll(
      fields => fields.map(field => field.firstChild.textContent.trim())
    ),['向量欄位','全文欄位','每路 Top K','Group by 合併欄位','Top N']);
    assert.equal(await dialog.getByLabel('查詢 Embedding Profile').count(),0);
    await page.getByLabel('每路 Top K').fill('5');
    await page.getByLabel('Top N',{exact:true}).fill('2');
    await page.evaluate(() => {
      current().indexIssue = {code:'INDEX_OWNERSHIP_UNVERIFIED',message:'目標索引的歸屬無法確認。'};
    });
    await button('驗證並發布').click();
    assert.match(await impact.innerText(),/歸屬無法確認/);
    assert.equal(await button('確認發布').isDisabled(),true);
    await button('返回').click();
    await page.evaluate(() => { delete current().indexIssue; });
    await button('驗證並發布').click();
    assert.match(await impact.innerText(),/沿用索引/);
    await button('確認發布').click();
    assert.match(await page.locator('#dialog-subtitle').innerText(),/revision-2/);
    assert.equal(await page.evaluate(() => params(current().active,'retrieval').top_n),2);
    assert.match(await card.locator('.meta').innerText(),/1 份文件/);
    await module('Chunking').click();
    await page.getByLabel('切分上限（tokens）').fill('450');
    await button('驗證並發布').click();
    assert.match(await impact.innerText(),/重建索引/);
    await button('重建並發布').click();
    await closeSystem();
    await openCardAction('◇ Inference');
    assert.equal(await button('執行查詢').isDisabled(),true);

    await page.reload();
    assert.match(await card.locator('.meta').innerText(),/0 份文件.*revision-3/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true);
    await openCardAction('⚙ Edit Config');
    assert.equal(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth),true);
    await page.setViewportSize({width:1440,height:900});

    const picker = page.getByRole('combobox',{name:'Component',exact:true});
    const componentOptions = {
      Import:['platform'],
      Parsing:['passthrough','remote_api'],
      Chunking:['recursive','fixed_size','header_aware','remote_api'],
      Embedding:['dense','remote_api'],
      Indexing:['elasticsearch'],
      'Inference Input':['platform'],
      'Query Transformation':['none','rewrite','remote_api'],
      Retrieval:['builtin','remote_api'],
      Rerank:['none','model_api','remote_api']
    };
    for (const [name,options] of Object.entries(componentOptions)) {
      await module(name).click();
      const entries = await picker.locator('option').evaluateAll(options => options.map(option => ({
        value:option.value, label:option.textContent.trim()
      })));
      assert.deepEqual(entries.map(entry => entry.value),options);
      for (const {label} of entries) assert.doesNotMatch(label,/規劃中|W1/);
      const preview = dialog.locator('details').filter({has:page.getByText('有效輸入／輸出規格',{exact:true})});
      assert.equal(await preview.evaluate(element => element.open),false);
    }

    await module('Chunking').click();
    await picker.selectOption('fixed_size');
    await page.getByLabel('切分上限（tokens）').fill('384');
    await picker.selectOption('header_aware');
    await page.locator('#advanced summary').click();
    assert.equal(await page.getByLabel('標題層級',{exact:true}).count(),3);
    await picker.selectOption('fixed_size');
    assert.equal(await page.getByLabel('切分上限（tokens）').inputValue(),'384');
    assert.equal(await page.getByLabel('標題層級',{exact:true}).count(),0);
    await picker.selectOption('recursive');
    assert.equal(await page.getByLabel('切分上限（tokens）').inputValue(),'450');

    await module('Import').click();
    await button('＋ 新增欄位').click();
    assert.equal(await page.getByLabel('field_1 型別').inputValue(),'string');
    await button('移除 field_1').click();
    const importPreview = dialog.locator('details').filter({has:page.getByText('Ingestion 入口 JSON Schema 與 Request 範例',{exact:true})});
    assert.equal(await importPreview.evaluate(element => element.open),false);
    await importPreview.locator('summary').click();
    const importContract = async () => JSON.parse(await importPreview.locator('pre').first().textContent());
    const importSample = async () => JSON.parse(await importPreview.locator('pre').last().textContent());
    assert.deepEqual((await importContract()).properties.documents.items.required,['document_id','structdata']);
    assert.ok((await importSample()).documents[0].structdata.body);
    await page.getByLabel('body 欄位名稱',{exact:true}).fill('source_body');
    await page.getByLabel('title 欄位名稱',{exact:true}).focus();
    assert.ok((await importContract()).properties.documents.items.properties.structdata.properties.source_body);
    await page.getByLabel('body 欄位名稱',{exact:true}).fill('body');
    await page.getByLabel('title 欄位名稱',{exact:true}).focus();
    await page.getByLabel('入口資料形式').selectOption('content');
    await module('Parsing').click();
    assert.equal(await picker.inputValue(),'');
    assert.deepEqual(await picker.locator('option').evaluateAll(options => options.map(option => option.value)),
      ['', 'pdf','pdf_ocr','office','image_ocr','text','json','remote_api']);
    await picker.selectOption('pdf');
    await module('Import').click();
    assert.deepEqual((await importSample()).documents[0].content,{media_type:'application/pdf',uri:'https://example.invalid/document'});
    assert.ok((await importContract()).properties.documents.items.required.includes('content'));
    await module('Chunking').click();
    assert.match(await page.getByLabel('切分來源').innerText(),/contenttext/);
    await module('Parsing').click();
    await picker.selectOption('remote_api');
    await page.getByLabel('服務網址（{{KEYNAME}}，讀取 System Variable）').fill('{{REMOTE_PARSING_URL}}');
    await page.getByLabel('服務版本（處理邏輯改變時更新，會觸發索引重建）').fill('2026.11.1');
    assert.equal(await page.getByLabel('逾時秒數').inputValue(),'30');
    await page.getByLabel('替換範圍').selectOption('embedding');
    await module('Embedding').click();
    assert.equal(await picker.count(),0);
    assert.match(await dialog.locator('.info').innerText(),/Parsing Remote API/);
    await module('Parsing').click();
    await page.getByLabel('替換範圍').selectOption('parsing');
    await page.getByLabel('輸出 structdata 欄位宣告（JSON）').fill('{"title":{"type":"string","required":true}}');
    await module('Chunking').click();
    assert.match(await page.getByLabel('切分來源').innerText(),/title/);
    assert.match(await page.getByLabel('切分來源').innerText(),/body（已失效）/);
    await module('Import').click();
    await page.getByLabel('入口資料形式').selectOption('structdata');
    await module('Parsing').click();
    await picker.selectOption('passthrough');

    await module('Embedding').click();
    assert.equal(await page.getByLabel('服務來源').inputValue(),'dev_test');
    assert.match(await page.getByText('向量空間的識別。',{exact:false}).innerText(),/Query Encoder/);
    assert.deepEqual(await dialog.locator('fieldset legend').allTextContents(),['組合文字欄位','Embedding 模型設定']);
    const model = dialog.getByRole('group',{name:'Embedding 模型設定'});
    const embeddingSource = model.getByLabel('服務來源');
    assert.equal(await embeddingSource.inputValue(),'dev_test');
    await embeddingSource.selectOption({label:'Embedding API'});
    assert.equal(await embeddingSource.inputValue(),'embedding_api');
    assert.equal(await model.getByLabel('Embedding 服務引用').count(),1);
    await embeddingSource.selectOption('dev_test');
    assert.equal(await model.getByLabel('Embedding Profile').inputValue(),'text-v1');
    await page.getByText('查看組合範例',{exact:true}).click();
    assert.match(await dialog.locator('fieldset pre').innerText(),/維護指南/);
    await page.getByLabel('啟用組合文字').check();
    assert.equal(await page.getByLabel('組合輸出欄位').inputValue(),'embedding_text');
    const mappings = dialog.locator('.field').filter({has:page.getByText('向量映射',{exact:true})});
    assert.equal(await mappings.locator('tbody tr').count(),1);
    assert.equal(await mappings.getByLabel('向量映射 1：來源欄位').inputValue(),'text');
    assert.equal(await mappings.getByLabel('向量映射 1：向量欄位').inputValue(),'text');
    assert.equal(await mappings.getByRole('button',{name:'移除此項'}).isDisabled(),true);
    await mappings.getByRole('button',{name:'＋ 新增'}).click();
    await mappings.getByLabel('向量映射 2：來源欄位').selectOption('embedding_text');
    await mappings.getByLabel('向量映射 2：向量欄位').fill('combined');
    await module('Indexing').click();
    const esSource = page.getByLabel('服務來源');
    assert.equal(await esSource.inputValue(),'dev_test');
    assert.deepEqual(await esSource.locator('option').allTextContents(),['Builder 測試用 ES','PLED ES']);
    for (const field of ['es_number','account','password']) assert.equal(await page.getByLabel(field,{exact:true}).count(),0);
    await esSource.selectOption('pled_es');
    await page.getByLabel('es_number',{exact:true}).fill('000123');
    await page.getByLabel('account',{exact:true}).fill('fixture-account');
    const password = page.getByLabel('password',{exact:true});
    assert.equal(await password.getAttribute('type'),'password');
    await password.fill('fixture-password');
    await esSource.selectOption('dev_test');
    assert.equal(await password.count(),0);
    await esSource.selectOption('pled_es');
    assert.equal(await page.getByLabel('es_number',{exact:true}).inputValue(),'000123');
    assert.equal(await password.inputValue(),'fixture-password');
    await esSource.selectOption('dev_test');
    assert.equal(await page.getByLabel('text 建立向量索引').isChecked(),true);
    assert.equal(await page.getByLabel('combined 建立向量索引').isChecked(),false);
    await page.getByLabel('combined 建立向量索引').check();
    const effectiveIndex = JSON.parse(await dialog.locator('pre[data-contract-preview="output"]').textContent());
    assert.equal(effectiveIndex.properties.vector_bindings.properties.combined.properties.source_field.const,'embedding_text');
    await module('Retrieval').click();
    const vectorFields = dialog.locator('.field').filter({has:page.getByText('向量欄位',{exact:true})});
    await vectorFields.getByRole('button',{name:'＋ 新增'}).click();
    await vectorFields.getByLabel('向量欄位',{exact:true}).nth(1).selectOption('combined');
    assert.deepEqual(await vectorFields.getByLabel('向量欄位',{exact:true}).evaluateAll(
      fields => fields.map(field => field.value)
    ),['text','combined']);
    await page.getByLabel('同 Query 多路融合').selectOption({label:'RRF'});
    assert.equal(await page.getByLabel('同 Query 多路融合').inputValue(),'rrf');
    await vectorFields.locator('tbody tr').nth(1).getByRole('button',{name:'移除此項'}).click();
    await module('Indexing').click();
    await page.getByLabel('combined 建立向量索引').uncheck();
    await module('Embedding').click();
    await mappings.locator('tbody tr').nth(1).getByRole('button',{name:'移除此項'}).click();
    assert.equal(await mappings.locator('tbody tr').count(),1);
    await page.getByLabel('啟用組合文字').uncheck();
    await module('Rerank').click();
    await picker.selectOption('model_api');
    assert.equal(await page.getByLabel('服務來源').inputValue(),'dev_test');
    await picker.selectOption('none');

    await module('Indexing').click();
    assert.equal(await picker.locator('option[value="local"]').count(),0);
    assert.equal(await picker.inputValue(),'elasticsearch');
    assert.equal(await page.getByLabel('MongoDB 服務引用').count(),0);
    await module('Query Transformation').click();
    await picker.selectOption('rewrite');
    assert.equal(await page.getByLabel('共用 LLM 引用').inputValue(),'default-llm');
    assert.equal(await page.getByRole('option',{name:'DEV LLM'}).count(),1);
    assert.equal(await page.getByLabel('跨 Query 合併時點').count(),0);
    await page.getByLabel('Rewrite Prompt').fill('Rewrite {{query}}');
    await page.getByLabel('同時檢索原始問題').check();
    assert.equal(await page.getByLabel('跨 Query 合併時點').inputValue(),'after_retrieval');
    assert.equal(await page.getByLabel('跨 Query 融合策略').count(),0);
    await dialog.locator('#advanced summary').click();
    await page.getByLabel('跨 Query 合併時點').selectOption({label:'Rerank 後'});
    await button('保存草稿').click();
    await button('驗證並發布').click();
    assert.match(await page.getByRole('alert').innerText(),/W1 模擬範圍未涵蓋.*可先保存草稿/);
    assert.equal(await page.locator('#publish').evaluate(el => el.open),false);
    await closeSystem();
    assert.match(await card.locator('.meta').innerText(),/revision-3/);

    await page.reload();
    await openCardAction('⚙ Edit Config');
    await module('Query Transformation').click();
    assert.equal(await picker.inputValue(),'rewrite');
    assert.equal(await page.getByLabel('Rewrite Prompt').inputValue(),'Rewrite {{query}}');
    assert.equal(await page.getByLabel('跨 Query 合併時點').inputValue(),'after_rerank');
    assert.equal(await page.getByLabel('跨 Query 融合策略').count(),0);
    await picker.selectOption('none');
    await module('Indexing').click();
    await picker.selectOption('elasticsearch');
    await module('Chunking').click();
    await picker.selectOption('fixed_size');
    assert.equal(await page.getByLabel('切分上限（tokens）').inputValue(),'384');
    await picker.selectOption('recursive');
    await button('驗證並發布').click();
    assert.match(await page.getByRole('alert').innerText(),/請填寫有效的 DEV API 帳密/);
    assert.equal(await apiAuth.getByLabel('Inference 密碼').inputValue(),'');
    await apiAuth.getByLabel('Ingestion 帳號').fill('ingestion');
    await apiAuth.getByLabel('Ingestion 密碼').fill('fixture-ingestion-after-reload');
    await apiAuth.getByLabel('Inference 帳號').fill('inference');
    await apiAuth.getByLabel('Inference 密碼').fill('fixture-inference-after-reload');
    await button('驗證並發布').click();
    assert.match(await impact.innerText(),/沿用索引/);
    await button('返回').click();
    page.once('dialog',confirmation => confirmation.accept());
    await closeSystem();
    await dialog.waitFor({state:'hidden'});
    await openCardAction('Runtime');
    await dialog.getByText('API 認證與傳輸',{exact:true}).click();
    const runtimeAuth = dialog.locator('details').filter({hasText:'API 認證與傳輸'});
    assert.match(await runtimeAuth.innerText(),/Istio mTLS/);
    assert.match(await runtimeAuth.getByRole('row').filter({hasText:'/health/ready'}).innerText(),/免帳密/);
    assert.match(await runtimeAuth.getByRole('row').filter({hasText:'System GET'}).innerText(),/Runtime 管理帳密/);
    await page.getByLabel('Runtime 拓撲').selectOption('split');
    assert.match(await dialog.innerText(),/dev-ingestion/);
    assert.match(await dialog.innerText(),/dev-inference/);
    const identity = await page.evaluate(() => ({system:current().id,generation:indexGeneration(current())}));
    assert.equal(identity.system,createdSystemId);
    assert.match(identity.generation,uuidV4);
    assert.match(await dialog.innerText(),new RegExp(`rag-builder-${identity.system}-${identity.generation}`));
    await button('卸載 Inference').click();
    await button('執行 Builder 同步').click();
    assert.match(await dialog.innerText(),/PIPELINE_NOT_ENABLED/);
    await button('補載 Inference').click();
    assert.equal(await button('卸載 Inference').isVisible(),true);
    await closeSystem();

    await openCardAction('↑ Ingest');
    await button('載入範例').click();
    const request = JSON.parse(await page.getByLabel('Ingestion Request').inputValue());
    request.documents = [request.documents[0]];
    await page.getByLabel('Ingestion Request').fill(JSON.stringify(request));
    await page.getByLabel('模擬首筆 ES Bulk 逾時').check();
    await button('預檢資料').click();
    await button('開始匯入').click();
    await run.getByText(/ES_BULK_TIMEOUT/).waitFor();
    assert.match(await run.innerText(),/失敗/);
    await button('預檢資料').click();
    await button('開始匯入').click();
    await run.getByText('已完成',{exact:true}).first().waitFor();
    await page.getByLabel('文件 ID',{exact:true}).fill(request.documents[0].document_id);
    await button('查最近 Run').click();
    assert.match(await run.innerText(),/已完成/);
    assert.deepEqual(errors,[]);
    console.log('PASS: W1 workflow, component settings, Runtime deployment, and Bulk timeout retry');
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
