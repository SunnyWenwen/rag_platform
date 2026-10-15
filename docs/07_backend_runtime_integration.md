# RAG Builder — Backend、Runtime API 與整體串接規格

> 文件集 v0.9 · 2026-10-15 · 開發規格草案
>
> 本文包裝 04 的 Engine，負責管理、HTTP、任務、持久化與交付。Endpoint 大方向沿用既有提案；精確 Envelope、認證、狀態與儲存細節為建議，依 Q-ID 核定後實作。

## 1. 責任邊界

| 層 | 責任 |
|---|---|
| [04 Engine](04_module_methods_io_contracts.md) | Config 驗證／編譯、模組初始化、Pipeline 組裝、Ingest／Query 執行及領域錯誤 |
| Builder Backend | System／Revision／Group、授權、服務目錄、Dataset、AI 助手、Evaluation Job、Export |
| Runtime API | 將 HTTP 請求轉成 05 型別，呼叫相同 Engine，包裝 Job／Query／Health |
| Runtime 內部管理 | 可信地綁定 System／Revision、建立或更新 Engine 實例；不開放任意外部使用者換租戶 |

Engine 可直接由 Python Config 使用，不能反向 import Builder Web App 或存取 Builder DB。UI、Runtime API、外部 Evaluation 使用同一核心流程，不複製一套模擬／真實 Pipeline。

兩種環境：共享 DEV Runtime 由 Builder 的可信路由選 System；獨立 Runtime 啟動時綁定一個 System／Config。相同 API 語意不代表相同 Base URL、權限或資料。確切多 System 路由／內部管理接口見 Q-019／Q-020。

## 2. 建議程式與依賴結構（Q-001）

```text
packages/contracts/       # 05：Pydantic／JSON Schema
packages/engine/          # 04：Compiler、Registry、模組、Adapters
services/runtime_api/     # 本文：HTTP／Job／Engine lifecycle
services/builder_backend/ # 本文：System、Revision、Dataset、Export、助手
apps/builder_ui/          # 06：正式 UI
examples/                # 完整 Config／資料／呼叫範例
```

以上為目錄草案，不是現有檔案。依賴允許 UI → Backend／Runtime → Engine → Contracts／Adapters；Engine 不依賴 UI／Backend。可先以同一 repository／同一服務程序開發，不要求每個邏輯元件部署成微服務。

技術版本、FastAPI 等 Web Framework、資料庫及建置方式仍待 Q-001／Q-016；不因示例路徑就強制選定。

## 3. 平台管理資料與儲存

以下為建議領域資料，完整 DB Schema 待決：

| 資料 | 保存語意 |
|---|---|
| Workspace／Group | 使用者可見範圍與系統組織；權限規則 Q-006 |
| RAGSystem | 穩定 system_id、顯示名稱、collection、管理狀態 |
| ConfigRevision | 有效 Config、草稿關聯、版本／Hash、建立時間與作者 |
| IndexBinding | System／Config 對應的索引資料版本、Profile、searchable 狀態 |
| ServiceReference | DEV 或使用者服務設定與 Secret 引用；System 的 llms 有明確作用域 |
| IngestionRun／EvaluationRun | 綁定 Config／資料版本、狀態、數量、錯誤、Trace、時間 |
| Dataset／EvaluationReport | 版本化 Dataset、逐題結果、指標、Judge／Rubric、Target |
| ExportArtifact | Config／Image／環境覆寫、驗證狀態、產出版本 |

Config Store 與 Artifact／Run Store 不等於 Local Search 的選配 MongoDB；使用者選 Memory 仍可能在 Builder 保存平台管理資料。獨立 Runtime 不強制連回這些平台儲存。

原始檔、ParsedDocument、Prompt／Context Trace、Job 跨重啟、報告保留期限與刪除規則見 Q-016。歷史報告不因新 Config 失效就自動刪除。

## 4. System／Revision 與 Engine 生命週期

### 4.1 建立與啟動（建議流程）

1. Backend 驗證身分與 Group 權限，建立 system_id／穩定 collection。
2. 收到 Draft，經 05 編譯／Validator，顯示錯誤與變更影響。
3. 保存 Config Revision；以可信管理呼叫要求 Runtime 綁定配置。
4. Runtime 呼叫 04 Engine 初始化；服務解析、Profile 與資料就緒分開回報。
5. UI 可執行 Ingest／Query；沒有索引時 Query 回明確不就緒。

共享 Runtime 不代表每建立 System 就新建 Pod。實例快取、資源配額、LRU／釋放、租戶隔離與同時工作限制見 Q-020。

### 4.2 Config 更新

Backend 儲存前以有效設定比較，依 05 判定影響；UI 與 AI 都不能繞過。Edit 使用獨立草稿，取消不生效。

**待決的發布模型**：

- 建議分開 saved_revision、active_revision、index_generation，查詢綁定可用的相容版本。
- 可選第一期簡化為新版 Ingestion 改動後阻止查詢，重建完成才啟用。
- 或允許舊 Revision 繼續服務，待新版完整成功後切換。

