# 交接狀態與後續工作

## 目前狀態

M1 的程式部分已完成：主流程（結構化資料 → Recursive 切分 → Dense Embedding → ES → 查詢）、兩條 LangGraph、內建 Retrieval 參數的 `{{KEY}}` 取值，以及 FTEST／ENT 獨立部署模式。M2 的 Fixed-size 與 Header-aware 切分也已實作（規則見 rag_platform 03#chunk-token-rules、03#header-aware-rules）。這些都在記憶體索引、hash 向量與測試 tokenizer 上端到端跑通，並以 `make run`＋`make smoke` 用真實 HTTP 操作過完整流程。接真實 ES 與 bge-m3 的部分尚未驗證，其餘 M2 方法尚未實作。測試分層與換成公司環境的做法見 [testing.md](testing.md)。

| 狀態 | 項目 | 證據 |
|---|---|---|
| 已實作並有測試 | DEV 的 17 個 HTTP 操作、MCP、Health、Basic 認證、`X-Request-Id`、錯誤格式 | `tests/test_runtime_flow.py`、`tests/test_mcp.py`（官方 MCP client 實測）；回應皆以 `runtime_http.schema.json` 驗證；`scripts/smoke_dev_runtime.py` 對啟動中的 Runtime 走真實 HTTP |
| 已實作並有測試 | 內建 Retrieval 參數的 `{{KEY}}`：先取 Request 值（含宣告預設），再取 Variable 並依參數型別解析；發布時能驗的先驗，只能由 Request 提供的逐次驗證 | `tests/test_engine_units.py`、`tests/test_runtime_flow.py` |
| 已實作並有測試 | FTEST／ENT 獨立部署模式（`RAG_MODE=standalone`）：匯出格式 Config、環境變數取值、`/v1` 與 `/mcp`、單一流程、索引不存在時 not ready | `tests/test_standalone.py` |
| 已實作並有測試 | 生命週期：initialize、reload、update（沿用／重建）、recover_index、detach、DELETE、Idempotency-Key、STALE_CONTEXT（記憶體索引） | `tests/test_runtime_flow.py` |
| 已實作並有測試 | 匯入控制：佇列、asyncio Worker、文件占用、整批衝突、取消含 `cancelling`、Bulk 逾時、紀錄保留 | `tests/test_ingestion_control.py` |
| 已實作並有測試 | Ingestion LangGraph：解析（直傳或 Remote）→ 切分 → Dense Embedding；寫入 ES 在圖外由 Runtime 處理 | `tests/test_runtime_flow.py`、`tests/test_remote_and_embedding.py` |
| 已實作並有測試 | 切分三種方法：Recursive；Fixed-size（固定 Token 視窗，規格範例與邊界案例）；Header-aware（Markdown ATX 標題切段、程式碼區塊、前言段、無標題退回 Recursive）。Catalog 由 rag_platform 的 Descriptor registry（`builder_form.descriptors.json`）依 `IMPLEMENTED` 篩選 | `tests/test_engine_units.py`、`tests/test_runtime_flow.py` |
| 已實作並有測試 | Inference LangGraph：查詢輸入 → Query Transformation（none 或 Remote）→ 內建檢索或 Remote → Rerank（none 或 Remote）→ 收斂成 `final` | `tests/test_runtime_flow.py`、`tests/test_mcp.py` |
| 已實作並有測試 | Config 編譯與索引指紋（與 rag_platform 指紋範例完全一致）；BM25／向量檢索、RRF／Sum、group_by、跨 Query 合併、Filter；Remote API Adapter | `tests/test_engine_units.py`、`tests/test_remote_and_embedding.py` |
| 已寫、未對真實服務驗證 | `ElasticsearchIndexStore`（ES 8.19、IK＋stconvert、`int8_hnsw`） | 只有假 client 測試；實機測試 `make test-es` 待跑（R1） |
| 已寫、未對真實服務驗證 | bge-m3 Embedding client | 只有 MockTransport 測試（R2） |
| 已寫、未對真實服務驗證 | 載入 bge-m3 `tokenizer.json` | 開發環境拿不到檔案，尚未執行過（R2） |
| 已寫、未對真實服務驗證 | PLED ES 位址組法（`RAG_PLED_ES_URL_TEMPLATE`） | 未測試（R1） |
| 還沒做 | 見 R4 功能缺口 | |

## 建議順序

每項完成時執行 `make check`，並補上對應測試。

### R0 公司環境

Base image 已定為 `python:3.12.13-slim-bookworm`。套上公司的 PyPI 映像、uv 來源 image 與 CI（見 `docs/tech_stack.md` 末表），並在公司建一次 Image 確認 `useradd`、uv 安裝與啟動正常。驗收：乾淨環境 `make install && make check` 通過。

### R1 PLED 測試 ES

