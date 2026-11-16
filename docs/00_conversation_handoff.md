# Retrieval Builder／Engine 對話交接

| 項目 | 交接資訊 |
|---|---|
| 來源 | ChatGPT 專案 Generic rag system platform 的 `[MAIN] 主要對話`，整理至 2026-11-16 |
| 目標 repo／分支 | `SunnyWenwen/rag_platform`／`docs/rag-system-factory` |
| 核對基準 | 交接撰寫前的分支 HEAD [`2cf5d1c`](https://github.com/SunnyWenwen/rag_platform/commit/2cf5d1c0516d31422083c0781b0b12005a38fc67)，之後若有新提交，先比對差異 |
| 對話停點 | Data Meta Schema、Filter、Remote 邊界及發布驗證已確認並同步。下一題是 ES 寫入逾時後的安全重送。 |

這份交接用於續談。[README](../README.md) 是規格入口，[08 決策登錄](08_plan_and_decisions.md) 維護正式決策與未決事項。讀到較早的對話、原型或歷史範例時，以現行規格和決策登錄核對。

## 1. 接手時先掌握的狀態

| 狀態 | 內容 |
|---|---|
| 分支已記錄 | Retrieval-only、LangGraph、單一 `Document`、User Remote API、Admin 全域模板、Inference 結果處理、System／索引生命週期、ES 文件覆寫、Builder 管理來源與重送、ES-first 的 M1。 |
| 已同步至規格 | Data Meta Schema 欄位宣告、索引覆寫、固定及動態 Filter、Remote I/O 與發布驗證。見 [第 6 節](#data-meta-handoff)。 |
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
- Inference Input 為平台節點。Query Transformation／Retrieval／Rerank 可單獨或相鄰合併。Remote I/O 都是 `QueryContext[]`。整段包給 Remote 時，Runtime 驗證回傳候選，再依對方順序交付。Remote Retrieval 查自有資料可直接用，候選仍須符合 System 從 Ingestion 推導的可檢索 `Document` Schema。Remote 收到合併後的 filters，自行決定過濾、排序及截斷。後續內建 Rerank 可使用同一套候選欄位。
- 有效設定在區段第一個節點使用 `component_id: remote_api`、`component_version`、`through`、`service_ref`，拒絕重疊，涵蓋節點不再單獨執行。原設定可留在 UI Draft。Import／Inference Input 宣告執行參數，`{{params.name}}` 可傳至下游，完整引用保留型別。認證用固定或動態 `secret_ref`，Runtime 檢查後解析並注入 Header。憑證與執行參數留在各自的環境／請求作用域。
- Graph 類檢索曾討論由平台方開發可選的內建模組，沿用共用資料形狀及契約。這是能力方向，M1 驗收範圍見第 7 節。

來源：[資料契約](02_data_contracts.md) · [Engine／Remote API](03_engine_and_components.md#remote-api) · [Descriptor](04_component_descriptor.md) · [Remote 範例](../examples/user_remote_api/README.md)

## 4. Inference 與結果處理

- Query Transformation 的 `none` 直接用原問題，`rewrite` 是一個 Component，使用 `llm_ref`、`prompt`、`count`、`include_original` 表達單筆和多筆改寫。LLM 服務集中設定，再從下拉選取。保留 `ori_query`。固定結構化輸出、去重、何時重試及 Prompt 單模組測試仍須依 Engine 草案定細節。
- **同 Query 多路**：內建 Retrieval 每 Query／每全文或向量路徑先取 `per_route_k`。一路可直接交付，多路須選 RRF 或 Sum Score，以 `data_id` 對齊。按當前排名分組後，才取 Retrieval `top_n`。每 Query 只交付一份 ResultSet，查無命中仍可交付空 `items`。路徑與融合策略的專屬參數及預設待定。
- **Rerank**：對候選做模型打分與重排，再做當步可選 `group_by`，最後做 Rerank Top N。**跨 Query** 的 UI 控制在 Query Transformation，可選 Retrieval 或 Rerank 完成後才執行，依序融合 → 分組 → 跨 Query Top N。可設在 `after_retrieval` 或 `after_rerank`，Config 正式形狀仍屬草案。Rerank 為 None 時仍可執行後置跨 Query 規則。
- **分組**：開啟時預選 `document_id`，也可選候選 `Document.structdata` 的 `string` 欄位，例如 `structdata.parent_chunk_id`。可多選成組合鍵，保留當時排名最高的候選。任一分組欄缺值的候選各自保留。分組候選欄位來源 `candidate.document_fields` 已加入 Descriptor 草案，內建選項可離線驗證。
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

<a id="data-meta-handoff"></a>
## 6. Data Meta Schema 已定案

- Import 宣告 structdata 欄位的 type、required、searchable、filterable。處理階段沿用保留欄位，依實際輸出宣告新欄位、轉型或補值保證。Indexing 只以 structdata_overrides 覆寫兩個搜尋旗標，最終形狀供 Inference 驗證候選。
- metadata 以巢狀 JSON object 整包攜帶。Filter、文字及分組欄位均使用有宣告的 structdata，group_by 另可用 document_id。首版型別與用途見 [欄位總表](02_data_contracts.md#data-meta-schema)。
- 固定 Filter 放在 Inference Pipeline 的 fixed_filters，請求另帶 filters。兩者以 AND 合併，可包含單層 any 群組。內建 Retrieval 各路先過濾再取 Top-K。Remote 收到共用 I/O，自行決定過濾、排序及截斷。
- 啟用中的引用失效會在草稿定位，修正後才能發布。資料形狀與參數見 [System Config](05_system_config.md#data-schema-config)，離線驗收入口見 [範例](../examples/system_config/README.md)。
- **下一題是 ES 寫入逾時後的安全重送**（Q-008／Q-009／Q-017、API-D05）。已有 Builder 重送的決策，仍要確認前次 ES 操作終止及如何清掉晚到資料。驗收情境為 A 逾時且仍在 ES 寫入，B 重送完成後 A 的 Chunk 才出現。重送前看到的舊 write_id 無法涵蓋晚到資料。見 [ES 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。

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

> 請先讀本交接與 [決策登錄](08_plan_and_decisions.md)。Data Meta Schema 已同步，接續討論 ES 寫入逾時的安全重送，以及 M1 的第一份可執行 Config。
