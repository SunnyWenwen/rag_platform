# W1 Builder ↔ Runtime HTTP 契約

Builder Backend 以此契約管理和測試 DEV Runtime 裡的 Retrieval System。[HTTP JSON 範例](../examples/system_config/w1_http.examples.json)可直接餵給 Mock。索引、佇列與部署行為見 [Runtime 手冊](06_runtime_api_and_deployment.md)。

## 1. 路由與資料格式

- **DEV 管理 API** 使用 `/internal/v1`。**DEV 業務 API** 使用 `/internal/systems/{system_id}/v1`。獨立部署只提供相同的業務 API，前綴為 `/v1`。Health 為服務層的 `/health/live`、`/health/ready`。
- 沿用 D-60。Runtime 端全部路由使用 HTTPS 與部署提供的 HTTP Basic 帳密，DEV 內部路由只允許可信 Builder Backend 存取。未通過驗證回 `401` 並帶 `WWW-Authenticate: Basic realm="retrieval-runtime"`。
- 有 body 的請求及回應用 `application/json`。下文的 ID／Revision／Cursor 都是非空、不透明的字串，路徑參數由 Client 作路徑 segment 編碼。型別後的 `?` 表示選填，`null` 表示須明確傳空值。

## 2. Catalog、設定與 System 管理

| Method／Path | 請求 | 成功回應 |
|---|---|---|
| `GET /internal/v1/catalog` | 無 | `200` ＋ [Catalog](../schemas/runtime_catalog.draft.schema.json)。 |
| `POST /internal/v1/systems/{system_id}/config:validate` | `ValidateRequest` | `200` ＋ `Validation`，可驗證尚未載入的 System。 |
| `PUT /internal/v1/systems/{system_id}` | `ApplyRequest` | `200` ＋ `SystemStatus`，完成後才回成功。 |
| `GET /internal/v1/systems` | 無 | `200` ＋ `{systems: SystemStatus[]}`，空集合回 `[]` 作為 `systems` 的值。 |
| `GET /internal/v1/systems/{system_id}` | 無 | `200` ＋ `SystemStatus`，查無 System 回 `404 SYSTEM_NOT_FOUND`。 |
| `DELETE /internal/v1/systems/{system_id}` | 無 | `204`，完成排空及清除後回應。已卸載可重送；無法確認清除結果時回錯誤。 |

Builder 進入設定或切換目標 Runtime 時取得 Catalog。固定選項讀 Descriptor，動態選項由 Builder 以 Catalog 資源與草稿中的上游輸出推導。Runtime 識別或 Catalog 版本不符回 `STALE_CATALOG`，Builder 重新取目錄並重驗草稿。

| 物件 | 欄位 |
|---|---|
| `ValidateRequest` | `runtime_ref: string`、`catalog_revision: string`、`draft_revision: string`、`config: Config`。`Config` 為 [System Config 快照](../schemas/system_config.draft.schema.json)內層的 `config` 物件。 |
| `Validation` | 回傳本次 `runtime_ref`、`catalog_revision`、`draft_revision`，另含 `context_revision: string`、`active_config_revision: string \| null`、`index_impact: {action, code, message}`。`code`、`message` 為字串。 |
| `ApplyRequest` | `ValidateRequest` 的全部欄位，另含 `context_revision: string`、`operation: "initialize" \| "update"`、`expected_active_revision: string \| null`、`config_revision: string`、`allow_rebuild?: boolean`（預設 `false`）。 |
| `SystemStatus` | `system_id: string`、`active_config_revision: string`、`busy: boolean`、`index_ready: boolean \| null`、`index_generation: string \| null`、`can_ingest: boolean`、`can_query: boolean`。 |

### 發布與索引影響

1. `config:validate` 檢查完整 Config、Component 版本、資源引用與上下游契約，並讀取索引狀態。它不改動 System 或 Index。Builder 以 `draft_revision` 對回本次草稿，捨棄過期結果。設定有錯回 `422 CONFIG_VALIDATION_FAILED`。
2. Builder 依 `index_impact.action` 呈現發布影響。Runtime 按下表決定索引操作。

   | `action` | `code` 範例 | Builder 行為 |
   |---|---|---|
   | `create` | `INDEX_MISSING` | 提示建立空索引，發布後開始初次匯入。 |
   | `reuse` | `INDEX_COMPATIBLE` | 沿用索引與既有資料。 |
   | `rebuild_required` | `INDEX_FINGERPRINT_CHANGED`、`INDEX_MAPPING_CHANGED` | 提示停查、清除與重新匯入。取得使用者確認後，才用 `update` 並設 `allow_rebuild: true`。 |
   | `blocked` | `INDEX_OWNERSHIP_UNVERIFIED`、`INDEX_CHECK_UNAVAILABLE`、`INDEX_RECONNECT_INCOMPATIBLE` | 保留草稿並顯示原因。修正後重驗。初始化遇到不相容的既有索引時使用此結果。 |
   | `none` | `INDEX_NOT_MANAGED` | 此設定沒有平台管理索引，例如完全由外部服務管理資料的 Retrieval。 |

