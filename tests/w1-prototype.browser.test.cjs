'use strict';

const assert = require('node:assert/strict');
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
    const module = name => page.getByRole('navigation',{name:'模組'}).getByRole('button',{name,exact:true});
    const impact = page.locator('#publish-impact');
    const dialog = page.locator('#system-dialog');
    const card = page.locator('.card').filter({has:page.getByRole('heading',{name:'W1 驗收',exact:true})});
    const openCardAction = name => card.getByRole('button',{name,exact:true}).click();
    const closeSystem = () => dialog.getByRole('button',{name:'關閉',exact:true}).click();
    await page.goto(url);
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
    assert.equal(await page.getByRole('navigation',{name:'模組'}).locator('.module-line').count(),2);

    await module('Chunking').click();
    await page.getByLabel('輸出欄位',{exact:true}).fill('body_text');
    await module('Embedding').click();
    assert.equal(await page.getByLabel('來源欄位',{exact:true}).inputValue(),'text');
    assert.match(await page.getByLabel('來源欄位',{exact:true}).innerText(),/text（已失效）/);
    await button('驗證並發布').click();
    assert.match(await page.getByRole('alert').innerText(),/已失效/);
    assert.equal(await page.locator('#publish').evaluate(el => el.open),false);

    await page.getByRole('navigation',{name:'模組'}).getByRole('button',{name:/^Chunking/}).click();
    await page.getByLabel('輸出欄位',{exact:true}).fill('text');
    await button('保存草稿').click();
    await button('驗證並發布').click();
    assert.match(await impact.innerText(),/建立索引/);
    await button('確認發布').click();
    await closeSystem();
    await openCardAction('◇ Inference');
    assert.equal(await button('執行查詢').isDisabled(),true);

    await closeSystem();
    await openCardAction('↑ Ingest');
    await page.getByLabel('Ingestion Request').fill('{"documents":[]}');
    await button('預檢資料').click();
    assert.match(await page.getByRole('alert').innerText(),/至少一份文件/);
    await page.getByLabel('上傳 CSV 或 JSON').setInputFiles({
      name:'manual.csv',mimeType:'text/csv',
      buffer:Buffer.from('\uFEFFdocument_id,body,title,price,tags\r\nmanual-a,"定期清潔散熱孔。\n注意電源。",設備保養,350,"[""設備""]"\r\n')
    });
    await page.getByText('CSV 欄位映射 · 1 列',{exact:true}).waitFor();
    await button('預檢資料').click();
    assert.match(await page.locator('.info[role=status]').innerText(),/1 份文件/);
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
    await module('Retrieval').click();
    await page.getByLabel('每路 Top K').fill('5');
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
    assert.match(await card.locator('.meta').innerText(),/1 documents/);
    await module('Chunking').click();
    await page.getByLabel('切分上限（tokens）').fill('450');
    await button('驗證並發布').click();
    assert.match(await impact.innerText(),/重建索引/);
    await button('重建並發布').click();
    await closeSystem();
    await openCardAction('◇ Inference');
    assert.equal(await button('執行查詢').isDisabled(),true);

    await page.reload();
    assert.match(await card.locator('.meta').innerText(),/0 documents.*revision-3/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true);
    await openCardAction('⚙ Edit Config');
    assert.equal(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth),true);
    assert.deepEqual(errors,[]);
    console.log('PASS: original workspace and dialogs, draft, publishing, CSV, runs, filters, index impact, persistence and mobile width');
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
