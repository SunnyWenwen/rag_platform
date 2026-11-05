# Retrieval Builder — Backend、Runtime API 與整體串接規格

> 文件同步：2026-11-05 · 開發規格草案（正式 SDK／Config 尚未凍結）
>
> D-56 已確認文件級覆寫、統一 Queue／Inference 流量控制、記憶體狀態與重啟不恢復。API 詳細盤點、回應範例及未決子項集中於 [21](21_runtime_ingestion_inference_api_inventory.md)；新增路徑／Envelope 仍是提案，Prototype 未改。
>
> 本文包裝 04 的 Engine，負責管理、HTTP、任務、持久化與交付。Endpoint 大方向沿用既有提案；精確 Envelope、認證、狀態與儲存細節為建議，依 Q-ID 核定後實作。

## 1. 責任邊界

Engine／Runtime／System、Config／部署設定及版本概念以 [03 §3](../03_architecture_proposal.md#terminology) 為準；本文描述對應的服務、API 與生命週期，不另創領域定義。

| 層 | 責任 |
|---|---|
| [04 Engine](04_module_components_io_contracts.md) | Config 驗證／編譯、模組初始化、Pipeline 組裝、Ingest／Query 執行及領域錯誤 |
| AI 設定助手核心（M4） | 不依賴 Builder 的需求／樣本＋Config 建議能力；引用共用 Schema／Registry／Validator，提供 Python／API 入口 |
| Builder Backend（M5） | System／Revision／Workspace、授權、服務目錄、Dataset、助手呼叫／UI 草稿基準、Evaluation Job、Export |
| Runtime API | 將 HTTP 請求轉成 05 型別，呼叫相同 Engine 與核定 Fusion Plan，包裝 Job／Query／Health |
| Runtime 內部管理 | 可信地綁定 System／Revision、建立或更新 Engine 實例；不開放任意外部使用者換租戶 |

Engine 可直接由 Python Config 使用，不能反向 import Builder Web App 或存取 Builder DB。UI、Runtime API、外部 Evaluation 使用同一核心流程，不複製一套模擬／真實 Pipeline。

助手核心也不得反向依賴 Builder UI／DB；獨立呼叫接受需求、明確允許的樣本及可選的既有 Config／基準識別，不以 Builder System ID 為必要條件。Builder Backend 負責把可信 Workspace／System 資訊與 UI Draft 轉成相同助手輸入，再將建議對回草稿。這是邏輯責任拆分，不要求獨立部署成多個微服務。

兩種環境：共享 DEV Runtime 由 Builder 的可信路由選 System；獨立 Runtime 啟動時綁定一個 System／Config。相同 API 語意不代表相同 Base URL、權限或資料。確切多 System 路由／內部管理接口見 Q-019／Q-020。

<a id="repository-build-boundaries"></a>

## 2. 兩個 repo、程式依賴與建置邊界

2026-10-28 已確認 repo 邊界，正式定義見 [03 §3.7](../03_architecture_proposal.md#repository-boundaries)。以下內部路徑仍是 Q-001 的建議配置，不是已建立的程式或額外 repo：

| Repo | 路徑草案 | 職責 |
|---|---|---|
| rag_platform | `apps/builder_ui/` | 06：正式 Builder UI |
| rag_platform | `services/builder_backend/` | System、Revision、Dataset、Export、Runtime Client 與助手 UI 請求協調 |
| rag_engine | `packages/sdk/` | 05：公開型別／Contract；04：Module 介面、Config／RunContext 與開發工具 |
| rag_engine | `packages/engine/` | Compiler、Registry、Pipeline 與執行政策；具體方法實作放 components |
| rag_engine | `components/` | 各 Module 的內建／客製 Component packages、相關 Adapters、能力宣告與測試 |
| rag_engine | `services/runtime_api/` | HTTP／Job／Engine lifecycle、可信管理與能力目錄接口 |
| rag_engine | `packages/config_assistant/`（建議） | M4 可獨立使用的助手核心，重用共用 Schema／Registry／Validator；M5 由 Builder 串接 |
| 各 repo | `tests/`、`examples/`、部署建置檔 | 各自測試與跨 repo 契約整合範例 |

執行時 Builder UI → Builder Backend → Runtime API → Engine → SDK／Components。Engine 與 Component packages 都依賴 SDK；SDK 不反向依賴 Engine 或 Builder。Builder 可以使用核定版本的共用型別／Client 作本地格式預檢，方法能力與完整 Config 驗證仍以目標 Runtime 的同一 Engine 為準，不安裝全部 Components 或複製組裝邏輯。

Component 開發在 rag_engine 的 components 目錄提交 PR；同 repo 的 CI 驗證 SDK／Engine／Components／Runtime API，產出完整 Runtime Image。rag_platform 依 Frontend／Backend 的服務邊界產出 Builder Image。Repo 數量不限制 Image 數量，也不要求每個方法各建一個服務。建置可使用多階段或內部基底，但正式交付不依賴另一個 rag_components repo 組裝。

M4 助手核心的建議位置在 rag_engine，以便使用相同 Registry／Validator；它仍可透過 Python／API 獨立執行，不需啟動 Builder 或存取 Builder DB。HTTP 宿主、套件可選依賴與 Image 包裝由 Q-001／Q-019／Q-024 核定，不要求 FTEST／ENT Runtime 一定啟用或攜帶助手。M5 保留 UI 草稿、Diff、套用／取消與授權整合的責任，階段順序不變。

技術版本、精確套件名稱／目錄、FastAPI 等 Web Framework、資料庫及建置工具仍待 Q-001／Q-016；已確認的 repo 分工不再列為待選方案。跨 repo 通訊的接口相容、Component 目錄及升級規則見 §5.8／§9.4。

## 3. 平台管理資料與儲存

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

原始檔、ParsedDocument、Prompt／Context Trace、評估報告保留與刪除規則仍見 Q-016。Ingestion Queue／Run／文件狀態的跨重啟方向已由 D-56 確認不保留；Builder 若另存歷史摘要，不能拿來覆蓋 Runtime 的 unknown 或宣稱工作已恢復。歷史評估報告不因新 Config 失效就自動刪除。

## 4. System／Revision 與 Engine 生命週期

### 4.1 建立與啟動（建議流程）

1. Backend 驗證身分與 Workspace 權限，建立 system_id，依 05 的既定自動命名方向建立穩定 collection；不要求 UI 使用者手填。
2. 收到 Draft，以目標 Runtime 的共用 Config 編譯／Validator 檢查有效設定，回傳錯誤與變更影響；本地格式預檢不取代完整驗證，接口依 §5.8 核定。
3. 保存 Config Revision；以可信管理呼叫要求 Runtime 綁定配置。
4. Runtime 呼叫 04 Engine 初始化；服務解析、Profile 與資料就緒分開回報。
5. UI 可執行 Ingest／Query；沒有索引時 Query 回明確不就緒。

共享 Runtime 不代表每建立 System 就新建 Pod。實例快取、資源配額、LRU／釋放、租戶隔離與同時工作限制見 Q-020。

### 4.1.1 Remote Image／External 的生命週期

D-51 下，Local 可在同程序／Pod 建立多個 System。Remote Image 每 System 額外建立獨立服務實例，整段不逐 Module 起 Pod；Backend 協調部署機制注入設定檔與 Secret 引用，建立 Deployment／Service、健康檢查並自動解析 Endpoint。記錄 System／Revision 與部署的對應，更新、失敗回收及停止／刪除時清理受管理資源；Ready 前阻止相依操作。具體控制介面、清理及儲存保留政策留 Q-017／Q-020／Q-021。

Remote External 不由 Builder 啟動／重啟；Developer／管理者登錄 Endpoint／認證並做相容／連線檢查，User 只選服務。該模式固定存取既有資料空間，平台不加 data_space_id、不承諾多 System 自動隔離。無狀態服務無儲存需求；Image 有儲存時必須透過啟動綁定分配獨立範圍，不以 Pod 獨立當作資料隔離證據。見 [18](18_remote_service_pipeline_integration.md)。

### 4.2 Config 更新

獨立 Runtime 初期透過重啟／重部署套用 Config，不做執行中熱切，見 21 §8.1；這可避免單一存活實例混讀不同 Config，但持久索引相容性與 Remote 在途寫入仍需處理。Builder 共用程序的更新範圍另決：整個程序重啟會影響其餘 System 的記憶體資料／工作，建議只重建目標 System 實例；何時切換／是否等待工作完成不在本輪宣稱已完成。

Backend 儲存前以有效設定比較，依 05 判定影響；UI 與 AI 都不能繞過。Edit 使用獨立草稿，取消不生效。

2026-10-30 Chunk 草案：Embedding／Indexing／Inference 共用 [15](15_chunk_contract.md) 與 [Chunk Schema](../schemas/chunk.schema.json)；來源位置若有提供則在 metadata._rag.source_refs（D-52：追溯選填），向量仍為具 Profile 識別的物件。該資料不改 API／Parser 的 IngestionDocument 輸入，也不核可直接匯入 Chunk／vectors。D-56 已確認文件級成功替換／失敗不發布半份新版；具體索引提交、崩潰可見性與 Config／索引版本切換仍依 Q-008～Q-010／Q-015 落實，不能由 Hash 就宣稱已實作。

2026-10-16 的內容保存簡化：Indexing 保存全部 Chunk.fields／metadata，Chunking 預設繼承全部有效業務 metadata；只選全文／向量／Filter 能力。原型的 indexing.stored／chunking.metadata 是待遷移的舊保存／繼承投影，不能直接套用為新規則。Metadata 全繼承仍保留可信 ACL／來源及 Schema 驗證，Memory／MongoDB 的持久化模式不變；保存內容也不等於全部內容回傳給 API，回傳與授權投影另外處理。

**待決的發布模型**：

- 建議分開 saved_revision、active_revision、index_generation，查詢綁定可用的相容版本。
- 可選第一期簡化為新版 Ingestion 改動後阻止查詢，重建完成才啟用。
- 或允許舊 Revision 繼續服務，待新版完整成功後切換。

兩者對 UI、併發及儲存差異很大，Q-010／Q-015 未核定前不能自行承諾原子切換／零停機。僅修改 Prompt／Retrieval 等 Inference 設定不重建，但仍記錄新版本並重新評估。

## 5. API 契約

### 5.1 Builder Backend（Control Plane）

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

### 5.2 Runtime API

D-58 更新為 7 支業務＋2 支 Health：統一 List 提交、文件存在／ID 清單查詢及 retire 直接刪除均已確認；完整管理 API 路徑／Envelope、同步刪除建議等仍待整理，見 [21](21_runtime_ingestion_inference_api_inventory.md)。

| HTTP method | Path 草案 | 行為 |
|---|---|---|
| POST | /v1/ingestions | 根層非空 IngestionDocument[]，單筆亦為一元素 List；整批預檢通過才 202＋run_id／Location |
| GET | /v1/ingestions/{run_id} | 一次提交及逐文件結果；Run partial 已確認，精確格式待 API-D02 |
| GET | /v1/documents/{document_id}/ingestion-status | 該 System 文件最近一次工作狀態；無可用紀錄為 unknown，不等於文件不存在 |
| POST | /v1/queries | query／filters／metadata；200 直接回 QueryContext[]；同步限流／併發／Deadline |
| GET | /v1/documents/{document_id}/exists | 讀取實際儲存判斷文件存在；回應格式為 21 草案，不從工作表推算 |
| GET | /v1/documents?limit=...&cursor=... | 去重分頁取得當前全部 document_id；排序／cursor 細節待定 |
| POST | /v1/documents/{document_id}:retire | 已確認直接刪除文件儲存／索引；建議同步 204，精確 HTTP／互斥與 Remote 配套待確認 |
| GET | /health/live | 程序是否存活 |
| GET | /health/ready | Runtime／必要資源是否初始化；不等同已有可查索引 |

獨立 Runtime 的業務請求不另帶 System ID；配置已綁定。Builder DEV 的可信路由先選 System，不能直接信任使用者提供的 tenant／system header；Run／文件狀態查詢也需驗證相同 System 權限。Retrieval API 暫按使用者的 basic oath 理解為 HTTP Basic Auth（帳密），採 HTTPS／TLS 與環境 Secret 引用；若原意為 OAuth 需再對齊。Basic 的檢查位置／帳號作用域尚待細化；Authorization／共享 System 路由仍見 Q-006／Q-019，Builder 登入方式延後。

Retire 納入首期能力；排隊／執行中文件取消確認首期不做。文件 ID 清單與存在查詢已納入；整份文件／Chunk 內容、索引診斷與單步測試仍未納入，見 21 §7／§9。

### 5.3 JSON Ingestion

2026-10-29 更新：Runtime 只提供 JSON Ingestion。單筆文件以 document_id＋content／base64／uri 三選一表示，欄位與解析責任見 [13](13_ingestion_parser_input_contract.md)，機器可讀 [JSON Schema](../schemas/ingestion_document.schema.json)。以下展示已確認的 List body，內含單份 IngestionDocument；單筆也包 List。每筆文件與 Parser input 共用相同 Schema，Parser 不收到 List／run_id；整批預檢通過才入列已確認，數值上限待定。

```json
[
  {
    "document_id": "manual-001",
    "source_revision": "v1",
    "content": {"text": "設備每月需清潔散熱孔。", "title": "保養規範"},
    "metadata": {"department": "manufacturing"}
  }
]
```

content 由相容 Parser 轉成 ParsedDocument.units；可接收已解析內容，但須符合對應 schema／Adapter，ParsedDocument 已有 [0.2 units 契約與驗證範圍](14_parsed_document_contract.md)，尚未凍結；不代表 Runtime 已載入這些 Parser。API 外層不直接宣告 fields／structure／vectors。**API 每個 List item 與 Parser Input 使用同一份 IngestionDocument JSON Schema（D-45／D-58）**，Parser 專屬內容限制再驗證。Parser 透過 SDK 共用 resolver 取得／解碼內容，不另要求轉成另一份 ParserInput；Context 為 Engine 注入的執行資源，不是 HTTP body。

Runtime 驗證分層，不以 API 外層通過就宣稱資料可搜尋：

| 交接位置 | 必須檢查 |
|---|---|
| 接收／Import → Parser | 13 的共同外層、單一來源、授權／資源限制及 Parser 專屬內容／路由能力 |
| Parser → Chunking | 14 的四鍵 Units Schema、Unit／位置語意、System 欄位宣告及 Chunker 相容能力 |
| Chunking → Embedding | 15 的六鍵 Schema、來源身分、有效 metadata、來源 refs／切分計畫、必要任務非零產出；vectors={} |
| Embedding → Indexing | 同一 Chunk，命名向量 values／Profile／來源／維度與 Binding 一致；純全文可略過 Embedding |
| 索引發布 → Retrieval | 完整 Chunk 的保存與可查詢版本狀態；回傳投影可 vectors={}，不能丟失下游所需內容或可信引用 |

錯誤須含模組、文件及可定位欄位／task_id。D-56 已確認不同文件獨立結果、文件級成功發布；Batch Run partial 的彙總 Envelope、實體索引提交與 HTTP 錯誤映射仍待 Q-009／Q-019，不以參考資料驗證器取代正式執行實作。

```json
{"run_id":"ing-001","status":"queued","config_revision":"C1-example"}
```

以上 202 只表示接受；回應前須完成授權、外層與必要同步預檢、容量／文件忙碌檢查，確保入列與記憶體紀錄一致。文件已 queued／running 時拒絕重複提交；完成／失敗後才可覆寫。Run／逐文件 receipt、Location 與 Batch 範例見 21；下載／昂貴處理延後至 Worker 的預檢界線為提案。Runtime 重啟後不恢復工作，202 不保證跨重啟完成；取得 run_id 不代表解析或索引成功。

### 5.4 Builder 上傳與自行部署

Engine 不提供 multipart 上傳端點。Builder 可接收檔案／CSV，轉成 content、Base64 或可存取 URI 再呼叫相同 JSON API；自行部署的呼叫端負責相同轉換。檔案傳輸轉換不等於語意 Parsing，原始檔案內容仍需 Engine 有相容 Parser。

Builder 上傳管理端點、暫存儲存與下載授權／生命週期尚待 Q-016／Q-019；獨立 Runtime 不得因此強制依賴 Builder Object Storage。MIME、大小／逾時限制與實際格式偵測待核定；選擇多個 Parser 不代表所有檔案都可解析。

### 5.5 工作查詢

D-56 採兩種查詢：run_id 追蹤一次提交；document_id 查文件最近一次狀態。ID 直接來自 Request，預檢通過入列即有 queued 紀錄；執行失敗也保留 failed 紀錄，並非只有索引成功才記錄。預檢前拒絕不建立新工作，直接回 HTTP 錯誤。Runtime 記憶體保存 Run／逐文件紀錄及最新對照，不把工作狀態寫入 Chunk／metadata，不從已儲存資料反推最近一次更新是否完成。

文件狀態為 queued／running／completed／failed；無可用紀錄或結果未確認為 unknown，後者須有可辨識原因。completed 代表該文件完整發布；Batch 不得用 completed 掩蓋部分失敗。Run partial 與無紀錄 HTTP 200＋unknown 已確認，counts／其他精確欄位仍待 [21 §4](21_runtime_ingestion_inference_api_inventory.md) 定義。

```json
{
  "document_id": "manual-001", "run_id": "ing-001", "status": "running",
  "module": "Embedding", "updated_at": "2026-11-05T08:30:00+08:00", "error": null
}
```

Batch 計數提案以收到的 IngestionDocument 為單位，不混入 Unit／Chunk 數；各計數拼字／彙總終態待 API-D02。舊 processed_documents／total_documents 示例不作正式欄位依據。

只清理可回收的終態紀錄；queued／running 不提前清除。保留時間／數量上限尚待設定。重啟後無紀錄回 unknown，不憑 ES／MongoDB 中有舊資料就宣稱最後那次工作成功。此政策不等於所有索引也清空，更不保證遠端寫入自動回滾。

文件存在／ID 清單與 retire 另見 21 §9：直接讀取／刪除該 System 的資料儲存與索引，不以 IngestionRun 當作文件目錄。retire 後歷史 Ingestion 狀態可仍為 completed，exists 卻為 false；工作紀錄按原政策清理，避免混用兩種狀態。後端不可用時不回 false／空清單，Remote 需對應管理能力。

### 5.6 Query

```json
{"query":"設備多久需要清潔？","filters":[{"field":"metadata.department","operator":"eq","value":"manufacturing"}],"metadata":{"language":"zh-TW"}}
```

query 必填；filters／metadata 選填，預設 []／{}。Runtime 先驗證 Filter 能力，與 System 預設全部 AND，建立一筆初始 QueryContext，再將 QueryContext[] 交給 Library。可信 ACL 由 Context 注入，額外限制候選；不能用 metadata／filters 放寬授權。Rewrite 複製 filters／metadata，不讓 LLM 改寫它們。

200 成功 body 直接是 QueryContext[]，以下為完整形狀示例（資料與分數為手動示意）：

```json
[
  {
    "ori_query": "設備多久需要清潔？",
    "query": "設備多久需要清潔？",
    "filters": [],
    "result_sets": [
      {
        "key": "es-hybrid",
        "items": [
          {
            "chunk": {
              "chunk_id": "c1",
              "document_id": "manual-001",
              "source_revision": "v1",
              "fields": {
                "text": "設備每月需清潔散熱孔。",
                "title": "每月保養"
              },
              "vectors": {},
              "metadata": {
                "department": "manufacturing"
              }
            },
            "score": 5.84
          },
          {
            "chunk": {
              "chunk_id": "c2",
              "document_id": "manual-002",
              "source_revision": "v1",
              "fields": {
                "text": "每週清潔濾網並記錄保養結果。",
                "title": "每週保養"
              },
              "vectors": {},
              "metadata": {
                "department": "manufacturing"
              }
            },
            "score": 4.47
          }
        ]
      }
    ],
    "metadata": {
      "language": "zh-TW"
    }
  }
]
```

Inference 的業務 Input／Output 統一為 `list[QueryContext]`（JSON root array），沒有 InferenceState 外框。QueryContext 固定 ori_query、query，並提供預設空值的 filters、result_sets、metadata。ResultSet 只有 key／items；ResultItem 只有 chunk／選填 score。只傳目前有效資料，處理後替換；歷史與診斷寫 Logs。items 順序就是排名，RRF 使用陣列位置。數值 score 經 Adapter 統一為越大越好，Sum Score 仍需驗證完整分數及可比性。

request_id／Config Revision 放回應 Headers／Logs 的提案位置；精確 Header 名稱與 HTTP 版本協商由 Q-019 定案，不為了記錄再造成功 Envelope。錯誤仍用 §5.7 的獨立 Envelope。跨 Query 未合併時回多筆 contexts／result_sets；空命中回空 items，不在 API 層額外融合或全域排序。原始問題保留在 ori_query。

ES 內部融合只回真正取得的 Hybrid 清單；平台不捏造分項排名。邏輯 Config／授權／資源由 Library 的可信 Context 取得，與業務 JSON 分開。這版為已確認開發 Contract，尚無可呼叫的 Prototype 後端；部署 URL、錯誤及發布細節仍見 Q-019。

### 5.7 標準錯誤

建議 HTTP Envelope：

```json
{"request_id":"req-001","error":{"code":"INDEX_NOT_READY","module":"Retrieval","message":"索引尚未就緒，請完成 Ingestion。","retryable":false}}
```

| HTTP | 領域例子 |
|---|---|
| 400 | 請求格式／Filter 非法 |
| 401／403 | 未認證／無權操作 |
| 404 | 不存在的工作／System |
| 409 | Revision 衝突、索引不相容或尚未就緒 |
| 503 | 必要外部服務不可用 |

這是草案而非完整錯誤碼表；422／413／429／504、錯誤陣列、lost Run 與重試提示見 Q-019。ModuleResult、HTTP error 與非同步 Run errors 各有層次，必須有明確映射；不能把 202 後的執行失敗當作 POST HTTP failure 重送。

<a id="runtime-capability-contract"></a>

### 5.8 Runtime Component 目錄與 Config 驗證邊界

兩個 repo 的服務透過 Runtime API 與 Component 目錄合作；實際路徑、認證與 Envelope 由 Q-019 核定，以下為需要覆蓋的介面能力，不新增已凍結端點：

- **方法與能力目錄**：提供目標 Runtime 的版本識別、核可 component_id／module_type／實作版本、相容 Contract、Config Schema、requires／provides 與支援的表單顯示資訊。Local 資訊應來自該 Image／Runtime 真正包含的內容；Remote 資訊來自核可 Manifest 與目標 Runtime 實際支援的 Adapter／範圍／協定，不把只有 repo 原始碼或只有 Manifest 的方法當成已 Ready。
- **完整 Config 驗證**：Builder／助手提交有效設定與目標版本，重用 Engine 的型別、跨模組相依與索引相容檢查；回傳可定位到 `[MODULE NAME]`／欄位的結果。格式有效、可組裝、服務已連通與資料可查詢分開，不把目錄查詢當成真實連線測試。
- **版本與目錄一致性**：目錄／Schema／驗證結果要能對回同一目標 Runtime 版本；Runtime 更新後，舊快取或過期驗證不得靜默套用。既有 System 保留所選版本，尚未安裝／不相容方法應明示，不自動取最新版。
- **相容範圍**：既有 API、Config Schema 與 UI 控制項足以支援時，新增 Component 可只發布／部署 Runtime；需要新型表單或破壞性接口時，需更新 Builder 並完成契約相容測試。目錄傳輸格式與欄位演進政策仍待 Q-002／Q-019／Q-025。

直接 Python 使用 Engine／M4 助手時仍可在本機取得同一 Registry／Validator，不因此強制所有呼叫都走 HTTP。平台整合使用公開服務邊界，Runtime 的可信管理與能力接口不等於允許外部一般使用者更改 System 綁定。

D-42 的 Descriptor、動態選項／能力 Context、規則與驗證回傳草案見 [12](12_component_schema_ui_contract.md)。除了靜態 Component 目錄，整合需提供依當前草稿／上游能力／授權解析的候選與欄位狀態；相依驗證與有效 Config 編譯由 Engine 統一處理，API 不另寫一套。服務 URL／Secret 綁定仍在部署設定，目錄／Context 不含憑證值。

設定檢查結果需對回 runtime_ref、catalog_revision、draft_revision、context_revision，錯誤使用 Module／節點引用／相對參數路徑定位。過期或取得失敗的結果不能沿用為新版設定驗證成功；建立／套用時再次核對版本。完整端點、Envelope、Context 型別及授權仍待 Q-019，12 不變更本文件的 Ingest／Query 公共 API 範例，也不把 UI 支援性與 Engine 設定合法性混為一談。

## 6. 非同步工作與一致性

D-56 已確認：Builder DEV 與 FTEST／ENT 共用 Runtime 工作控制，Library 執行流程；Builder 上傳與直接呼叫 API 走同一 Queue，不再重複排一次。每 System 文件執行併發可配置、預設 1；Runtime 再設總量，Inference 有頻率／併發／Deadline。限制可配置已確認；放 E 是先前建議，管理者／存放位置／Schema 本輪暫緩定案；不由每次文件／Query 任意覆寫。

Batch 逐文件處理；併發 1 時依序，併發 2 時不同文件可同時處理。相同 (System, document_id) 已 queued／running 時拒絕再次提交。支援提高併發仍需驗證 Component／Client／共享索引的安全性，必要提交階段加鎖，不承諾任意 backend 可無限制並行。

每份文件完整替換舊資料、成功才發布、失敗保留最後成功版本。不保留續跑 checkpoint；Runtime 重啟丟棄 Queue／工作／記憶體狀態，查詢為 unknown。索引持久化恢復與工作恢復不同；Remote timeout／崩潰後可能已有副作用，不能當作一定未寫入或自動安全重試。

Local Search 第一版仍同程序／單副本。背景執行不能把唯一 Memory 索引放在會退出的獨立 Job，也不能 fork 多個 worker 期待共享 Python 記憶體。這裡的 Worker 是執行排程概念，不要求新增 Pod；精確執行模型需測試。

尚待 Q-008～Q-010／Q-015／Q-017／Q-019：

- 21 的 counts／錯誤 Envelope 與文件管理細節；統一 List、整批預檢、Run partial 與 retire 直接刪除方向已確認。
- 文件級索引 staging／舊 Chunk 清除／發布點、搜尋可見性及崩潰一致性；不以單次 Bulk／Hash 宣稱原子替換已完成。
- 每個存活實例固定 Config、重啟／重建生效的生命週期；Builder 共用實例更新範圍、持久索引相容性，以及 Query 讀寫鎖或允許短暫混合的取捨見 21 §8。
- 未知遠端寫入已確認不自動重試；具體結果查核、同文件隔離、Idempotency-Key／版本控制及清理仍待定，首期不做取消。
- Queue／並行／Rate／Deadline／紀錄保留的具體值，與未來多 replica 下的一致控制。

方向已確認不表示提交機制已實作；詳細盤點與待決子項見 [21](21_runtime_ingestion_inference_api_inventory.md)。

## 7. Local Search 恢復與儲存

| 模式 | 重啟 | 正式要求 |
|---|---|---|
| Memory | Chunk／向量／搜尋結構遺失 | 回需要 Ingestion；不回示意檢索結果 |
| MongoDB | 讀保存的 Chunk／vectors／Manifest 重建 | 驗證 Config／Profile／資料版本，完成前不提供不完整索引 |
| ES | 驗證既有 Index／Mapping／Profile | 有相容可用資料才 Query；不存在時可接受 Ingestion |

MongoDB 保存不等於跨 Pod 索引同步。重建失敗、DB 中斷、Profile 不符、損壞資料及大資料量啟動時間見 Q-012／Q-027。原始檔／ParsedDocument 若未保留，不保證可自動重新切分／Embedding。

## 8. Evaluation 與 AI 助手服務

另有待確認的 Query Rewrite 單模組測試提案，見 06 §3.3.1／10 UIB-007：若採用，Backend 以請求草稿呼叫相同 Engine 模組／LLM Adapter，測試不依賴已保存 System 或索引。認證、服務引用與逾時規則仍需核定；接口精確路徑／Envelope 留 Q-019，不新增已凍結的公開 Runtime API。M2 可先由 SDK 驗證模組，Builder 入口屬 M5；Mock 與真實呼叫分開驗收。

Evaluation Runner 於 M6 交付完整驗收，綁定 Dataset／Config／Index／Engine／Judge 版本，逐題呼叫同一 Target，收集實際 ResultSets／排名／來源／錯誤後交 04 評分。重用相同 Retrieval-only Query API；不收集生成答案或做答案正確性評估。併發、快取、重試、成本與 Gate 見 Q-018／Q-027。

AI 助手在 M4 先交付獨立核心與 Python／API 入口：接受需求、明確允許的樣本、可用服務資訊及可選的既有 Config／基準識別，產生受 Schema／Registry 限制的 Config 草稿、理由、Diff、缺少設定與驗證結果。資訊不足可回需補齊的草稿，不宣稱已可執行；不猜服務／憑證，不自動 Ingestion。Config 合法仍需使用者／驗收腳本明確交給 Engine／Runtime 執行，不等同檢索品質已驗收。

M5 的 Builder Backend 串接同一核心，加入 Workspace／System 授權、目前 UI Draft 與基準版本，回傳可對回控制項的建議。使用者套用時先重驗基準及 Config，過期建議不覆蓋人工變更；套用只改草稿，Create／Save 前不改 active Config。前端另驗收樣本／映射、Diff／取消、收合欄位錯誤定位及變更影響。M4 的獨立測試不能取代 M5 的 UI 整合證據。

Prototype 規則模擬不能當作正式助手。Prompt、資料保留、最大樣本、輸出／Diff 與舊建議合併見 Q-024；HTTP 宿主／Envelope／認證見 Q-019。對應 Prototype 需求先記 [10 §7](10_ui_adjustment_backlog.md#ui-backlog-pending)，本輪未修改畫面。

## 9. Export、獨立部署與 Secret

### 9.1 Bundle 目標

交付 Retrieval Runtime，不打包整個 Builder。

Runtime Image 可自 M3 開始建置；M7 才驗收完整 FTEST／ENT 獨立交付。以同一版本／Digest 的可配置 Runtime 承載相容 System，不要求每份 Config 建一個 Image。獨立 Runtime 讀取已提供的 Config 即可啟動，使用 AI 助手生成 Config 是可選的前置操作，不能變成部署後必須連回 Builder 的依賴。

目標 Bundle 包含：

- Runtime Image 版本／Digest、Module 版本、Config Revision／Hash。
- 選定 System／Revision 的相同邏輯 Config，及另存的目標環境部署設定；不能把 URL／Secret 差異當成不同處理邏輯。
- ConfigMap／Deployment／Service 等 K8s 設定及 Secret references。
- FTEST／ENT 的環境檔案、啟動與 API 說明、資料準備步驟。
- 若有評估報告，清楚綁定測試環境／資料版本，不能宣稱目標環境已驗證。

Remote Image 另輸出所選遠端服務的 Image 引用、Deployment／Service／資源／設定檔／Secret 引用等 YAML；External Endpoint 只輸出目標環境連線／Secret 引用，不建立遠端部署。

不含 Image 本體、真實 Secret、原始文件、Chunk／vectors、Builder DB 或外部 DB／模型資料。目標環境需有相容資料或執行 Ingestion；部署後仍可持續 API 匯入。

Local Search 的持久化模式沿用同版 Config：DEV 為 Memory，FTEST／ENT 也為 Memory；Export 只補齊該模式所需部署綁定，不將 Memory 切成 MongoDB。MongoDB 模式可填不同環境的 URI／Secret／DB／Collection，實際資料不隨匯出搬移。

<a id="remote-service-deployment"></a>
### 9.1.1 Remote Service Manifest 與環境綁定

Developer 提供 Manifest 描述服務識別／版本、操作範圍、Contract、可選設定描述與 Image 部署需求；管理者審核並綁定各環境連線／Secret，User 不自行輸入 Developer Service 的 API。Metadata／Contract 版本檢查與健康／連線檢查分開，目錄查詢不得觸發任意部署。

DEV 自動部署與 Export 共用部署描述的語意；FTEST／ENT 補齊目標環境資源，維持相同邏輯參數與相容服務版本。固定服務不要求參數表單，支援 per-call 參數時另定傳遞協定；不把任意 Config／連線設定藏入文件 metadata 或改寫 Parser 輸入；Component 已宣告支援的文件層 metadata 提示依 D-52 保留。Manifest 與部署描述的正式 Schema 及管理 API 仍為 Q-028／Q-019／Q-021，完整責任與驗收見 [18](18_remote_service_pipeline_integration.md)。

### 9.2 驗證與部署

狀態分開：needs_configuration → configured_unverified →（外部連線／資料檢查結果）→ 實際部署結果。本文不指定未核定的完整狀態枚舉；不能用 configured_unverified 表示可直接部署成功。

Local Search replicas=1 且單 API worker；ES 是否多副本需驗證工作／權限／版本策略。resource limits、Probe、TLS／Ingress、CD 工具與 FTEST／ENT 命名見 Q-021／Q-027。

Secret Vault 位於 Runtime 外，以環境支援的解析／注入方式提供；`secret-name/key` 為目前示意引用。正式產品、SDK、檔案掛載路徑與更新政策 Q-021。URL、Header、Trace 與匯出均不得內嵌帳密。換 Embedding Profile 要回 Engine 重建，不能只在匯出改模型 ID。

### 9.3 獨立啟動

建議步驟：讀選定 Config Revision＋該環境部署設定 → 解析服務／資料綁定與 Secret → 04 驗證／初始化建立 System 執行實例 → 驗證資料／恢復索引 → 啟動 HTTP。Live／Ready 與 IndexReady 分開；無資料可以接受 Ingestion，Query 回不就緒。部署後 Config 更新可先經重新部署，熱更新／零停機另案。

<a id="release-deployment-boundaries"></a>

### 9.4 建置、發布與部署的變更範圍

發布新版本與讓既有環境採用新版是兩個動作。以下描述採用新版時的交付範圍，實際 CI／CD 工具與核可權限仍依 Q-021／Q-022：

| 變更來源 | 建置／測試與部署範圍 | 跨 repo 配合條件 |
|---|---|---|
| 僅 Builder UI／Backend | 建置並部署受影響的 Builder Image，驗證與所支援 Runtime 的契約 | 沿用相容 Runtime；不因 Builder 發版而重建所有 Runtime |
| 新增／修改 Local Component／Runtime Adapter | rag_engine 的方法與整合測試後，建置完整 Runtime Image；欲使用新版的環境更新 Runtime | API／Schema／表單相容時 Builder 可維持原版，更新目錄即可；新 UI 能力另配合 |
| Engine／SDK／Runtime API | 在 rag_engine 驗證受影響 Components 與 API，再建置並部署 Runtime；SDK 如另發行須保留版本對照 | 破壞性 API／Config／SDK 變更需要使用方適配；不能承諾所有變更都單邊升級 |
| Remote Service／Manifest（D-51） | 相容宣告可更新核可目錄／環境綁定，不因新服務強制重建 Runtime；Image 服務更新其部署，External 由 Developer 更新 | 若新協定／連續範圍能力不被 Adapter 支援，仍需更新 Engine／Runtime；語意改變須重新驗證 |
| 文件／未納入產物的測試資料 | 執行相應文件／測試檢查 | 不僅因 repo 有新 commit 就強制重新部署服務 |

每個完整 Runtime Image 應可追溯同一 rag_engine 交付來源、SDK／Engine／Component package 版本與依賴鎖定結果。同 repo 可以讓它們一起驗證，並不抹去各自的契約／實作版本。既有 System 可維持鎖定版本，新版發布不自動觸發所有 DEV／FTEST／ENT 升級；欲交付的選定版本應完成 DEV 驗證，再由使用單位以同一 Runtime Image／邏輯 Config 補齊環境設定進行部署。

Runtime 更新若重啟 Memory 模式，依既有規則需要重新 Ingestion；MongoDB／ES 依索引與版本相容性恢復。重建、快照、切換與回復仍依 Q-008～Q-010／Q-015，不因兩個 repo 分工就新增熱插拔 Component 或零停機升級承諾。

## 10. Observability、認證與權限

request／run／trace 必須可跨 Backend／Runtime／模組關聯。輸出結構化錯誤、耗時、輸入輸出數及可取得用量；模型與 Judge 也記版本。OTel／Langfuse 為候選，非每個 Runtime 必備外部依賴，具體方案 Q-016／Q-027。

Builder 使用者登入依本輪指示延後討論；既有 tSSO 圖示不代表本輪已凍結或實作登入方案，具體方式見 Q-006。呼叫 Runtime 的認證與 Runtime 呼叫模型／DB 的 Secret 不同。System／Workspace／ACL 由可信 Backend／Runtime Context 注入，Filter 不能提權；獨立 Runtime 仍需部署端認證，不因 API only 就公開匿名。

## 11. 待討論與決策

| 主題 | 追蹤 |
|---|---|
| API、認證、路由、檔案 manifest、標準錯誤 | [Q-006](08_implementation_plan.md#q-006)、[Q-019](08_implementation_plan.md#q-019) |
| 更新、partial、併發、Revision | [Q-008](08_implementation_plan.md#q-008)～Q-010、[Q-015](08_implementation_plan.md#q-015) |
| DB／資料保留、重試、Run 恢復 | [Q-012](08_implementation_plan.md#q-012)、[Q-016](08_implementation_plan.md#q-016)、[Q-017](08_implementation_plan.md#q-017) |
| DEV 共享 Runtime、Export／Vault | [Q-020](08_implementation_plan.md#q-020)、[Q-021](08_implementation_plan.md#q-021) |
| 評估、AI、效能／成本 | [Q-018](08_implementation_plan.md#q-018)、[Q-024](08_implementation_plan.md#q-024)、[Q-027](08_implementation_plan.md#q-027) |

## 12. 完成條件

直接 SDK 與 HTTP 入口在相同配置／資料上得到相容結果；UI 呼叫真實 API；獨立 Runtime 不需要 Builder 啟動；Config／Run／Index 版本可追蹤。建立、重送、錯誤、重啟、併發與部署驗收按 08 分階段完成，不用示意 YAML／固定回應取代整合證據。




## 2026-11-04 D-55：Indexing／Retrieval 交接

每 System 一組邏輯索引，IndexBinding 只有 artifact_type／target／fulltext_fields／filter_fields／vector_bindings，省略 index_ref。Indexing 提供，Engine 驗證與管理；Retrieval 須宣告支援格式／版本，並只搜尋 Binding 宣告且相容的能力。target 依受控註冊的格式 Schema 驗證；Developer 還需共同儲存／讀取規格與 SDK／範例才能開發。完整定義見 [19 IndexBinding 與索引格式契約](19_index_binding_artifact_contract.md)。

Component Config 是處理參數；RunContext 是 Engine 準備的必要資源／Binding 引用，實際 Client／索引物件不放業務 JSON。searchable 不在 Binding，Runtime 管就緒；格式版本與 Component 版本、資料發布版本分開。內建 ES target 有 collection，Local target 可空並使用 System 唯一資源。首版不新增多組選擇；UI 差異只記 backlog。正式 SDK、後端讀寫布局、Remote 協定及更新／發布政策仍需後續核定／實作。