3. `PUT` 傳回驗證過的 `config` 及對應的版本值，`expected_active_revision` 取自 `Validation.active_config_revision`。首次或重連用 `initialize` 和 `null`，已載入的 System 用 `update` 與目前生效版本。每次發布給新的 `config_revision`。Runtime 在該 System 的管理鎖內比對 Catalog 與生效版本，重驗 Config、索引相容及歸屬，再開始切換。`context_revision` 綁定 Runtime、Catalog、System、草稿版本、Config、生效版本和索引影響的判定依據，索引中一般文件的新增／更新不造成 Context 過期。判定依據已變更時回 `409 STALE_CONTEXT`，由 Builder 重驗並重新顯示影響。
4. 同一發布請求重送且該 Revision 已生效時，回目前的 `SystemStatus`，不再操作索引。用相同 `config_revision` 發布不同 Config 回 `409 REVISION_CONFLICT`。驗證或切換前失敗時舊版本繼續生效；若舊索引已清除但新索引建立失敗，GET 仍回最後生效版本，`index_ready`、`can_ingest`、`can_query` 都為 `false`。收到逾時或連線中斷時，Builder 先查 GET 確認生效狀態，再視結果重驗。Runtime 在索引操作結果待查核時回 `503 SYSTEM_STATE_UNKNOWN`，直到能安全判定。
5. `busy` 表示管理變更目前會被阻擋，例如已有生命週期操作、排隊／執行中的 Ingestion 或未收尾的文件寫入。是否可匯入或查詢分別讀 `can_ingest`、`can_query`。`index_generation` 隨建索引或重建變更，沿用索引時保持相同。未管理或尚無已確認的索引時為 `null`，未管理平台索引時 `index_ready` 也為 `null`。Runtime 可查空索引；Builder 依 [初次匯入規則](07_builder_ui.md#builder-initial-ingestion-readiness)在新建／重建後等待預定資料成功匯入再開放查詢。

卸載前，Builder 顯示會刪除受管理索引及其中資料，保留 Builder 的 System 和發布歷史。Runtime 按 System 序列化管理操作；排空或確認索引歸屬失敗就停止，僅在確認無待清除的受管資源時回 `204`。管理呼叫同步完成，排空等待採 Runtime 的 Query Deadline；超過時回 `504`，已送出的索引操作需先查核結果。

## 3. 業務 API

下表相對於 `/internal/systems/{system_id}/v1`（DEV）或 `/v1`（獨立部署）。每次請求使用 Runtime 當下生效的固定 Config 快照。

| Method／Path | 請求 | 成功回應 |
|---|---|---|
| `POST /ingestions` | [IngestionRequest](../schemas/ingestion_request.schema.json)，單筆也放 `documents[]`。 | `202` ＋ `{run_id, status:"queued", config_revision, documents:[{document_id,status:"queued"}]}`。`Location` 為同一 API 路由前綴下的 `/ingestions/{run_id}`。整批預檢後一併接受，輪詢 `Location` 直到終態。 |
| `GET /ingestions/{run_id}` | 無 | `200` ＋ `{run_id,status,config_revision,counts,documents:RunDocument[]}`。查無紀錄或到期回 `{run_id,status:"unknown"}`。 |
| `GET /documents/{document_id}/ingestion-status` | 無 | `200` ＋ `RunDocument` 加 `run_id: string \| null`。查無紀錄時 `status:"unknown"`，`run_id`、`module`、`updated_at`、`error` 為 `null`。 |
| `GET /documents/{document_id}/exists` | 無 | `200` ＋ `{document_id,exists:boolean}`，讀實際文件資料。 |
| `GET /documents?limit=…&cursor=…` | `limit` 預設 `100`，範圍 `1–1000`，選填 `cursor`。 | `200` ＋ `{documents:[{document_id,source_revisions:string[]}],next_cursor:string \| null}`。以 `document_id` 升冪分頁，Cursor 限同一 System，終頁回 `null`。列出實際可見版本，資料寫入期間可變動。 |
| `POST /documents/{document_id}:retire` | 無 | `200` ＋ `{document_id,result:"deleted" \| "not_found"}`，同步完成，文件忙碌回 `409`。 |
| `POST /queries` | [InferenceRequest](../schemas/inference_request.schema.json)。 | `200` ＋根層 [QueryContext[]](../schemas/query_context.schema.json)。有命中回候選，全路徑成功但無命中回空 `items`，必要路徑失敗則整次請求回錯誤。`X-Config-Revision` 回所用版本，有平台索引時 `X-Index-Generation` 回所用索引世代。 |

服務根路徑的 `GET /health/live`、`GET /health/ready` 皆無 Request body，成功回 `200` ＋ `{status:"ok"}`。Readiness 只表示服務初始化就緒，未就緒回 `503 RUNTIME_NOT_READY`。

`RunDocument` 欄位為 `document_id: string`、`status`、`module: string | null`、`updated_at: RFC 3339 字串 | null`、`error: Error | null`。文件狀態為 `queued`、`running`、`completed`、`failed`、`unknown`；Run 另有 `partial`。`counts` 欄位固定為 `total`、`queued`、`running`、`completed`、`failed`、`unknown`，均為非負整數。已接受的工作結果從 `GET` 讀取，即使工作失敗也維持 HTTP `200`。Builder 停止輪詢終態。`unknown` 表示結果無法確認，檢查最新文件狀態及實際資料後再決定是否補送，避免逾時後自動重送 Ingestion。

## 4. 錯誤與 Builder 處理

HTTP 錯誤用 `{error: {code: string, message: string, module: string | null, path?: string, run_id?: string}}`。`module` 用 Config 的模組鍵，例如 `embedding`。`path` 用相對於當次 Request body 的 JSON Pointer，如 `/config/pipelines/ingestion/embedding/parameters/mappings/0/source_field`。首版回第一個可定位問題。Run／文件狀態的 `error` 直接放內層 `Error`。Builder 依 `code` 作分流，`message` 呈現細節。

| HTTP | W1 `code` 與處理 |
|---|---|
| `400`／`415` | `INVALID_JSON`／`UNSUPPORTED_MEDIA_TYPE`。修正請求格式。 |
| `401`／`403` | `UNAUTHENTICATED`／`FORBIDDEN`。由 Backend 檢查連線認證或存取權限。 |
| `404` | `SYSTEM_NOT_FOUND`。確認 Runtime 及 System 是否已載入。 |
| `409` | `STALE_CATALOG` → 重新取 Catalog；`STALE_CONTEXT` → 重驗 Config；`REVISION_CONFLICT` → GET 重新確認生效版本；`REBUILD_CONFIRMATION_REQUIRED` → 顯示預覽與重建確認。 |
| `409` | `SYSTEM_BUSY`／`DOCUMENT_BUSY` → 等工作或管理操作收尾，若文件關聯 Run 已知則附 `error.run_id`；`INDEX_CONFLICT` → 顯示索引歸屬或相容性問題。 |
| `413`／`422` | `BODY_TOO_LARGE`／`REQUEST_VALIDATION_FAILED`、`CONFIG_VALIDATION_FAILED`、`INVALID_CURSOR`。修正大小、欄位或分頁請求。 |
| `429` | `RATE_LIMITED` → 按 `Retry-After` 等候（整數秒，有可用時間時回傳）。 |
| `501`／`502`／`503`／`504`／`500` | `OPERATION_UNSUPPORTED`、`UPSTREAM_ERROR`、`RUNTIME_NOT_READY`／`RUNTIME_CAPACITY_EXHAUSTED`／`INDEX_NOT_READY`／`SYSTEM_STATE_UNKNOWN`、`DEADLINE_EXCEEDED`、`INTERNAL_ERROR`。Builder 顯示原因；管理操作結果不明時先同步 System 狀態。 |

## 5. Mock 與驗收

[HTTP JSON 範例](../examples/system_config/w1_http.examples.json)按情境列出每次實際的 Method、Path、Body、Status 與相關 Headers。`body_file` 讀取同目錄的完整 JSON 內容，例如 Catalog。`happy_path` 從 Catalog 跑到首次 Query、文件管理及卸載。`reuse_and_rebuild` 從同一 System 的 `revision-1` 生效且有索引開始。其餘情境是獨立的 Mock 回應，涵蓋欄位驗證、索引歸屬、過期、Run 結果及 Query 空候選與失敗。從 repo 根目錄執行 `python3 examples/system_config/validate_w1_http_examples.py` 驗證 fixture 使用的 Catalog、Config、資料 Schema 與跨步驟關聯。實際 HTTP、ES 與模型由 DEV 環境串接驗收。
