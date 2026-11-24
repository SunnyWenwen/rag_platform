# 程式架構

## 分層

```
runtime     FastAPI app、Basic 認證、X-Request-Id、錯誤格式、System 生命週期、Pod 內匯入控制、查詢限流、MCP
  │
engine      Config 編譯器、索引指紋、LangGraph 流程、文件驗證、索引寫入（write_id 批次替換）
  │
components  切分（Recursive、Fixed-size、Header-aware）、Dense Embedding、Rewrite、融合／分組／跨 Query 合併、Remote API Adapter
  │
adapters    IndexStore（記憶體／Elasticsearch）、ES mapping 與查詢、Embedding client、LLM client、Tokenizer
  │
core        資料型別、錯誤、Filter 語意、RFC 8785、Runtime resources
  │
contracts   rag_platform 的 JSON Schema、OpenAPI、Descriptor registry 複本
```

上層可以 import 下層，反向禁止，由 `make layers` 檢查。

## 主要模組

| 模組 | 責任 | 規格 |
|---|---|---|
| `engine/compiler.py` | 驗證 System Config、推導各階段欄位、Remote 連線解析、Index 計畫、指紋投影 | 05、06#index-fingerprint-v1-proposal |
| `engine/plan.py` | 編譯結果的資料型別（`CompiledSystem`、各階段計畫），只有欄位沒有邏輯 | |
| `engine/pipelines.py` | 每個 Config Revision 編譯兩張 LangGraph：Ingestion（parse→chunk→embed）、Inference（input→transform→retrieval→rerank→finalize） | 03 |
| `engine/index_writer.py` | 固定舊批次範圍 → Bulk 新 `write_id` → 新版可搜尋後清舊 | 06#es-write-control-record |
| `runtime/systems.py` | 載入的 System、預檢 `index_impact`、initialize／reload／update／recover_index、detach、DELETE | 06#system-lifecycle-api |
| `runtime/idempotency.py` | 管理操作的 Idempotency-Key 重送與衝突判斷（Pod 內記憶體，逾期清除） | 06#system-lifecycle-api |
| `runtime/ingestion.py` | 文件占用、Queue、Worker、Run 狀態、取消（含 `cancelling`）、保留期清理 | 06#pod-local-ingestion-control |
| `runtime/inference.py` | 每 System 速率與併發、全域併發、60 秒 Deadline、排空 | 06#inference-api |
| `runtime/mcp.py` | 每個 System 一個查詢工具 | 06#inference-mcp |
| `adapters/es_store.py`、`es_mapping.py` | ES 8.19 讀寫、mapping、IK＋stconvert、Filter 轉 Query DSL | 02#filter-semantics |
| `components/rewrite.py`、`adapters/llm.py` | Rewrite：Prompt 取值、JSON Schema 結構化輸出、格式驗證、重試與退回原始問題；LLM client 只負責 Chat Completions 傳輸 | 03#rewrite-rules、06#llm-service-deployment |

## 併行模型

v1 採最簡單的做法：一個 uvicorn 程序、一條執行緒、一個 asyncio 事件迴圈。

| 範圍 | 做法 | 主要設定 |
|---|---|---|
| Ingestion | 收件後逐份文件放進各 System 的佇列；n 個 asyncio Worker 輪流從各 System 取件，執行 LangGraph 並寫入 ES | `RAG_INGESTION_MAX_CONCURRENCY_TOTAL`（n，預設 4）、`RAG_INGESTION_MAX_CONCURRENCY_PER_SYSTEM`（預設 2） |
| Inference 與 MCP | 每個請求在自己的協程內直接執行 LangGraph，不排隊；額滿立即拒絕 | 每 System 速率 5 次／秒、並行 2，每 Pod 並行 8，期限 60 秒 |

等 bge-m3、ES、Remote API 時以 `await` 讓出執行緒，所以這些等待可以重疊。切分、tokenize、向量 JSON 解析是 CPU 工作，會在事件迴圈上執行到完成，匯入大文件時同 Pod 的查詢會短暫變慢。目前接受這個代價，不加 `asyncio.to_thread` 或多程序；若之後持續卡住，再改用 rag_platform `docs/todo_enhance.md#ingestion-process-workers` 的多程序 Worker。

## 請求流程

**發布（DEV）**：Builder `config:validate` → 編譯 Config、算候選指紋、查核實體索引 → 回 `index_impact` 與 `context_revision` → Builder 以相同內容加 `target_index_generation` 送 PUT → Runtime 依操作建立或接回索引、編譯 LangGraph、建立 Snapshot。

**匯入**：驗證 IngestionRequest 與 Import 欄位 → 同一同步區段內檢查整批占用與容量、建立 Run、入列 → 回 `202`。Worker 取件 → LangGraph 執行到 Embedding → 取得寫入權（與取消競爭的唯一檢查點）→ Bulk → 清舊 → 結案。

**取消**：`queued` 與尚未取得寫入權的 `running` 直接 `cancelled` 並釋放占用；已取得寫入權的改 `cancelling`，寫入成功後轉 `completed`，失敗轉 `cancelled`。

**查詢**：限流 → 取當下 Snapshot（舊查詢保留舊 Snapshot 直到結束）→ LangGraph → 收斂成一份 `final` Context 與 `query_variants`。

## 不可破壞的規則

1. 每個 Pod 一個程序（`--workers 1`）。
2. `runtime/ingestion.py` 修改狀態的區段內不能有 `await`。asyncio 單執行緒保證這些區段不會被打斷，取消與寫入權就是靠這一點互斥。
3. Snapshot 不可變。切版時建立新 Snapshot，進行中的請求繼續用舊的。
4. 影響索引內容的設定都要進指紋投影。新增 Component 時同時定義它的投影參數。
5. `contracts/data/` 只能用 `scripts/sync_contracts.py` 從 rag_platform 同步，不在這裡手改。
6. Secret 只用在認證欄位；Log 與錯誤不得含 Secret 值或 `Authorization`。
7. LangGraph 節點之間傳值只能放在 state。`config["configurable"]` 在每個節點是副本，只放呼叫端傳入的唯讀值（Deadline、request_id、進度回呼等）。查詢的 Request 參數與逐次解析的 Retrieval 設定都放在 `InferenceState`。
