# Retrieval Builder／Engine 對話交接

| 項目 | 交接資訊 |
|---|---|
| 來源 | ChatGPT 專案 Generic rag system platform 的 `[MAIN] 主要對話`，整理至 2026-11-16 |
| 目標 repo／分支 | `SunnyWenwen/rag_platform`／`docs/rag-system-factory` |
| 核對基準 | 交接撰寫前的分支 HEAD [`2cf5d1c`](https://github.com/SunnyWenwen/rag_platform/commit/2cf5d1c0516d31422083c0781b0b12005a38fc67)，之後若有新提交，先比對差異 |
| 對話停點 | `structdata` 的宣告、沿用／新增與 Indexing 最後覆寫已在對話確認。接著討論 `metadata` 如何宣告可查路徑、Filter 細節，以及 ES 逾時的安全重送。 |

這份交接用於續談。[README](../README.md) 是規格入口，[08 決策登錄](08_plan_and_decisions.md) 維護正式決策與未決事項。以下會標記「分支已記錄」、「對話已確認、待同步」或「提案／待定」。讀到較早的對話、原型或歷史範例時，依這些狀態核對。此交接提交只新增本文件。

## 1. 接手時先掌握的狀態

| 狀態 | 內容 |
|---|---|
| 分支已記錄 | Retrieval-only、LangGraph、單一 `Document`、User Remote API、Admin 全域模板、Inference 結果處理、System／索引生命週期、ES 文件覆寫、Builder 管理來源與重送、ES-first 的 M1。 |
| 對話已確認、待同步 | Data Import 宣告 `structdata` 的原始欄位。後續保留的欄位繼承宣告，新增欄位在產生點宣告。Indexing 對最終仍存在的欄位保留最後覆寫 `searchable`／`filterable` 的能力。使用者已回覆「好」。 |
| 草案、待定稿 | `string_array` 作唯一集合型別、範圍 Filter、完整型別／能力矩陣、日期與缺值語意、Remote Filter 能力表達、`metadata` 路徑宣告、索引覆寫差異的正式 Config 鍵名。 |
| 現有交付 | 規格、HTML Prototype、圖面、JSON Schema／Descriptor／Config 草案及離線 fixtures。基準分支尚未交付可對真實 ES 執行的正式 Engine、Runtime 或 Builder。 |

使用者習慣先看取捨與具體例子，再決定並同步到規格。文件更新沿用 `docs/rag-system-factory`。以中文溝通，保留英文術語和欄位鍵名。當需求是續談時，先解決當前設計問題。收到更新文件或圖面的指示時，連同受影響的 Schema、範例、Prototype Backlog 及決策登錄檢查，並回報 commit 與檔案連結。

## 2. 產品範圍、名詞與部署

- 早期在對話中叫 RAG Builder／RAG Engine。現行 repo README、架構與圖面使用 **Retrieval Builder／Retrieval Engine／Retrieval System／Retrieval Runtime**。產品範圍是 **Retrieval-only**。Inference 回傳排序候選、分數和來源，沒有 Generation。Rewrite 與 AI 設定助手仍可用 LLM，Evaluation 保留。
- 正式管理階層為 **Workspace → System**。同一 System 可有多個 Config Revision。同一 Revision 在 DEV／FTEST／ENT 使用同一份邏輯 Config。服務 URL、Secret、實體資料／索引目標、執行資源屬 Deployment Settings。獨立追蹤 `system_id`、`config_revision`、`source_revision`、索引資料狀態／版本、Runtime Image 版本。早期的 Blueprint 沒有成為正式物件。
- **Engine Library + 有效 Config + 必要環境綁定 → Retrieval System**。Library 提供 Registry、契約驗證、模組組裝與執行，Python 可直接使用。Engine 採共用 **LangGraph Flow／Executor**，每次執行帶入 System 設定快照。Module 是職責與契約，Component 是可選實作，正式引用為 `component_id` + `component_version`。Engine Platform 是 Library、Runtime API 包裝和共用 Image 的交付，圖上的 Retrieval Service 表示 Runtime 裡的 System 執行實例。
- **Builder** 管理 Workspace／System、Config 草稿與版本、測試 UI、模板、資料來源、Evaluation 和匯出。Builder Backend 經內部管理 API 發布。**DEV Runtime** 是獨立程序，可從零組 Config 啟動並承載多個 System。Engine 不直接讀 Builder DB。DEV 可選平台測試用 ES、LLM、Embedding、Rerank，也可使用自備連線。
- **FTEST／ENT** 第一版基準是主 Runtime 一 Pod／一個 API service／一份 System Config。使用單位以匯出的 K8s YAML 配合共用 Image 自行部署，補目標環境的服務、Secret Vault 及觀測綁定。Runtime 啟動時套用 Config，對外提供業務 API、關閉 Builder 內部管理路由。匯出設定與部署綁定，正式環境資料另行準備。
- 內建 Elasticsearch、Local Search／Memory、Local Search／MongoDB 仍有既有規格和示例。**首條真實端到端驗收已改為 ES**。Memory 重啟需重新匯入。MongoDB 方向是以已存 Chunk／向量／Manifest 重建 Local 搜尋結構，正式恢復細節仍在 Q-012。

來源：[架構與名詞](01_architecture.md) · [System Config](05_system_config.md) · [Runtime](06_runtime_api_and_deployment.md)

## 3. 共用資料、Pipeline 與 Remote API

**Ingestion**：Import → Parsing → Chunking → Embedding → Indexing。**Inference**：Inference Input → Query Transformation → Retrieval → Rerank，依 Config 執行融合、分組及截斷。骨架固定，可選 Component，支援的相鄰節點可合併給一支 Remote API。

| 契約 | 現行規格 |
|---|---|
| `Document` | 原始文件、解析 Unit、切片和檢索候選共用外層。`document_id` 代表來源文件，`data_id` 辨識切分後每筆候選並供融合去重。`source_revision` 供追溯。`structdata` 放結構化業務資料，`content` 放待解析的 `media_type` + `uri`／`base64` 二選一，`metadata` 可帶巢狀 JSON，`vectors` 存具名向量。舊 `IngestionDocument`／`ParsedDocument`／`Chunk` 外層、`fields` 和 `ResultItem.chunk` 屬歷史設計。 |
| Import／Parsing | `POST /v1/ingestions` 接 `{documents: Document[], parameters?: object}`。批次預檢後以文件拆工作，Parsing 一次收到一份 `Document`，輸出同來源 `Document[]`。結構化 JSON 可直通。一個內建檔案 Parser 可產 `structdata.contenttext`。 |
| Chunking | 每個 Unit 各自對同一個選定的 `structdata` 字串欄位切分，overlap 限於 Unit 內。設定可指定複製欄位、切分輸出欄位及保留原文，預設繼承合法 metadata。已討論 Fixed-size、Recursive、Header-aware，M1 先 Recursive。 |
| Embedding | 依來源欄位與 Profile 產具名向量，含 `values`、`embedding_profile_id`、`source_field`。可先組合文字，常用映射 `structdata.text` → `vectors.text`。文件／Query Encoder 必須同向量語意空間，維度相同只是形狀檢查。純全文流程可略過 Embedding。 |
| Indexing | 保存全部有效 `structdata`／`metadata`，按能力設定全文、向量及 Filter。第一版一個 System 至多一組平台 `IndexBinding`，供內建 Retrieval 取索引定位、欄位與 Profile 能力。多欄向量仍可在同一組 Binding。 |
| `QueryContext[]` | Inference 各處理節點的固定 I/O，也是成功回應根層。Context 有 `ori_query`、`query`、`filters`、`result_sets`、`metadata`。ResultSet 有 `key`、排序後的 `items`。`ResultItem.data` 是候選 `Document`，`score` 選填。 |

**有效 Schema 與 Component Descriptor**：平台團隊維護內建 Component、描述及規則。從 Import 取得原始 Schema，沿所選方法逐步推導有效輸出，供下游欄位選項、相依檢查、Remote I/O 預覽與 Engine 驗證共用。失效選值保留在草稿並顯示原因。Descriptor Meta-schema 定義如何描述內建 Component、參數及推導規則。Data Meta Schema 定義欄位的宣告形狀。System Config 選擇方法、參數與欄位。這三者各有用途，正式序列化仍屬 Q-002。

**Remote API**：取消 Developer 角色、元件上架、Manifest 註冊與 Remote Image 流程。User 自行實作並部署服務，在 System 內設定端點、認證、範圍與參數。Admin 用版本化設定檔維護全域模板，Builder 提供「選用模板」，複製到草稿供編輯，更新模板不會改動既有 System。平台仍可自行開發內建 Component。

- 固定 HTTP 契約為 POST `{"input": ..., "parameters": {...}}` → `{"output": ...}`。平台從上游推導 input，從同一份共用資料契約與 User 宣告產出 output 契約。既有服務的 payload 轉接由外部服務處理。
- Ingestion 可替換 Parsing／Chunking／Embedding 各自或連續組合。Parsing 起始時 input 是單一 `Document`，其他情況是同文件 `Document[]`，output 為 `Document[]`。涵蓋 Parsing／Chunking 時宣告輸出欄位，涵蓋 Embedding 時宣告向量。Import 與 Indexing 為平台節點。
- Inference Input 為平台節點。Query Transformation／Retrieval／Rerank 可單獨或相鄰合併。Remote I/O 都是 `QueryContext[]`。整段包給 Remote 時，Runtime 驗證回傳候選，再依對方順序交付。Remote Retrieval 查自有資料可直接用，候選仍須符合 System 從 Ingestion 推導的可檢索 `Document` Schema。後續內建 Rerank 可使用同一套候選欄位。
- 有效設定在區段第一個節點使用 `component_id: remote_api`、`component_version`、`through`、`service_ref`，拒絕重疊，涵蓋節點不再單獨執行。原設定可留在 UI Draft。Import／Inference Input 宣告執行參數，`{{params.name}}` 可傳至下游，完整引用保留型別。認證用固定或動態 `secret_ref`，Runtime 檢查後解析並注入 Header。憑證與執行參數留在各自的環境／請求作用域。
- Graph 類檢索曾討論由平台方開發可選的內建模組，沿用共用資料形狀及契約。這是能力方向，M1 驗收範圍見第 7 節。

來源：[資料契約](02_data_contracts.md) · [Engine／Remote API](03_engine_and_components.md#remote-api) · [Descriptor](04_component_descriptor.md) · [Remote 範例](../examples/user_remote_api/README.md)

## 4. Inference 與結果處理

- Query Transformation 的 `none` 直接用原問題，`rewrite` 是一個 Component，使用 `llm_ref`、`prompt`、`count`、`include_original` 表達單筆和多筆改寫。LLM 服務集中設定，再從下拉選取。保留 `ori_query`。固定結構化輸出、去重、何時重試及 Prompt 單模組測試仍須依 Engine 草案定細節。
- **同 Query 多路**：內建 Retrieval 每 Query／每全文或向量路徑先取 `per_route_k`。一路可直接交付，多路須選 RRF 或 Sum Score，以 `data_id` 對齊。按當前排名分組後，才取 Retrieval `top_n`。每 Query 只交付一份 ResultSet，查無命中仍可交付空 `items`。路徑與融合策略的專屬參數及預設待定。
- **Rerank**：對候選做模型打分與重排，再做當步可選 `group_by`，最後做 Rerank Top N。**跨 Query** 的 UI 控制在 Query Transformation，可選 Retrieval 或 Rerank 完成後才執行，依序融合 → 分組 → 跨 Query Top N。可設在 `after_retrieval` 或 `after_rerank`，Config 正式形狀仍屬草案。Rerank 為 None 時仍可執行後置跨 Query 規則。
- **分組**：開啟時預選 `document_id`，也可選候選 `Document` 的單值欄位，例如 `metadata.parent_chunk_id`。可多選成組合鍵，保留當時排名最高的候選。任一分組欄缺值的候選各自保留。分組候選欄位來源 `candidate.document_fields` 已有 Descriptor 提案，Meta-schema／編譯整合仍待做。
- **失敗**：必要 Query、搜尋路徑或 Rerank 任一最終失敗，就回整次 Inference 錯誤。必要操作全部成功但查無資料時回 `200` 和空候選。文件／檔案級 ACL 先延後，System 隔離與 MCP API key 的 System／工具授權保留。

來源：[Engine 結果處理](03_engine_and_components.md) · [Config 結果處理](05_system_config.md#inference-result-processing) · [08 相關決策](08_plan_and_decisions.md)

## 5. Runtime、ES 與 Builder 的資料責任

### System 生命週期

1. DEV 由可信 Builder Backend 套用、列出、查詢、卸載 System。管理路徑草案是 `PUT/GET/DELETE /internal/v1/systems/{system_id}` 與 `GET /internal/v1/systems`。獨立部署啟動時呼叫同一 Python 管理函數。正式 OpenAPI、版本衝突、排空逾時、更新逾時後查生效版本在 M3／Q-019 收斂。
2. 初始化／重啟／重連確認 ES 索引不存在才建立；既有索引歸屬、指紋、mapping 相容就接回。未知歸屬或不相容回衝突並保留索引，連線或授權錯誤依原原因回報。
3. 相容的明確更新沿用索引。每個請求／已接收工作固定單一 Config Revision，已開始的 Query 可跑完。System 有排隊／執行中的 Ingestion 或另一管理操作時，可存草稿，暫不啟用新設定（`409 system_busy` 為草案）。
4. 不相容的明確更新先驗證新版，排空該 System，刪除受管理索引再建，建好才啟用。若舊索引已刪而新索引建立失敗，System 保持不可用，重試建好後再重匯。明確卸載排空後刪受管理索引與資料，Builder 保存 System／Config 歷史。外部 Retrieval 資料由服務提供者管理。
5. **索引指紋**：取有效 Config 裡影響索引內容或搜尋能力的設定，正規化後算 SHA-256。包含有效解析／切分、文件 Embedding Profile（含模型版本與維度）、有效欄位／mapping／搜尋能力。物件鍵順序無影響，具語意順序要保留。`top_n` 沿用，改 Chunking 或換文件向量模型會影響相容性。ES `mappings._meta` 存 `system_id`、`index_fingerprint`、規則版本，完整 Config 由 Builder 保存。精確輸入、序列化與升版仍待 Q-015。

### 文件覆寫與查詢開放

- 同一 System 按 `document_id` 新增或整份覆寫。`source_revision` 只供追溯，相同 revision 帶不同內容仍按同一 `document_id` 覆寫。一般寫入／retire 和 Query 併行，接受短暫新舊混合。相同文件 queued／running 時拒絕重複工作。
- **Elasticsearch 索引存取層**為每次文件寫入產生內部 `write_id`。同一次的 Chunk 共用。ES `_id` 從 `document_id`、`write_id`、`data_id` 穩定衍生。`write_id` 留在 ES 內部欄位，與共用 `Document` 契約分離。Indexing 是 Pipeline 節點，Elasticsearch index 是資料位置，索引存取層供 Indexing 與文件查詢、刪除等操作使用。`ElasticsearchIndexStore` 是討論時建議的實作名稱。
- 查舊批次 → 產出並驗證所有新 Chunk → 寫入並逐筆檢查 Bulk → 確認新版全部可搜尋 → 依文件 ID 與既有 `write_id` 清舊 → 清理可見後才標文件 `completed`。舊 10 筆、新 6 筆的正常驗收最後只留新 6 筆。確認新版中途失敗時，只清該次新批次並保留舊版。新版已成功、清舊失敗時保留新版並回報清理問題。
- ES 寫入或刪除結果不明回 `unknown`，先依預期 ES `_id`、`write_id` 與操作結果查核。可安全重試同一操作時沿用原內容和 ID；新的 Ingestion 工作用新 `write_id`。Runtime 重啟後工作紀錄丟失、舊 Run 查詢為 `unknown`。**Runtime 不做跨重啟自動修復，由 Builder 重送整份來源文件**。前次後端寫入確認已結束後，重送成功再清除查到的舊批與殘留。
- **Builder 保存並管理原始資料**（原始檔、原始結構化資料）。索引重建成功後，由 Builder 用保存資料重新提交 Ingestion。來源儲存、保存期限、重匯狀態、重送辨識及流程留 Builder 設計。
- **Engine／Runtime 就緒**：索引可查且必要依賴就緒就接受 Inference，空索引可回成功空候選。**Builder UI 就緒**：新建或清空後重建，等初次預定資料全部匯入成功且可搜尋才開放，失敗要補齊。一般後續新增或逐文件更新不關閉查詢。
- **Builder CSV 上傳是整批替換**：每列一份 `Document`。先預檢完整 CSV 與映射，再清除目標 System 既有索引資料，最後匯入整份。每批內文件 ID 唯一。CSV 自動 ID、清除用哪個 API、清除後匯入失敗如何處理等由 Builder 規劃。這個產品操作和一般 Runtime 多文件 Ingestion 的逐文件覆寫有不同語意。

### API 與工作狀態速查

| 能力 | 現行路徑／契約 |
|---|---|
| 提交／查 Run | `POST /v1/ingestions` → `202` 與 `run_id`、`status`、`config_revision`、`documents`、Location。`GET /v1/ingestions/{run_id}` 取得 Run 與逐文件結果。整批先預檢和預留容量，入列後逐文件獨立，Run 可 `partial`。 |
| 文件工作／索引資料 | `GET /v1/documents/{document_id}/ingestion-status` 查工作，`GET /v1/documents/{document_id}/exists`、`GET /v1/documents?limit=...&cursor=...` 讀實際索引，後者回 `document_id`／`source_revisions[]` 摘要。工作紀錄 `unknown` 和索引文件存在性分開。 |
| 直接刪除 | `POST /v1/documents/{document_id}:retire`，同步回 `deleted` 或 `not_found`。同文件忙碌回 409。Ingestion 進度管控與取消另議。 |
| 查詢／健康 | `POST /v1/queries` 同步回 `QueryContext[]`，Request Schema 有 `query`、`filters`、`metadata`、`parameters`。`GET /health/live` 與 `GET /health/ready` 查程序／資源，System 的查詢就緒另行判定。 |

Runtime 首版 Queue／Job Store 在程序 Memory。重要可調預設：單批 100 文件、HTTP body 20 MiB、單來源檔 10 MiB，等待容量 System／Runtime 100／500，Ingestion 併發 1／2，Inference 併發 2／8。Runtime HTTP 暫採一組 Basic 帳密，Builder 登入方式與正式部署接線延後。HTTP 錯誤核心是 `error.{code,message,module}`，輸入驗證可帶 JSON Pointer `path`。已接收工作的失敗透過 GET 狀態回報。

來源：[Runtime API](06_runtime_api_and_deployment.md) · [索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle) · [ES 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement) · [Builder 查詢開放](07_builder_ui.md#builder-initial-ingestion-readiness) · [CSV 整批替換](07_builder_ui.md#builder-csv-replacement)

## 6. 最新待續談：Data Meta Schema、metadata、Filter

### 已確認、待同步到規格

使用者原意是「`structdata` 的 data schema 在 Data Import 就要宣告，後面都是繼承前面的或是新增」，並確認下列 Indexing 最後調整方向。

| 階段 | 欄位宣告責任 |
|---|---|
| Data Import | 原始欄位宣告 `type`、`required`、`searchable`、`filterable`，布林能力在這一步提供預設。 |
| Parsing／Chunking／Remote 等 | 保留下來的欄位沿用上游宣告。新欄在產生點用同一套格式宣告。需要改型別或必填性時，回到產生點處理，維持上下游驗證一致。 |
| Indexing | 顯示真正到達這一步的有效欄位，包含中途新增的欄位。可逐欄覆寫 `searchable`／`filterable`，沿用 `type`／`required`。向量能力仍從 Embedding 與 Indexing 的向量設定取得。 |
| Retrieval | 全文及 Filter 選單讀取最終的有效能力。`searchable` 表示建立全文索引，某次 Retrieval 要用哪幾個全文欄位仍在 Retrieval 選。ES mapping 與指紋以最終能力推導。 |

具體例：Import 有 `title`，Parser 新增 `section_title` 並設 `searchable: false`。若 Chunking 保留該欄，Indexing 可把 `section_title.searchable` 改成 `true`，其他屬性沿用。若上游刪除、改名或 Chunking 未保留，該欄不會出現在 Indexing 的可選清單。前一輪建議 Config 僅存覆寫差異，Builder 標出失效覆寫，精確鍵名、刪除／改名後的發布驗證仍待定。

### 已提出的欄位與 Filter 草案

資料來源是同事整理的 [CH_additional_Note.md](https://github.com/x21530317x/rag_platform/blob/docs/rag-system-factory/CH_additional_Note.md)。以下是 MAIN 對照平台契約後的草案，與基準分支的機器 Schema 仍有差異。

| 欄位型別草案 | 值形狀 | 全文搜尋 | `filterable: true` 時的運算子草案 |
|---|---|---|---|
| `string` | 字串 | 可 | `eq`、`in` |
| `string_array` | 一維 `string[]`，陣列元素皆為字串 | 先關閉 | `eq`、`in`，匹配任一元素 |
| `integer` | 整數 | — | `eq`、`in`、`gt`、`gte`、`lt`、`lte` |
| `number` | 有限數值 | — | 同上 |
| `boolean` | 布林 | — | `eq`、`in` |
| `date` | 日期字串，首版候選 `YYYY-MM-DD` | — | `eq`、`in` 與範圍 |

- `string_array` 是討論中的唯一集合型別。`structdata` 仍維持平面欄位。草案允許複製、回傳和精確過濾，Chunking 切分來源、Embedding／Rerank 文字來源與 `group_by` 選單仍取符合契約的單值欄位。例：`["AI", "ML"]` 符合 `eq "AI"`、`in ["ML", "NLP"]`。
- Filter 草案沿用 `{field, operator, value}` 與 AND。`{"field":"structdata.price","operator":"gte","value":300}` 翻成 ES `range`，`eq`／`in` 對應 `term`／`terms`。上下界可寫兩個條件。草案拒絕 Filter 的 `null` 值，文件欄位缺省或空陣列不命中。`required` 是否只要求存在（例如必填 `tags: []`）及日期時間／時區支援尚待定。範圍 Filter 影響評估為中等，主要涉及 API、型別驗證、表單和 Remote 相容性。
- ES mapping 草案：`string` 只全文用 `text`，只 Filter 用 `keyword`，兩者皆用 `text` 加 `.keyword`。`string_array` 過濾用多值 `keyword`。`integer` 建議 `long`、`number` 建議 `double`、日期用 `date`、布林用 `boolean`。僅保存的欄位可留在 `_source`，用 `dynamic: false` 與明確 mapping。若明確映射到可用 doc values 的型別，需一起檢查 `index` 和 `doc_values` 設定。
- Remote Retrieval 會收到共用 `QueryContext.filters`。擴增運算子時，討論過由 Remote 宣告支援範圍，平台拒絕把未支援的條件送入。能力宣告放在哪裡、由誰驗證及舊服務如何相容待定。

### 新對話可直接開始的議題

1. **先談 `metadata` 路徑宣告**（Q-006／Q-013）。現行允許巢狀自由 JSON，供索引或過濾的路徑需要型別。最新提案是僅對需全文、Filter 或分組的路徑宣告，並讓 `metadata.department` 與 `metadata.parent_chunk_id` 的需求共用欄位路徑機制。前者要可過濾，後者只需候選可讀且是單值，分組不要求建立 Filter 索引。請用這兩例確認宣告應在產生階段、Indexing，或以可繼承宣告加 Indexing 覆寫，並把 `_rag` 保留路徑、缺值及巢狀路徑限制一併說清楚。
2. **再定 Filter 和完整範例**（Q-002／Q-013／Q-028）。確認 `string_array`、range、日期、缺值／`null`／空陣列、Remote 能力，再擬一份從 Import 到 Retrieval 的 System Config（含欄位新增、索引覆寫及 metadata）。基準分支 `document.schema.json` 仍只接純量，`query_context.schema.json` 仍只列 `eq`／`in`，其 `$defs.filter` 也給 `inference_request.schema.json` 引用。同步時檢查 Context 內嵌 Filter 及共用 `$defs`，再對照 Engine、Descriptor、System Config、Runtime API、Builder 表單、有效 Schema fixtures 與 Q-013。現有 `0.2-draft` Local Memory 範例可參考結構。
3. **ES 逾時後的安全重送**（Q-008／Q-009／Q-017、API-D05）。已定 Builder 重送。仍要定如何確認前一次 ES 操作確實終止、如何觀測與清掉晚到資料。驗收情境：舊寫入 A 逾時且實際還在 ES 跑，重送 B 已寫入成功，A 的部分／全部 Chunk 才出現。現行「重送前查到的舊 `write_id`」無法涵蓋尚未出現的 A，需明確定出完成確認及清理邊界。避免把後端「目前查不到」當成終止證據。`write_id` 精確鎖定批次，單靠它無法證明當初該寫幾筆或後端已結束。

來源：[資料契約](02_data_contracts.md) · [Descriptor 的分組欄位來源](04_component_descriptor.md#group-by-option-source) · [Q-013](08_plan_and_decisions.md#q-013) · [ES 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)

## 7. 里程碑、Prototype 與圖面待辦

| 階段 | 交付與驗收重點 |
|---|---|
| M0 | 契約、版本、程式結構、有效 Schema／Config 驗證和乾淨環境基礎。 |
| **M1** | 第一個可執行最小 Engine。拿支援範圍內的手寫 Config，直接用 Python／CLI 跑 **Structured JSON → Recursive Chunking → Dense Embedding → Elasticsearch → Query**。真實 ES、空索引空結果、命中可追來源、重啟接回相容索引。需先挑 ES 版本、Embedding API／模型 Profile 和 Tokenizer，準備環境綁定及測資。 |
| M2 | 更多 Engine 方法與能力，包括分塊方法、BM25／融合、Rewrite、Rerank、Remote、ES 進階搜尋。 |
| M3 | 以 Runtime HTTP 包裝可用 Engine，交付 OpenAPI、工作狀態／逾時測試、管理 API 及 SDK／cURL 範例。 |
| M4／M5 | M4 先交付獨立的 AI 設定助手 Python／API。M5 才交付 Builder UI／Backend 並接入助手、管理資料與測試流程。 |
| M6／M7 | Evaluation Dataset／Runner／指標，之後交付 FTEST／ENT 獨立部署及運維驗收。 |

- **Prototype** 是單一 [01_ui_prototype.html](../01_ui_prototype.html)。Workspace／System 卡片包含 Ingest、Inference、Evaluation、Edit／Export 等。Create／Edit 共用流程，可先設定再上傳 CSV，或先放 CSV 樣本讓助手建議 Schema、映射及草稿。助手建議先驗證、看差異、套草稿，儲存時才生效。Prototype 已操作過的功能要列入正式規格盤點。原型是瀏覽器模擬，Runtime／真實 ES／模型請求另行驗收。落差和待辦見 [07 Builder UI](07_builder_ui.md)。
- **圖面與文件交叉檢查**：使用者曾要求所有規格交叉檢查，以及仔細重畫 `02_infra_architecture`，從「如何向主管說明 Builder／Engine 如何合作、各自依賴哪些外部 ES」的角度呈現。已核對 [`b236eb7`](https://github.com/SunnyWenwen/rag_platform/commit/b236eb747ed9a8198d188e5e8931082e88ccc92d) 有一輪圖面更新。它早於索引生命週期、ES-first、Builder 管理原始資料及索引指紋的提交。本輪僅記錄落差，完整逐檔校稿與符合最新決策的主管版圖面尚待依原需求驗收。
- 圖面已有共用 Engine Platform 直接連 DEV Runtime 與獨立 Runtime，FTEST／ENT 大框含 Runtime、Secret Vault、外部依賴及觀測。畫圖時保留這個關係，補清楚 Builder Backend 下發有效 Config、Engine Library 在 Runtime 內執行、Runtime 直接存取外部 ES，以及重建後由 Builder 重送資料的責任。既有圖只標 ES／MongoDB（依後端），ES-first 是新版應清楚呈現的首條實作路徑。改圖時同步檢查 [.mmd](../diagrams/02_infra_architecture.mmd)、[.svg](../diagrams/02_infra_architecture.svg)、[.png](../diagrams/02_infra_architecture.png) 與說明文字。

## 8. 規格、驗證與提交索引

| 要接續的內容 | 主責檔案 |
|---|---|
| 名詞、責任、環境與流程 | [01 架構](01_architecture.md) · [L1 圖](../diagrams/01_user_system_l1.mmd) · [Infra 圖](../diagrams/02_infra_architecture.mmd) · [Module/Component 圖](../diagrams/03_module_component_concept.mmd) |
| Document、QueryContext、IndexBinding | [02 資料契約](02_data_contracts.md) · [Schemas 入口](../schemas/README.md) |
| 模組、Remote、Chunking、Retrieval、Rerank | [03 Engine](03_engine_and_components.md) |
| 內建 Component Descriptor／欄位推導 | [04 Descriptor](04_component_descriptor.md) · [Descriptor 草案](../schemas/component_descriptor.draft.schema.json) |
| Config、版控、服務參照與模板 | [05 Config](05_system_config.md) · [Config 草案](../schemas/system_config.draft.schema.json) · [Examples](../examples/system_config/README.md) |
| Runtime HTTP、工作狀態、索引、環境與部署 | [06 Runtime](06_runtime_api_and_deployment.md) |
| Builder UI、原型差異、進度待辦 | [07 UI](07_builder_ui.md) · [DOM 測試](../tests/inference-processing.dom.test.cjs) |
| Q-001～Q-028、里程碑、驗收 | [08 計畫與決策](08_plan_and_decisions.md) · [舊設計索引](history/superseded/2026-11-11_developer_mode.md) |

**驗證入口**：repo 根目錄下可用 `python3 examples/system_config/validate_descriptor_draft.py` 與 `python3 examples/user_remote_api/validate.py` 驗證離線契約。Python 範例使用 `jsonschema`，Remote 驗證也用 `referencing`。Prototype 可用 `node tests/inference-processing.dom.test.cjs`（需 `jsdom`）測互動。Local Memory 的 Config fixture 驗證資料形狀與跨節點規則，真實 ES 的 M1 驗收另做。

| 提交 | 內容 |
|---|---|
| [`dcc63fe`](https://github.com/SunnyWenwen/rag_platform/commit/dcc63fe) · [`b779dd7`](https://github.com/SunnyWenwen/rag_platform/commit/b779dd7) | User Remote API 與單一 `Document` |
| [`b236eb7`](https://github.com/SunnyWenwen/rag_platform/commit/b236eb7) · [`18c0c12`](https://github.com/SunnyWenwen/rag_platform/commit/18c0c12) · [`e70e7a4`](https://github.com/SunnyWenwen/rag_platform/commit/e70e7a4) | 圖面、System Config 草案、Component 版本 |
| [`c233246`](https://github.com/SunnyWenwen/rag_platform/commit/c233246) · [`d5cb6fe`](https://github.com/SunnyWenwen/rag_platform/commit/d5cb6fe) · [`bb88f00`](https://github.com/SunnyWenwen/rag_platform/commit/bb88f00) · [`b6d7043`](https://github.com/SunnyWenwen/rag_platform/commit/b6d7043) | Inference 融合與分組、每 Query 單一清單、Chunking 單欄、單一 Rewrite |
| [`3560ba9`](https://github.com/SunnyWenwen/rag_platform/commit/3560ba9) · [`4819d8c`](https://github.com/SunnyWenwen/rag_platform/commit/4819d8c) · [`784a936`](https://github.com/SunnyWenwen/rag_platform/commit/784a936) | System／索引生命週期、ES 文件覆寫、Builder 原始資料 |
| [`839de1b`](https://github.com/SunnyWenwen/rag_platform/commit/839de1b) · [`298e365`](https://github.com/SunnyWenwen/rag_platform/commit/298e365) · [`2cf5d1c`](https://github.com/SunnyWenwen/rag_platform/commit/2cf5d1c) | Inference 失敗與文件權限、查詢開放／CSV／ES-first、Builder 重送／索引指紋 |

## 9. 貼給新對話的指令

> 請先讀 `SunnyWenwen/rag_platform` 的 `docs/rag-system-factory` 分支，從 `docs/00_conversation_handoff.md` 接手。以交接的已確認／草案狀態為準，先對照 02、03、04、05、08 的規格。接著用 `metadata.department` 要做 Filter、`metadata.parent_chunk_id` 要 `group_by` 的例子，提出一版 metadata 欄位宣告與 Indexing／Retrieval 的串接方式，並說明如何和 `structdata`、`string_array`、範圍 Filter 的設計對齊。先跟我討論，等我確認後再同步規格與相關 Schema／範例。後續接 ES 寫入逾時安全重送，以及 M1 的第一份可執行 Config。
