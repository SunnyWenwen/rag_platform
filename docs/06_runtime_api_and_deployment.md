# Runtime API、工作控制與部署

## 閱讀目錄

- [平台管理資料與儲存](#src-07-3-平台管理資料與儲存)
- [System／Revision 與 Engine 生命週期](#src-07-4-systemrevision-與-engine-生命週期)
- [Builder Backend（Control Plane）](#src-07-51-builder-backendcontrol-plane)
- [Builder 上傳與自行部署](#src-07-54-builder-上傳與自行部署)
- [Runtime Component 目錄與 Config 驗證邊界](#src-07-58-runtime-component-目錄與-config-驗證邊界)
- [範圍與已確認基準](#src-21-1-範圍與已確認基準)
- [API 清單：7 支業務 API＋2 支 Health API](#src-21-2-api-清單7-支業務-api2-支-health-api)
- [Ingestion 的提交與接收](#src-21-3-ingestion-的提交與接收)
- [Elasticsearch 文件覆寫](#elasticsearch-document-replacement)
- [文件狀態與一次提交的狀態](#src-21-4-文件狀態與一次提交的狀態)
- [Inference](#src-21-5-inference)
- [HTTP、狀態與錯誤層次提案](#src-21-6-http狀態與錯誤層次提案)
- [非必備端點與本輪待討論](#src-21-7-非必備端點與本輪待討論)
- [API-D05／06 的具體情境](#src-21-8-api-d0506-的具體情境)
- [文件資料查詢與直接刪除](#src-21-9-文件資料查詢與直接刪除)
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


更新：2026-11-05。本手冊主責 Builder Backend／Runtime 整合、HTTP、Queue、狀態、環境控制與 Export。業務資料引用資料契約；不為 HTTP 另外建立 InferenceState／ParserInput。

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
| ServiceReference | DEV 或使用者服務設定與 Secret 引用；System 的 llms 有明確作用域 |
| Runtime IngestionRun／文件工作狀態 | D-56：Runtime 記憶體內的提交／逐文件狀態、計數、Module、時間與錯誤；重啟不保留；不要求平台 DB |
| EvaluationRun | 評估的 Config／資料版本、狀態、數量、錯誤與報告引用，依 M6／Q-018 處理 |
| Dataset／EvaluationReport | 版本化 Dataset、逐題結果、指標、Judge／Rubric、Target |
| ExportArtifact | Config／Image／環境覆寫、驗證狀態、產出版本 |

正式管理階層只有 Workspace → System；同一 System 在 DEV／FTEST／ENT 沿用相同邏輯 Config Revision，部署綁定分環境保存。部署識別／儲存形狀待定，不額外建 Group 或 Blueprint。Config Store 與 Artifact／Run Store 不等於搜尋選配 MongoDB；Memory 模式仍可能保存平台管理資料；獨立 Runtime 不強制連回平台儲存。

Builder 保存並管理可供重新匯入的原始資料（原始檔、CSV 或結構化 JSON）。儲存及保留方式由 Builder 後續規劃，見 [Q-016](08_plan_and_decisions.md#q-016)。解析結果、Prompt／Context Trace、評估報告保留與刪除規則也依 Q-016 追蹤。D-56 已確認 Ingestion Queue、Run 與文件工作狀態在 Runtime 重啟後清除；若 Builder 另存歷史摘要，Runtime 仍依實際工作紀錄回報 `unknown`。歷史評估報告保留對應的舊 Config。

<a id="src-07-4-systemrevision-與-engine-生命週期"></a>
## System／Revision 與 Engine 生命週期

<a id="src-07-41-建立與啟動建議流程"></a>
### System 管理介面

Builder 保存 System、草稿與發布歷史，Runtime 持有已載入的 `system_id`、生效的 `config_revision`、索引綁定與工作狀態。Builder DEV 的 Runtime 獨立於 Builder Backend，啟動時可有零組 Config。Builder Backend 透過受保護的內部管理 API 下發設定。單組 Config 獨立部署在啟動時直接呼叫同一套 Python 管理函數，並停用管理 API 路由。

| 管理操作 | 內部 HTTP 路徑草案 | 行為 |
|---|---|---|
| 初始化／更新 | `PUT /internal/v1/systems/{system_id}` | 傳入 `config_revision` 與完整 `config`。可共用 `apply_system()`，由呼叫方明確區分初始化和更新意圖。 |
| 列出 | `GET /internal/v1/systems` | 列出此 Runtime 目前載入的 System 與生效版本。 |
| 查單一 | `GET /internal/v1/systems/{system_id}` | 回報生效版本、是否忙碌、能否匯入及能否查詢。 |
| 卸載 | `DELETE /internal/v1/systems/{system_id}` | 排空該 System 的請求、刪除其受管理索引及資料、釋放執行資源。Builder 保有 System 與 Config 歷史。 |

管理操作僅供可信 Builder Backend。業務 HTTP／MCP 使用相同的 Runtime 狀態與執行入口。MCP 的業務 API key 只授權相應 System 與工具。正式管理路徑、請求／回應 Schema、逾時及認證接線依 Q-019 定義。

<a id="system-index-lifecycle"></a>
### 初始化、重連與索引重建

`apply_system()` 先驗證 Config，推導平台索引應有的 mapping、搜尋欄位與 Embedding Profile，再依操作意圖處理索引。Config 成功載入與索引能否執行搜尋分開回報。索引就緒不要求已有文件。Builder 依[初次匯入規則](07_builder_ui.md#builder-initial-ingestion-readiness)決定何時開放其查詢入口。

| 操作 | 條件 | 結果 |
|---|---|---|
| 初始化／重啟後重新載入／重連 | 確認索引不存在 | 建立空索引與 mapping。索引可正常查詢後即可接受 Ingestion 與 Inference，空索引查詢回成功空候選。 |
| 初始化／重啟後重新載入／重連 | 既有索引的歸屬、索引相容性指紋及實際 mapping 相符 | 接回既有索引，依其實際可用性開放匯入與查詢。 |
| 初始化／重啟後重新載入／重連 | 無法確認索引歸屬，或指紋／mapping 不相容 | 回報衝突並保留索引。連線或授權錯誤依實際原因回報，不能當作索引不存在。 |
| 明確更新 | 既有索引與新版相容 | 沿用索引。切換後新請求使用新版，已開始的查詢固定原版至結束。 |
| 明確更新 | 確認索引不存在 | 建立新版空索引與 mapping。新索引建立成功後才啟用新版，並等待 Builder 重新匯入。 |
| 明確更新 | 新版與本 System 的受管理索引不相容 | 驗證新版後排空請求，刪除舊索引及資料，再建立新索引與 mapping。新索引建立成功後才啟用新版並接收匯入，Builder 以保存的原始資料重新提交 Ingestion。 |
| 明確卸載 | 已排空，且索引已不存在或可確認由本 System 管理 | 刪除仍存在的受管理索引及資料，完成卸載。無法確認歸屬時回報衝突。 |

Elasticsearch 使用 `mappings._meta` 記錄 `system_id` 與 `index_fingerprint`。Runtime 讀取實際 mapping 並驗證歸屬及相容性。指紋基於影響索引內容、向量語意及搜尋能力的有效設定，純 Inference 參數如 `top_n` 不改變指紋。精確輸入與正規化規則依 Q-015 定義。參考 [Elasticsearch mapping `_meta`](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/mapping-meta-field)。

Local Memory 使用同一套相容判定與 `system_id` 隔離；程序重啟後記憶體索引遺失，需重新匯入。外部 Retrieval 查詢自有資料時，依其服務就緒狀態與候選契約執行；上述索引建立、重建與卸載的刪除範圍只涵蓋平台管理的資料。

<a id="src-07-411-remote-imageexternal-的生命週期"></a>
### 外部 Remote API 的生命週期

User 設定已部署的外部服務。Runtime 在執行時依有效環境綁定呼叫，平台驗證契約與連線。外部資料、服務部署與維護歸提供者，平台索引仍由 Indexing 管理。

### 更新／卸載的併發與失敗

每個 `system_id` 一次處理一個生命週期變更。有其他管理操作或排隊／執行中的 Ingestion 時，第一版回 `409 system_busy`（錯誤名稱草案），Builder 保留設定後重送，Runtime 無須另建 Revision 更新佇列。開始變更與接收新 Ingestion 共用該 System 的狀態檢查，避免檢查空閒後仍接受工作。其他 System 照常執行。

相容更新時，舊查詢可繼續，等引用結束才釋放原版專用資源。需要刪除索引的更新或卸載會先停止接收該 System 的新請求，等既有查詢結束，再操作索引。此排空限於生命週期操作；一般文件寫入仍依 D-60 與查詢併行。

新版驗證失敗時，原生效版本與索引繼續使用。若已刪除索引但建立新索引失敗，回報更新失敗，該 System 保持不可用，待重試成功後由 Builder 重新匯入。Runtime 重啟後舊工作仍回 `unknown`。刪除或建立結果不明時，先查證目標索引狀態及歸屬，再決定如何重試；錯誤碼、重試協定與跨重啟的更新狀態仍待 API-D05／Q-019。

獨立部署重新載入 Config 時採初始化規則；若既有索引不相容，由部署管理者安排明確的重建及重新匯入。獨立部署的重建入口與部署流程另議。Backend 依 [變更影響](05_system_config.md#變更影響)向使用者呈現重建及停查影響。

實作驗收覆蓋首次建立、相容重連、未知歸屬拒絕、相容切版、忙碌拒絕、排空後重建／卸載、刪除後建立失敗，以及 Local Memory 重啟與 ES 索引接回。正式管理 API 的版本衝突與重試、排空逾時，以及 Builder 初次匯入完成狀態的追蹤方式仍待定。


2026-10-16 的內容保存簡化：Indexing 保存全部 Document.structdata／metadata，Chunking 預設繼承全部有效業務 metadata；只選全文／向量／Filter 能力。原型的 indexing.stored／chunking.metadata 是待遷移的舊保存／繼承投影，不能直接套用為新規則。繼承 metadata 時仍驗證 Schema 並保留可信來源，API 回傳欄位另依資料契約。

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

兩個 repo 的服務透過 Runtime API 與 Component 目錄合作；實際路徑、認證與 Envelope 由 Q-019 核定，以下為需要覆蓋的介面能力，不新增已凍結端點：

- **方法與能力目錄**：提供目標 Runtime 已交付的內建方法、版本、Schema 與能力。Remote API 的有效契約由 User 設定及 System Schema 推導。
- **完整 Config 驗證**：Builder／助手提交有效設定與目標版本，重用 Engine 的型別、跨模組相依與索引相容檢查；回傳可定位到 `[MODULE NAME]`／欄位的結果。格式有效、可組裝、服務已連通與資料可查詢分開，不把目錄查詢當成真實連線測試。
- **版本與目錄一致性**：目錄／Schema／驗證結果要能對回同一目標 Runtime 版本；Runtime 更新後，舊快取或過期驗證不得靜默套用。既有 System 保留所選版本，尚未安裝／不相容方法應明示，不自動取最新版。
- **相容範圍**：既有 API、Config Schema 與 UI 控制項足以支援時，新增 Component 可只發布／部署 Runtime；需要新型表單或破壞性接口時，需更新 Builder 並完成契約相容測試。目錄傳輸格式與欄位演進政策仍待 Q-002／Q-019／Q-025。

直接 Python 使用 Engine／M4 助手時仍可在本機取得同一 Registry／Validator，不因此強制所有呼叫都走 HTTP。平台整合使用公開服務邊界，Runtime 的可信管理與能力接口不等於允許外部一般使用者更改 System 綁定。

D-42 的 Descriptor、動態選項／能力 Context、規則與驗證回傳草案見 [Descriptor](04_component_descriptor.md)。除了靜態 Component 目錄，整合需提供依當前草稿／上游能力／授權解析的候選與欄位狀態；相依驗證與有效 Config 編譯由 Engine 統一處理，API 不另寫一套。服務 URL／Secret 綁定仍在部署設定，目錄／Context 不含憑證值。

設定檢查結果需對回 runtime_ref、catalog_revision、draft_revision、context_revision，錯誤使用 Module／節點引用／相對參數路徑定位。過期或取得失敗的結果不能沿用為新版設定驗證成功；建立／套用時再次核對版本。完整端點、Envelope、Context 型別及授權仍待 Q-019，12 不變更本文件的 Ingest／Query 公共 API 範例，也不把 UI 支援性與 Engine 設定合法性混為一談。

<a id="src-21-1-範圍與已確認基準"></a>
## 範圍與已確認基準

<a id="src-21-11-這份清單是哪一層"></a>
### 這份清單是哪一層

這裡盤點 **Retrieval Runtime 對外的業務 API**：Builder DEV 與自行部署到 FTEST／ENT 使用同一語意與實作，D-64 已確認 Runtime 限制初始預設與管理方式，歸 E 的 Runtime 環境設定，由 Admin／部署管理者提供，可調項集中見 Runtime API／部署；正式參數名稱／機器 Schema 與載入方式仍待核定。Builder DEV 共用一組或少數幾組 API service，啟動不綁單一 System Config，可信路由先選定 System 的已驗證 Config 快照，共用 Flow／Executor 依配置執行；FTEST／ENT 主 Runtime 以一 Pod＋一組 API service＋一份 Config 啟動。不把 system_id／tenant 任意覆寫放進業務 JSON。

以下不是本文件的新增範圍：Builder Workspace／System CRUD、Config／Component 目錄管理、Export、AI 助手、Evaluation，以及 User Remote API 的 operation HTTP 協定。後者引用 [Engine／Component 開發](03_engine_and_components.md)，不是將每個 Module 都公開成 Runtime API。

Library 仍可直接由 Python 使用；本表描述 Runtime HTTP／工作管理層，不要求每次 Library 呼叫都經 HTTP。

<a id="src-21-12-已確認不再當成待選方向"></a>
### 已確認，不再當成待選方向

- 同一 System 的同一 document_id 以新文件完整替換；不存在則新增，成功後移除該文件不再產出的舊 Chunk。
- 更新與執行結果以 `document_id` 為單位，Batch 中各文件獨立。ES 確認新批次完整可搜尋後才清理舊資料，清理完成才標 `completed`。依 D-60，更新期間可讀到新舊混合。詳見 [Elasticsearch 文件覆寫](#elasticsearch-document-replacement)。
- 不保存斷點續跑；重試整份文件。Runtime 重啟不恢復已接受的排隊／執行工作。
- Runtime 統一管理有上限的 Ingestion Queue、併發、Inference Rate limit／併發與逾時。每 System 的文件執行併發可配置，預設 1；調高前需驗證 Component／共享資源安全，不等於無限制並行。
- 同一 System 的同一 document_id 已 queued／running 時，拒絕再次提交；終態後才可重新提交覆寫。不同文件可依上限並行；Batch 是文件集合，不是另一種資料契約。
- Runtime 額外保存文件級工作紀錄於記憶體，不放入 Document，也不從既有索引反推執行狀態；重啟後查不到的狀態為 unknown。
- 202 表示已接受排隊，不表示解析、Embedding、索引或可搜尋已成功；提交後須可查詢結果。
- Inference 沿用 query／filters／metadata 輸入，同步回 QueryContext[]；不做 Generation，不因非同步 Ingestion 而新增 InferenceState。
- D-57：整批接收前預檢通過才入列、回 202；入列後逐文件結果，文件無 partial，Run 可 partial，無紀錄回 200＋unknown。這不是要求完成 Parsing／Embedding／Indexing 才回 202。
- D-57／D-58：首期需要 retire，已確認為直接刪除該 System／document_id 的儲存資料與搜尋索引，不是保留資料的邏輯停用；後續 D-64 確認同步 200＋deleted／not_found，忙碌文件 409，後端／Remote 清理協定仍待細化。Ingestion 的進度管控及排隊／執行中工作的取消另議。
- D-58：一支 POST /v1/ingestions 接收批次物件，documents 為非空 Document[]；Parser 每次仍接收單份物件，不另開 :batch。
- D-58：新增文件存在性與全部 document_id 清單的查詢能力，資料來源為該 System 的實際儲存／索引，與 Runtime 工作狀態分開；清單需對 Chunk 的 document_id 去重。
- D-60：讀寫各自進行，不因 Ingestion／retire 寫入而阻擋 Query，不加共享查詢讀寫鎖／全索引快照；同文件重複 Ingestion 的忙碌拒絕維持。
- D-60：Runtime API 暫採 HTTP Basic Auth，預設一組帳密可操作該 API service 提供的全部 API，首期不做逐角色／逐 API 權限；Builder 使用者登入另議。
- D-61～D-63：多個 System 共用 Runtime 與 LangGraph，各請求固定 Config 快照。切版、索引及資源交接見 [System 管理](#src-07-4-systemrevision-與-engine-生命週期)。服務池分組與快取回收策略依 Q-020。

- D-64：確認接收／文件與 Run 狀態核心欄位及錯誤格式；覆寫失敗留 Runtime 記憶體可查，不代表資料回復舊版。初始限制見 Runtime API／部署手冊；可信內部 System 路由見 相關章節。文件 ID 每頁數量／排序／cursor 的細節仍待確認。

- D-65：文件清單回 documents[]＋next_cursor，每筆 document_id／source_revisions[]，彙整實際儲存版本；不提供最新成功版或版本歷史推定。精確分頁參數／cursor 後續整理。

<a id="src-21-2-api-清單7-支業務-api2-支-health-api"></a>
## API 清單：7 支業務 API＋2 支 Health API

**能力、Ingestion 批次 Request、狀態／錯誤核心欄位及 retire 同步結果已確認；完整 OpenAPI、存在／清單精確格式與分頁細節仍待整理。**查詢以目標 System 為作用範圍，不直接開放任意 DB／Collection 管理。

| 優先 | Method／Path 草案 | 用途 | Request | 成功回應／狀態 | 主要行為 |
|---|---|---|---|---|---|
| P0 | POST /v1/ingestions | 提交一份或多份文件 | 批次物件，documents 為非空 Document[] | 202：run_id、queued、config_revision、文件清單；Location 指向查詢 | 整批預檢通過才入列；不再另開 :batch；每個 item 與 Parser input 同 Schema |
| P0 | GET /v1/ingestions/{run_id} | 查一次提交及逐文件結果 | run_id | 200：Run 狀態／計數／逐文件結果 | 資料來自 Runtime 記憶體工作紀錄；Run 可 partial |
| P0 | GET /v1/documents/{document_id}/ingestion-status | 查文件最近一次工作 | document_id | 200：run_id、status、Module、時間／錯誤；無紀錄為 unknown | 工作狀態，不用成功儲存的文件反推 |
| P0 能力；格式草案 | GET /v1/documents/{document_id}/exists | 查目前文件資料是否存在 | document_id | 200：document_id／exists | 從實際文件儲存／索引讀取；不是工作紀錄是否存在；backend 無法確認時回錯誤 |
| P0 核心已確認 | GET /v1/documents?limit=...&cursor=... | 列出目前文件摘要 | 分頁參數 | 200：documents[]／next_cursor；每筆 document_id／source_revisions[] | 從實際 Chunk 去重彙整文件與版本；不當作工作歷史／最新成功版本 |
| P0 | POST /v1/documents/{document_id}:retire | 直接刪除文件資料 | document_id | 200：document_id／result=deleted 或 not_found；同文件忙碌 409 | 清除對應 Chunk／向量、持久儲存與本地搜尋副本，避免重啟重建復活；不取消 Ingestion 工作 |
| P0 | POST /v1/queries | 完整 Inference | {query, filters?, metadata?} | 200：根層 QueryContext[] | 同步完成；Runtime 控制 Rate／併發／Deadline |
| P0 支援 | GET /health/live | 程序存活 | — | 200：存活 | 不依是否有資料判斷 |
| P0 支援 | GET /health/ready | Runtime／必要資源初始化 | — | 200：就緒；否則 503 | 尚無可查索引不一律等於不 Ready |

共享 Builder DEV 的 System 選擇與資料權限由可信層決定，單一 Pod Health 不能代表每個 System 的 Query-ready。D-64 已採可信 Backend 的內部 System 路由，S1 為 system_id 示意，見 相關章節；API-D06 仍涵蓋實際認證／部署保護；清單／存在／retire 也必須受相同存取邊界限制。

Document 管理細節見 [Runtime API相關章節](#src-21-9-文件資料查詢與直接刪除)。整份文件／Chunk 內容、單步 Module 測試及 Ingestion 進度管控各有獨立的規格討論。

<a id="src-21-3-ingestion-的提交與接收"></a>
## Ingestion 的提交與接收

<a id="src-21-31-已確認單一端點單份也包-list"></a>
### 單一端點，批次物件

`POST /v1/ingestions` 接收 `{documents: Document[], parameters?: object}`，documents 非空。整批預檢通過才 202，單份同樣置入 documents。Runtime 在 Parser 前拆成逐文件工作，每次傳入一筆 Document。有效 parameters 隨同一批每筆工作傳遞，Parser 後仍可按同一文件處理 Document[]。

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
### 202 回應核心欄位（D-64 已確認）

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

提交一份或多份使用相同 receipt，一份只有一筆 documents；Receipt 的 documents 是回應格式，不代表 Request 必須有 documents wrapper。Receipt 是接受當下的快照，Client 查詢時可能已 running 或完成。

建議接收階段只做授權、JSON／外層 Schema、有效 Config／Parser 能力等快速預檢、文件忙碌檢查與容量預留。下載、昂貴 Parsing、Embedding／Indexing 在 Worker 執行，失敗由狀態 API 回報，不能把 202 當作最後成功。

**D-57 已確認：「預檢整批通過才入列；入列後逐文件獨立結果」。**例如外層不合法、同批重複 ID、某文件已 queued／running、容量不足時，先拒絕整次請求，保證沒有未交代的部分入列；接收政策與批次物件包裝均已確認；完整錯誤／OpenAPI 規格另行整理。合法文件入列後，另一份文件 Parsing 失敗不回滾已成功文件。

併發與 Queue 容量建議以文件工作計數，並另限制排隊資料量／總請求大小，避免一個巨大 Batch 算一個 queue slot。已確認每次最多 100 份文件、body 20 MiB、每 System 100／Runtime 500 份等待容量等初始值集中見 Runtime API／部署手冊；參數可調，接收容量預留及公平排程細節仍見 API-D04。預留文件忙碌標記、Queue 容量與狀態紀錄須一致，不能檢查後因競態收進同文件兩份工作。

<a id="src-21-4-文件狀態與一次提交的狀態"></a>
## 文件狀態與一次提交的狀態

<a id="src-21-41-文件級狀態"></a>
### 文件級狀態

**document_id 來自 Request 的每份 Document，不需要先在索引中成功存在。**整批預檢通過、入列時即建立 Run 與每份文件的 queued 紀錄；Worker 更新 running，再記錄 completed／failed。失敗紀錄與成功紀錄同樣保留到終態清理，不只有成功文件才有狀態。

| 階段 | Runtime 工作紀錄 | 搜尋資料／判斷 |
|---|---|---|
| 入列前整批拒絕 | 不建立新的 Run／工作；HTTP 回位置與錯誤，可辨識時附 document_id | 不改既有文件；若有舊狀態，不覆寫成這次的新工作 |
| 已入列 | queued | 不代表已產生／寫入 Chunk |
| 執行中 | running，必要時附 Module | 舊版可仍存在，不能以此推算本次完成 |
| 執行失敗 | failed＋error | 工作失敗紀錄仍可查；不等於必有成功索引 |
| 成功發布 | completed | 才表示本次完整處理成功 |
| Runtime 重啟／紀錄到期 | 查詢為 unknown | 持久索引可能存在，不能據此假造本次工作狀態 |


| status | 定義 |
|---|---|
| queued | 已接受，等待執行 |
| running | 正在處理；module 可提供目前邊界 |
| completed | 該文件完整處理、替換與索引發布完成；不是剛取得模型回應或只送出索引寫入 |
| failed | 已知處理失敗，附可定位錯誤；不續跑半份文件 |
| unknown | 沒有可用工作紀錄，或執行結果無法確認；不等於文件不存在／未寫入／失敗 |

unknown 的兩種原因需可區分：一是重啟／到期後已無紀錄；二是 Remote timeout 等造成提交結果未確認。後者若尚有紀錄應帶 error code，不能將「不知道是否寫入」偽裝為確定失敗可安全重送。具體 code 與再次提交前如何確認／隔離，列 API-D05。

module 可為 null（例如 queued 或終態），亦可指目前 Local Module 或 Remote operation 的可知邊界；不假造 Remote 私有流程內部的百分比。D-64：文件狀態核心為 document_id／run_id／status／module／updated_at／error，Run 另含 config_revision／counts／documents。error 在沒有錯誤時為 null，失敗時使用 code／module／message，輸入驗證另附 path，不公開 Stack／Secret；狀態物件的 error 內不再包一層 error。核心已確認，完整型別／未知結果原因及 OpenAPI 待 API-D02／05。

```json
{
  "document_id": "manual-001",
  "run_id": "ing-001",
  "status": "running",
  "module": "Embedding",
  "updated_at": "2026-11-05T08:30:00+08:00",
  "error": null
}
```

重啟或紀錄已清除的回應提案：

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

文件最新狀態索引以可信的 (System, document_id) 對應最近一次 run_id；每次合法重新提交建立新 run_id，先前 Run 的結果在保留期內仍能查，不被文件最新狀態覆寫。這不要求持久儲存完整執行歷史。

D-57 已確認 Batch 彙總方向：仍有 running 為 running，只有等待且尚無終態為 queued；已處理部分且還有待處理文件時為 running；全成功為 completed、全失敗為 failed、已全部終結但有成功亦有失敗為 partial。**partial 只適用 Run 彙總，半份處理不能標文件 completed；不代表更新期間讀取有原子保證。**沒有活躍工作但至少一筆結果未確認時，Run 為 unknown，不偽裝為全失敗或已確認 partial。Run partial／未知紀錄 HTTP 200 已確認；精確欄位與未知結果處理仍見 API-D02／資料契約手冊。

```json
{
  "run_id": "ing-001",
  "status": "partial",
  "config_revision": "C1-example",
  "counts": {"total": 2, "queued": 0, "running": 0, "completed": 1, "failed": 1, "unknown": 0},
  "documents": [
    {"document_id": "manual-001", "status": "completed", "module": null, "updated_at": "2026-11-05T08:31:00+08:00", "error": null},
    {"document_id": "manual-002", "status": "failed", "module": "Parsing", "updated_at": "2026-11-05T08:30:30+08:00", "error": {"code": "PARSER_CONTENT_INVALID", "module": "Parsing", "message": "內容不符合所選 Parser 的輸入要求。"}}
  ]
}
```

counts 指這次接收的 Document 數，不是 Unit／Chunk／模型呼叫次數；大文件不偽造固定完成百分比。分頁／批次大小上限應一起決定，避免無界狀態回應。Run 失去紀錄時建議只回 run_id／status=unknown，不填 0 個文件冒充空 Batch。

<a id="src-21-43-紀錄的保存與重啟"></a>
### 紀錄的保存與重啟

- 由 Runtime 記憶體保存 Queue、Run／逐文件狀態，以及 document_id 的最新 Run 對照；不新增必要 DB。
- 僅完成／失敗等可回收紀錄依保留時間／數量清理，不能因 TTL 提前刪除活躍工作；未確認結果的紀錄需依 API-D05 處理。D-64 已確認初始保存 24 小時且最多 10,000 份可回收終態文件紀錄，以最舊已結束 Run 整組清理，集中見 Runtime API／部署手冊；unknown 紀錄回收仍待 API-D05，不能據此推定 Remote 副作用不存在。
- Runtime 重啟後不恢復 Queue／工作／狀態。已接受但未完成的工作可能遺失；202 不承諾跨重啟完成。
- 狀態清空不保證 ES／MongoDB／Remote Service 也回滾。既有持久資料或仍在執行的 External 呼叫須按實際結果確認，不能從「查不到 Run」推定沒有副作用。
- Memory 索引重啟遺失仍依既定政策重新 Ingestion；ES／MongoDB 的資料恢復與工作續跑是兩件事。
- 初期單實例／同程序規劃沿用 07。若增加多 API replica／worker process，記憶體 Queue／狀態不會自然共用，需另定路由或共享控制，不在此次承諾。

<a id="src-21-5-inference"></a>
## Inference

<a id="src-21-51-request-與結果"></a>
### Request 與結果

```json
{"query": "設備多久需要清潔？", "filters": [{"field": "metadata.department", "operator": "eq", "value": "manufacturing"}], "metadata": {"language": "zh-TW"}, "parameters": {"top_k": 5}}
```

`query` 必填，`filters`／`metadata`／`parameters` 選填，預設 []／{}／{}。Runtime 先確定呼叫可操作的 System，依 Inference Input 宣告驗證參數，再初始化 QueryContext[] 並執行所選 Component。`filters` 用於資料篩選，System 選擇及授權由 Runtime 的路由和認證設定決定。見 [資料契約](02_data_contracts.md)。

成功 body 根層是 **QueryContext[]**。索引與必要查詢依賴已就緒時，空索引可以正常執行 Inference。首版每次請求的所有必要節點、Query 及搜尋路徑成功後才回 `200`。索引不就緒、服務失敗或逾時依原因回錯誤；首版沒有部分成功回應或自動降級。既有錯誤的 HTTP 映射見 [HTTP 與錯誤](#src-21-6-http狀態與錯誤層次提案)。

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
## HTTP、狀態與錯誤層次提案

| 情境 | 建議 HTTP／行為 |
|---|---|
| JSON 不可解析 | 400，未接受工作 |
| 授權缺失／不足 | 401／403，適用提交與所有狀態查詢 |
| Request body 超過限制 | 413，未接受工作 |
| 外層 Schema 不合法／同 Batch 重複 document_id | 422，附位置；整批預檢拒絕已確認，具體錯誤 code／位置格式待定 |
| 同 System 的 document_id 已 queued／running | 409，附目前 run_id 或可查狀態；不建立第二份工作 |
| System／使用者的請求速率或接收配額已滿 | 429，附可用的 Retry-After／錯誤原因；不回 202 |
| Runtime 不就緒／整體容量無法接收／Query 索引不就緒 | 503，使用可區別的 code；接收容量與 Query index-ready 分開 |
| 已成功接收 Ingestion | 202＋run_id／Location；尚未成功完成 |
| 202 之後的文件執行失敗 | 狀態 GET 仍為 200，文件 status=failed 與 error；不是將原 POST 改回 HTTP 500 |
| 狀態紀錄遺失／到期 | 狀態 GET 200＋unknown 已確認；不宣稱文件不存在，精確欄位列 API-D02 |
| Query 成功但無命中 | 200＋QueryContext[] 中的空候選 |
| Query 執行／上游 API 失敗或超時 | 依錯誤來源映射 5xx（502／503／504 等）與 code；不偽造成功結果 |

輸入預檢拒絕、工作執行失敗、索引可見性、狀態查不到是不同問題。錯誤碼與數值上限尚未完整核定，不能把這張表當成完整 OpenAPI。

202／狀態監看依據：[RFC 9110 相關章節](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)；429／Retry-After 依據：[RFC 6585 [Runtime API相關章節](#src-21-4-文件狀態與一次提交的狀態)](https://www.rfc-editor.org/rfc/rfc6585.html#section-4)。RFC 支持 HTTP 語意，不替本專案決定 Queue 耐久性、批次政策或錯誤 Envelope。

<a id="src-21-61-已確認的錯誤核心格式d-64"></a>
### 已確認的錯誤核心格式（D-64）

HTTP 請求失敗使用 error 外框，核心欄位為 code／message／module；module 無法歸屬時為 null，輸入驗證另附相對該 Request body 的 JSON Pointer path。以下是 422 輸入錯誤示例，code 的完整枚舉及所有 HTTP 映射仍待 OpenAPI：

```json
{"error": {"code": "REQUEST_VALIDATION_FAILED", "message": "document_id 為必填。", "module": null, "path": "/documents/0/document_id"}}
```

path 指向 documents 第一筆的 document_id，不是 UI Config 的 node_ref 或 Python Stack。無驗證位置時省略 path。SDK 內部 ModuleError 與 ModuleResult 不直接當作 HTTP body，retryable／details 等擴充尚非已確認的必要對外欄位。

已接受工作後的執行失敗仍以 GET 200＋status=failed 查詢；其 error 直接放相同 code／message／module 核心，不再嵌套 HTTP error 外框。失敗工作紀錄只留 Runtime 記憶體，重啟／到期未知，不自動轉成持久歷史或保證舊資料回復。Query 成功 body 保持 QueryContext[]；request／版本的 Header 名稱、正式型別、多筆驗證問題及完整錯誤碼仍待核定。

<a id="src-21-7-非必備端點與本輪待討論"></a>
## 非必備端點與本輪待討論

<a id="src-21-71-首期不納入後續能力"></a>
### 後續能力與待議範圍

| 能力 | 狀態 | 後續界線 |
|---|---|---|
| Ingestion 進度管控（含取消） | 延後討論 | 屆時確認進度呈現、排隊／執行中的操作，以及外部服務的中止與副作用處理 |
| 整份文件／Chunk 內容查詢 | 先延後 | document_id 清單與存在查詢已納入；不因此提供內容、向量或任意 DB 查詢 |
| 索引詳細狀態／容量資訊 | 可作後續管理診斷 | index-ready／恢復／統計來源，不用 Health／最後 Run 反推 |
| Rewrite／Rerank 單步測試、async Inference／streaming | 目前不納入 | 有明確需求再定義，不重新引入 Generation |

Retire 已確認為直接刪除，不做 soft delete／restore API；再次使用同 document_id 需重新 Ingestion。D-64 已確認同步結果／忙碌拒絕／重複刪除的不同結果；Remote／儲存清理與未知結果等後端細節見 [Runtime API相關章節](#src-21-9-文件資料查詢與直接刪除)／API-D03。

<a id="src-21-72-決策狀態與剩餘討論"></a>
### 決策狀態與剩餘討論

| ID | 已確認 | 仍待確認／建議 | 關聯 |
|---|---|---|---|
| API-D01 | 單一 POST、批次物件的非空 documents、單筆也置於 documents；整批預檢通過才 202；逐文件結果 | 方向已收斂；完整 Runtime Request／錯誤 OpenAPI 後續整理，不改單筆共用資料契約 | Q-019／Q-009 |
| API-D02 | 保留 Run／文件兩種查詢；文件無 partial、Run 可 partial；無紀錄 GET 200＋unknown；D-64 確認狀態／counts／error 核心欄位及 22 的終態保存初始值 | 完整型別／錯誤碼、輪詢、未知結果與機器 OpenAPI；不把記錄失敗等同自動回復資料 | Q-019／Q-017 |
| API-D03 | retire 同步確認後 200＋document_id／result=deleted 或 not_found，同文件 queued／running 回 409；不取消工作或 soft delete／restore | 後端完整刪除能力、部分刪除／未知結果與重試清理協定仍待核定 | Q-008／Q-017／Q-028 |
| API-D04 | D-64 確認 22 的初始預設與管理方式：E 的 Runtime 環境設定，由 Admin／部署管理者提供；Query 額滿直接拒絕 | 候選參數路徑、正式機器 Schema／載入方式、排程／計數算法與實際容量驗證；不新增單次請求覆寫 | Q-017／Q-020／Q-027 |
| API-D05 | 共用 Runtime 固定每次執行的 Config 快照；按 System 判斷忙碌；相容更新沿用索引，不相容的明確更新先刪再建，明確卸載移除索引；重啟或重連驗證後接回 | 管理路徑及 Schema、逾時與未知結果、跨重啟失敗處理、獨立部署重建操作方式 | Q-008～010／Q-015／Q-017／Q-019／Q-028 |
| API-D06 | Builder 登入延後；Runtime API 暫用一組 HTTP Basic 帳密操作全部 API；首期不做角色／逐 API 授權 | D-64 已選 相關章節 的受保護內部 System 路由；HTTPS／Secret 注入／網路保護與檢查位置待細化；對外 Health 同一帳密，Probe 接法為部署細節 | Q-006／Q-019／Q-020 |
| API-D07 | 查 document_id 是否存在；D-65 文件清單回 documents[]＋next_cursor，每筆 document_id／source_revisions[]，讀取實際 Chunk 而非工作表 | exists 精確格式、分頁參數／排序／cursor、Remote 讀取操作及完整 OpenAPI 後續整理；不任選最新版本 | Q-019／Q-028 |

API-D01～07 沿用既有 Q-ID，不另凍結完整 OpenAPI。批次物件、接收／Run 彙總、文件 ID 管理與 retire 直接刪除沿用既有決策。進度管控及取消另議。D-64 已收斂刪除結果／錯誤核心及 Runtime 參數，D-65 進一步確認文件摘要核心，存在查詢的精確格式、分頁參數／cursor 與完整 OpenAPI 仍待整理；不因此關閉所有 Q-ID。



實作驗收涵蓋單筆／Batch 接收、文件忙碌衝突、Queue 滿、逐文件 partial、兩種狀態查詢、重啟 unknown、同 ID 完整替換、Query 無命中／不就緒／限流、Inference 路徑或 Rerank 失敗，以及已授權 System 隔離。

<a id="src-21-8-api-d0506-的具體情境"></a>
## API-D05／06 的具體情境

<a id="src-21-81-builder-共用模式與獨立部署模式d-61d-62"></a>
### Builder 共用模式與獨立部署模式（D-61／D-62）

使用者的 service 指 **API server 應用程式／程序，不是 Pod 或 Kubernetes Service 路由資源**。

| 環境 | API service 啟動與 Config | 請求／更新 |
|---|---|---|
| Builder DEV | Runtime 以獨立程序啟動，共用 Library／Registry／LangGraph，可先載入零組 Config | Builder Backend 經內部管理 API 下發多組 Config。每次業務請求固定該 System 的一份生效快照。 |
| FTEST／ENT | 同一套 Runtime 於啟動時載入單組 Config，管理 API 關閉 | 業務請求由啟動設定選定 System，Config 更新透過重啟／重新部署。 |

Builder 儲存許多 UI Config 不等於建立等量 API service／Pod。Runtime 依已驗證快照準備必要 Component／資源，各 System 的 Config、Binding、索引及工作作用範圍分開；共用 Flow 不要求共用所有實例。配置解析快取、實例／資源預載與回收、Namespace 或服務池分組的精確機制待 Q-020。Library 不直接連 Builder DB；由 Backend 經可信邊界管理 Config 與目標 Runtime 對應。

「不綁單份 Config」不代表程式可任意熱替換：可用 Local Components／Adapters 仍由所選 Runtime Image／Registry 版本決定。新 Component 程式依既定 Image 發布流程；不同 Config 在既有能力內組裝 System。

Builder 下發新版時，依 [System 管理](#src-07-4-systemrevision-與-engine-生命週期)判斷忙碌、索引相容性及切換方式。Runtime 重啟會清除所有 System 的記憶體索引與工作狀態。Builder 可重新下發 Config，持久索引依相容性檢查接回。

FTEST／ENT 的一 Pod 基準是主 Runtime。外部 API、ES／MongoDB 等資源以環境綁定提供。

<a id="src-21-82-remote-寫入可能成功但-runtime-timeout"></a>
### 索引寫入逾時與未知結果

Runtime 透過 Indexing 寫入 Elasticsearch 時，回應逾時可能發生在寫入前、寫入中或寫入完成後。依 D-59 回報 `unknown` 及可辨識原因，並依 [Elasticsearch 文件覆寫](#elasticsearch-document-replacement) 查核。Runtime 重啟會清除工作紀錄，後端已執行的操作仍可能生效。

<a id="elasticsearch-document-replacement"></a>
### Elasticsearch 文件覆寫

本節定義同一個 System 內以 `document_id` 為單位的 Elasticsearch 更新。一批 Ingestion 中的每份文件各自處理。相同 `document_id` 有 queued／running 工作時沿用忙碌拒絕。整個 System 的索引重建依 [索引生命週期](#system-index-lifecycle) 處理。

Elasticsearch 索引存取層為每次文件寫入產生一個 `write_id`，例如 UUID。同一份文件此次輸出的全部 Chunk 共用此值。將它存入每筆 ES Chunk 的內部欄位（mapping 為 `keyword`）。ES `_id` 由 `document_id`、`write_id`、`data_id` 唯一且穩定地衍生，讓舊批次和新批次在同一索引內並存。`source_revision` 仍描述來源內容版本。`write_id` 用於精確定位寫入批次，時間可供診斷。共用 `Document` 的 API 契約及 `data_id` 語意維持原定義。

1. 寫入前先取得該 System／文件現有的舊 `write_id`，作為本次成功後的清理範圍。產出並驗證完整的新 Chunk 集合後，使用新的 `write_id` 寫入。
2. 逐筆檢查 ES Bulk 結果，確認新 Chunk 全部成功且已可搜尋，才依 `document_id` 和先前取得的舊 `write_id` 刪除舊 Chunk。舊資料的刪除對搜尋可見後，文件才標為 `completed`。
3. 若確認新批次未完整寫入，只清理本次 `write_id` 的 Chunk，保留舊資料。若新版已可搜尋，舊資料清理失敗時保留新版並回報清理失敗或未完成。清理結果及殘留須可辨識，已知失敗回 `failed`，結果不明回 `unknown`。
4. 若 ES 寫入或刪除逾時而無法判定結果，回 `unknown`。查核以原定的 Chunk `_id`、`write_id` 和後端操作結果為依據，確認後才決定是否清理或重送。安全重試同一次寫入時沿用原 `write_id`、Chunk 內容和 ES `_id`。重新提交的 Ingestion 工作產生新的 `write_id`。

D-60 允許更新及清理期間查到新舊混合。驗收案例為舊批次 10 筆、新批次 6 筆。新版全部成功後只留下新 6 筆。若新版第 4 筆確認失敗，應保留舊 10 筆並清理本次所有實際成功的新 Chunk。另需覆蓋寫入逾時、舊資料刪除失敗與重啟後結果查核。

待定細節包括舊索引缺少 `write_id` 的遷移、清理方式與錯誤碼、未知結果的查核／隔離，以及重啟後如何辨識和清理未完成批次。參考 [Elasticsearch Bulk](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk) 和 [Refresh](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/refresh-parameter)。

<a id="src-21-83-已確認不加平台-query-讀寫鎖"></a>
### 已確認：不加平台 Query 讀寫鎖

D-60：使用者確認不採「寫入時禁止查詢」的共享讀寫鎖，讀寫各自執行；不為更新窗口加查詢等待、全域停讀、版本快照或分散式鎖。

接受的行為是：更新／刪除途中發出的 Query，可能讀到舊資料、新資料或短暫的新舊混合；已取得候選的 Query 也可能在 retire 完成後才回應。平台不保證一次 Query 看到單一文件／整個索引的原子快照，也不因正在寫入就排入等待鎖的隊列。實際後端的原生可見性／refresh／錯誤行為照其實作，不假造平台強一致保證。

這不撤銷已確認的 **同文件重複 Ingestion 忙碌拒絕**，它是寫入對寫入的排程規則，與查詢讀寫鎖不同。Ingestion 的成功／失敗仍逐文件記錄：沒有完整執行成功不得標 completed，已知失敗不得偽裝成功；清理與崩潰後恢復仍需 backend 定義。不再把「成功才發布」解讀成「新資料處理完成前，所有讀取都看不到任何變更」。

索引尚未建立／資源未就緒、Rate limit 或真實後端失敗仍按原 API 回應；正在 Ingestion 這件事本身不作為封鎖 Query 的理由。

<a id="src-21-84-已確認暫採單一-basic-帳號builder-登入延後"></a>
### 已確認暫採單一 Basic 帳號；Builder 登入延後

D-60：Runtime API 暫採 **HTTP Basic Auth（帳號／密碼）**，預設一組帳密可操作該 API service 對外提供的所有 API，包括 Ingestion、Query、Run／文件狀態、文件存在／ID 清單、retire 與對外 Health。此處限定在該 service 提供的 System／資料範圍，不代表同組密碼跨全部環境／其他服務硬編碼共用。

第一版不增加多帳號、角色、逐 API 權限或使用者 ACL 管理；同一組帳密通過驗證即可執行該服務提供的全部 API。服務端仍須使用正確 System 路由，不能把任意外部 Header 當作載入／選擇未提供 System 的授權。

採 HTTPS／TLS，帳密以部署環境 Secret 引用提供，不寫入 D／文件 metadata 或原始碼。具體驗證位置、Secret 包裝及內部 Probe 如何帶認證／探測仍待部署設計；不自行新增匿名對外 API 例外。標準依據：[RFC 7617](https://www.rfc-editor.org/rfc/rfc7617.html)。

Builder 的使用者登入方式之後再討論；不因 Runtime Basic 決策而替 Builder 加上登入流程，也不新增 OAuth／SSO 服務。User Remote API／模型／DB 的憑證是各自服務連線，不預設沿用 Runtime 對外帳密。

<a id="src-21-85-可信-system-路由與-s1-的意思d-64"></a>
### 可信 System 路由與 S1 的意思（D-64）

S1 是 system_id 示意：由 Builder Backend 建立並維護的穩定 Retrieval System 識別碼，在同一 Builder 管理範圍內唯一。它不是可變顯示名稱、Workspace 名稱、Config Revision、document_id 或索引集合名；System 改名或換 Config Revision 不因此換 system_id。實際 ID 格式／生成方式尚未凍結。

| 呼叫方向 | 規劃路由示例 | System／Config 選擇 |
|---|---|---|
| Builder UI → Backend | POST /api/systems/S1/queries | Backend 經可信管理關係選定目標 System；Builder 登入具體方案仍延後 |
| Backend → 共用 Runtime | POST /internal/systems/S1/v1/queries | 只供可信 Backend 存取且驗證認證；Runtime 查已註冊 S1 的有效配置，固定快照後執行 |
| 呼叫端 → FTEST／ENT | POST /v1/queries | 單 System Runtime 已載入配置，業務請求不需再帶 S1 |

七支業務 API 依同一內部前綴選 System，Request／Response 的業務語意不複製兩套；Health 仍是 service 級 /health/live／ready，不逐 System 複製。Builder 路由前綴為 /api/systems/{system_id}，共用 Runtime 為 /internal/systems/{system_id}/v1，完整 Backend CRUD／Config 註冊接口與 OpenAPI 另定。

路徑識別不能單獨充當授權；內部路由須受可信網路／Backend 存取與認證保護，不依任意外部 Header 載入配置。具體部署保護、Secret／Probe 接法仍待核定，Runtime 暫採單一 Basic 帳號的政策不變。工作狀態、文件管理與 Query 都遵守相同 System 作用範圍，不在業務 body 加入整份 Config／任意索引位置。Library 不讀 Builder DB。

<a id="src-21-9-文件資料查詢與直接刪除"></a>
## 文件資料查詢與直接刪除

<a id="src-21-91-資料來源與工作狀態不同"></a>
### 資料來源與工作狀態不同

這裡的 DB 是該 System 綁定的文件資料／索引後端，可能是 Elasticsearch、Local Memory、MongoDB 配本地搜尋或支援協定的 Remote Service；不要求為了查 ID 新增一個中央 DB。查詢反映目前後端可見的文件資料；若正有更新，依 D-60 可看到更新中的結果，不用工作 completed 當作讀取閘門，也不把「有資料」當成這次工作成功。

預設儲存單位是 Chunk，透過其 document_id 判斷存在與去重列出文件，不要求額外長期保存解析階段的 Document。實際後端可用適當 metadata／catalog 加速，但必須與資料一致，不能以 Runtime 的工作紀錄當成唯一依據。API-D07 保留實體布局與查詢策略的實作選擇。

| 問題 | 查詢位置 | Runtime 重啟後 |
|---|---|---|
| 最近一次 Ingestion 是否成功／失敗 | Runtime 記憶體工作紀錄 | 無紀錄為 unknown |
| 文件目前是否存在／有哪些 ID | System 實際文件儲存／索引 | ES／MongoDB 等持久資料仍可在後端就緒後查；Local Memory 資料若已遺失則清單為空 |
| retire 是否刪掉文件資料 | 直接刪除對應儲存、索引與本地搜尋副本 | 不能只清記憶體索引而保留供重建資料，否則可能重啟復活 |

「更新失敗但舊版仍存在」可以同時得到 ingestion-status=failed、exists=true；「成功後已 retire」也可以同時是歷史工作 completed、exists=false。這些不是矛盾，不把狀態改成 retired 或抹掉成功紀錄來代替資料查詢。工作歷史仍按其記憶體保留政策清理。

<a id="src-21-92-存在查詢提案"></a>
### 存在查詢提案

GET /v1/documents/manual-001/exists

```json
{"document_id": "manual-001", "exists": true}
```

不存在時建議仍為 200 並回 exists=false。後端無法連線、尚未初始化或不支援操作時，應回可辨識錯誤，不回 false 偽裝不存在。這支 API 不回原始內容／Chunk／向量，也不表示最近一次工作成功。

<a id="src-21-93-文件摘要清單d-65-已確認核心"></a>
### 文件摘要清單（D-65 已確認核心）

GET /v1/documents?limit=100&cursor=...

```json
{
  "documents": [
    {"document_id": "manual-001", "source_revisions": ["v2"]},
    {"document_id": "manual-002", "source_revisions": ["v1", "v2"]}
  ],
  "next_cursor": null
}
```

D-65 採 documents[]＋next_cursor，取代早期 document_ids[]；每筆為 document_id＋source_revisions[]。直接查該 System 實際保存的 Chunk／ES／Local 資料，以 document_id 去重並分頁，一份文件不論多少 Chunk 都只列一筆。每筆 source_revisions 為實際 Chunk.source_revision 的去重集合：正常通常一版，更新中／部分寫入失敗可能多版。這不是最新成功版本或持久歷史，不依 Run／文件工作紀錄推定，不將單一 Chunk 的 source_revision 改成陣列。

每頁預設 100／上限 1,000、document_id 升冪、System 綁定 cursor 與不加快照先留為 [Runtime API／部署](06_runtime_api_and_deployment.md#src-22-4-文件摘要與分頁參數) 的候選規格；精確值、頁面排序、cursor 有效期與同時寫入一致性後續於 API-D07／OpenAPI 整理，不把它們當成本輪新核定。初版不要求全量 total、文件／Chunk 原文、metadata 投影或任意版本回復。

分頁只代表清單分批傳回。例如 250 份不同文件，每頁取 100 個 ID，可依 next_cursor 取得第 1 批 100、第 2 批 100、第 3 批 50；最後 next_cursor=null。每個分頁項目是一份文件摘要，包含該文件目前可見的來源版本；不是每個版本各占一筆，也不以 Chunk 數計算 limit。Client 可讀完所有頁取得當時可遍歷的清單。

後端實作可依布局選擇：ES 以可精確聚合的 document_id 欄位作去重，候選是 composite aggregation，使用回傳 after_key 接續頁面；不能只取前 N 個 Chunk hits 去重，就當作已列出所有文件；source_revisions 也不能只取任意首筆或被截斷的版本子聚合。Local 可由 Chunk store 的 document_id／source_revision 去重集合或一致維護的文件對照取得，MongoDB 模式使用實際保存的文件資料；不查 Runtime 工作表，也不需要為這個 API 再建中央目錄 DB。

ES 分頁聚合依據：[Composite aggregation](https://www.elastic.co/docs/reference/aggregations/search-aggregations-bucket-composite-aggregation)。具體 Mapping、排序、資料更新中的頁面一致性與效能仍由 Artifact／backend 驗證，不把方案寫成已實作。

<a id="src-21-94-retire-直接刪除"></a>
### Retire 直接刪除

Retire 刪除該 System／document_id 對應的 Chunk、vectors、全文／向量索引，以及供恢復／重建使用的持久儲存與搜尋副本。具體儲存布局由 Artifact／backend 決定，不因 ID 命名相同就刪除其他 System 的文件，也不要求刪除使用者傳入 URI 所指的外部來源檔案。

D-64 已確認同步完成並回 200，以 result 區分「確實刪除」與「確認原本就不存在」；取代早期 204 提案。同文件仍 queued／running 時回 409，不取消工作。回應核心如下：

```json
{"document_id": "manual-001", "result": "deleted"}
```

```json
{"document_id": "manual-001", "result": "not_found"}
```

not_found 只在已確認目標範圍沒有資料時使用，不能把 DB／索引未就緒、連線失敗或不支援操作當成不存在。後端 timeout、部分刪除或結果未確認時回對應錯誤，不回成功；具體 code、Remote 查核／重試／清理協定仍待 API-D架構／資料契約手冊。多個儲存／搜尋副本的清除以完整目標為準，不只刪一個 Chunk 就回 deleted。

刪除完成後新發起的查詢／exists／ID 清單應反映刪除結果；先前已取得候選的在途 Query 仍可能回傳舊資料，依 D-60 不加鎖或回收其候選。exists 應為 false，ID 清單不再列出該 ID。此處沒有 soft delete 標記或 restore；若需要再次使用，重新提交文件 Ingestion。Retire 不透過改寫 metadata／Query filters 來假裝完成實際刪除。

<a id="src-21-95-localremote-的能力配套"></a>
### Local／Remote 的能力配套

Document 管理是索引／儲存管理能力，不新增 Pipeline Module。平台可直接管理後端時由對應 storage／index adapter 提供操作；外部 Retrieval 的資料空間由外部服務維運。

平台只對受管理資料提供文件查詢、清單及刪除。能力不可用時明確回報，查詢就緒與文件管理能力分別驗證。

<a id="src-22-1-範圍與管理方式"></a>
## Runtime 設定：範圍與管理方式

本文件集中記錄 Runtime 的接收大小、Queue、併發、Rate、Deadline 及工作狀態保存參數。使用者已確認前輪建議的預設與做法，並要求有固定位置整理可調參數；下表為初始開發／測試預設，不代表已量測的正式容量或已實作設定功能。

- **設定歸屬 E：Runtime 環境／資源設定。**與 D 的演算法、Component 選用、Chunk 大小及搜尋 Top N 分開；後者仍見 資料契約手冊／各 Component Config Schema，不在此重複列出。
- **Builder DEV**：Admin／平台部署管理者提供預設與限制，Runtime 在後端執行控制。一般 Builder User 不透過每次 Ingestion／Query body 覆寫；不因本文件新增 Admin 設定頁。
- **FTEST／ENT**：部署管理者提供同一套 Runtime 設定，可以調整上限；使用相同實作，無須連回 Builder DB。
- 表中的參數路徑是文件用候選名稱。正式檔案名稱、JSON Schema／環境變數映射、載入／重載方式與 OpenAPI 仍待實作規格核定；不因此宣稱熱更新或零停機。若套用方式需重啟，仍遵守記憶體工作／索引遺失政策。
- Runtime 總量與每 System 限制同時生效，不把每 System 上限乘以 System 數量當成總容量；個別 System 差異化覆寫、User／Workspace 額外配額及公平排程另案。

<a id="src-22-2-已確認的初始預設"></a>
## Runtime 設定：已確認的初始預設

1 MiB＝1,048,576 bytes；大小以 bytes 計算，不以中文字數或 Base64 解碼前後混用。

| 候選參數路徑 | 調整內容／單位 | 初始預設 | 作用範圍 | 執行位置／語意 |
|---|---|---:|---|---|
| request.ingestion.max_documents | 每次提交文件數／份 | 100 | 單次 Ingestion Request | 對批次物件的非空 documents 計數；不是 Unit／Chunk 數，超限整批拒絕 |
| request.max_body_bytes | JSON HTTP body 大小／bytes | 20,971,520（20 MiB） | 單次 Runtime 業務 Request | 計入 JSON 與 Base64 編碼內容；HTTP 入口限制，不先接受後才當大小合格 |
| sources.max_file_bytes | URI／Base64 單份檔案大小／bytes | 10,485,760（10 MiB） | 每份來源檔案 | 以下載／解碼後內容計算；SDK resolver／相容 Component 限制。已超過此值的遠端來源可在 Worker 取得時失敗，不承諾 202 前下載完所有檔案 |
| ingestion.queue.max_waiting_per_system | 等待文件數／份 | 100 | 每 System | 只計 queued；執行中受 concurrency 控制，整批接收須一致預留容量 |
| ingestion.queue.max_waiting_total | 等待文件總數／份 | 500 | 整個 Runtime 程序 | 共用 Queue 容量，不是每 System 都額外取得 500 份 |
| ingestion.max_concurrency_per_system | 同時執行文件數／份 | 1 | 每 System | 不同文件可提高並行；同 document_id queued／running 仍拒絕重複提交 |
| ingestion.max_concurrency_total | 同時執行文件總數／份 | 2 | 整個 Runtime 程序 | 與每 System 上限共同控制；Worker 是排程概念，不要求新 Pod |
| ingestion.document_timeout_seconds | 單文件處理 Deadline／秒 | 600 | 每份已開始執行的文件 | 由 Worker 開始處理起計算；排隊等待不算入本值。逾時不等於 Remote 寫入已停止，未知結果依 API-D05 |
| inference.rate_limit_per_system_rps | 請求速率／次每秒 | 5 | 每 System | 在 Runtime 接收入口執行；具體計數／突發算法待實作，不新增未確認的 burst 參數 |
| inference.max_concurrency_per_system | 同時執行 Query 數／個 | 2 | 每 System | 同步查詢額滿直接拒絕，不進 Ingestion 的長工作 Queue |
| inference.max_concurrency_total | 同時執行 Query 總數／個 | 8 | 整個 Runtime 程序 | 各 System 共用總量，不以所有個別上限之和代替 |
| inference.timeout_seconds | 同步 Query Deadline／秒 | 60 | 單次 Query | 包含所選 Query Transformation／Retrieval／Fusion／Rerank 的整體執行；上游逾時與失敗不可偽裝成功 |
| status.retention_seconds | 可回收終態工作紀錄保存時間／秒 | 86,400（24 小時） | Runtime 記憶體工作紀錄 | 按 Run 與逐文件對應一起清理，queued／running 不因 TTL 被移除 |
| status.max_terminal_documents | 可回收終態文件紀錄上限／份 | 10,000 | 整個 Runtime 程序 | 計文件工作，不是唯一 document_id 數；超過時間或數量限制時清最舊已結束 Run，保留完整 Run／文件關聯 |

數值須為有效正值；份數、bytes、併發數及紀錄數為正整數。每 System 的 Queue／併發上限不得超過對應 Runtime 總上限。完整驗證錯誤、設定格式與套用接口留 Q-002／Q-017／Q-019，不把候選路徑當成已發布機器 Schema。

HTTP body、檔案及文件數限制各自生效。例如單個 Base64 檔案解碼後低於 10 MiB，不代表多份檔案合計一定低於 20 MiB Request 上限；JSON content 仍受 body 限制，Parser 可另宣告更嚴格內容限制。

<a id="src-22-3-容量失敗與保存行為"></a>
## Runtime 設定：容量、失敗與保存行為

- 接收時先做整批快速預檢、同文件忙碌檢查及容量預留，再建立 Run／queued 狀態並回 202。不做部分入列；來源取得、昂貴 Parsing、Embedding／Indexing 仍由 Worker 執行。
- 每 System 配額／Rate 額滿與 Runtime 整體無容量要可區分；21 的 HTTP／錯誤碼表仍需完整 OpenAPI 對齊，不因本表凍結所有錯誤 code。
- Inference 使用同步入口，額滿直接拒絕，首期不新增短等待 Queue 或 async Query 工作 API。
- 完成、失敗與可安全回收的 Run 以時間與數量雙重限制保存，任一到達即清理最舊已結束 Run；不能只刪文件最新對照卻留下錯誤 Run 彙總，或無界保存全部歷史。
- 查無工作紀錄回 unknown；狀態保存不等於索引保存。Runtime 重啟仍不恢復工作，即使 24 小時未到也可能查不到紀錄；ES／MongoDB 資料可能仍存在。
- Remote 寫入結果不明時不自動重試，也不因記錄清理推定副作用不存在；unknown 紀錄回收、再次提交及查核仍沿用 API-D05。10,000 是可回收終態紀錄控制，不是整個程序記憶體 bytes 配額。
- 調整併發須驗證 Component、Client 與索引的安全性；本文件不取消 D-60 的無 Query 讀寫鎖政策，也不新增分散式 Queue／多副本一致性承諾。

<a id="src-22-4-文件摘要與分頁參數"></a>
## Runtime 設定：文件摘要與分頁參數

D-65 已確認摘要回應為 documents[]＋next_cursor，每筆 document_id＋source_revisions[]，由實際 Chunk 去重彙整；source_revisions 不代表最新成功版或版本歷史。下列分頁參數先留候選規格，後續定稿，不混入 [Runtime 控制相關章節](#src-22-2-已確認的初始預設) 已確認的 14 項 Runtime 控制預設：

| 候選參數／規則 | 前輪建議 | 狀態 |
|---|---|---|
| documents.list.default_limit | 每頁 100 份唯一 document_id 的摘要 | 待確認 |
| documents.list.max_limit | 每頁最多 1,000 份唯一 document_id 的摘要 | 待確認 |
| 文件清單排序 | document_id 升冪 | 待確認 |
| Cursor | Runtime 產生、綁定目標 System；最後一頁 next_cursor=null | 待確認 |
| 清單一致性 | 不加快照；分頁途中更新資料可能改變清單 | 待確認 |

分頁分批取得文件摘要清單，不改變 Ingestion Batch、Parser Units、Chunking 或 Retrieval Top N。例如已有 250 份文件，每頁 100 份時，依序取得 100、100、50 筆摘要；一份文件即使有多個 Chunk 或來源版本，也只列一次，各版列在該筆 source_revisions。API／來源與候選格式見 [Runtime API](#src-21-2-api-清單7-支業務-api2-支-health-api)。

<a id="src-22-5-文件維護與驗收待辦"></a>
## Runtime 設定：文件維護與驗收待辦

之後新增／修改 Runtime 控制參數，需在本表記錄名稱、單位、預設、作用範圍與執行位置，並同步環境設定 Schema、驗證及部署說明；目前尚未交付該機器 Schema／實作。模型／HTTP Client 的逐次 timeout、重試及檔案暫存保存規則若另行定案，再納入對應表，不把它們假裝已由整體 Deadline 完整決定。

實作驗收至少覆蓋：文件數／body／來源大小邊界、整批容量預留、每 System 與全域限制同時生效、Query 額滿拒絕、處理逾時、終態 Run 整組清理、活躍工作不被 TTL 清掉、重啟 unknown，以及 Builder DEV／FTEST／ENT 使用相同控制。這是未來驗收要求，不是已通過的 Runtime 測試。

<a id="src-07-6-非同步工作與一致性"></a>
## 排程、同程序 Memory 與一致性限制

D-56 已確認：Builder DEV 與 FTEST／ENT 共用 Runtime 工作控制，Library 執行流程；Builder 上傳與直接呼叫 API 走同一 Queue，不再重複排一次。每 System 文件執行併發可配置、預設 1；Runtime 再設總量，Inference 有頻率／併發／Deadline。D-64 已確認初始預設與管理方式：E 的 Runtime 環境設定，由 Admin／部署管理者控制，不由每次文件／Query 任意覆寫；完整可調項、單位與作用範圍集中見 22，正式參數路徑／機器 Schema 與載入方式仍待核定。

Batch 逐文件處理；併發 1 時依序，併發 2 時不同文件可同時處理。相同 (System, document_id) 已 queued／running 時拒絕再次提交。支援提高併發仍需驗證 Component／Client／共享索引的安全性，必要的同文件寫入互斥與資源安全由執行實作處理，但不加阻擋 Query 的共享讀寫鎖；不承諾任意 backend 可無限制並行。

每份文件完整替換。ES 的寫入、失敗清理及查詢可見性依 [Elasticsearch 文件覆寫](#elasticsearch-document-replacement)。Runtime 重啟丟棄 Queue／工作狀態，舊 `run_id` 查詢為 `unknown`。既有索引可依相容性接回。逾時或崩潰後的未確認寫入須先查核，才可判斷是否重送。

Local Search 第一版仍同程序／單副本。背景執行不能把唯一 Memory 索引放在會退出的獨立 Job，也不能 fork 多個 worker 期待共享 Python 記憶體。這裡的 Worker 是執行排程概念，不要求新增 Pod；精確執行模型需測試。

尚待 Q-008～Q-010／Q-015／Q-017／Q-019：

- 21 的 counts／錯誤 Envelope 與文件管理細節；批次物件、整批預檢、Run partial 與 retire 直接刪除方向已確認。
- ES 文件覆寫順序已定，仍待驗證清理失敗、未知結果查核及崩潰後殘留處理。其他後端的寫入與搜尋可見性另議。
- 固定快照、System 切版／卸載及持久索引相容規則見 [System 管理](#src-07-4-systemrevision-與-engine-生命週期)。一般寫入與 Query 依 D-60 併行，未知寫入與失敗清理仍依 API-D05 追蹤。
- 未知遠端寫入已確認不自動重試；具體結果查核、同文件隔離、Idempotency-Key／版本控制及清理仍待定。進度管控及取消另議。
- Queue／並行／Rate／Deadline／紀錄保留初始值已依 D-64 記於Runtime 控制手冊；尚待正式設定 Schema／載入方式、未知紀錄清理與未來多 replica 一致控制。

方向已確認不表示提交機制已實作；詳細盤點與待決子項見 Runtime API／部署。

<a id="src-07-7-local-search-恢復與儲存"></a>
## Local Search 恢復與儲存

| 模式 | 重啟 | 正式要求 |
|---|---|---|
| Memory | Chunk／向量／搜尋結構遺失 | 回需要 Ingestion；不回示意檢索結果 |
| MongoDB | 讀保存的 Chunk／vectors／Manifest 重建 | 驗證 Config／Profile／資料版本，完成前不提供不完整索引 |
| ES | 檢查既有 Index 的歸屬、指紋、mapping 與可用性 | 相容時接回，確認不存在時建立空索引並接受 Ingestion。衝突與暫時不可用分開回報。 |

MongoDB 保存不等於跨 Pod 索引同步。重建失敗、DB 中斷、Profile 不符、損壞資料及大資料量啟動時間見 Q-012／Q-027。原始檔／解析結果 若未保留，不保證可自動重新切分／Embedding。

<a id="src-07-8-evaluation-與-ai-助手服務"></a>
## Evaluation 與 AI 助手服務

另有待確認的 Query Rewrite 單模組測試提案，見 [Builder UI／Backlog](07_builder_ui.md#src-06-331-討論提案query-rewrite-單模組測試)／UI Backlog手冊 UIB-007：若採用，Backend 以請求草稿呼叫相同 Engine 模組／LLM Adapter，測試不依賴已保存 System 或索引。認證、服務引用與逾時規則仍需核定；接口精確路徑／Envelope 留 Q-019，不新增已凍結的公開 Runtime API。M2 可先由 SDK 驗證模組，Builder 入口屬 M5；Mock 與真實呼叫分開驗收。

Evaluation Runner 於 M6 交付完整驗收，綁定 Dataset／Config／Index／Engine／Judge 版本，逐題呼叫同一 Target，收集實際 ResultSets／排名／來源／錯誤後交 04 評分。重用相同 Retrieval-only Query API；不收集生成答案或做答案正確性評估。併發、快取、重試、成本與 Gate 見 Q-018／Q-027。

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
- 選定 System／Revision 的相同邏輯 Config，及另存的目標環境部署設定；不能把 URL／Secret 差異當成不同處理邏輯。
- ConfigMap／Deployment／Service 等 K8s 設定及 Secret references。
- FTEST／ENT 的環境檔案、啟動與 API 說明、資料準備步驟。
- 若有評估報告，清楚綁定測試環境／資料版本，不能宣稱目標環境已驗證。

Remote API 匯出目標環境的連線／Secret 引用。

不含 Image 本體、真實 Secret、原始文件、Chunk／vectors、Builder DB 或外部 DB／模型資料。目標環境需有相容資料或執行 Ingestion；部署後仍可持續 API 匯入。

Local Search 的持久化模式沿用同版 Config：DEV 為 Memory，FTEST／ENT 也為 Memory；Export 只補齊該模式所需部署綁定，不將 Memory 切成 MongoDB。MongoDB 模式可填不同環境的 URI／Secret／DB／Collection，實際資料不隨匯出搬移。

<a id="remote-service-deployment"></a>
<a id="src-07-911-remote-service-manifest-與環境綁定"></a>
### Remote API 與環境綁定

同版邏輯 Config 使用環境 Endpoint、認證與 Secret 綁定。認證欄位支援固定 Secret reference 或 `{{params.remote_secret_ref}}`。Runtime 使用本次已驗證的 secret_ref 參數，檢查系統使用權限、解析並注入 Header。認證值與業務 Document、Remote parameters、模板、索引及記錄分離。匯出包含 Runtime 與外部依賴引用，外部服務維運由服務提供者負責。

<a id="src-07-92-驗證與部署"></a>
### 驗證與部署

狀態分開：needs_configuration → configured_unverified →（外部連線／資料檢查結果）→ 實際部署結果。本文不指定未核定的完整狀態枚舉；不能用 configured_unverified 表示可直接部署成功。

Local Search replicas=1 且單 API worker；ES 是否多副本需驗證工作／權限／版本策略。resource limits、Probe、TLS／Ingress、CD 工具與 FTEST／ENT 命名見 Q-021／Q-027。

Secret Vault 位於 Runtime 外，以環境支援的解析／注入方式提供；`secret-name/key` 為目前示意引用。正式產品、SDK、檔案掛載路徑與更新政策 Q-021。URL、Header、Trace 與匯出均不得內嵌帳密。換 Embedding Profile 要回 Engine 重建，不能只在匯出改模型 ID。

<a id="src-07-93-獨立啟動"></a>
### 獨立啟動

建議步驟：讀選定 Config Revision＋該環境部署設定 → 解析服務／資料綁定與 Secret → 04 驗證 Config 快照／準備 Component 及資源 → 驗證資料／恢復索引 → 啟動 HTTP，以共用 Executor 執行該配置。Live／Ready 與 IndexReady 分開。相容索引可查詢後即接受 Ingestion 和 Inference，空索引回成功空候選。部署後 Config 更新可先經重新部署，熱更新／零停機另案。

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

每個完整 Runtime Image 應可追溯同一 rag_engine 交付來源、SDK／Engine／Component package 版本與依賴鎖定結果。同 repo 可以讓它們一起驗證，並不抹去各自的契約／實作版本。既有 System 可維持鎖定版本，新版發布不自動觸發所有 DEV／FTEST／ENT 升級；欲交付的選定版本應完成 DEV 驗證，再由使用單位以同一 Runtime Image／邏輯 Config 補齊環境設定進行部署。

Runtime 更新若重啟 Memory 模式，依既有規則需要重新 Ingestion；MongoDB／ES 依索引與版本相容性恢復。重建、快照、切換與回復仍依 Q-008～Q-010／Q-015，不因兩個 repo 分工就新增熱插拔 Component 或零停機升級承諾。

<a id="src-07-10-observability認證與權限"></a>
## Observability、認證與權限

request／run／trace 必須可跨 Backend／Runtime／模組關聯。輸出結構化錯誤、耗時、輸入輸出數及可取得用量；模型與 Judge 也記版本。OTel／Langfuse 為候選，非每個 Runtime 必備外部依賴，具體方案 Q-016／Q-027。

Builder 使用者登入與文件／檔案級 ACL 延後討論，見 Q-006。可信 Backend 與 Runtime 負責 System 存取範圍。MCP 固定 API key 對應可操作的 System 與工具，Runtime 依授權列出工具並在呼叫時驗證。獨立 Runtime 採部署端認證。模型與 DB 的連線憑證由各服務綁定提供。

<a id="src-18-5-執行實例儲存與資料共用"></a>
## 外部 Retrieval 就緒與資料責任

搜尋自有資料的 Remote Retrieval 可直接查詢，不需要平台 Ingestion 或 IndexBinding。Runtime 仍驗證每筆候選 Document 是否符合 System 的有效 Ingestion 輸出 Schema，後續內建 Rerank 使用同一欄位規格。外部服務負責其資料空間及授權。平台的文件狀態、清單及刪除僅處理平台管理的資料。若 Remote 接管 Query Transformation 到 Rerank 的整段流程，Runtime 驗證外部回應與候選契約，按服務回傳的排名交付。見 [Remote 執行邊界](03_engine_and_components.md#remote-api)。