1. 設定 `RAG_TEST_ES_URL`、帳密，執行 `make test-es`。確認 IK＋stconvert 分析器建立成功、簡體查詢命中繁體內容、`int8_hnsw` kNN 與 Filter 可用。
2. 檢查 `runtime/systems.py` 的 `mapping_compatible`：ES 讀回的 mapping 可能補上預設值（例如 `index_options` 的 `m`、`ef_construction`），確認比對方向正確，不會誤判。
3. 用 `RAG_INDEX_BACKEND=elasticsearch` 與 `RAG_ES_URL` 等設定啟動 Runtime，執行 `make smoke` 走完整流程（見 [testing.md](testing.md#4-整機-smoke)）。

### R2 bge-m3

1. 部署 Embedding 服務（例如 `deploy/k8s/bge-m3-embedding.example.yaml` 的 TEI），確認 `/v1/embeddings` 回 1024 維。
2. 量測匯入並行：目前預設每 System 2、每 Pod 4（`RAG_INGESTION_MAX_CONCURRENCY_PER_SYSTEM`／`_TOTAL`）。以實際文件量測 Embedding 服務的延遲與吞吐，決定每 Pod 維持 4 或調到 8，並回寫 rag_platform 06 的初始預設表。
3. 把 `tokenizer.json` 放到 `models/bge-m3/`，`resources/dev.yaml` 填入同一個 commit。
4. 新增 `-m embedding` 實機測試：同一句話的 Query 向量與文件向量 cosine 接近 1，長度超過 8192 token 會回 `EMBEDDING_INPUT_TOO_LONG`。

### R3 DEV 上線

1. 建 Image、套 `deploy/k8s/dev-runtime.yaml`，接 Istio 與 Gateway（見 rag_platform `examples/system_config/deployment.istio-http.example.yaml`）。
2. 執行 `make smoke URL=<DEV Runtime 位址>`（設定 `RAG_SMOKE_MANAGEMENT_USERNAME`／`_PASSWORD`），走完 17 個操作與 MCP，作為上線驗收。rag_platform 的 `test_runtime_http_contract.py` 綁定 Mock 的情境重設與固定 body，不拿來打真實 Runtime。
3. 和外包 Builder 一起跑 Catalog → 預檢 → 發布 → 匯入 → 查詢 → 取消 → 卸載。

### R4 功能缺口（依里程碑）

| 缺口 | 里程碑 | 備註 |
|---|---|---|
| `content` 來源與檔案 Parser | M2 | Q-005；目前只有 `passthrough` |
| 切分的 `preserve_original`、`include_original_chunk` | M2 | 目前編譯時拒絕，語意見 D-53 |
| Rewrite（LLM）與 Rerank `model_api` | M2 | Catalog 尚未列出 |
| Remote Query Transformation 產生多 Query 後的平台合併設定 | M2 | Q-014／Q-028，目前用預設合併 |
| FTEST／ENT 首次建立索引的指令 | M7 | rag_platform `docs/todo_enhance.md#standalone-index-initialization` |
| SIGTERM 優雅關閉 | 後續 | `todo_enhance.md#runtime-graceful-shutdown` |
| OpenTelemetry | M3 | Readiness 依 06 只檢查服務初始化（獨立部署另檢查綁定索引），不檢查 ES 連線 |
| 切分改用 `asyncio.to_thread` | 暫不做 | 依 KISS 先維持單執行緒；查詢明顯被大文件切分拖慢時再評估 |
| 事件迴圈延遲 Log | 暫不做 | 同上；需要判斷是否改多程序 Worker 時再加 |
| Ingestion 多程序 Worker | 後續優化 | 需要時再啟動，見 rag_platform `docs/todo_enhance.md#ingestion-process-workers` |
| 未載入 System 的 GET 查核只查 `dev_test` 叢集 | M3 | PLED 叢集的位址需要 Config，未載入時無從得知 |

## 補測試時發現並已修正的問題

| 問題 | 影響 | 修正 |
|---|---|---|
| 查詢的 Request 參數寫在 `config["configurable"]`，LangGraph 每個節點拿到的是副本 | Remote Inference 節點收不到 Request 參數，`{{KEY}}` 只能取到 Variable 或報缺值 | 改放 `InferenceState`；`test_remote_rerank_receives_request_parameters` |
| 單一 System 的匯入 Queue 額滿回 `429 RATE_LIMITED` | 與 06 不符，Builder 會用錯的分流 | 改回 `503 RUNTIME_CAPACITY_EXHAUSTED`；`test_full_queue_answers_runtime_capacity_exhausted` |
| `ContractError` 是 frozen dataclass | 例外被重新拋出時變成 `FrozenInstanceError` | 改成一般例外類別（不用 dataclass，避免例外無法 hash） |
| 執行中的 Retire 沒有計入 Pod 的執行總量 | 與 06 不符，大量 Retire 可無上限累積 | Retire 佔一個執行名額，額滿回 `503 RUNTIME_CAPACITY_EXHAUSTED`；`test_retire_takes_a_slot_of_the_pod_total` |
| `{{KEY}}` 解析錯誤不屬於單一參數時（例如缺 `fusion`），訊息的參數名稱是空的 | 錯誤訊息難讀 | 直接使用原訊息，`path` 為 `/parameters` |
| 獨立部署啟動錯誤包在 MCP 的 TaskGroup 裡；`RAG_INDEX_GENERATION` 格式沒檢查 | 部署錯誤訊息難讀；格式錯時要到回應才失敗 | 先載入 System 再啟動 Worker 與 MCP；啟動時檢查 UUID v4 |

## 已回寫 rag_platform 的實作決定

以下四點已在 rag_platform `docs/rag-system-factory`（commit `83e0ac1`）更新，本 repo 的契約複本已同步：

1. 索引 mapping 以 `{"type": "object", "enabled": false}` 保存 `metadata`，指紋範例同步更新。
2. MCP 錯誤結果只回 `content` 文字（`CODE: message`）與 `isError: true`，不帶 `structuredContent`。
3. Runtime 的 `separators` 預設為 `["\n\n", "\n", " ", ""]`；Builder 對中文內容預填含 `。！？；` 的分隔符。
4. `catalog_revision` 由 Descriptor 與 resources 內容計算，格式為 `catalog-<hash>`。
