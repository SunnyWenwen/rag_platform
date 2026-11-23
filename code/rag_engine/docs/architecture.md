# 程式架構

## 分層

```
runtime     FastAPI app、Basic 認證、X-Request-Id、錯誤格式、System 生命週期、Pod 內匯入控制、查詢限流、MCP
  │
engine      Config 編譯器、索引指紋、LangGraph 流程、文件驗證、索引寫入（write_id 批次替換）
  │
components  Recursive 切分、Dense Embedding、融合／分組／跨 Query 合併、Remote API Adapter
  │
adapters    IndexStore（記憶體／Elasticsearch）、ES mapping 與查詢、Embedding client、Tokenizer
  │
core        資料型別、錯誤、Filter 語意、RFC 8785、Runtime resources
  │
contracts   rag_platform 的 JSON Schema、OpenAPI、Catalog Descriptor 複本
```

上層可以 import 下層，反向禁止，由 `make layers` 檢查。

## 主要模組

| 模組 | 責任 | 規格 |
|---|---|---|
| `engine/compiler.py` | 驗證 System Config、推導各階段欄位、Remote 連線解析、Index 計畫、指紋投影 | 05、06#index-fingerprint-v1-proposal |
| `engine/pipelines.py` | 每個 Config Revision 編譯兩張 LangGraph：Ingestion（parse→chunk→embed）、Inference（input→transform→retrieval→rerank→finalize） | 03 |
| `engine/index_writer.py` | 固定舊批次範圍 → Bulk 新 `write_id` → 新版可搜尋後清舊 | 06#es-write-control-record |
| `runtime/systems.py` | 載入的 System、預檢 `index_impact`、initialize／reload／update／recover_index、detach、DELETE、Idempotency-Key | 06#system-lifecycle-api |
| `runtime/ingestion.py` | 文件占用、Queue、Worker、Run 狀態、取消（含 `cancelling`）、保留期清理 | 06#pod-local-ingestion-control |
| `runtime/inference.py` | 每 System 速率與併發、全域併發、60 秒 Deadline、排空 | 06#inference-api |
| `runtime/mcp.py` | 每個 System 一個查詢工具 | 06#inference-mcp |
| `adapters/es_store.py`、`es_mapping.py` | ES 8.19 讀寫、mapping、IK＋stconvert、Filter 轉 Query DSL | 02#filter-semantics |

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