兩者對 UI、併發及儲存差異很大，Q-010／Q-015 未核定前不能自行承諾原子切換／零停機。僅修改 Prompt／Retrieval 等 Inference 設定不重建，但仍記錄新版本並重新評估。

## 5. API 契約

### 5.1 Builder Backend（Control Plane）

以下路徑沿用原提案，完整 OpenAPI／認證／欄位 Q-019：

| Method | Path | 責任 |
|---|---|---|
| POST | /api/rag-systems | 在授權 Group 建立 System |
| POST | /api/rag-systems/{id}/config:validate | Schema／相依驗證，回傳模組及欄位錯誤 |
| POST | /api/rag-systems/{id}/revisions | 保存配置與變更影響；需處理版本衝突 |
| POST | /api/rag-systems/{id}/evaluation-runs | 選 Dataset／Target 啟動評估 |
| GET | /api/evaluation-runs/{run_id} | 狀態與報告引用 |
| POST | /api/rag-systems/{id}/exports | 套用目標環境覆寫並產生 Bundle |

System 列表／讀取、Group／Dataset CRUD、AI suggestion／連線檢查、DEV Runtime Binding 的完整路徑尚未定義；由 Q-019 在 M3／M4 前補齊。不以表中六條當作完整 Backend API。

### 5.2 Runtime API

| Method | Path | 行為 |
|---|---|---|
| POST | /v1/ingestions | JSON records 或 multipart files；202 回 run_id、status、config_revision |
| GET | /v1/ingestions/{run_id} | 工作狀態、進度、逐項錯誤及就緒資訊 |
| POST | /v1/queries | 問題、本次 filters；回答、引用與版本 |
| GET | /health/live | 程序是否存活 |
| GET | /health/ready | Config／必要資源是否初始化；不等同已有可查索引 |

獨立 Runtime 的業務請求不另帶 System ID；配置已綁定。DEV 的可信路由選定 System，不能直接信任使用者提供的 tenant／system header。Bearer Token 僅為認證示意，實際 Gateway／Token 政策見 Q-006／Q-019。

### 5.3 JSON Ingestion

```json
{
  "records": [{
    "document_id": "manual-001",
    "source_revision": "v1",
    "fields": {"text": "設備每月需清潔散熱孔。", "title": "保養規範"},
    "metadata": {"department": "manufacturing"}
  }]
}
```

Record 格式見 05；input 欄位已是 Schema 目標名，不傳 structure／vectors。請求與回應的大小／數量上限、冪等鍵見 Q-008／Q-019。

```json
{"run_id":"ing-001","status":"queued","config_revision":3}
```

以上 202 只表示接受；回應前須先完成授權、請求形狀與必要的同步預檢。正式預檢深度、排隊可用性、拒絕後是否留 run 記錄見 Q-017／Q-019。

### 5.4 檔案 Ingestion

Content-Type 為 multipart/form-data，files 可重複多次，由 HTTP Client 生成 boundary。HTTP 層保存暫存／ArtifactRef，仍走同一 Import → Parsing → Pipeline。

每檔 metadata manifest、穩定 ID 派生、混合檔案＋records、支援 MIME、檔案偵測、超限及清理的正式契約見 Q-005／Q-007／Q-016／Q-019。未核定前不得以「支援 multipart」宣稱所有 PDF／PPTX／圖片均可解析。

### 5.5 工作查詢

建議結果草案：

```json
{
  "run_id":"ing-001","status":"completed","config_revision":3,
  "processed_records":1,"total_records":1,
  "searchable":true,"errors":[]
}
```

processed_records／total_records 指解析後的邏輯文件數，不是 Chunk 數；可另有模組層 Chunk 計數。檔案尚未解析完時 total 可能未知，不能偽造固定百分比。正式未知計數表示、partial 狀態與 searchable 是否在本回應返回見 Q-002／Q-009／Q-019。

### 5.6 Query

```json
{"query":"設備多久需要清潔？","filters":[{"field":"metadata.department","operator":"eq","value":"manufacturing"}]}
```

```json
{
  "request_id":"req-001","config_revision":3,
  "answer":"依保養規範，每月清潔散熱孔。[1]",
  "citations":[{"citation_id":"1","document_id":"manual-001","chunk_id":"chunk-example"}]
}
```

HTTP query 映射成 Engine 的原始問題；filters 與預設／ACL AND。Index 版本、Usage／Trace 回傳層級待 Q-019；引用完整規格見 05。Streaming、History、任意 Config override 不預設納入。

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

## 6. 非同步工作與一致性

已選 Local Search 第一版同程序／單副本。Runtime 可用同一服務程序接收 Ingestion 並背景執行；不能用執行完就退出的獨立 Job 保存唯一記憶體索引。CPU 工作／執行緒與並發控制需測試，不能 fork 多個 worker 期待共享 Python 記憶體。

