# Runtime API、工作控制與部署

## 閱讀目錄

- [HTTP 共通規格](#runtime-http-common)
- [平台管理資料與儲存](#src-07-3-平台管理資料與儲存)
- [System／Revision 與 Engine 生命週期](#src-07-4-systemrevision-與-engine-生命週期)
- [Builder Backend（Control Plane）](#src-07-51-builder-backendcontrol-plane)
- [Builder 上傳與自行部署](#src-07-54-builder-上傳與自行部署)
- [Runtime Component 目錄與 Config 驗證邊界](#src-07-58-runtime-component-目錄與-config-驗證邊界)
- [範圍與已確認基準](#src-21-1-範圍與已確認基準)
- [資料生命週期、Inference 與 Health API](#data-lifecycle-api)
- [部署環境與 ES 索引歸屬](#runtime-index-ownership)
- [Ingestion 的提交與接收](#src-21-3-ingestion-的提交與接收)
- [Pod 內文件占用與派工](#pod-local-ingestion-control)
- [批量取消 Ingestion 文件](#ingestion-cancel-api)
- [Elasticsearch 文件覆寫](#elasticsearch-document-replacement)
- [文件狀態與一次提交的狀態](#src-21-4-文件狀態與一次提交的狀態)
- [Ingestion Queue、工作紀錄與重啟](#ingestion-job-records)
- [Inference API](#inference-api)
- [HTTP 錯誤格式與狀態碼](#runtime-http-errors)
- [Runtime API 的待決範圍與驗收](08_plan_and_decisions.md#runtime-api-decisions)
- [執行模式、覆寫與認證](#src-21-8-api-d0506-的具體情境)
- [文件資料查詢與直接刪除](#src-21-9-文件資料查詢與直接刪除)
- [設定來源與保存位置](#runtime-config-sources)
- [Runtime 設定：範圍與管理方式](#src-22-1-範圍與管理方式)
- [Runtime 設定：已確認的初始預設](#src-22-2-已確認的初始預設)
- [Runtime 設定：容量、失敗與保存行為](#src-22-3-容量失敗與保存行為)
- [Runtime 設定：文件摘要與分頁參數](#src-22-4-文件摘要與分頁參數)
- [Runtime 設定：文件維護與驗收待辦](#src-22-5-文件維護與驗收待辦)
- [排程、同程序 Memory 與一致性限制](#src-07-6-非同步工作與一致性)
- [Local Search 恢復與儲存](#src-07-7-local-search-恢復與儲存)
- [Evaluation 與 AI 助手服務](#src-07-8-evaluation-與-ai-助手服務)
- [Export、獨立部署與 Secret](#src-07-9-export獨立部署與-secret)
- [Observability、認證與權限](#src-07-10-observability認證與權限)


更新日期為 2026-11-23。本手冊說明 Builder Backend／Runtime 整合、HTTP 行為、Queue、環境控制與 Export。HTTP 物件形狀及代碼見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json)。業務資料結構見 [共用資料契約](02_data_contracts.md)，可執行的 Mock 測資見 [HTTP JSON 範例](../examples/system_config/README.md#runtime-http-examples)。

<a id="runtime-http-common"></a>
## HTTP 共通規格

- **DEV 管理 API** 使用 `/internal/v1`。**DEV 業務 API** 使用 `/internal/systems/{system_id}/v1`。獨立部署的業務 API 前綴為 `/v1`。兩種部署的服務層 Health 路徑均為 `/health/live`、`/health/ready`。
- 沿用 D-60。Runtime 端全部路由使用 HTTPS 與部署提供的 HTTP Basic 帳密，DEV 內部路由只允許可信 Builder Backend 存取。未通過驗證回 `401` 並帶 `WWW-Authenticate: Basic realm="retrieval-runtime"`。
- 有 body 的請求及回應用 `application/json`。HTTP 契約中的 ID／Revision／Cursor 均為非空、不透明的字串。System ID 與索引世代使用 [UUID 格式](#runtime-index-ownership)。Client 將每個路徑參數編碼為單一路徑片段。欄位名稱後的 `?` 表示選填，允許空值的必填欄位須明確傳 `null`。

<a id="src-07-3-平台管理資料與儲存"></a>
## 平台管理資料與儲存

以下為建議領域資料，完整 DB Schema 待決：

| 資料 | 保存語意 |
|---|---|
| Workspace | 使用者可見範圍與系統組織；權限規則 Q-006 |
| RetrievalSystem（模型名草案） | 穩定 system_id、顯示名稱、collection、管理狀態 |
| ConfigRevision | 同一 System 的邏輯 Config、草稿關聯、版本／Hash、時間與作者；不因環境 URL 不同另改邏輯版本 |
| 部署紀錄（建議形狀） | 對應同一 system_id／config_revision，另記環境、連線／Secret 引用、資料目標及 Runtime 資源；欄位與部署 ID 待 Q-015／Q-021 |
| IndexBinding | 單 System 唯一索引的格式、target、欄位／向量能力；資料版本／就緒狀態另由 Runtime 管理 |
| ServiceReference | DEV 或使用者服務連線設定。認證欄位可引用所屬 System 的 `{{KEY}}`。System 的 llms 有明確作用域。 |
| Runtime IngestionRun／文件工作狀態 | Queue、占用、Run 和逐文件狀態皆在受理 Pod 的記憶體。見 [工作紀錄與保留](#ingestion-job-records) |
| 文件寫入與清理進度 | IndexStore 在本機記憶體保存目前操作的查核資訊。見 [ES 寫入與清理](#es-write-control-record) |
| EvaluationRun | 評估的 Config／資料版本、狀態、數量、錯誤與報告引用，依 M6／Q-018 處理 |
| Dataset／EvaluationReport | 版本化 Dataset、逐題結果、指標、Judge／Rubric、Target |
| ExportArtifact | Config／Image／環境覆寫、驗證狀態、產出版本 |

Builder 的 System 部署紀錄與 Runtime 重連同步見 [MongoDB Collection 草案](drafts/builder_system_deployment_mongodb.md)。

正式管理階層只有 Workspace → System；同一 System 在 DEV／FTEST／ENT 沿用相同邏輯 Config Revision，部署綁定分環境保存。部署識別／儲存形狀待定，不額外建 Group 或 Blueprint。Config Store 與 Artifact／Run Store 不等於搜尋選配 MongoDB；Memory 模式仍可能保存平台管理資料；獨立 Runtime 不強制連回平台儲存。

Builder 保存並管理可供重新匯入的原始資料（原始檔、CSV 或結構化 JSON）。儲存及保留方式由 Builder 後續規劃，見 [Q-016](08_plan_and_decisions.md#q-016)。解析結果、Prompt／Context Trace、評估報告保留與刪除規則也依 Q-016 追蹤。Ingestion 的 Queue 和工作結果由受理 Pod 在記憶體保存。歷史評估報告保留對應的舊 Config。

<a id="src-07-4-systemrevision-與-engine-生命週期"></a>
## System／Revision 與 Engine 生命週期

<a id="src-07-41-建立與啟動建議流程"></a>
<a id="system-lifecycle-api"></a>
### System 生命週期 API

Builder 保存 System、草稿、發布歷史和預期部署狀態。每個 Runtime Pod 在記憶體中持有已載入的 `system_id`、Config 快照、索引綁定及本地工作狀態。Builder DEV 的 Runtime 獨立於 Builder Backend，啟動時可有零組 Config。Builder Backend 透過受保護的內部管理 API 下發設定。DEV 請求可在 `config.secret` 與 `config.variable` 提供測試值，驗證與套用回應只回報 Secret Key／欄位路徑與狀態。單組 Config 獨立部署在啟動時直接呼叫同一套 Python 管理函數，並停用管理 API 路由。

| Method／Path | Request | 成功回應 |
|---|---|---|
| `PUT /internal/v1/systems/{system_id}` | `ApplyRequest` ＋ `Idempotency-Key` | `200` ＋ `SystemStatus`，完成套用後回應。 |
| `GET /internal/v1/systems` | 無 | `200` ＋ `{systems: SystemStatus[]}`，列出目標 Runtime 已載入的 System。 |
| `GET /internal/v1/systems/{system_id}` | 無 | Config 已載入或仍有可確認的既有受管索引綁定時，回 `200` ＋ `SystemStatus`。兩者皆無回 `404 SYSTEM_NOT_FOUND`。 |
| `POST /internal/v1/systems/{system_id}:detach` | 選填 `?pipeline=ingestion` 或 `?pipeline=inference`。空 Body ＋ `Idempotency-Key`、`X-Expected-Config-Revision`、`X-Expected-Index-Generation` | `204`，已卸載指定流程，保留受管 ES 索引。 |
| `DELETE /internal/v1/systems/{system_id}` | 空 Body ＋ `Idempotency-Key`、`X-Expected-Config-Revision`；受管索引另帶 `X-Expected-Index-Generation` | `204`，確認已卸載且受管索引已清除。相同操作可重送。 |

物件定義見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json) 的 `apply_request`、`system_status` 與 `pipeline_status`。

- System GET 的 `loaded` 表示目標 Runtime 至少載入一條流程，`can_ingest`、`can_query` 分別對應兩條流程的 `ready`。頂層 `active_config_revision`、`index_generation` 是 System 共用的生效版本及索引世代。頂層與本機快照不符的流程回 `loaded: true`、`ready: false`。兩條流程都未載入但可確認受管索引綁定時，回 `200` 及 `loaded: false`。連線失敗或操作結果未明而無法判斷時回 `503 SYSTEM_STATE_UNKNOWN`。清單 GET 列出目標 Runtime 至少載入一條流程的 System。
- `PUT` 將預檢的操作、`pipeline`、Config 和 `context_revision` 原樣送回。`expected_active_revision` 取自 `Validation.active_config_revision`；這是 Runtime 可確認的生效版本，即使各 Pod 的記憶體已清空，仍可由共用控制紀錄取得。首次部署、已卸載或無法從已存在紀錄確認生效版本時為 `null`；後者須依恢復規則查核，不能以此單獨判定可初始化。
- Runtime 在改變生效版或索引綁定前，取得該 System 的管理權，再重查預期版本、索引綁定與世代、有效 Config、索引影響及[匯入排空條件](#system-ingestion-drain)。`reload` 在目標 Pod 載入後核對共用版本與世代仍有效，確認可受理才開放該 Pod。既有一般 Ingestion 和 Query 可繼續。預檢後的狀態變更回 `409 STALE_CONTEXT`，操作與目前狀態不符回 `409 SYSTEM_STATE_CONFLICT`，版本或同一版本的 Config 內容不符回 `409 REVISION_CONFLICT`，忙碌回 `409 SYSTEM_BUSY`。一般文件新增或更新不使預檢 Context 過期；接收新的 Ingestion 仍可能使管理操作暫時忙碌。
- 負責管理 API 的 Builder Backend 先保存 `pending_operation`，以其 `operation_id` 作為 `Idempotency-Key`。Runtime 在共用控制紀錄按部署目標、System 和操作鍵核對操作身分、`pipeline` 及前置條件，並在 ES 有副作用前記錄進度與預定的實體目標。已成功的同一操作重送回該次結果，Builder 要讀當下狀態時再用 GET。相同鍵改變操作或目標流程回 `409 IDEMPOTENCY_CONFLICT`。狀態仍待查核回 `503 SYSTEM_STATE_UNKNOWN`；逾時本身不足以解除占用或重做實體索引操作。
- 已結束的管理操作結果依 Builder 的查核／重送窗口保留。仍在執行或結果待查的操作紀錄及必要占用保留至安全結算。超過結果保留期且 Builder 尚未確認時，先核對 System 狀態及原操作能否確認，再決定是否可重新發起。正式保留期限見 [Q-019](08_plan_and_decisions.md#q-019)。
- `busy` 表示管理變更目前會被阻擋，例如已有生命週期操作、本機仍有匯入工作，或其他 Ingestion Runtime 尚未完成[排空](#system-ingestion-drain)。是否可匯入或查詢分別讀 `can_ingest`、`can_query`。`index_generation` 隨建索引或重建變更，沿用索引時保持相同。未管理或目前沒有已確認的索引時為 `null`，未管理平台索引時 `index_ready` 也為 `null`。Runtime 可查空索引；Builder 依[初次匯入規則](07_builder_ui.md#builder-initial-ingestion-readiness)在新建／重建後等待預定資料成功匯入再開放查詢。

<a id="runtime-pipeline-deployment"></a>
#### 按流程部署 System

`runtime_ref` 選目標 Runtime，`pipeline` 選該 Runtime 要載入的 `ingestion` 或 `inference`。Builder 在預檢和套用的 Body 傳入 `pipeline`，卸載時用同名 Query 參數。省略時沿用整組 Config 的既有行為。兩條流程共用 `system_id`、同一份完整 System Config、共用生效版本及索引綁定。Runtime 只啟動指定流程的執行元件；可在同一個 DEV Runtime 個別載入，也可用同一 Runtime Image 分別部署。首版在 DEV／FTEST／ENT 預設提供 ES，以受管 ES 作為內建索引的部署與驗收基準。

| `operation` | `pipeline: ingestion` | `pipeline: inference` |
|---|---|---|
| `initialize` | 建立 System 綁定並啟用 Ingestion | 待 Ingestion 初始化後以 `reload` 接回 |
| `reload` | 接回已發布的版本與索引，啟用 Ingestion | 接回已發布的版本與索引，啟用 Inference |
| `update` | 發布共用新版本，依索引影響決定沿用或重建 | 以 `reload` 套用已發布版本 |
| `recover_index` | 依確認後的恢復流程建立新世代 | 恢復後以 `reload` 接回新世代 |

Inference 指定 `initialize`、`update` 或 `recover_index` 時，預檢回 `index_impact.action: blocked`、`code: PIPELINE_OPERATION_UNSUPPORTED`，套用回 `409 PIPELINE_OPERATION_UNSUPPORTED`。Inference 指定 `reload` 時須已有可核對的已發布 Config 及其相容索引。首次啟用時 Builder 先送 `initialize` ＋ `ingestion`，再對相同或不同的目標 Runtime 送 `reload` ＋ `inference`。使用中的索引相容時，停用其中一條流程不影響另一條的受理。

指定 `pipeline` 的 `update` 或 `recover_index` 可由負責索引的 Ingestion Runtime 執行，並保留既有啟用意圖。原本在該 Runtime 停用的流程，等 Builder 明確執行 `reload` 才載入。需要重匯資料時，Builder 先確認 Ingestion 就緒。

首版允許切版期間暫停新查詢。Builder 先用 `config:validate` 對各預期上線的 Inference 目標驗證草稿，這一步省略 `operation`。對 Ingestion 目標預檢 `update`，再提交發布。共用版本提交後，對仍預期上線且尚未載入有效快照的流程預檢及執行 `reload`。已載入的 Config Revision 或索引世代與共用綁定不符時，新查詢回 `503 PIPELINE_NOT_READY`，已受理請求依原快照與排空規則結束。Builder 核對目標 Inference 的版本、索引世代及 `ready` 後恢復測試入口。補載失敗時，保存共用發布結果及 Inference 的失敗狀態，後續針對未就緒流程重新預檢與補載。重試週期及回退策略見 [Q-020](08_plan_and_decisions.md#q-020)。

#### 刪除整個 System 的索引

刪除前，Builder 顯示會清除受管索引及其中資料，並保留 System 和發布歷史。Builder 從單一 System GET 取得預期版本與索引世代，向負責管理索引的 Ingestion Runtime 發出一次 DELETE。DELETE 以整個 System 為範圍。若多個 Runtime 共用該索引，Builder 在待確認期間暫停其相關目標與流程的補載及索引恢復，確認刪除後更新受影響的部署狀態。

Runtime 收到 DELETE 後取得管理權，核對索引歸屬、版本與世代。版本不吻合回 `409 REVISION_CONFLICT`，世代不吻合回 `409 INDEX_CONFLICT`。Runtime 依[匯入排空條件](#system-ingestion-drain)確認其他寫入目標已退出，並關閉該索引的新請求入口。排空既有查詢後清除受管索引與生效綁定，受理 DELETE 的 Runtime 清除本機載入狀態。索引綁定可確認時，`loaded: false` 同樣可執行 DELETE。刪除前依[索引歸屬驗證](#runtime-index-ownership)核對已生效綁定的指紋。確認清除後回 `204`。排空等待採 Runtime 的 Query Deadline；超過時回 `504 DEADLINE_EXCEEDED`。已送出的索引操作需先查核原操作結果。

管理操作僅供可信 Builder Backend。業務 HTTP／MCP 使用相同的 Runtime 狀態與執行入口。MCP 的業務 API key 只授權相應 System 與工具。

<a id="runtime-system-detach"></a>
#### 卸載單一 Runtime 的流程

`detach` 適用於由 Builder 管理、具受管 ES 綁定的 DEV System。Builder 從目標 Runtime 的單一 System GET 取得共用預期版本與索引世代，先記錄該流程的待確認操作並暫停補載，再向該 `runtime_ref` 的管理入口送出 POST。收到 `204` 後，將該流程的部署狀態更新為 `unloaded`。稍後明確部署該流程時，Builder 發起 `reload` 接回相容索引，成功後設回 `online`。省略 `pipeline` 時卸載該 Runtime 上的兩條流程。

Runtime 核對索引綁定、版本與世代，並對目標流程的本機管理操作與新請求受理做序列化。卸載 Ingestion 時，該 Runtime 持有排隊或執行中 Ingestion、Retire 或待查核寫入就回 `409 SYSTEM_BUSY`。卸載 Inference 時，關閉目標流程的入口並等既有 Query 結束，等待使用 Query Deadline。逾時則維持本機載入狀態並回 `504 DEADLINE_EXCEEDED`；若原版本與索引綁定仍可受理，恢復該入口。共用索引、索引世代、資料及其他流程或 Runtime 的受理狀態予以保留。

版本或世代不吻合時，分別回 `409 REVISION_CONFLICT` 或 `409 INDEX_CONFLICT`。同一成功操作以原 `Idempotency-Key` 重送時回 `204`。已卸載且仍可確認原綁定時也可回 `204`；查無載入與既有綁定時回 `404 SYSTEM_NOT_FOUND`。成功後單一 System GET 在索引綁定可確認時回 `200`，指定流程的 `loaded` 為 `false`，頂層索引世代可供 Builder 查核。

<a id="builder-managed-dev-runtimes"></a>
#### Builder 主動管理 DEV Runtime

Runtime 是載入 Engine Library 並提供 API 的執行程序。首版 DEV 每個 Runtime 部署目標以一個 Pod 運行一個 Runtime，可承載多個 System。Builder Backend 負責對各目標發起 Config 發布、更新、卸載與重啟後的補載。

DEV 平台管理員在部署時指定 `runtime_ref`。同一環境內，每個由 Builder 管理的部署目標有自己的固定值。Runtime 啟動時讀取此值並由 Catalog 回傳，Builder 用於核對目標與保存發布狀態。

| 情境 | Builder 管理方式 |
|---|---|
| 同一 Runtime 承載兩條流程 | 兩條流程使用同一個 `runtime_ref`。Builder 分別指定 `pipeline`，管理頁面顯示各自的載入與就緒狀態。 |
| 分開部署 | 每個 Runtime 使用自己的 `runtime_ref` 和管理入口。Builder 依 `(environment, runtime_ref)` 路由，按 `(environment, runtime_ref, system_id)` 保存部署紀錄，並逐流程追蹤意圖與發布結果。 |
| DEV Runtime 重啟或 Pod 更換 | 沿用原 `runtime_ref`。Builder 查核每一條預期上線的流程，既有索引可接回時，向尚未載入的目標下發指定 `pipeline` 的 `reload`。Runtime 核對版本與索引世代後載入，再受理該流程的新請求。 |

Builder Backend 啟動、Runtime 恢復連線後，以及每 60 秒（可由 Builder 部署設定調整），依部署紀錄呼叫單一 System GET，比對 `desired_pipelines`、各流程的 `loaded`／`ready`、本機 Config Revision 與索引世代。對預期上線但未載入有效快照的流程，使用已發布 Config 預檢並執行 `reload`；已卸載的流程維持原意圖。Runtime 或索引狀態待查時保留部署意圖及最後確認狀態，按[索引恢復規則](#system-index-lifecycle)處理。補載以目前狀態差異為觸發條件，沿用現有管理 API。

每個目標的管理入口須能接受 Builder 下發 Config，System 的 Ingest／Query 依各流程就緒狀態開放。多個 Runtime 可共用同一受管 ES 索引，部署時遵循 [Pod 內文件占用與派工](#pod-local-ingestion-control)的寫入分流條件。

**共用索引的 Runtime 加入與退出。** Builder 核對各 DEV 目標，向尚未載入已發布 Config 的 Runtime 發出 `reload`，包括後加入的 Runtime。Runtime 載入相同 Config 並接回既有索引。加入時的跨 Runtime 綁定授權及狀態查核依 [Q-020](08_plan_and_decisions.md#q-020)追蹤。單一 Runtime 停止承載 System 時使用 [detach](#runtime-system-detach)。整體刪除共用索引使用既有 DELETE。

<a id="system-index-lifecycle"></a>
### 初始化、重連與索引重建

`apply_system()` 先驗證 Config，推導平台索引應有的 mapping、搜尋欄位與 Embedding Profile，再依操作意圖處理索引。下表以受管 ES 為範圍。Config 載入與索引可用性分開報告。

| 操作 | 合法前置條件 | 成功結果 |
|---|---|---|
| A `initialize` | 首次部署或已明確卸載，確認目標索引不存在，預期生效版本為 `null`。 | 建立空索引與新世代並載入 Config。 |
| B `reload` | 目標 Runtime 的指定流程尚未載入與目前生效版本及索引世代相符的快照。送入既有生效版本及其已發布 Config；核對索引歸屬、綁定、指紋與實際 mapping。 | 載入該流程並接回目前的索引世代。 |
| C `update` | System 已有生效版本與可使用的受管索引；送入預期舊版和新發布版本。 | 相容時沿用索引，已開始的查詢固定舊版到結束。候選版需要重建時，先驗證舊索引仍符合原綁定。明確確認後排空、刪除舊實體索引、以新世代建立索引，完成後才啟用新版。 |
| D DELETE | 可確認索引歸屬及綁定，版本和世代符合 DELETE 前置值。Config 可處於已載入或未載入。 | 關閉入口、排空、清除受管索引與載入狀態，回到可初始化。 |
| `detach` | 預期版與世代符合目標 Runtime 的受管 ES 綁定。 | 關閉選定流程的本機入口、排空並卸載，保留受管索引。 |
| `recover_index` | Builder 仍要求已發布版本上線，Runtime 確認舊索引已遺失，且使用者已確認重建。可用於 Config 已載入或尚未載入。 | 以原 Config 建立同一 Revision 的新空索引與新世代，由目標 Runtime 載入或更新索引綁定，再由 Builder 重新匯入。 |

- **恢復發起。** 在 DEV，Builder 維持 `desired` 的已發布版本。Runtime 未載入或 `index_ready: false` 時，Builder 可在同步期間以預檢查核原因，並依發布紀錄區分首次部署與遺失。已確認索引遺失時，Runtime 暫停受影響 System 的查詢與匯入。Builder 顯示新索引會從空的開始、須重新匯入，等使用者確認後才提交 `recover_index` 和原已發布的 Config。同步與補載流程只查核與回報遺失，已確認發起的操作可依原操作鍵查核及重送。
- **恢復查核。** 帶入 `recovery_from` 的已發布版本及最後確認的索引世代。Runtime 先確認[共用控制索引](#es-runtime-control-index)可用。若索引可用但該 System 的控制紀錄缺失，可信 Builder 的部署記錄可補已發布身分，Runtime 仍須在取得管理權後確認實體目標不存在、沒有競爭綁定且沒有尚待查明的舊操作。若不能安全查證，維持待查。任何找到的索引都須先核對歸屬與綁定；ES 連線失敗或權限不足也維持待查。`recover_index` 只建立缺失的檢索索引。
- **失敗與交接。** 新版驗證失敗時舊版繼續服務。刪除後新建失敗時，保留最後提交的版本供對照並回報不可用；待查核中的 ES 寫入先用操作 ID、預定索引及最後已確認步驟確認結果，再按原操作接手。新建成功但版本尚未提交時，先查證新索引，再完成提交。共用索引由一個管理操作建立新世代，完成後由 Builder 向仍預期上線的其他目標下發 `reload`。各目標核對並載入新世代後才恢復受理。恢復成功後初次匯入仍依 Builder 的查詢開放規則。
- System Config 依[部署模式與設定來源](#runtime-config-sources)載入。

Runtime 從有效 Config 推導會影響索引內容、向量語意及搜尋能力的設定，將結果正規化後計算 SHA-256。輸入包括生效的解析／切分設定、文件 Embedding Profile（含模型版本與維度）及推導出的索引 mapping 和搜尋設定。正規化消除 JSON 物件鍵順序的影響，保留具語意的順序。純 Inference 參數如 `top_n` 不改變指紋。精確欄位與序列化見[索引指紋 v1](#index-fingerprint-v1-proposal)。

<a id="runtime-index-ownership"></a>
#### 部署環境與 ES 索引歸屬

- Builder Backend 建立 System 時產生小寫標準 UUIDv4 作為 `system_id`，在建立時以唯一鍵防止重複。更名、發布新 Config、匯出及部署到不同環境皆沿用同一值。格式見 [Runtime 識別 Schema](../schemas/runtime_identity.schema.json)。
- Runtime 啟動時從部署設定載入 `env`。Builder 管理的 Runtime 固定用 `builder`。獨立部署匯出可預填所選的 `ftest` 或 `ent`，部署方可在環境設定修改，並在啟動時驗證。獨立部署使用的名稱須與 `builder` 分開。共享 ES 叢集上的獨立部署若應有各自資料，須使用不同的 `env`。切換 `env` 時只查新環境的綁定，不接回或搬動原環境資料。[部署設定範例](../examples/system_config/deployment.env.example.json)
- 在選定 ES 叢集的環境控制索引中，以 `(env, system_id)` 定位目前生效的綁定。受管 ES 資料索引名為 `rag-<env>-<system_id>-<index_generation>`。Runtime 每次建立實體索引都產生新的小寫 UUIDv4 世代，含重建、恢復及刪除後重建。重送同一次管理操作沿用已登記的目標及世代；相容更新沿用原世代。讀寫與刪除以綁定的完整實體索引名定位。
- 接回、沿用或刪除前，核對實體索引名與綁定世代，並比對 `mappings._meta` 的 `env`、`system_id`、`index_fingerprint_version` 及 `index_fingerprint`。接回核對已發布版本的預期指紋；刪除核對生效綁定記錄的指紋。欄位缺失、不符或世代對應的實體名稱不符時，預檢回 `index_impact.action: blocked`、`code: INDEX_OWNERSHIP_UNVERIFIED`，執行管理操作回 `409 INDEX_OWNERSHIP_UNVERIFIED`。保留相關索引、metadata 及既有綁定。ES 無法讀取時按既有待查規則處理。[ES mapping metadata](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/mapping-meta-field)
- 發布時先對現存索引核對原生效綁定。原綁定核對成功後，若新 Config 的預期指紋與原版不同，才回 `rebuild_required`，並要求明確確認後使用新世代。原索引本身的指紋與原綁定不符時，`allow_rebuild` 無法解除歸屬拒絕。完整 Config 以 `(system_id, config_revision)` 追蹤。
- 建立索引時以 Create Index API 一次提交 mapping 與 `_meta`。重建在刪除舊索引前先登記下一代名稱，並確認新名未被占用。建立時遇到同名資源，只有同一筆已登記操作重送且能核對先前建立結果時才接續，其他情況回 `409 INDEX_OWNERSHIP_UNVERIFIED`。部署須停用受管資料索引的隱式建立。索引重建與刪除只操作已查核的完整實體索引名。[Create Index API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-indices-create) · [ES 自動建索引設定](https://www.elastic.co/docs/reference/elasticsearch/configuration-reference/index-management-settings)

既有索引若使用舊命名或缺少 `_meta.env`，進入歸屬查核，保留原索引供確認或遷移。

Local Memory 使用同一套相容判定與 `system_id` 隔離；程序重啟後記憶體索引遺失，需重新匯入。外部 Retrieval 查詢自有資料時，依其服務就緒狀態與候選契約執行；上述索引建立、重建與卸載的刪除範圍只涵蓋平台管理的資料。

<a id="index-fingerprint-v1-proposal"></a>
#### ES 索引指紋 v1

Runtime 的 Config 編譯器輸出 [指紋投影 Schema](../schemas/index_fingerprint.v1.schema.json)。輸入是解析預設值、別名與外部依賴後的有效索引計畫。Schema 的 `$defs.mapping_meta` 另驗證 Runtime 寫入 `mappings._meta` 的欄位。

| 投影欄位 | 內容及推導規則 |
|---|---|
| `version` | 投影規則版本，首版固定為 `1`，參與計算。 |
| `ingestion` | 依 Import → Parsing → Chunking → Embedding 的實際執行順序列出階段。內建方法以 `kind: builtin`、`module`、`component_id`、`component_version` 識別。每個有效階段攜帶 `output_structdata`，欄位的 `required`、`searchable`、`filterable` 全部展開。 |
| 內建階段的 `parameters` | 由 Component 投影允許清單產生。Import 保留有效 `source`，欄位約束取自 `output_structdata`。Parsing 保留會改變輸出的生效模式及參數，Passthrough 為 `{}`。Recursive Chunking 保留有效切分／輸出欄位、複製映射、長度、overlap、分隔符及切分選項，並以 `tokenizer_revision` 表示已解析的穩定 Tokenizer 識別。Dense Embedding 保留實際啟用的文字合成與有效模板，向量映射及模型識別由 `index` 記錄。其他 Component 需定義各自的輸出影響投影，編譯器才可判定相容。 |
| Remote 階段 | `kind: remote` 以 `module`／`through` 表示含首尾的替代範圍，附 `adapter_version`、Remote HTTP 的 `contract_version`、穩定的 `implementation_revision`、有效 `parameters` 和輸出 `output_structdata`。缺少可解析的實作版本時回報相容性未確認。 |
| `index.component_id`、`component_version`、`structdata` | 解析後的 Indexing 實作識別及套用 overrides 後的有效欄位型別與搜尋能力。 |
| `index.vector_bindings`、`embedding_spaces` | 兩個物件都以已選入索引的向量名稱為鍵，鍵集合必須一致。前者沿用 IndexBinding 的來源欄位、Profile ID 與維度，後者記錄實際模型 ID 與穩定版本。沒有索引向量時皆為 `{}`。 |
| `index.mapping`、`settings` | 解析後的 ES 欄位、動態規則、runtime fields、`_source` 及會影響相容性的原生 `analysis`、`similarity`。預設值由目標後端能力與設定解析；無宣告的 `dynamic_templates` 用 `[]`，無定義的 `runtime`、`analysis`、`similarity` 用 `{}`。原生 ES 物件由 ES 驗證。後端若有會改變索引語意而 v1 投影未涵蓋的設定，回報相容性未確認。 |

純 Inference 的 Rewrite、融合、Rerank、固定 Filter、`top_n`、運作限額、端點、憑證與單文件的 `source_revision` 都不參與指紋。`env`、`system_id` 和 `index_generation` 各自用於識別與定位，也排除在指紋投影外。以 System Variable 提供的切分長度等入庫設定，按解析後的有效參數判定索引相容性。遷移 ES 叢集或索引名稱時，Runtime 依環境綁定重新查找實體目標並核對歸屬。

1. 編譯器先解析預設值、舊欄位名稱及依賴版本，檢查階段順序與覆蓋範圍、向量鍵集合及 mapping 維度。無順序語意的陣列按穩定鍵排序，例如 `copy_fields` 按唯一的 `output_field`；切分分隔符、分析器 pipeline 及 `dynamic_templates` 保留順序。
2. 對整份投影執行 [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)，以 canonical UTF-8 bytes 計算 SHA-256。將小寫十六進位摘要連同 `index_fingerprint_version`、`env` 和 `system_id` 寫入 ES `mappings._meta`。完整 [JSON 範例](../examples/system_config/index_fingerprint.v1.example.json) 可離線核對。
3. 只有歸屬、指紋版本、指紋、實際 mapping 及必要 settings 均符合才能沿用。候選版有相容性變更時，依[索引歸屬驗證](#runtime-index-ownership)確認舊索引後走重建流程。未知規則版本、缺少可信的依賴版本、無法確認歸屬或讀取 mapping 時保留現有索引並回報需要查核。

Runtime 驗收要驗物件換序、等效預設值及只改 Inference 參數不改指紋，切分長度、同維度換模型或搜尋能力變更會改指紋，以及實際 mapping 偏離或缺少指紋版本時不得當作相容。已存在且缺少指紋的索引如何遷移，以及未來規則升版，由 [Q-015](08_plan_and_decisions.md#q-015) 追蹤。

<a id="src-07-411-remote-imageexternal-的生命週期"></a>
### 外部 Remote API 的生命週期

User 設定已部署的外部服務。Runtime 在執行時依有效環境綁定呼叫，平台驗證契約與連線。外部資料、服務部署與維護歸提供者，平台索引仍由 Indexing 管理。

### 更新／卸載的併發與失敗

<a id="system-ingestion-drain"></a>
每個 `system_id` 一次處理一個生命週期變更。發布、生效綁定變更或刪除前，受理管理操作的 Runtime 在本機同步關閉新 Ingestion／Retire 的入口並檢查本機工作。若有本機工作、待結算的索引寫入或 Retire，或其他 Runtime 尚未確認退出寫入，回 `409 SYSTEM_BUSY`。查核所需狀態無法取得時回 `503 SYSTEM_STATE_UNKNOWN`。操作未能取得管理權且原版本仍可服務時恢復原本的本機入口。各 System 各自處理。

啟用 Ingestion 時，Runtime 在共用 System 生命週期紀錄登記目前的索引世代與 `runtime_instance_id`，並與新版本發布及關閉入口使用同一份紀錄核對。這項登記只在流程啟用、退出或管理時更新。DEV 由 Builder 先暫停對其他 Ingestion 目標送件，再逐一呼叫 `detach?pipeline=ingestion`。目標在本機無工作及未結算寫入後移除登記並回 `204`。獨立部署由部署方排空並停止其他寫入程序。若 Runtime 非預期停止，須有部署層確認程序已終止，才可移除遺留的啟用登記。刪除或重建時，管理操作仍按原索引世代和實體目標執行。已送出的 ES 請求可能在程序終止後才完成。管理操作完成後，由 Builder 或部署方依新生效版本恢復需要的寫入目標。

相容更新時，舊查詢保留原 Config 和索引世代引用，等引用結束才釋放原版資源。需要刪除索引時，由共用生命週期紀錄先禁止取得新查詢引用，確認既有引用已排空才刪除。一般文件寫入仍可與查詢併行。

新版驗證失敗時，原生效版本與索引繼續使用。若已刪除索引但建立新索引失敗，回報更新失敗，該 System 保持不可用，待重試成功後由 Builder 重新匯入。Runtime 重啟後，Ingestion 工作紀錄和占用從空的狀態開始。未完成的管理操作依共用控制紀錄中的操作 ID、已確認步驟及實體索引目標查核後再接手。

獨立部署遇到相容索引時可接回。部署時若確認目標索引不存在，是否須由部署者指定建立，或由部署流程按綁定狀態建立，留到 [Q-021](08_plan_and_decisions.md#q-021) 定案。部署方在新索引建立後重新匯入資料。DEV 由 Builder 依 [變更影響](05_system_config.md#變更影響)向使用者呈現重建及停查影響。

DEV 實作驗收以受管 ES 為準，覆蓋首次建立、Runtime 重啟後由 Builder 下發及接回索引、多 Runtime 管理請求按目標隔離、逐流程 `detach` 後其他流程可沿用原索引、索引恢復、未知歸屬拒絕、切版至補載期間的停查、忙碌拒絕、排空後重建／卸載、過期 DELETE、刪除後建立失敗、逾時重送與中斷後接手。


2026-10-16 的內容保存簡化：Indexing 保存全部 Document.structdata／metadata，Chunking 預設繼承全部有效業務 metadata；只選全文／向量／Filter 能力。原型的 indexing.stored／chunking.metadata 是待遷移的舊保存／繼承投影，不能直接套用為新規則。metadata 以 JSON object 整包保存與回傳，搜尋能力依 [structdata 欄位規格](02_data_contracts.md#data-meta-schema) 推導。

**D-60 的讀寫範圍與仍待決的版本機制**：

- Ingestion／retire 與 Query 各自進行，不因寫入阻擋查詢，不加共享 Query 讀寫鎖／全索引快照；使用者接受更新期間的短暫新舊混合。
- 同 document_id 重複 Ingestion 的忙碌拒絕保留；文件未完整成功不得標 completed。失敗清理、崩潰處理及最終資料正確性仍需 backend 實作，不代表讀取有原子保證。
- System 更新或卸載遵守本節的忙碌與排空規則。相容的 Inference 更新沿用現有索引。索引格式／Profile 相容與版本識別仍依 Q-010／Q-015。

<a id="src-07-51-builder-backendcontrol-plane"></a>
## Builder Backend（Control Plane）

以下路徑沿用原提案，完整 OpenAPI／認證／欄位 Q-019：

| HTTP method | Path | 責任 |
|---|---|---|
| POST | /api/rag-systems | 在授權 Workspace 建立 System |
| POST | /api/rag-systems/{id}/config:validate | Schema／相依驗證，回傳模組及欄位錯誤 |
| POST | /api/rag-systems/{id}/revisions | 保存配置與變更影響；需處理版本衝突 |
| POST | /api/rag-systems/{id}/evaluation-runs | 選 Dataset／Target 啟動評估 |
| GET | /api/evaluation-runs/{run_id} | 狀態與報告引用 |
| POST | /api/rag-systems/{id}/exports | 套用目標環境覆寫並產生 Bundle |

System 列表／讀取、Workspace／Dataset CRUD、AI suggestion／連線檢查、DEV Runtime Binding 的完整路徑尚未定義；Q-019 依階段補齊：Runtime API 在 M3 前、獨立助手 API 在 M4 前、Builder 管理與助手 UI API 在 M5 前。不以表中六條當作完整 Backend API。

<a id="src-07-54-builder-上傳與自行部署"></a>
## Builder 上傳與自行部署

Engine 不提供 multipart 上傳端點。Builder 可接收檔案／CSV，轉成 content、Base64 或可存取 URI 再呼叫相同 JSON API；自行部署的呼叫端負責相同轉換。檔案傳輸轉換不等於語意 Parsing，原始檔案內容仍需 Engine 有相容 Parser。

Builder 管理的 System 重建索引後，由 Builder 使用保存的原始資料，以生效的新 Config 透過既有 Ingestion API 重新匯入。索引刪除與原始資料保留各由 Runtime 和 Builder 管理。Builder 的 [CSV 整批替換](07_builder_ui.md#builder-csv-replacement)由 Builder 協調清除資料和重新提交。獨立部署的資料由部署方提供，使用相同的 Ingestion API。

檔案儲存、上傳／下載授權、來源版本、保留與刪除、重新匯入的觸發與管理流程由 Builder 後續規劃，見 Q-016／Q-019。Builder 上傳入口的 MIME、大小、逾時及實際格式偵測規則另待核定。Runtime 的 JSON／來源取得限制依 Runtime 控制手冊，檔案來源須符合該 System 所選 Parser 的格式契約。

<a id="runtime-capability-contract"></a>

<a id="src-07-58-runtime-component-目錄與-config-驗證邊界"></a>
## Runtime Component 目錄與 Config 驗證邊界

Builder Backend 透過 Runtime API 取得目錄並驗證草稿。共用的路由、認證與錯誤格式見 [HTTP 共通規格](#runtime-http-common)與 [HTTP 錯誤格式](#runtime-http-errors)。

- **方法與能力目錄**：提供目標 Runtime 已交付的內建方法、版本、Component Schema 與能力。Remote API 的有效契約由 User 設定及 System Schema 推導。
- **完整 Config 驗證**：Builder／助手提交有效設定與目標版本，重用 Engine 的型別、跨模組相依與索引相容檢查；回傳可定位到 `[MODULE NAME]`／欄位的結果。格式有效、可組裝、服務已連通與資料可查詢分開，不把目錄查詢當成真實連線測試。
- **版本與目錄一致性**：目錄／Schema／驗證結果要能對回同一目標 Runtime 版本；Runtime 更新後，舊快取或過期驗證不得靜默套用。既有 System 保留所選版本，尚未安裝／不相容方法應明示，不自動取最新版。
- **相容範圍**：既有 API、Config Schema 與 UI 控制項足以支援時，新增 Component 可只發布／部署 Runtime；需要新型表單或破壞性接口時，需更新 Builder 並完成契約相容測試。長期欄位演進政策由 Q-002／Q-019／Q-025 追蹤。

System Config Schema 由目標 Runtime 提供，版本須與 Catalog 及 Config 驗證結果對應。現行 Catalog API 回傳 Component Descriptor 與資源，完整 System Config Schema 的 HTTP 交付方式待定。

直接 Python 使用 Engine／M4 助手時仍可在本機取得同一 Registry／Validator，不因此強制所有呼叫都走 HTTP。平台整合使用公開服務邊界，Runtime 的可信管理與能力接口不等於允許外部一般使用者更改 System 綁定。

Descriptor 的欄位推導規則見 [Component Descriptor](04_component_descriptor.md)。Builder 依 Catalog、草稿及上游輸出規則產生編輯候選。服務 URL／Secret 由部署綁定解析。

<a id="w1-catalog"></a>
<a id="w1-config-options"></a>
### Catalog API 與草稿選項

開啟設定編輯或切換 Runtime 時，Builder Backend 呼叫目標 DEV Runtime 的 `GET /internal/v1/catalog`，無 Request body。成功回 `200`，提供 `runtime_ref`、`catalog_revision`、該 Runtime 的 `descriptors` 及可用的 `resources`。每個 Descriptor 以 `(module, component_id, component_version)` 識別，每種資源以 Config 使用的 ID 為鍵。目錄可附顯示名稱。Embedding Profile 提供向量維度。

| Catalog 回應欄位 | 用途 |
|---|---|
| `runtime_ref` | DEV 部署設定提供的 Runtime 目標識別。Runtime 由 Catalog 回傳，Builder 驗證與套用時須回送。同一目標重啟或更換 Pod 時沿用此值。 |
| `catalog_revision` | Descriptor 與資源清單的版本。Builder 與 Runtime 以此判斷是否使用相同目錄。 |
| `descriptors` | 已交付方法的 Descriptor 陣列。每組 `(module, component_id, component_version)` 在同份 Catalog 只出現一次。見 [Descriptor 欄位](04_component_descriptor.md#descriptor-fields)。 |
| `resources` | 四個以 ID 為鍵的資源清單。每個資源可附 `label`，Embedding Profile 須附正整數 `dimensions`。 |

| Catalog 資源清單 | 用途 |
|---|---|
| `resources.profiles` | Embedding Profile ID、顯示名稱及向量維度。 |
| `resources.tokenizer_profiles` | Chunking 可引用的 Tokenizer Profile ID 及顯示名稱。 |
| `resources.models` | 可選的邏輯模型引用及顯示名稱。 |
| `resources.elasticsearch_services` | 可選的 Elasticsearch 邏輯服務引用及顯示名稱。 |

以 [Catalog Schema](../schemas/runtime_catalog.draft.schema.json) 驗證 [Catalog 回應範例](../examples/system_config/runtime_catalog.response.json)。四種資源集合皆可為空。Catalog 不帶實際認證憑證或連線測試結果。Runtime 變更 Descriptor 或可用資源清單時更新 `catalog_revision`。Builder 在同一次目標環境編輯中共用目錄。驗證或套用若發現 Runtime 識別或 Catalog 版本不符，回 `409 STALE_CATALOG`。Builder 重新取目錄並檢查既有選值。已選版本找不到時保留原值並提示修正。

#### 在 Builder 解析 `option_sources`

| Descriptor 指定的來源 | Builder 的解析依據 |
|---|---|
| `profiles`、`models`、`tokenizer_profiles`、`elasticsearch_services` | 同一份 Catalog 的對應 `resources` 子表。 |
| `input.structdata`、`input.vectors` | 目前草稿沿 Pipeline 推導的上游有效輸出。 |
| `index_plan.fulltext`、`index_plan.vectors` | 草稿推導的 Indexing 欄位用途及選定的向量。 |
| `candidate.structdata`、`candidate.document_fields` | 草稿推導的有效候選文件欄位。 |

Builder 依來源及 Descriptor 宣告的型別、必填條件和固定 `enum` 篩選。改 Import 的欄名後，Builder 重新推導受影響的下游候選。合法來源沒有相符欄位時顯示空清單；上游尚未填完時提示相依設定；現選值失效時留在草稿並標示原因。索引欄位表、向量表與有效 I/O 預覽共用推導結果。表單的呈現與存值見 [Renderer 契約](07_builder_ui.md#ui-hints-contract)。

<a id="config-validation-api"></a>
### Config Validation API

Builder 編輯時依 Descriptor 與推導出的有效 I/O 檢查必填、型別、範圍及欄位相依。發布前呼叫 `POST /internal/v1/systems/{system_id}/config:validate`。這是帶完整 Config 的唯讀預檢，檢查設定能否在目標 Runtime 執行及索引影響。可驗證尚未載入的 System。GET 用於查目前狀態，這裡以提交的 Config 試算效果。

本機推導與 Engine 驗證結果不一致，以及 Builder 遇到未支援規則時的行為，見 [共用推導驗收](04_component_descriptor.md#descriptor-derivation-conformance)。

請求與回應見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json) 的 `validate_request`、`validation` 與 `index_impact`。

`Config` 為 [System Config 快照](../schemas/system_config.draft.schema.json)內層的 `config`。Runtime 驗證完整 Config 結構及跨流程資料、索引契約，並檢查指定流程要使用的 Component 和資源。Inference 預檢可讀取 Ingestion 的欄位、Embedding Profile 與索引綁定資訊，執行時只載入所選流程的元件。Config 驗證失敗回 `422 CONFIG_VALIDATION_FAILED`，定位見 [HTTP 錯誤格式](#runtime-http-errors)。

`draft_revision` 識別 Builder 送驗的草稿或相同已發布快照，供比對及捨棄過期回應。指定 `pipeline` 時，`loaded` 回報該流程在目標 Runtime 是否已載入；省略時回報整組 Config 是否已載入。`active_config_revision` 是 System 共用的生效版本。`context_revision` 綁定 System、Runtime、Catalog、送驗快照、`pipeline`、操作、預期版本及受影響的索引世代。套用時由目標 Runtime 再查核載入與索引狀態。未指定操作時可預覽草稿影響；送 `PUT` 前須以選定操作和相同 `pipeline` 取得 Context。不符合操作前置條件時，預檢回 `blocked`，實際套用也須拒絕。

| `index_impact.action` | `code` 範例 | Builder 行為 |
|---|---|---|
| `create` | `INDEX_MISSING` | 首次部署或已卸載時提示建立空索引。若發布紀錄顯示應有索引，改走恢復預檢，等使用者確認。 |
| `reuse` | `INDEX_COMPATIBLE` | 重新載入已發布版本或套用相容新版，沿用索引與既有資料。 |
| `rebuild_required` | `INDEX_FINGERPRINT_CHANGED`、`INDEX_MAPPING_CHANGED` | 提示停查、清除與重新匯入。確認後才用 `update` 並設 `allow_rebuild: true`。 |
| `recover` | `PUBLISHED_INDEX_MISSING` | 舊索引已確認遺失，顯示需建立新世代並重新匯入。使用者確認後才以 `recover_index` 套用，`config_revision` 必須等於 `recovery_from.config_revision`。 |
| `blocked` | `INDEX_OWNERSHIP_UNVERIFIED`、`INDEX_CHECK_UNAVAILABLE`、`INDEX_RECONNECT_INCOMPATIBLE`、`SYSTEM_STATE_CONFLICT`、`PIPELINE_OPERATION_UNSUPPORTED` | 保留狀態並顯示原因。索引連線未知時保持待查。 |
| `none` | `INDEX_NOT_MANAGED` | 此設定沒有平台管理索引，例如完全由外部服務管理資料的 Retrieval。 |

<a id="src-21-1-範圍與已確認基準"></a>
## 範圍與已確認基準

<a id="src-21-11-這份清單是哪一層"></a>
### 這份清單是哪一層

Builder DEV 與自行部署到 FTEST／ENT 使用同一組 Retrieval Runtime 業務 API。D-64 的初始 Runtime 限制由 Admin／部署管理者在 E 的環境設定提供。DEV 可由共用 Runtime 承載多個 System，可信路由先選擇 System 與流程的有效快照。獨立部署可用同一 Runtime Image 啟動選定流程，見[獨立部署](#src-07-92-驗證與部署)。System 識別由可信路由或部署配置決定。

Builder Workspace／System CRUD、Export、AI 助手與 Evaluation 各有自己的服務介面。User Remote API 的 operation HTTP 協定見 [Engine／Component 開發](03_engine_and_components.md)。

Library 仍可直接由 Python 使用；本表描述 Runtime HTTP／工作管理層，不要求每次 Library 呼叫都經 HTTP。

<a id="src-21-12-已確認不再當成待選方向"></a>
### 已確認，不再當成待選方向

- 同一 System 的同一 document_id 以新文件完整替換；不存在則新增，成功後移除該文件不再產出的舊 Chunk。
- 更新與執行結果以 `document_id` 為單位，Batch 中各文件獨立。ES 確認新批次完整可搜尋後才清理舊資料，清理完成才標 `completed`。依 D-60，更新期間可讀到新舊混合。詳見 [Elasticsearch 文件覆寫](#elasticsearch-document-replacement)。
- 排隊、執行及工作結果都在記憶體。Runtime 重啟或 Pod 被替換後，舊工作和結果一併遺失，不補跑或結算。
- Runtime 統一管理有上限的 Ingestion Queue、併發、Inference Rate limit／併發與逾時。每 Pod 內每 System 的文件執行併發可配置，預設 1；調高前需驗證 Component／共享資源安全，不等於無限制並行。
- 同一 Pod 內，同一 System 的同一 `document_id` 有有效占用時拒絕再次提交。已登記終態並解除占用的 ES Bulk 逾時工作可重新提交，詳見 [ES 寫入查核](#es-write-control-record)。
- Run／文件狀態查詢使用受理 Pod 的記憶體。文件存在性與摘要由實際檢索資料索引判斷。
- 202 表示已接受排隊，不表示解析、Embedding、索引或可搜尋已成功；提交後須可查詢結果。
- Inference 沿用 query／filters／metadata 輸入，同步回 [Inference 成功物件](#inference-api)；不做 Generation，不因非同步 Ingestion 而新增 InferenceState。
- D-57：整批接收前預檢通過才入列、回 202；入列後逐文件結果，文件無 partial，Run 可 partial，無紀錄回 200＋unknown。這不是要求完成 Parsing／Embedding／Indexing 才回 202。
- D-57／D-58：首期需要 retire，已確認為直接刪除該 System／document_id 的儲存資料與搜尋索引，不是保留資料的邏輯停用；後續 D-64 確認同步 200＋deleted／not_found，忙碌文件 409，後端／Remote 清理協定仍待細化。排隊與執行中的工作見[批量取消](#ingestion-cancel-api)。
- D-58：一支 POST /v1/ingestions 接收批次物件，documents 為非空 Document[]；Parser 每次仍接收單份物件，不另開 :batch。
- D-58：新增文件存在性與全部 document_id 清單的查詢能力，資料來源為該 System 的實際儲存／索引，與 Runtime 工作狀態分開；清單需對 Chunk 的 document_id 去重。
- D-60：讀寫各自進行，不因 Ingestion／retire 寫入而阻擋 Query，不加共享查詢讀寫鎖／全索引快照；同文件的忙碌拒絕以受理 Pod 為範圍。
- D-60：Runtime API 暫採 HTTP Basic Auth，預設一組帳密可操作該 API service 提供的全部 API，首期不做逐角色／逐 API 權限；Builder 使用者登入另議。
- D-61～D-63：多個 System 共用 Runtime 與 LangGraph，各請求固定 Config 快照。切版、索引及資源交接見 [System 管理](#src-07-4-systemrevision-與-engine-生命週期)。服務池分組與快取回收策略依 Q-020。

- D-64：確認接收／文件與 Run 狀態核心欄位及錯誤格式；Pod 存續期間的覆寫失敗可從本機工作紀錄查詢，實際索引狀態依文件覆寫規格查核。初始限制見 Runtime API／部署手冊。可信內部 System 路由見 [HTTP 共通規格](#runtime-http-common)。

- D-65：文件清單回 documents[]＋next_cursor，每筆 document_id／source_revisions[]，彙整實際儲存版本；不提供最新成功版或版本歷史推定。分頁參數見 [資料生命週期 API](#data-lifecycle-api)。

<a id="src-21-2-api-清單7-支業務-api2-支-health-api"></a>
<a id="data-lifecycle-api"></a>
## 資料生命週期、Inference 與 Health API

業務路徑相對於 `/internal/systems/{system_id}/v1`（DEV）或 `/v1`（獨立部署）。每次請求固定使用 Runtime 當下生效的 Config 快照。

路由可固定註冊，由 Runtime 依 System 及流程的狀態受理。`/ingestions`、`/documents` 與其子操作都屬 Ingestion，`/queries` 屬 Inference。System 可確認但指定業務流程未載入時回 `409 PIPELINE_NOT_ENABLED`。流程已載入但切版中或本機快照尚未對齊時回 `503 PIPELINE_NOT_READY`。只有索引尚未就緒時沿用 `503 INDEX_NOT_READY`。每條流程就緒後可獨立受理，例如 Ingestion 卸載後，索引仍就緒時可繼續查詢。

Run 查詢、文件工作狀態與批量取消都送原受理 Pod。對目標 Runtime 執行 `:detach?pipeline=ingestion` 後，這些 API 依流程門檻暫停；同一程序內重新啟用後可查仍在保留期內的紀錄。Pod 被替換後，即使沿用 `runtime_ref`，也查不到前一個程序的工作。

| Method／Path | 請求 | 成功回應 |
|---|---|---|
| `POST /ingestions` | [IngestionRequest](../schemas/ingestion_request.schema.json)，單筆也放 `documents[]`。 | `202` ＋ `ingestion_accepted`。整批預檢後一併接受。透過 `Location` 指向的 `/ingestions/{run_id}` 查工作結果，沿用同一 API 路由前綴。 |
| `GET /ingestions/{run_id}` | 無 | `200` ＋ `ingestion_run_status`，含查無或到期的簡式回應。 |
| `POST /ingestions/{run_id}/cancel` | [CancelIngestionRequest](../schemas/ingestion_cancel_request.schema.json)，指定 `document_ids`。 | `200` ＋ `ingestion_cancel_result`，逐筆回報結果。見[批量取消](#ingestion-cancel-api)。 |
| `GET /documents/{document_id}/ingestion-status` | 無 | `200` ＋ `document_ingestion_status`。 |
| `GET /documents/{document_id}/exists` | 無 | `200` ＋ `document_exists`，讀實際文件資料。 |
| `GET /documents?limit=…&cursor=…` | `document_list_query`。 | `200` ＋ `document_list`。以 `document_id` 升冪分頁，Cursor 限同一 System，終頁回 `null`。僅彙整實際可見的非空版本字串，沒有就回 `[]`。資料寫入期間可變動。 |
| `POST /documents/{document_id}:retire` | 無 | `200` ＋ `document_retire`，同步完成，文件忙碌回 `409`。 |
| [`POST /queries`](#inference-api) | [InferenceRequest](../schemas/inference_request.schema.json)。 | `200` ＋[inference_response](../schemas/runtime_http.schema.json#/$defs/inference_response)。 |

回應物件及分頁參數的定義見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json)。提交範例、狀態欄位與儲存語意分別見 [Ingestion](#src-21-3-ingestion-的提交與接收)、[Ingestion Run 與文件狀態](#src-21-4-文件狀態與一次提交的狀態)與 [文件管理](#src-21-9-文件資料查詢與直接刪除)。錯誤見 [HTTP 格式與狀態碼](#runtime-http-errors)。

服務根路徑的 `GET /health/live`、`GET /health/ready` 皆無 Request body，成功回 `200` ＋ `health`。Readiness 檢查服務初始化，服務未就緒回 `503 RUNTIME_NOT_READY`。Builder 查個別 System 的匯入與查詢能力時讀取 [SystemStatus](#system-lifecycle-api)。

<a id="src-21-3-ingestion-的提交與接收"></a>
## Ingestion 的提交與接收

<a id="src-21-31-已確認單一端點單份也包-list"></a>
### 單一端點，批次物件

`POST /v1/ingestions` 接收 [IngestionRequest](../schemas/ingestion_request.schema.json)。整批預檢通過才 202，單份同樣置入 documents。Runtime 在 Parser 前拆成逐文件工作，每次傳入一筆 Document。有效 parameters 隨同一批每筆工作傳遞，Parser 後仍可按同一文件處理 Document[]。

```json
{
  "documents": [
    {"document_id": "manual-001", "structdata": {"text": "清潔散熱孔"}},
    {"document_id": "manual-002", "structdata": {"text": "檢查風扇"}}
  ],
  "parameters": {"language": "zh-TW"}
}
```

Runtime 驗證 Import 宣告的參數和每筆有效 Document Schema。接收後保留同一 Config 與參數快照。共用 [Request Schema](../schemas/ingestion_request.schema.json) 由 System 欄位再細化。此格式更新 D-58 的根層陣列，保留單一端點、預檢及逐文件工作語意。

<a id="src-21-33-202-回應核心欄位d-64-已確認"></a>
### 202 收件回應

若 `202` 或 `run_id` 遺失，呼叫方可用 `GET /documents/{document_id}/ingestion-status` 取得提交文件最近一次已受理的 `run_id`，再用 `GET /ingestions/{run_id}` 核對整批文件。逐文件狀態只指向最近一次提交，後續有其他匯入時可能指向其他 Run。首版以這兩個查詢入口為準，Ingestion 的 `Idempotency-Key` 及 Run 清單留待 [Q-008](08_plan_and_decisions.md#q-008) 後續討論。

Location: /v1/ingestions/ing-001

```json
{
  "run_id": "ing-001",
  "status": "queued",
  "config_revision": "C1-example",
  "documents": [
    {"document_id": "manual-001", "status": "queued"},
    {"document_id": "manual-002", "status": "queued"}
  ]
}
```

提交一份或多份使用相同 receipt，一份只有一筆 documents；Request 與 Receipt 都以 documents 陣列列出各筆文件。Receipt 是接受當下的快照，Client 查詢時可能已 running 或完成。

建議接收階段只做授權、JSON／外層 Schema、有效 Config／Parser 能力等快速預檢、文件忙碌檢查與容量預留。下載、昂貴 Parsing、Embedding／Indexing 在 Worker 執行，失敗由狀態 API 回報，不能把 202 當作最後成功。

**D-57 已確認：「預檢整批通過才入列；入列後逐文件獨立結果」。**例如外層不合法、同批重複 ID、某文件仍有占用（含已取消但待收尾的工作）、容量不足時，先拒絕整次請求，保證沒有未交代的部分入列；接收政策與批次物件包裝均已確認。錯誤碼見 [HTTP 錯誤格式](#runtime-http-errors)。合法文件入列後，另一份文件 Parsing 失敗不回滾已成功文件。

受理 Pod 一次檢查整批的本機占用。只要有一份文件被占用，整批回 `409 DOCUMENT_BUSY`，並用 [`error.conflicts`](#ingestion-document-busy)列出該 Pod 當次檢查的全部衝突。

Ingestion 依 [Pod 內文件占用與派工](#pod-local-ingestion-control)在本機一次完成預留、建立 Run 與入列，再回 `202`。容量與大小上限見 [Runtime 設定](#src-22-2-已確認的初始預設)。

<a id="ingestion-cancel-api"></a>
### 批量取消 Ingestion 文件

`POST /ingestions/{run_id}/cancel` 接收 [CancelIngestionRequest](../schemas/ingestion_cancel_request.schema.json)。`run_id` 限於路由選定的 System。Runtime 只處理此 Run 及清單中指定的文件。成功處理的請求回 `200`，`documents` 依請求順序逐筆回報，其他文件的結果不影響可取消文件的處理。

| 文件狀態 | `result` | 回傳的 `status` |
|---|---|---|
| `queued` 或 `running`，已登記取消 | `cancelled` | `cancelled` |
| 先前已登記取消，目前仍為 `cancelled` | `cancelled` | `cancelled` |
| `completed` 或 `failed` | `already_finished` | 原本的 `completed` 或 `failed` |
| 執行結果待查的 `unknown` | `not_cancellable` | `unknown` |
| 指定文件不屬於此 Run | `not_found` | `null` |

Runtime 登記取消後，取消與狀態查詢皆直接顯示 `cancelled`。若原 Worker 已取得寫入權，受理 Pod 保留占用至本次寫入結算；此期間同一 Pod 收到重送回 `409 DOCUMENT_BUSY`。

- 對 `queued` 工作，取消與領取在本機同步機制內核對同一筆 `run_id`、`document_id` 和狀態。取消先成功時，保存 `cancelled` 後釋放文件占用及等待名額。Worker 之後取到本機 Queue 中的該項目，領取檢查失敗便跳過。
- 對 `running` 工作，取消與取得首次索引寫入權使用同一個本機同步機制。取消先成功時，保存 `cancelled` 並釋放占用，舊 Worker 的首次寫入檢查會失敗。若原 Worker 已取得寫入權並完成原批次，確認索引發布成功後將該文件改為 `completed`。若以失敗或 Bulk 逾時結案，則維持 `cancelled`。兩種情況都依[寫入結算規則](#es-write-control-record)釋放原占用。
- 取消由原受理 Pod 直接處理。其他 Pod 查無該 Run 時回 `404 INGESTION_RUN_NOT_FOUND`，與原程序重啟後查無 Run 的行為相同。

查無或已到期的 Run 回 `404 INGESTION_RUN_NOT_FOUND`。Request body 不合 Schema 回 `422 REQUEST_VALIDATION_FAILED`。若呼叫端未收到回應，可向原受理 Pod 查核或用相同的 `run_id` 及 `document_ids` 重送。重送時依該 Run 文件當下的狀態回報，仍為 `cancelled` 時回 `cancelled`，已成功發布時回 `already_finished`。完整請求及混合結果見 [HTTP Mock](../examples/system_config/README.md#runtime-http-examples)。

<a id="src-21-4-文件狀態與一次提交的狀態"></a>
## 文件狀態與一次提交的狀態

<a id="src-21-41-文件級狀態"></a>
### 文件級狀態

**`document_id` 由呼叫端提供。** 入口、狀態、批量取消、存在查詢與 Retire 均使用同一 [文件識別契約](02_data_contracts.md#document-identities)。帶入 URL 時，以 UTF-8 對文件 ID 做 percent-encoding，作為單一路徑區段；Runtime 解碼一次後驗證。首次匯入可帶尚未存在於索引的 ID。整批預檢通過、入列時即建立 Run 與每份文件的 queued 紀錄；Worker 按進度更新 running、最後可知 Module、狀態時間與結果。Run 與逐文件狀態皆從原受理 Pod 查詢。

| 階段 | Runtime 工作紀錄 | 搜尋資料／判斷 |
|---|---|---|
| 入列前整批拒絕 | 不建立新的 Run／工作；HTTP 回錯誤，有可定位的輸入時附 `path` | 不改既有文件；若有舊狀態，不覆寫成這次的新工作 |
| 已入列 | queued | 不代表已產生／寫入 Chunk |
| 執行中 | running，必要時附 Module | 舊版可仍存在，不能以此推算本次完成 |
| 已登記取消 | `cancelled` | 原批次仍可能完成。占用未釋放時同文件仍忙碌 |
| 執行失敗 | failed＋error | 工作失敗紀錄仍可查；不等於必有成功索引 |
| 成功發布 | completed | 才表示本次完整處理成功 |
| Runtime 重啟或 Pod 被替換 | 舊工作紀錄遺失，狀態查詢回 `unknown` | 已寫入的 Chunk 仍可能存在，依檢索資料索引確認 |
| 紀錄已到期或不存在 | unknown | 文件存在性透過實際檢索索引查詢 |


| status | 定義 |
|---|---|
| queued | 已接受，等待執行 |
| running | 正在處理；module 可提供目前邊界 |
| cancelled | 已登記取消。已取得寫入權的原批次若成功發布，可轉為 `completed` |
| completed | 該文件完整處理、替換與索引發布完成；不是剛取得模型回應或只送出索引寫入 |
| failed | 本次匯入已結案為失敗，附可定位錯誤。ES Bulk 等待逾時也標 `failed`。清理可能殘留的 Chunk 時使用該批次的 `write_id` |
| unknown | 沒有可用工作紀錄，或執行結果無法確認；不等於文件不存在／未寫入／失敗 |

查詢應區分「查無紀錄」及「有紀錄但結果未確認」。後者保留已知的 `run_id`、Module 與原因，例如已進入清理階段但清理結果尚未確認。Bulk 回應逾時依 [ES 寫入查核](#es-write-control-record)結案為 `failed`。

狀態物件見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json) 的 `run_document` 與 `document_ingestion_status`。`module` 標示 Local Module 或 Remote operation 的最後可知邊界。

```json
{
  "document_id": "manual-001",
  "run_id": "ing-001",
  "status": "running",
  "module": "embedding",
  "updated_at": "2026-11-05T08:30:00+08:00",
  "error": null
}
```

紀錄到期或查無紀錄的回應範例。

```json
{
  "document_id": "manual-001",
  "run_id": null,
  "status": "unknown",
  "module": null,
  "updated_at": null,
  "error": null
}
```

<a id="src-21-42-run-是一次接收文件是更新單位"></a>
### Run 是一次接收，文件是更新單位

文件狀態查詢以可信的 `(system_id, document_id)` 找出最新收件的 Run。依本機收件順序查找該文件最後受理且仍保留的 Run。每次合法重新提交建立新 Run，各 Run 的狀態按各自的 `run_id` 保存，保留期內皆可查詢。

已接受的工作以 `GET` 查詢，回傳 `200`。Run 依逐文件狀態彙總，對應關係見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json) 的 `ingestion_run_status`。

`partial` 只用於 Run 彙總。單份文件完整處理及索引發布後才標為 `completed`。更新期間的資料可見性見 [Elasticsearch 文件覆寫](#elasticsearch-document-replacement)。

```json
{
  "run_id": "ing-001",
  "status": "partial",
  "config_revision": "C1-example",
  "counts": {"total": 2, "queued": 0, "running": 0, "completed": 1, "cancelled": 0, "failed": 1, "unknown": 0},
  "documents": [
    {"document_id": "manual-001", "status": "completed", "module": null, "updated_at": "2026-11-05T08:31:00+08:00", "error": null},
    {"document_id": "manual-002", "status": "failed", "module": "parsing", "updated_at": "2026-11-05T08:30:30+08:00", "error": {"code": "PARSER_CONTENT_INVALID", "module": "parsing", "message": "內容不符合所選 Parser 的輸入要求。"}}
  ]
}
```

計數以接收的 Document 為單位。計數及查無紀錄時的回應形狀見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json)。呼叫方可用原 `run_id` 重新查詢取消後的結果，Runtime 依最新文件狀態彙總 Run 狀態及各項計數。

<a id="src-21-43-紀錄的保存與重啟"></a>
<a id="ingestion-job-records"></a>
### 工作紀錄、保留與重啟

受理 Pod 在記憶體保存 Queue、占用、Run、逐文件狀態及當次寫入或刪除的清理資訊。這些工作資料不寫入 ES。程序終止時這些資料一併遺失，重啟從空狀態開始。已送到 ES 的資料操作仍可能生效。HTTP 連線中斷但程序繼續執行時，已入列的工作照常執行。

<a id="ingestion-status-retention"></a>
#### 終態紀錄清理

- 每個 Run 從最後一份文件完成本機結案起最多保留三天（259,200 秒）。已回報 `cancelled` 但仍在收尾的文件，完成收尾後才算結案。
- Runtime 初始化記憶體工作紀錄後，每個程序啟動一個背景 Task。依 [Runtime 清理間隔](#src-22-2-已確認的初始預設)等待後執行，清理已到期的 Run、逐文件紀錄及本機查詢對照。前一輪完成後才開始下一輪。Runtime 關閉時停止並等待 Task 結束。
- 查詢及取消只檢查目標紀錄是否到期，到期即視為查無。提交 Ingestion 只檢查本批文件的活躍占用與容量。
- 每個 Pod 最多保留 10,000 份已結案的文件工作紀錄。Run 結案時若超過上限，立即從最早結案的 Run 開始整組回收，直到回到上限內。容量回收與背景清理使用同一套本機紀錄同步機制。活躍工作由 Queue 容量、執行 Deadline、結案及取消管理。三天清理只處理歷史紀錄。
- 到期、程序重啟或切換 Pod 後查無紀錄時，GET Run 及文件工作狀態回既有的 `200` ＋ `unknown`，取消回 `404 INGESTION_RUN_NOT_FOUND`。呼叫方可查實際文件是否存在，或決定是否重新提交完整文件。Runtime 不續跑或補結算舊工作。

<a id="es-runtime-control-index"></a>
#### Elasticsearch System 生命週期控制索引

對使用 Elasticsearch 的 System，在同一部署環境、同一 ES 叢集共用一個控制索引。每個 System 的檢索資料索引按原有生命週期管理。控制紀錄依 System 與索引綁定隔離。多個 Runtime 共用同一 System 的受管索引時，共用該索引綁定的控制紀錄。控制索引保存 System 級的版本、索引世代、管理操作及生命週期協調資訊。

首版控制索引名稱為 `rag-<env>-runtime-control-v1`，如 `rag-builder-runtime-control-v1` 或 `rag-ftest-runtime-control-v1`。`<env>` 使用部署環境的小寫識別，`v1` 是控制紀錄格式版本。各 Runtime 以同一環境識別存取同一叢集時使用相同名稱。

每個 Runtime 在載入使用受管 ES 的 System Config 時，先檢查該環境的控制索引是否存在，並驗證格式版本與必要的 mapping，確認就緒後才開放依賴控制紀錄的操作。

| 檢查結果 | Runtime 行為 |
|---|---|
| 索引已存在且格式相容 | 接回共用索引。 |
| 索引不存在，且部署紀錄可確認是此叢集與環境的首次初始化 | 原子取得一次性的首建資格後，以固定的首版 mapping 建立同名索引。多個 Runtime 同時載入時，其餘等待初始化完成，再重新查核並接回共用索引。 |
| 已運作的環境缺少控制索引、格式不相容，或無法核實索引及部署狀態 | System 的協調操作維持未就緒，回 `503 SYSTEM_STATE_UNKNOWN`。保留狀態供查核，等待部署方確認或恢復原控制資料。 |

控制索引之外的環境層級部署紀錄記錄首建資格和結果。Runtime 確認此叢集與環境已完成初始建立後才開放 System 操作。首建結果不明時先查核先前的建立操作。單一 System 尚未建立檢索索引，或 ES 回報控制索引不存在，都不足以確認環境首次初始化。控制紀錄寫入限已初始化的索引，首次建立走上述流程。檢索索引的 `initialize`／`recover_index` 依 [System 索引生命週期](#system-index-lifecycle) 執行。

<a id="src-21-5-inference"></a>
<a id="inference-api"></a>
## Inference API

<a id="src-21-51-request-與結果"></a>
### Request 與結果

`POST /queries` 使用 [InferenceRequest Schema](../schemas/inference_request.schema.json) 與 [InferenceResponse Schema](../schemas/runtime_http.schema.json#/$defs/inference_response)。有命中、無命中、純外部 Retrieval 及上游失敗的完整回應見 [HTTP JSON 範例](../examples/system_config/README.md#runtime-http-examples)。

```json
{"query": "設備多久需要清潔？", "filters": [{"field": "structdata.department", "operator": "eq", "value": "manufacturing"}], "metadata": {"language": "zh-TW"}, "parameters": {"top_k": 5}}
```

`query` 必填，`filters`／`metadata`／`parameters` 選填，預設 []／{}／{}。Runtime 先確定呼叫可操作的 System，依 Inference Input 宣告驗證參數，並依同一 Config Revision 驗證請求 Filter 的有效欄位、運算子和值。Runtime 合併固定 Filter 與請求 Filter 後，再初始化 QueryContext[] 並執行所選 Component。無效 Filter 回輸入驗證錯誤。`filters` 用於資料篩選，System 選擇及授權由 Runtime 的路由和認證設定決定。見 [資料契約](02_data_contracts.md)。

成功回應的 `contexts` 承載 [QueryContext[]](../schemas/query_context.schema.json)，`config_revision` 與 `index_generation` 記錄該次查詢實際使用的快照。兩值也透過 `X-Config-Revision` 和 `X-Index-Generation` 回傳，已回的 Header 須與 body 一致。純外部 Retrieval 若未使用平台索引，body 的 `index_generation` 為 `null` 且省略對應 Header。Client 忽略未識別的外層欄位。

索引與必要查詢依賴已就緒時，空索引可以正常執行 Inference。首版每次請求的所有必要節點、Query 及搜尋路徑成功後才回 `200`。索引不就緒、服務失敗或逾時依原因回錯誤；首版沒有部分成功回應或自動降級。既有錯誤的 HTTP 映射見 [HTTP 與錯誤](#src-21-6-http狀態與錯誤層次提案)。

| 執行情境 | 回應 |
|---|---|
| Hybrid 的 BM25 成功且向量路徑最終失敗 | 整次回錯誤，標示失敗的 Module。 |
| Multi-Query 中任一必要 Query 最終逾時 | 整次回錯誤。 |
| 設定啟用的 Rerank 最終失敗 | 整次回錯誤。 |
| 各路皆成功，其中一路無命中 | 成功，該路以空候選參與融合。全部無命中時回 `200` 及空候選。 |

<a id="src-21-52-執行與流量"></a>
### 執行與流量

每 System 配置請求頻率、執行併發、等待／執行 Deadline；Runtime 再控制共享資源總量。Builder 可額外限制 User／Workspace 的平台測試配額。共用 Runtime 的限制不能只寫在前端。

D-64：第一版同步查詢額滿直接拒絕，不加短等待 Queue，也不進 Ingestion 的長工作 Queue。初始每 System 5 次／秒、同時 2 個，Runtime 同時 8 個，整體 Deadline 60 秒；數值可調且集中記於 22，由 Admin／部署管理者在 E 的 Runtime 環境設定控制。正式名稱／機器 Schema 與載入方式仍待核定，不把環境流量控制混入 query body 或 D 的搜尋演算法參數。

目前不需要另開 async Query／查詢工作狀態 API，也不增加獨立 Rewrite／Retrieval／Rerank 測試端點；後者需有明確需求再討論，既有 UIB-007／008 仍未核定。

<a id="src-21-6-http狀態與錯誤層次提案"></a>
<a id="runtime-http-errors"></a>
## HTTP 錯誤格式與狀態碼

<a id="src-21-61-已確認的錯誤核心格式d-64"></a>
HTTP 錯誤物件見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json) 的 `error_response` 與 `document_busy_error_response`。`module` 用 Config 的模組鍵，例如 `embedding`，無對應模組時為 `null`。`path` 用相對於當次 Request body 的 JSON Pointer，如 `/config/pipelines/ingestion/embedding/parameters/mappings/0/source_field`，無定位時省略。輸入驗證回第一個可定位的問題。`POST /ingestions` 的 `409 DOCUMENT_BUSY` 加上[整批文件衝突清單](#ingestion-document-busy)。Run／文件狀態的 `error` 直接放內層 `Error`。Builder 依 `code` 作分流，`message` 呈現細節。

| HTTP | W1 `code` 與處理 |
|---|---|
| `400`／`415` | `INVALID_JSON`／`UNSUPPORTED_MEDIA_TYPE`。修正請求格式。 |
| `401`／`403` | `UNAUTHENTICATED`／`FORBIDDEN`。由 Backend 檢查連線認證或存取權限。 |
| `404` | `SYSTEM_NOT_FOUND`。管理 System GET 用於回報無載入且無可確認的既有受管索引綁定；業務 API 依該路由的 System 作用範圍判定。取消時查無或已到期的 Run 回 `INGESTION_RUN_NOT_FOUND`。 |
| `409` | `STALE_CATALOG` 時重新取 Catalog。`STALE_CONTEXT` 時重驗 Config。`REVISION_CONFLICT` 時用 GET 確認生效版本。`REBUILD_CONFIRMATION_REQUIRED` 時顯示影響與重建確認。 |
| `409` | `SYSTEM_STATE_CONFLICT` 時用 System GET 確認當前狀態，再預檢合適的操作。`IDEMPOTENCY_CONFLICT` 時核對已保存的原請求及操作鍵。 |
| `409` | `SYSTEM_BUSY`／`DOCUMENT_BUSY` → 等工作或管理操作收尾，若文件關聯 Run 已知則附 `error.run_id`。批量匯入遇到 `DOCUMENT_BUSY` 時附 `error.conflicts`。`INDEX_OWNERSHIP_UNVERIFIED` 時顯示歸屬核對失敗並保留資料。`INDEX_CONFLICT` 時顯示管理請求中的預期索引世代已變更，或回報其他相容性問題。`PIPELINE_NOT_ENABLED` 表示業務流程未載入，`PIPELINE_OPERATION_UNSUPPORTED` 表示管理操作不適用於所選流程。 |
| `413`／`422` | `BODY_TOO_LARGE`／`REQUEST_VALIDATION_FAILED`、`CONFIG_VALIDATION_FAILED`、`INVALID_CURSOR`。修正大小、欄位或分頁請求。 |
| `429` | `RATE_LIMITED` → 按 `Retry-After` 等候（整數秒，有可用時間時回傳）。 |
| `500` | `INTERNAL_ERROR`。 |
| `501` | `OPERATION_UNSUPPORTED`。 |
| `502` | `UPSTREAM_ERROR`。 |
| `503` | `RUNTIME_NOT_READY`、`RUNTIME_CAPACITY_EXHAUSTED`、`INDEX_NOT_READY`、`PIPELINE_NOT_READY`、`SYSTEM_STATE_UNKNOWN`。 |
| `504` | `DEADLINE_EXCEEDED`。 |

Builder 顯示錯誤原因。管理操作結果不明時先同步 System 狀態。

例如匯入請求缺少第一筆文件的 ID 時回 `422`。

```json
{"error": {"code": "REQUEST_VALIDATION_FAILED", "message": "document_id 為必填。", "module": null, "path": "/documents/0/document_id"}}
```

`202` 收件後發生的文件執行錯誤仍可用狀態 API 查詢。GET 回 `200`，文件狀態為 `failed` 並帶錯誤。回應一律省略 Stack 與 Secret。

HTTP 語意參考 [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3) 與 [RFC 6585](https://www.rfc-editor.org/rfc/rfc6585.html#section-4)。

<a id="ingestion-document-busy"></a>
### Ingestion 文件占用衝突

`POST /ingestions` 回 `409 DOCUMENT_BUSY` 時，`error.conflicts` 必須是非空陣列，依 `documents` 請求順序列出受理 Pod 同一次本機檢查中所有仍被占用的文件。每筆包含 `document_id`、當下的文件工作 `status`，以及已知時的 `run_id`。若占用來自 `retire`，`status` 為 `null`，省略 `run_id`。仍持有占用的 `cancelled` 工作也會列入。

`error.path` 指向第一筆衝突文件的 `document_id`，`error.run_id` 在能確認第一筆所屬 Run 時回傳。Builder 用 `error.conflicts` 顯示整批衝突；這次拒絕不入列任何文件，也不新增 Run。見[批量占用衝突範例](../examples/system_config/README.md#runtime-http-examples)。

<a id="src-21-7-非必備端點與本輪待討論"></a>
<a id="src-21-71-首期不納入後續能力"></a>
<a id="src-21-72-決策狀態與剩餘討論"></a>
[Runtime API 的待決範圍與驗收](08_plan_and_decisions.md#runtime-api-decisions)

<a id="src-21-8-api-d0506-的具體情境"></a>
## 執行模式、覆寫與認證

<a id="src-21-81-builder-共用模式與獨立部署模式d-61d-62"></a>
### Builder 共用模式與獨立部署模式

使用者的 service 指 **API server 應用程式／程序，不是 Pod 或 Kubernetes Service 路由資源**。

| 環境 | API service 啟動與 Config | 請求／更新 |
|---|---|---|
| Builder DEV | 每個 Pod 運行一個 Runtime，可先載入零組 Config。同一 Runtime 可承載一個 System 的兩條流程。 | Builder 依 `runtime_ref` 及 `pipeline` 部署和補載。每次業務請求固定該流程的一份生效快照。 |
| FTEST／ENT | 使用同一 Runtime Image，Pod 啟動時載入單組 Config 與部署設定選定的流程，管理 HTTP 關閉。 | 業務請求由啟動設定選定 System，Config 更新透過重啟／重新部署。 |

FTEST／ENT 獨立部署可省略 `runtime_ref`。如需部署標籤，同一部署的 Pod 可共用此值。System 與索引由啟動的 Config 及其索引綁定決定。若部署共用受管 ES 索引，依 [Pod 內寫入分流](#pod-local-ingestion-control)及 [System 排空條件](#system-ingestion-drain)處理。

Builder 儲存許多 UI Config 不等於建立等量 API service／Pod。Runtime 依已驗證快照準備必要 Component／資源，各 System 的 Config、Binding、索引及工作作用範圍分開；共用 Flow 不要求共用所有實例。配置解析快取、實例／資源預載與回收、Namespace 或服務池分組的精確機制待 Q-020。Library 不直接連 Builder DB；由 Backend 經可信邊界管理 Config 與目標 Runtime 對應。

「不綁單份 Config」不代表程式可任意熱替換：可用 Local Components／Adapters 仍由所選 Runtime Image／Registry 版本決定。新 Component 程式依既定 Image 發布流程；不同 Config 在既有能力內組裝 System。

Builder 下發新版時，依 [System 管理](#src-07-4-systemrevision-與-engine-生命週期)判斷忙碌、索引相容性及切換方式。Runtime 重啟時各 System 從空的工作狀態開始。Builder 可重新下發 Config，通過相容性檢查後接回 ES 索引。

兩條流程可在同一 Pod 啟用，也可拆成 Ingestion 與 Inference Pod 並連同一受管 ES 索引。多副本寫入遵循 [Pod 內文件占用與派工](#pod-local-ingestion-control)的範圍與分流條件。外部 API、ES 及其他依賴以環境綁定提供。

<a id="src-21-82-remote-寫入可能成功但-runtime-timeout"></a>
### 索引寫入逾時

Runtime 等待 ES Bulk 回應逾時時，將該文件結案為 `failed`，已登記取消的文件維持 `cancelled`。解除本次占用後，呼叫方可以再次匯入。ES 可能已寫入部分或全部 Chunk，依 [Elasticsearch 文件覆寫](#elasticsearch-document-replacement) 用原批次的 `write_id` 定位殘留。

<a id="elasticsearch-document-replacement"></a>
### Elasticsearch 文件覆寫

本節定義同一個 System 內以 `document_id` 為單位的 Elasticsearch 更新。一批 Ingestion 中的每份文件各自處理，受理時在 Pod 內檢查占用。整個 System 的索引重建依 [索引生命週期](#system-index-lifecycle) 處理。

Elasticsearch 索引存取層為每次文件寫入產生一個 `write_id`，例如 UUID。同一份文件此次輸出的全部 Chunk 共用此值。將它存入每筆 ES Chunk 的內部欄位（mapping 為 `keyword`）。ES `_id` 對 `[document_id, write_id, data_id]` 依 RFC 8785 序列化後，以 UTF-8 計算 SHA-256 並輸出小寫十六進位摘要，讓舊批次和新批次在同一索引內並存。`source_revision` 供來源追溯。相同 `document_id` 的新提交依既有覆寫規則執行，即使 `source_revision` 相同而內容有變。`write_id` 用於精確定位寫入批次，時間可供診斷。

<a id="es-write-control-record"></a>
#### ES 寫入與清理

1. 準備新版 Chunk，查詢這份文件目前可見的舊批次並固定清理範圍。在記憶體保留目標實體索引、索引世代、本次 `write_id`、預期 Chunk ID 及舊批次範圍。首次 Bulk 前，Worker 在本機核對原 Run、文件、占用權杖、索引世代與狀態。
2. Bulk 有回應時逐筆檢查。新版完整可搜尋後才清理指定的舊批次，確認清理後將文件標為 `completed`。若新版確認寫入失敗，只清理本次 `write_id` 的 Chunk。若清舊結果在單文件 Deadline 內仍無法確認，結案為 `unknown`，已登記取消則保留 `cancelled`。
3. ES Bulk 回應逾時時停止本次後續寫入與清舊，結案為 `failed`，錯誤為 `ES_BULK_TIMEOUT`。已登記取消時維持 `cancelled`。釋放占用後可手動重送。本機若嘗試清理逾時批次，只按其實體索引、`document_id` 與原 `write_id` 清理。晚到回應不得改變已結案的 Run 或新工作的占用。
4. Runtime 終止後丟棄原寫入和清理進度。下次匯入按當時可見的 Chunk 正常覆寫。舊請求若晚到，可能留下多批 Chunk；持續異常時查實際索引。

驗收包含舊版 10 筆、新版 6 筆成功後只剩新 6 筆，以及新版有一筆失敗時只清理本批 Chunk。另驗收 Bulk 逾時後可重匯，舊回應及清理限原批次。

<a id="src-21-83-已確認不加平台-query-讀寫鎖"></a>
### 已確認：不加平台 Query 讀寫鎖

D-60：使用者確認不採「寫入時禁止查詢」的共享讀寫鎖，讀寫各自執行；不為更新窗口加查詢等待、全域停讀、版本快照或分散式鎖。

接受的行為是：更新／刪除途中發出的 Query，可能讀到舊資料、新資料或短暫的新舊混合；已取得候選的 Query 也可能在 retire 完成後才回應。平台不保證一次 Query 看到單一文件／整個索引的原子快照，也不因正在寫入就排入等待鎖的隊列。實際後端的原生可見性／refresh／錯誤行為照其實作，不假造平台強一致保證。

這不撤銷已確認的 **同文件重複 Ingestion 忙碌拒絕**，它是寫入對寫入的排程規則，與查詢讀寫鎖不同。Ingestion 的成功／失敗仍逐文件記錄：沒有完整執行成功不得標 completed，已知失敗不得偽裝成功；清理與崩潰後恢復仍需 backend 定義。不再把「成功才發布」解讀成「新資料處理完成前，所有讀取都看不到任何變更」。

索引尚未建立／資源未就緒、Rate limit 或真實後端失敗仍按原 API 回應；正在 Ingestion 這件事本身不作為封鎖 Query 的理由。

<a id="src-21-84-已確認暫採單一-basic-帳號builder-登入延後"></a>
### 已確認暫採單一 Basic 帳號；Builder 登入延後

D-60：Runtime API 暫採 **HTTP Basic Auth（帳號／密碼）**，預設一組帳密可操作該 API service 對外提供的所有 API，包括 Ingestion、取消匯入工作、Query、Run／文件狀態、文件存在／ID 清單、retire 與對外 Health。此處限定在該 service 提供的 System／資料範圍，不代表同組密碼跨全部環境／其他服務硬編碼共用。

第一版不增加多帳號、角色、逐 API 權限或使用者 ACL 管理；同一組帳密通過驗證即可執行該服務提供的全部 API。服務端仍須使用正確 System 路由，不能把任意外部 Header 當作載入／選擇未提供 System 的授權。

採 HTTPS／TLS，帳密以部署環境 Secret 引用提供，不寫入 D／文件 metadata 或原始碼。具體驗證位置、Secret 包裝及內部 Probe 如何帶認證／探測仍待部署設計；不自行新增匿名對外 API 例外。標準依據：[RFC 7617](https://www.rfc-editor.org/rfc/rfc7617.html)。

Builder 的使用者登入方式之後再討論；不因 Runtime Basic 決策而替 Builder 加上登入流程，也不新增 OAuth／SSO 服務。User Remote API／模型／DB 的憑證是各自服務連線，不預設沿用 Runtime 對外帳密。

<a id="src-21-85-可信-system-路由與-s1-的意思d-64"></a>
### 可信 System 路由

S1 是 system_id 示意：由 Builder Backend 建立並維護的穩定 Retrieval System 識別碼，在同一 Builder 管理範圍內唯一。System 改名、更新 Config 或跨環境匯出時仍沿用該 ID。格式及產生方式見 [Runtime 識別規格](#runtime-index-ownership)。

| 呼叫方向 | 規劃路由示例 | System／Config 選擇 |
|---|---|---|
| Builder UI → Backend | POST /api/systems/S1/queries | Backend 經可信管理關係選定目標 System；Builder 登入具體方案仍延後 |
| Backend → 共用 Runtime | POST /internal/systems/S1/v1/queries | 只供可信 Backend 存取且驗證認證；Runtime 查已註冊 S1 的有效配置，固定快照後執行 |
| 呼叫端 → FTEST／ENT | POST /v1/queries | 單 System Runtime 已載入配置，業務請求不需再帶 S1 |

業務 API 依同一內部前綴選 System，Request／Response 的業務語意不複製兩套；Health 仍是 service 級 /health/live／ready，不逐 System 複製。Builder 路由前綴為 /api/systems/{system_id}，共用 Runtime 為 /internal/systems/{system_id}/v1。Config 套用格式見 [System 生命週期 API](#system-lifecycle-api)。Builder 自有 CRUD 另定。

路徑識別不能單獨充當授權；內部路由須受可信網路／Backend 存取與認證保護，不依任意外部 Header 載入配置。具體部署保護、Secret／Probe 接法仍待核定，Runtime 暫採單一 Basic 帳號的政策不變。工作狀態、文件管理與 Query 都遵守相同 System 作用範圍，不在業務 body 加入整份 Config／任意索引位置。Library 不讀 Builder DB。

<a id="src-21-9-文件資料查詢與直接刪除"></a>
## 文件資料查詢與直接刪除

<a id="src-21-91-資料來源與工作狀態不同"></a>
### 資料來源與工作狀態不同

這裡的 DB 是該 System 綁定的文件資料／索引後端，可能是 Elasticsearch、Local Memory、MongoDB 配本地搜尋或支援協定的 Remote Service；不要求為了查 ID 新增一個中央 DB。查詢反映目前後端可見的文件資料；若正有更新，依 D-60 可看到更新中的結果，不用工作 completed 當作讀取閘門，也不把「有資料」當成這次工作成功。

預設儲存單位是 Chunk，透過其 document_id 判斷存在與去重列出文件，不要求額外長期保存解析階段的 Document。實際後端可用適當 metadata／catalog 加速，但必須與資料一致，不能以 Runtime 的工作紀錄當成唯一依據。API-D07 保留實體布局與查詢策略的實作選擇。

| 問題 | 查詢位置 | Runtime 重啟後 |
|---|---|---|
| 最近一次 Ingestion 是否成功／失敗 | 受理 Pod 記憶體 | 舊紀錄遺失，狀態回 `unknown` |
| 文件目前是否存在／有哪些 ID | System 實際文件儲存／索引 | ES／MongoDB 等持久資料仍可在後端就緒後查；Local Memory 資料若已遺失則清單為空 |
| retire 是否刪掉文件資料 | 直接刪除對應儲存、索引與本地搜尋副本 | 不能只清記憶體索引而保留供重建資料，否則可能重啟復活 |

「更新失敗但舊版仍存在」可以同時得到 ingestion-status=failed、exists=true；「成功後已 retire」也可以同時是歷史工作 completed、exists=false。這些不是矛盾，不把狀態改成 retired 或抹掉成功紀錄來代替資料查詢。工作歷史依 [紀錄保留政策](#ingestion-job-records) 清理。

<a id="src-21-92-存在查詢提案"></a>
### 存在查詢

GET /v1/documents/manual-001/exists

```json
{"document_id": "manual-001", "exists": true}
```

不存在時回 200 並回 exists=false。後端無法連線、尚未初始化或不支援操作時，應回可辨識錯誤，不回 false 偽裝不存在。這支 API 不回原始內容／Chunk／向量，也不表示最近一次工作成功。

<a id="src-21-93-文件摘要清單d-65-已確認核心"></a>
### 文件摘要清單

GET /v1/documents?limit=100&cursor=...

```json
{
  "documents": [
    {"document_id": "manual-001", "source_revisions": ["v2"]},
    {"document_id": "manual-002", "source_revisions": ["v1", "v2"]},
    {"document_id": "manual-003", "source_revisions": []}
  ],
  "next_cursor": null
}
```

D-65 的文件清單採 `documents[]` 與 `next_cursor`。直接查該 System 實際保存的 Chunk，以 `document_id` 去重並分頁。每筆 `source_revisions` 為實際 Chunk 所帶非空 `source_revision` 字串的去重集合。省略、`""` 與 `null` 略過，沒有非空版本字串的文件仍列出並回 `[]`。更新中或部分寫入失敗時可能有多版。清單反映當下儲存狀態，不依 Run 或文件工作紀錄推定最新成功版本。

W1 清單每頁預設 100／上限 1,000、依 document_id 升冪、Cursor 綁定 System，分頁期間可反映更新。實作細節與進階分頁需求留 API-D07。

分頁只代表清單分批傳回。例如 250 份不同文件，每頁取 100 個 ID，可依 next_cursor 取得第 1 批 100、第 2 批 100、第 3 批 50；最後 next_cursor=null。每個分頁項目是一份文件摘要，包含該文件目前可見的來源版本；不是每個版本各占一筆，也不以 Chunk 數計算 limit。Client 可讀完所有頁取得當時可遍歷的清單。

後端實作可依布局選擇：ES 以可精確聚合的 document_id 欄位作去重，候選是 composite aggregation，使用回傳 after_key 接續頁面；不能只取前 N 個 Chunk hits 去重，就當作已列出所有文件；source_revisions 也不能只取任意首筆或被截斷的版本子聚合。Local 可由 Chunk store 的 document_id／source_revision 去重集合或一致維護的文件對照取得，MongoDB 模式使用實際保存的文件資料；不查 Runtime 工作表，也不需要為這個 API 再建中央目錄 DB。

ES 分頁聚合依據：[Composite aggregation](https://www.elastic.co/docs/reference/aggregations/search-aggregations-bucket-composite-aggregation)。具體 Mapping、排序、資料更新中的頁面一致性與效能仍由 Artifact／backend 驗證，不把方案寫成已實作。

<a id="src-21-94-retire-直接刪除"></a>
### Retire 直接刪除

Retire 刪除該 System／document_id 對應的 Chunk、vectors、全文／向量索引，以及供恢復／重建使用的持久儲存與搜尋副本。具體儲存布局由 Artifact／backend 決定，不因 ID 命名相同就刪除其他 System 的文件，也不要求刪除使用者傳入 URI 所指的外部來源檔案。

D-64 已確認同步完成並回 200，以 `result` 區分確實刪除和確認原本不存在。同文件在受理 Pod 仍有有效占用時回 `409 DOCUMENT_BUSY`，並依同一本機占用規則排斥匯入。Retire 限本機操作期間追蹤刪除進度。逾時或結果不明時回對應錯誤，單次操作結束就釋放占用。原 ES 請求晚到時，仍可能改變文件的存在狀態。回應核心如下。

```json
{"document_id": "manual-001", "result": "deleted"}
```

```json
{"document_id": "manual-001", "result": "not_found"}
```

not_found 只在已確認目標範圍沒有資料時使用，不能把 DB／索引未就緒、連線失敗或不支援操作當成不存在。後端 timeout、部分刪除或結果未確認時回對應錯誤，不回成功。HTTP 錯誤碼見 [HTTP 錯誤格式](#runtime-http-errors)，Remote 查核、重試與清理細節由 API-D03 追蹤。多個儲存／搜尋副本的清除以完整目標為準，不只刪一個 Chunk 就回 deleted。

刪除完成後新發起的查詢／exists／ID 清單應反映刪除結果；先前已取得候選的在途 Query 仍可能回傳舊資料，依 D-60 不加鎖或回收其候選。exists 應為 false，ID 清單不再列出該 ID。此處沒有 soft delete 標記或 restore；若需要再次使用，重新提交文件 Ingestion。Retire 不透過改寫 metadata／Query filters 來假裝完成實際刪除。

<a id="src-21-95-localremote-的能力配套"></a>
### Local／Remote 的能力配套

Document 管理是索引／儲存管理能力，不新增 Pipeline Module。平台可直接管理後端時由對應 storage／index adapter 提供操作；外部 Retrieval 的資料空間由外部服務維運。

平台只對受管理資料提供文件查詢、清單及刪除。能力不可用時明確回報，查詢就緒與文件管理能力分別驗證。

<a id="runtime-config-sources"></a>
## 設定來源與保存位置

| 設定 | 作用範圍 | 載入與保存 |
|---|---|---|
| System Config | 個別 System 的 Pipeline、Component、Variable 與 Secret。以 `system_id` 和 `config_revision` 辨識，使用同一份 [System Config Schema](../schemas/system_config.draft.schema.json)。 | DEV 由 Builder 保存發布快照與部署紀錄，經管理 API 下發，重啟後由 Builder 補載。獨立部署由部署方隨 Bundle 提供快照，Runtime 每次啟動時讀取。兩個入口都把已載入的快照保存在 Runtime 記憶體。 |
| Runtime 程序設定 | 整個 Runtime 程序共用的 Queue 容量、Deadline、工作紀錄保留與清理間隔等。 | Runtime 啟動時先讀取部署設定，對省略的欄位套用 Runtime 預設值，再用有效設定初始化 Queue 及背景 Task。有效值在程序記憶體保存，與 System Config Revision 分開。 |

[Builder 部署紀錄](drafts/builder_system_deployment_mongodb.md) · [獨立啟動](#src-07-93-獨立啟動) · [Runtime 程序預設](#src-22-2-已確認的初始預設)

<a id="src-22-1-範圍與管理方式"></a>
## Runtime 設定：範圍與管理方式

本文件集中記錄 Runtime 的接收大小、Queue、併發、Rate、Deadline 及工作狀態保存參數。使用者已確認前輪建議的預設與做法，並要求有固定位置整理可調參數；下表為初始開發／測試預設，不代表已量測的正式容量或已實作設定功能。

- **設定歸屬 E：Runtime 環境／資源設定。**與 D 的演算法、Component 選用、Chunk 大小及搜尋 Top N 分開；後者仍見 資料契約手冊／各 Component Config Schema，不在此重複列出。
- **Builder DEV**：Admin／平台部署管理者提供預設與限制，Runtime 在後端執行控制。一般 Builder User 不透過每次 Ingestion／Query body 覆寫；不因本文件新增 Admin 設定頁。
- **FTEST／ENT**：部署管理者提供同一套 Runtime 設定，可以調整上限；使用相同實作，無須連回 Builder DB。
- 表中的參數路徑是文件用候選名稱。正式檔案名稱、JSON Schema／環境變數映射、載入／重載方式與 OpenAPI 仍待實作規格核定；不因此宣稱熱更新或零停機。若套用方式需重啟，依各後端的索引接回規則處理。
- Runtime 總量與每 System 限制同時生效，不把每 System 上限乘以 System 數量當成總容量；個別 System 差異化覆寫、User／Workspace 額外配額及公平排程另案。

<a id="src-22-2-已確認的初始預設"></a>
## Runtime 設定：已確認的初始預設

1 MiB＝1,048,576 bytes；大小以 bytes 計算，不以中文字數或 Base64 解碼前後混用。

| 候選參數路徑 | 調整內容／單位 | 初始預設 | 作用範圍 | 執行位置／語意 |
|---|---|---:|---|---|
| request.ingestion.max_documents | 每次提交文件數／份 | 100 | 單次 Ingestion Request | 對批次物件的非空 documents 計數；不是 Unit／Chunk 數，超限整批拒絕 |
| request.max_body_bytes | JSON HTTP body 大小／bytes | 20,971,520（20 MiB） | 單次 Runtime 業務 Request | 計入 JSON 與 Base64 編碼內容；HTTP 入口限制，不先接受後才當大小合格 |
| sources.max_file_bytes | URI／Base64 單份檔案大小／bytes | 10,485,760（10 MiB） | 每份來源檔案 | 以下載／解碼後內容計算；SDK resolver／相容 Component 限制。已超過此值的遠端來源可在 Worker 取得時失敗，不承諾 202 前下載完所有檔案 |
| ingestion.queue.max_waiting_per_system | 等待文件數／份 | 100 | 每 Pod 內每 System | 只計 queued；執行中受 concurrency 控制，整批接收須一致預留容量 |
| ingestion.queue.max_waiting_total | 等待文件總數／份 | 500 | 整個 Runtime 程序 | 共用 Queue 容量，不是每 System 都額外取得 500 份 |
| ingestion.max_concurrency_per_system | 同時執行文件數／份 | 1 | 每 Pod 內每 System | 不同文件可提高並行；同 document_id 仍有有效占用時拒絕重送 |
| ingestion.max_concurrency_total | 同時執行文件總數／份 | 2 | 整個 Runtime 程序 | 與每 System 上限共同控制；Worker 是排程概念，不要求新 Pod |
| ingestion.document_timeout_seconds | 單文件處理 Deadline／秒 | 600 | 每份已開始執行的文件 | 由 Worker 開始處理起計算；排隊等待不算入本值。逾時不等於 Remote 寫入已停止，未知結果依 API-D05 |
| inference.rate_limit_per_system_rps | 請求速率／次每秒 | 5 | 每 System | 在 Runtime 接收入口執行；具體計數／突發算法待實作，不新增未確認的 burst 參數 |
| inference.max_concurrency_per_system | 同時執行 Query 數／個 | 2 | 每 System | 同步查詢額滿直接拒絕，不進 Ingestion 的長工作 Queue |
| inference.max_concurrency_total | 同時執行 Query 總數／個 | 8 | 整個 Runtime 程序 | 各 System 共用總量，不以所有個別上限之和代替 |
| inference.timeout_seconds | 同步 Query Deadline／秒 | 60 | 單次 Query | 包含所選 Query Transformation／Retrieval／Fusion／Rerank 的整體執行；上游逾時與失敗不可偽裝成功 |
| status.retention_seconds | 已結案 Run 的紀錄保留時間／秒 | 259,200（3 天） | 受理 Pod 記憶體 | 見 [終態紀錄清理](#ingestion-status-retention) |
| status.max_terminal_documents | 可回收終態文件紀錄上限／份 | 10,000 | 整個 Runtime 程序 | 回收順序見 [終態紀錄清理](#ingestion-status-retention) |
| status.cleanup_interval_seconds | 終態 Run 的背景清理間隔／秒 | 3,600（1 小時） | 整個 Runtime 程序 | 首版使用程序預設值。此路徑保留作部署覆寫的候選名稱。見 [終態紀錄清理](#ingestion-status-retention) |

數值須為有效正值；份數、bytes、併發數及紀錄數為正整數。每 System 的 Queue／併發上限不得超過對應 Runtime 總上限。完整驗證錯誤、設定格式與套用接口留 Q-002／Q-017／Q-019，不把候選路徑當成已發布機器 Schema。

HTTP body、檔案及文件數限制各自生效。例如單個 Base64 檔案解碼後低於 10 MiB，不代表多份檔案合計一定低於 20 MiB Request 上限；JSON content 仍受 body 限制，Parser 可另宣告更嚴格內容限制。

<a id="src-22-3-容量失敗與保存行為"></a>
## Runtime 設定：容量、失敗與保存行為

- 接收時先做整批快速預檢、同文件忙碌檢查及容量預留，再建立 Run／queued 狀態並回 202。不做部分入列；來源取得、昂貴 Parsing、Embedding／Indexing 仍由 Worker 執行。
- 每 System 配額／Rate 額滿與 Runtime 整體無容量要可區分；21 的 HTTP／錯誤碼表仍需完整 OpenAPI 對齊，不因本表凍結所有錯誤 code。
- Inference 使用同步入口，額滿直接拒絕，首期不新增短等待 Queue 或 async Query 工作 API。
- Run 歷史紀錄依 [終態紀錄清理](#ingestion-status-retention)回收。Runtime 重啟後工作紀錄與占用從空開始。
- 調整併發須驗證 Component、Client 與索引的安全性。占用、排隊及執行容量按 [Pod 內文件占用與派工](#pod-local-ingestion-control)管理。

<a id="src-22-4-文件摘要與分頁參數"></a>
## Runtime 設定：文件摘要與分頁參數

W1 的預設筆數、上限、排序與 Cursor 行為見 [資料生命週期 API](#data-lifecycle-api)與[文件摘要清單](#src-21-93-文件摘要清單d-65-已確認核心)。Runtime 控制參數的正式名稱與載入方式見[環境控制待決](08_plan_and_decisions.md#runtime-api-decisions)。

<a id="src-22-5-文件維護與驗收待辦"></a>
## Runtime 設定：文件維護與驗收待辦

之後新增／修改 Runtime 控制參數，需在本表記錄名稱、單位、預設、作用範圍與執行位置，並同步環境設定 Schema、驗證及部署說明；目前尚未交付該機器 Schema／實作。模型／HTTP Client 的逐次 timeout、重試及檔案暫存保存規則若另行定案，再納入對應表，不把它們假裝已由整體 Deadline 完整決定。

實作驗收至少覆蓋：文件數／body／來源大小邊界、整批容量預留、每 System 與全域限制同時生效、Query 額滿拒絕、處理逾時、無新請求時背景 Task 仍會清理到期紀錄、查詢即時判定到期、Run 結案時立即執行容量回收、關閉 Runtime 時停止清理 Task、清理不觸碰活躍占用、重啟後查無舊 Run，以及 Builder DEV／FTEST／ENT 使用相同控制。這是未來驗收要求，不是已通過的 Runtime 測試。

<a id="src-07-6-非同步工作與一致性"></a>
## 排程、同程序 Memory 與一致性限制

D-56 已確認：Builder DEV 與 FTEST／ENT 共用 Runtime 工作控制，Library 執行流程；Builder 上傳與直接呼叫 API 走同一 Queue，不再重複排一次。每 Pod 內每 System 的文件執行併發可配置、預設 1；Runtime 再設總量，Inference 有頻率／併發／Deadline。D-64 已確認初始預設與管理方式：E 的 Runtime 環境設定，由 Admin／部署管理者控制，不由每次文件／Query 任意覆寫；完整可調項、單位與作用範圍集中見 22，正式參數路徑／機器 Schema 與載入方式仍待核定。

Batch 逐文件處理。併發 1 時依序，併發 2 時不同文件可同時處理。相同 `(system_id, document_id)` 在受理 Pod 有有效占用時拒絕再次提交。提高併發須驗證 Component、Client 與共享索引，Query 沿用 D-60 的讀寫併行規則。

每份文件完整替換。ES 的寫入、逾時重匯及清理依 [Elasticsearch 文件覆寫](#elasticsearch-document-replacement)。Runtime 重啟丟棄工作及清理進度，既有索引可依相容性接回。

Local Search 屬後續部署範圍。其設計採同程序／單副本，Memory 索引由同一程序內的兩條流程共用。首版部署和驗收採受管 ES。

尚待 Q-008～Q-010／Q-015／Q-017／Q-019：

- Run counts、HTTP 錯誤與文件管理的 W1 格式依本手冊。後端的清理、分頁與部署整合依 API-D03／API-D07 驗收。
- ES 文件覆寫順序已定，仍待驗證清理失敗、未知結果查核及崩潰後殘留處理。其他後端的寫入與搜尋可見性另議。
- 固定快照、System 切版／卸載及持久索引相容規則見 [System 管理](#src-07-4-systemrevision-與-engine-生命週期)。一般寫入與 Query 依 D-60 併行，未知寫入與失敗清理仍依 API-D05 追蹤。
- ES Bulk 回應逾時可結案後重匯，清理限原 `write_id`。等待清舊結果、Retire 的查核、殘留清理與告警細節仍需整合驗收。
- Queue／並行／Rate／Deadline／紀錄保留初始值已依 D-64 記於Runtime 控制手冊；尚待正式設定 Schema／載入方式、以及 ES 寫入與逾時清理的整合驗收。

方向已確認不表示提交機制已實作；詳細盤點與待決子項見 Runtime API／部署。

<a id="pod-local-ingestion-control"></a>
### Pod 內文件占用與派工

每個 Runtime Pod 以記憶體保存 `(system_id, document_id)` 的活躍占用、Queue 及容量。同一 Pod 的 HTTP Handler 與 Worker 共享同步機制。Run 收件、文件狀態、批次寫入進度及歷史紀錄也由受理 Pod 在記憶體保存。

| 階段 | 執行方式 |
|---|---|
| 預檢與入列 | 通過輸入預檢後，在同一個本機臨界區檢查 System 入口、整批文件占用及容量。若有占用，整批回 `409 DOCUMENT_BUSY` 並列出全部[本機衝突](#ingestion-document-busy)。容量不足回 `503 RUNTIME_CAPACITY_EXHAUSTED`。通過才一起預留、建立 Run 及入列，再回 `202`。 |
| 領取與寫入 | 受理 Pod 的 Worker 取得執行名額時，核對原 Run 及文件的本機占用權杖，原子轉成執行中。同一個本機同步機制也管[取消](#ingestion-cancel-api)與首次索引寫入。 |
| 結算與釋放 | 更新本機文件狀態，由持有同一占用權杖的工作釋放占用及名額。首次寫入前取消可釋放文件占用，已開始執行的 Worker 仍計入併發至實際停止。Retire 使用同一占用鍵，結束當次操作後釋放。寫入逾時依[寫入規則](#es-write-control-record)結案。 |

排隊與執行上限各 Pod 獨立計算。仍在查核或執行 Retire 的工作也須計入本機總量，避免未結算工作無界累積。

不同 Pod 可各自受理同一 `(system_id, document_id)`，並行匯入可能讓同一文件留下多個批次，Retire 後亦可能因另一 Pod 的寫入而再出現。需要避免上述競爭的 System，首版將 Ingestion 與 Retire 集中路由到同一個寫入 Pod；Inference 可獨立擴展。切換寫入 Pod 前先排空舊入口。共用索引的版本與管理操作遵循 [System 排空條件](#system-ingestion-drain)。跨 Pod 文件鎖列入 [Todo Enhance](todo_enhance.md)。

<a id="src-07-7-local-search-恢復與儲存"></a>
## Local Search 恢復與儲存

本節保留 Local Search 的後續設計。首版 DEV／FTEST／ENT 部署與驗收採受管 ES。

| 模式 | 重啟 | 正式要求 |
|---|---|---|
| Memory | Chunk／向量／搜尋結構遺失 | 回需要 Ingestion；不回示意檢索結果 |
| MongoDB | 讀保存的 Chunk／vectors／Manifest 重建 | 驗證 Config／Profile／資料版本，完成前不提供不完整索引 |
| ES | 檢查既有 Index 的歸屬、指紋、mapping 與可用性 | 相容時接回。DEV 依[索引生命週期](#system-index-lifecycle)區分首次初始化與使用者確認後的同版本恢復。獨立部署的索引建立策略見 [Q-021](08_plan_and_decisions.md#q-021)。衝突與暫時不可用分開回報。 |

MongoDB 保存不等於跨 Pod 索引同步。重建失敗、DB 中斷、Profile 不符、損壞資料及大資料量啟動時間見 Q-012／Q-027。原始檔／解析結果 若未保留，不保證可自動重新切分／Embedding。

<a id="src-07-8-evaluation-與-ai-助手服務"></a>
## Evaluation 與 AI 助手服務

另有待確認的 Query Rewrite 單模組測試提案，見 [Builder UI／Backlog](08_plan_and_decisions.md#rewrite-test-proposal)／UI Backlog手冊 UIB-007：若採用，Backend 以請求草稿呼叫相同 Engine 模組／LLM Adapter，測試不依賴已保存 System 或索引。認證、服務引用與逾時規則仍需核定；接口精確路徑／Envelope 留 Q-019，不新增已凍結的公開 Runtime API。M2 可先由 SDK 驗證模組，Builder 入口屬 M5；Mock 與真實呼叫分開驗收。

Evaluation Runner 於 M6 交付完整驗收，綁定 Dataset／Config／Index／Engine／Judge 版本，逐題呼叫同一 Target，讀取成功回應的 `contexts`、快照版本及錯誤，按指定 ResultSet 執行 [文件排名評估](03_engine_and_components.md#document-level-evaluation)。重用相同 Retrieval-only Query API；不收集生成答案或做答案正確性評估。併發、快取、重試、成本與 Gate 見 Q-018／Q-027。

AI 助手在 M4 先交付獨立核心與 Python／API 入口：接受需求、明確允許的樣本、可用服務資訊及可選的既有 Config／基準識別，產生受 Schema／Registry 限制的 Config 草稿、理由、Diff、缺少設定與驗證結果。資訊不足可回需補齊的草稿，不宣稱已可執行；不猜服務／憑證，不自動 Ingestion。Config 合法仍需使用者／驗收腳本明確交給 Engine／Runtime 執行，不等同檢索品質已驗收。

M5 的 Builder Backend 串接同一核心，加入 Workspace／System 授權、目前 UI Draft 與基準版本，回傳可對回控制項的建議。使用者套用時先重驗基準及 Config，過期建議不覆蓋人工變更；套用只改草稿，Create／Save 前不改 active Config。前端另驗收樣本／映射、Diff／取消、收合欄位錯誤定位及變更影響。M4 的獨立測試不能取代 M5 的 UI 整合證據。

Prototype 規則模擬不能當作正式助手。Prompt、資料保留、最大樣本、輸出／Diff 與舊建議合併見 Q-024；HTTP 宿主／Envelope／認證見 Q-019。對應 Prototype 需求先記 [UI Backlog](07_builder_ui.md#src-10-7-驗證與剩餘整合)，本輪未修改畫面。

<a id="src-07-9-export獨立部署與-secret"></a>
## Export、獨立部署與 Secret

<a id="src-07-91-bundle-目標"></a>
### Bundle 目標

交付 Retrieval Runtime，不打包整個 Builder。

Runtime Image 可自 M3 開始建置；M7 才驗收完整 FTEST／ENT 獨立交付。以同一版本／Digest 的可配置 Runtime 承載相容 System，不要求每份 Config 建一個 Image。獨立 Runtime 讀取已提供的 Config 即可啟動，使用 AI 助手生成 Config 是可選的前置操作，不能變成部署後必須連回 Builder 的依賴。

目標 Bundle 包含：

- Runtime Image 版本／Digest、Module 版本、Config Revision／Hash。
- 選定 System／Revision 的相同邏輯 Config 及另存的目標環境部署設定。匯出沿用原 `system_id`，依匯出目標在部署設定預填 `env`。[部署環境規格](#runtime-index-ownership)
- ConfigMap／Deployment／Service 等 K8s 設定。部署 Config 的 `variable` 與 `secret` 保留 Key 與 `null`，Deployment 指定同名環境變數的注入。
- FTEST／ENT 的環境檔案、啟動與 API 說明、資料準備步驟。
- 若有評估報告，清楚綁定測試環境／資料版本，不能宣稱目標環境已驗證。

Remote API 匯出目標環境的連線設定及 System Secret 引用表達式。

不含 Image 本體、真實 Secret、原始文件、Chunk／vectors、Builder DB 或外部 DB／模型資料。目標環境需有相容資料或執行 Ingestion；部署後仍可持續 API 匯入。

首版匯出受管 ES 的環境連線設定，沿用發布快照的邏輯設定。Local Search 的 Memory／MongoDB 部署屬後續範圍，若採用則持久化模式仍隨同一版 Config 沿用，實際資料由各環境準備。

<a id="remote-service-deployment"></a>
<a id="src-07-911-remote-service-manifest-與環境綁定"></a>
### Remote API 與環境綁定

Remote API 在部署設定解析 Endpoint。需要 Bearer 認證時，節點的 `auth.bearer_token` 填 `{{KEY}}`。Runtime 只使用該 System 啟動時載入的值來組出認證 Header。一般執行參數按 [Request 優先規則](05_system_config.md#parameter-references)解析。業務 Request、Document、Remote 業務參數、模板、索引及記錄只承載各自的業務資料或引用。

<a id="system-secret-deployment"></a>
### Runtime 啟動與 Variable／Secret 注入

同一 System 在 DEV 及正式環境使用相同的 `{{KEY}}`。DEV 由 Builder 提供測試值。正式 Deployment 為 `config.secret` 使用 `env[].valueFrom.secretKeyRef`，為 `config.variable` 使用 `configMapKeyRef`。環境變數名稱與兩張表的 Key 完全相同，每個 Pod 各自在 Runtime 啟動時讀值。缺少 Key 時中止啟動，錯誤訊息列出缺少的 Key，遮罩解析出的值。Kubernetes 以環境變數注入 Secret 時，更新後需重新啟動容器才會取得新值。

[DEV Config](../examples/system_config/local_memory.remote_parsing.json)、[匯出 Config](../examples/system_config/local_memory.remote_parsing.export.json)與[容器 env 片段](../examples/system_config/deployment.secret-env.example.yaml)示範同一份設定在兩個環境如何供值。

<a id="src-07-92-驗證與部署"></a>
### 驗證與部署

狀態分開：needs_configuration → configured_unverified →（外部連線／資料檢查結果）→ 實際部署結果。本文不指定未核定的完整狀態枚舉；不能用 configured_unverified 表示可直接部署成功。

首版預設提供 ES 連線，兩條流程分 Pod 時使用同一受管 ES 綁定，各自的 Service 只受理相應流程的業務 API。多副本、權限、版本策略、Deployment／Service 路由與 Probe 接線見 [Q-021](08_plan_and_decisions.md#q-021)／Q-027。

獨立部署的 ES 索引建立策略及部署方的操作入口見 [Q-021](08_plan_and_decisions.md#q-021)。

若環境使用 Vault，可在部署流程先供應 Kubernetes Secret，Runtime 按 [System Secret 注入規則](#system-secret-deployment)啟動。對外的驗證結果及 Trace 遮罩認證資訊。換 Embedding Profile 要回 Engine 重建，不能只在匯出改模型 ID。

<a id="src-07-93-獨立啟動"></a>
### 獨立啟動

Runtime 啟動時讀取同一份 System Config 快照及環境部署設定。環境設定的 `pipeline` 選用 `ingestion` 或 `inference`，省略時載入兩條。Runtime 解析環境綁定，準備選定流程的 Component 及資源，再查核索引和開放該流程的業務 API。Inference 接回相容的既有索引；受管索引初始化及恢復由 Ingestion 端依部署策略執行。分 Pod 時兩端須使用同一 `env`、`system_id`、Config Revision 及受管索引綁定。Live／Ready 與 IndexReady 分開；空索引可查時回成功空候選。環境設定的載體與匯出接線由 [Q-021](08_plan_and_decisions.md#q-021) 追蹤。

<a id="release-deployment-boundaries"></a>

<a id="src-07-94-建置發布與部署的變更範圍"></a>
### 建置、發布與部署的變更範圍

發布新版本與讓既有環境採用新版是兩個動作。以下描述採用新版時的交付範圍，實際 CI／CD 工具與核可權限仍依 Q-021／Q-022：

| 變更來源 | 建置／測試與部署範圍 | 跨 repo 配合條件 |
|---|---|---|
| 僅 Builder UI／Backend | 建置並部署受影響的 Builder Image，驗證與所支援 Runtime 的契約 | 沿用相容 Runtime；不因 Builder 發版而重建所有 Runtime |
| 新增／修改 Local Component／Runtime Adapter | rag_engine 的方法與整合測試後，建置完整 Runtime Image；欲使用新版的環境更新 Runtime | API／Schema／表單相容時 Builder 可維持原版，更新目錄即可；新 UI 能力另配合 |
| Engine／SDK／Runtime API | 在 rag_engine 驗證受影響 Components 與 API，再建置並部署 Runtime；SDK 如另發行須保留版本對照 | 破壞性 API／Config／SDK 變更需要使用方適配；不能承諾所有變更都單邊升級 |
| 外部 Remote API | 修改環境連線或相容設定 | 變更輸出欄位或處理語意時重新驗證有效 Config、資料與後段相依 |
| 文件／未納入產物的測試資料 | 執行相應文件／測試檢查 | 不僅因 repo 有新 commit 就強制重新部署服務 |

每個完整 Runtime Image 應可追溯同一 rag_engine 交付來源、SDK／Engine／Component package 版本與依賴鎖定結果。同 repo 可以讓它們一起驗證，並不抹去各自的契約／實作版本。既有 System 可維持鎖定版本，新版發布不自動觸發所有 DEV／FTEST／ENT 升級；欲交付的選定版本應完成 DEV 驗證，再由使用單位以對應版本的 Runtime Image 與同版邏輯 Config 補齊環境設定進行部署。

Runtime 更新若重啟 Memory 模式，依既有規則需要重新 Ingestion；MongoDB／ES 依索引與版本相容性恢復。重建、快照、切換與回復仍依 Q-008～Q-010／Q-015，不因兩個 repo 分工就新增熱插拔 Component 或零停機升級承諾。

<a id="src-07-10-observability認證與權限"></a>
## Observability、認證與權限

request／run／trace 必須可跨 Backend／Runtime／模組關聯。輸出結構化錯誤、耗時、輸入輸出數及可取得用量；模型與 Judge 也記版本。OTel／Langfuse 為候選，非每個 Runtime 必備外部依賴，具體方案 Q-016／Q-027。

Builder 使用者登入與文件／檔案級 ACL 延後討論，見 Q-006。可信 Backend 與 Runtime 負責 System 存取範圍。MCP 固定 API key 對應可操作的 System 與工具，Runtime 依授權列出工具並在呼叫時驗證。獨立 Runtime 採部署端認證。模型與 DB 的連線憑證由各服務綁定提供。

<a id="src-18-5-執行實例儲存與資料共用"></a>
## 外部 Retrieval 就緒與資料責任

搜尋自有資料的 Remote Retrieval 可直接查詢，不需要平台 Ingestion 或 IndexBinding。Runtime 仍驗證每筆候選 Document 是否符合 System 的有效 Ingestion 輸出 Schema，後續內建 Rerank 使用同一欄位規格。外部服務負責其資料空間及授權。平台的文件狀態、清單及刪除僅處理平台管理的資料。若 Remote 接管 Query Transformation 到 Rerank 的整段流程，Runtime 驗證外部回應與候選契約，按服務回傳的排名交付。見 [Remote 執行邊界](03_engine_and_components.md#remote-api)。
