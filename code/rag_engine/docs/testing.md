# 測試方式

測試分四層。前兩層不需要任何外部服務，在任何機器與 CI 都能跑；後兩層接真實服務或已部署的 Runtime，用環境變數或參數指定目標。

| 層 | 指令 | 跑在哪裡 | 需要什麼 |
|---|---|---|---|
| 1. 單元測試 | `make check`（含在 pytest 內） | 程序內 | 無 |
| 2. HTTP 流程測試 | `make check`（含在 pytest 內） | 程序內 Runtime，httpx 直接呼叫 ASGI app；MCP 測試起真的 uvicorn | 無（記憶體索引＋hash 向量＋測試 tokenizer） |
| 3. 真實服務 Adapter 測試 | `make test-es` | 程序內 | `RAG_TEST_ES_URL` 等環境變數指向真實 ES |
| 4. 整機 Smoke | `make smoke URL=...` | 對一個已啟動的 Runtime 走真實 HTTP | 一個在跑的 Runtime（本機 `make run` 或公司 DEV Runtime） |

## 1. 單元測試

純函式與元件：切分（Recursive、Fixed-size 的規格範例與邊界、Header-aware 的標題規則）、融合／分組、Filter、編譯器與錯誤定位、索引指紋、ES mapping 與 Query DSL、Remote API 封裝（`httpx.MockTransport`）、OpenAI-compatible Embedding client（MockTransport）、ES 請求形狀（假 client）。

## 2. HTTP 流程測試

`tests/conftest.py` 用 `create_app(settings)` 建一個完整 Runtime，lifespan 在自己的 task 執行，請求經 `httpx.ASGITransport` 送進 app，走完整的路由、認證、錯誤格式、LangGraph 與 Worker。每個回應都用 vendored 的 `runtime_http.schema.json` 驗證（`validate_http`）。

| 檔案 | 範圍 |
|---|---|
| `test_runtime_flow.py` | 發布、匯入、查詢、文件管理、detach、DELETE、update（沿用／重建）、`{{KEY}}` 參數、錯誤定位 |
| `test_ingestion_control.py` | 占用與整批衝突、取消（含 `cancelling`）、Bulk 逾時、Queue 額滿 `503`、Retire 計入 Pod 總量、保留期 |
| `test_mcp.py` | 真的 uvicorn＋官方 MCP client |
| `test_remote_and_embedding.py` | Remote Parsing 進 Ingestion、Remote Rerank 收到 Request 參數 |
| `test_standalone.py` | FTEST／ENT 模式：匯出格式 Config、環境變數取值、`/v1`、單一流程、索引不存在時 not ready、啟動錯誤 |

記憶體索引、hash 向量與測試 tokenizer 只是替身，排名結果不代表真實品質。這一層驗證的是 Runtime 邏輯與 API 契約，換成真實 ES 或 bge-m3 時這些測試照樣有效，不需要改。

## 3. 真實服務 Adapter 測試

`tests/test_es_store.py` 的 `-m es` 測試直接對 ES 建索引、Bulk、BM25、kNN＋Filter、列文件、刪除，最後刪掉測試索引。預設分析器是 `zh_ik`，所以叢集要裝 IK 與 stconvert；它也驗證簡體查詢命中繁體內容。

```bash
RAG_TEST_ES_URL=https://... RAG_TEST_ES_USERNAME=... RAG_TEST_ES_PASSWORD=... make test-es
```

bge-m3 的實機測試（`-m embedding`）還沒寫，見 roadmap R2。

## 4. 整機 Smoke

`scripts/smoke_dev_runtime.py` 對一個正在跑的 DEV Runtime 走完 Builder 的完整流程，涵蓋 17 個操作與 MCP：

Health → Catalog → 預檢 → initialize（含 Idempotency-Key 重送）→ GET／列表 → 匯入 → Run 與文件狀態、存在、分頁列表 → 查詢（一般、Filter、`{{TOP_N}}`、錯誤值、錯帳密）→ MCP → 取消 → Retire → update（沿用索引）→ detach → DELETE。

它用一個隨機 System ID，結束時刪除 System 與索引。檢查只依 API 契約，不依分數或排名，所以同一支腳本可以直接拿去驗公司的 DEV Runtime（真實 ES＋bge-m3）。

本機：

```bash
make run
```

```bash
make smoke
```

公司 DEV Runtime：

```bash
RAG_SMOKE_MANAGEMENT_USERNAME=... RAG_SMOKE_MANAGEMENT_PASSWORD=... make smoke URL=https://dev-runtime.example
```

腳本取 Catalog 中第一個 Embedding Profile 與 Tokenizer Profile 組 Config，ES 來源用 `dev_test`。

## 換成公司環境時

| 測試 | 是否通用 | 要做的事 |
|---|---|---|
| 1、2 層 | 通用 | 無。CI 直接跑 `make check`。 |
| 3 層 ES | 通用 | 設 `RAG_TEST_ES_URL` 等環境變數，指向裝好 IK＋stconvert 的 PLED 測試 ES。 |
| 3 層 bge-m3 | 待補 | 新增 `-m embedding` 測試（roadmap R2）。 |
| 4 層 Smoke | 通用 | 部署 DEV Runtime 後執行 `make smoke URL=...`，可當上線驗收。 |