基本狀態方向 queued → running → completed／failed；partial 的終態與取消／恢復尚未定案。不得以 completed 掩蓋部分項目失敗，或只靠前端計時器顯示進度。

Q-008～Q-010／Q-017 需決定：

- 相同文件、相同版本與同一 Idempotency-Key 重送語意。
- 跨批／跨程序 key 的持久性及有效期。
- 文件級／批次級原子性；部分向量成功如何處理。
- 先寫新 Chunk 再刪舊版的切換點；搜尋 refresh 與確認。
- Ingestion 同時 Query、同 System 多個 Ingestion 的順序／鎖。
- Timeout／取消的副作用清理；Client 中斷是否取消工作。
- 程序崩潰後 Run／索引狀態如何辨識、重試與恢復。

階段一可先限定不支援的併發操作並回明確錯誤；不能默默採最後寫入勝出。

## 7. Local Search 恢復與儲存

| 模式 | 重啟 | 正式要求 |
|---|---|---|
| Memory | Chunk／向量／搜尋結構遺失 | 回需要 Ingestion；不回示意答案 |
| MongoDB | 讀保存的 Chunk／vectors／Manifest 重建 | 驗證 Config／Profile／資料版本，完成前不提供不完整索引 |
| ES | 驗證既有 Index／Mapping／Profile | 有相容可用資料才 Query；不存在時可接受 Ingestion |

MongoDB 保存不等於跨 Pod 索引同步。重建失敗、DB 中斷、Profile 不符、損壞資料及大資料量啟動時間見 Q-012／Q-027。原始檔／ParsedDocument 若未保留，不保證可自動重新切分／Embedding。

## 8. Evaluation 與 AI 助手服務

Evaluation Runner 綁定 Dataset／Config／Index／Engine／Judge 版本，逐題呼叫同一 Target，收集實際候選／Context／答案／錯誤後交 04 評分。可重用 Query Client，但 Retrieval-only 入口是否公開需核定。併發、快取、重試、成本與 Gate 見 Q-018／Q-027。

AI 助手 Backend 取得需求、明確允許的樣本及草稿版本，呼叫選定模型並產生受 Schema／Registry 限制的結構化建議；Backend 重驗，不直接修改 active Config 或執行 Ingestion。Prototype 規則模擬不能當作正式助手。Prompt、資料保留、最大樣本、輸出／Diff 與舊建議合併見 Q-024。

## 9. Export、獨立部署與 Secret

### 9.1 Bundle 目標

交付 RAG Runtime，不打包整個 Builder。目標 Bundle 包含：

- Runtime Image 版本／Digest、Module 版本、Config Revision／Hash。
- 有效 Pipeline Config、實際引用服務與環境覆寫。
- ConfigMap／Deployment／Service 等 K8s 設定及 Secret references。
- FTEST／ENT 的環境檔案、啟動與 API 說明、資料準備步驟。
- 若有評估報告，清楚綁定測試環境／資料版本，不能宣稱目標環境已驗證。

不含真實 Secret、原始文件、Chunk／vectors、Builder DB 或外部模型／搜尋服務。目標環境需有相容資料或執行 Ingestion；部署後仍可持續 API 匯入。

### 9.2 驗證與部署

狀態分開：needs_configuration → configured_unverified →（外部連線／資料檢查結果）→ 實際部署結果。本文不指定未核定的完整狀態枚舉；不能用 configured_unverified 表示可直接部署成功。

Local Search replicas=1 且單 API worker；ES 是否多副本需驗證工作／權限／版本策略。resource limits、Probe、TLS／Ingress、CD 工具與 FTEST／ENT 命名見 Q-021／Q-027。

Secret Vault 位於 Runtime 外，以環境支援的解析／注入方式提供；`secret-name/key` 為目前示意引用。正式產品、SDK、檔案掛載路徑與更新政策 Q-021。URL、Header、Trace 與匯出均不得內嵌帳密。換 Embedding Profile 要回 Engine 重建，不能只在匯出改模型 ID。

### 9.3 獨立啟動

建議步驟：讀 Config／環境覆寫 → 解析 Secret → 04 驗證／初始化 → 驗證資料／恢復索引 → 啟動 HTTP。Live／Ready 與 IndexReady 分開；無資料可以接受 Ingestion，Query 回不就緒。部署後 Config 更新可先經重新部署，熱更新／零停機另案。

## 10. Observability、認證與權限

request／run／trace 必須可跨 Backend／Runtime／模組關聯。輸出結構化錯誤、耗時、輸入輸出數及可取得用量；模型與 Judge 也記版本。OTel／Langfuse 為候選，非每個 Runtime 必備外部依賴，具體方案 Q-016／Q-027。

tSSO 是 Builder 的登入方向，實際 Token／Gateway／Backend 驗證見 Q-006。呼叫 Runtime 的認證與 Runtime 呼叫模型／DB 的 Secret 不同。System／Workspace／ACL 由可信 Backend／Runtime Context 注入，Filter 不能提權；獨立 Runtime 仍需部署端認證，不因 API only 就公開匿名。

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
