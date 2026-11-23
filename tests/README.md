# 驗證入口

## 現行契約

在 repo 根目錄執行以下離線驗證。需要 Python 3.10 以上、`jsonschema` 4.x 和 `referencing`。

```sh
python3 examples/system_config/validate_descriptor_draft.py
python3 examples/system_config/validate_runtime_http_examples.py
python3 examples/user_remote_api/validate.py
```

三支腳本分別驗證 System Config／Descriptor／Catalog、Runtime HTTP 範例及其跨步驟關聯，以及共用 Document 與 Remote API。DEV Runtime 的實際 HTTP、部署與搜尋由整合測試驗收。

<a id="dev-runtime-http-contract-test"></a>
## DEV Runtime HTTP 情境契約

```sh
python3 examples/system_config/test_runtime_http_contract.py
```

使用與離線驗證相同的 Python 套件。測試自行開啟本機暫用 TCP Port，每組情境前重設 Mock。它以 HTTP 傳送 [共用情境](../examples/system_config/runtime_http.examples.json) 的請求，依打包後的 [OpenAPI](../openapi/runtime.dev.v1.json) 檢查路由、參數、認證挑戰、HTTP 狀態、Header 和 body，再以收到的回應檢查 Context、Run、索引世代、重送和狀態轉移。面向 Builder 的 Mock 啟動與重設見 [使用方式](../examples/system_config/README.md#mock-runtime)。

認證測試包含免 Basic 的兩支 Health GET、System GET 的管理帳密，以及管理／Ingestion／Inference 帳密不可交叉使用。正式 Runtime 的部署、真實資料狀態、Elasticsearch 和外部服務仍由 DEV 環境驗收。

## 共用 Descriptor 推導測資

以下兩個入口讀取[同一份測資](../examples/system_config/descriptor_derivation.fixture.json)，核對有效 Schema、動態選項和失效選值的錯誤。Node.js 腳本直接執行 Prototype 的推導函式，使用 Node.js 18 以上。Python 腳本執行 Engine 側的離線參考編譯器。正式服務的驗收要求見 [Descriptor 手冊](../docs/04_component_descriptor.md#descriptor-derivation-conformance)。

```sh
node tests/descriptor-derivation.test.cjs
python3 examples/system_config/validate_descriptor_draft.py
```

## UI prototype 回歸

瀏覽器回歸涵蓋草稿保存、元件選擇、索引發布及重建、Variable 表、System UUIDv4、CSV 缺主鍵拒絕及組合主鍵穩定性、Run 狀態與 Filter，也檢查 Runtime 分開部署、逐流程卸載／補載及 Bulk 逾時重匯。在 repo 根目錄用已安裝 Playwright 和 Chromium 的 Node.js 環境執行。

```sh
node tests/w1-prototype.browser.test.cjs
```

可用 `CHROMIUM_EXECUTABLE` 指定 Chromium。舊版的九支測試和對應 HTML 一起保留在[舊 Prototype 快照](../docs/history/source_snapshots/ui-prototype-v015/)。
