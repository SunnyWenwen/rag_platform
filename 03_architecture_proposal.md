# RAG Builder — Architecture Proposal

> Version 0.2 · 2026-10-14 · Audience: Engineering / Platform / Management
>
> 本版整合已確認的 UI、模組、資料契約與兩種使用情境。文件描述目標架構；目前 UI Prototype v0.5 只在瀏覽器內模擬，尚未實作 RAG Engine、Runtime API、模型／DB 連線或部署服務。
> 最新模組細節見 [資料契約與索引設計 v0.5](docs/05_data_contracts_search_design.md)；Infra 圖見 [Mermaid](diagrams/02_infra_architecture.mmd)／[PNG](diagrams/02_infra_architecture.png)。

## 1. 平台目的與兩種使用情境

RAG Builder 提供「設定 RAG System → Ingestion → Inference → Evaluation → 調整 Config → 匯出部署」流程，讓不同 Use Case 共用模組化 Engine，減少重複開發 Pipeline。

本文統一使用以下名詞：

| 名詞 | 定義 |
|---|---|
| RAG Builder | 提供設定、測試、評估與匯出功能的開發平台；平台產品的正式名稱 |
| RAG System | 使用者在 RAG Builder 建立的個別系統，包含 Config 與對應資料／索引 |
| RAG Runtime | 載入 RAG System 配置、透過 API 操作的執行服務，可獨立部署 |
| RAG Engine | Runtime 內共用的 Pipeline 執行核心 |

**RAG Builder 提供設定與測試介面；自行部署交付可獨立運作、只透過 API 操作的 RAG Runtime。兩者使用同一套 Engine、模組契約與 Runtime API。**

| 面向 | RAG Builder | 自行部署的 RAG Runtime |
|---|---|---|
| 操作入口 | Workspace／Group、System 卡片、Create／Edit、測試 UI；亦可呼叫 API | Runtime API，供應用程式／外部系統呼叫 |
| 設定 | UI 編輯草稿、檢查相依性、保存 Config Revision | 載入匯出的 Config 與目標環境服務設定 |
| Ingestion | UI 上傳或 API 匯入；UI 呼叫相同 Runtime API | API 接收檔案／JSON records，查詢進度與錯誤 |
| Inference | UI 輸入問題或呼叫 API | API 回傳答案、引用及 request_id |
| Evaluation | 平台上傳 QA Dataset、批次呼叫 Runtime API、保存報告 | 第一版不附 Evaluation UI；可由外部評估工具呼叫 Query API |
| 外部服務 | DEV test use 或使用者自行提供 | 使用單位申請／提供 URL、Model、DB、認證與 Secret |
| 交付內容 | 平台管理與測試能力 | Engine Image Reference、Config、Secret References、部署範例及 API 說明 |
| 執行依賴 | 平台管理 Config、測試資源與執行紀錄 | 啟動及日常操作不依賴 RAG Builder；不打包 Workspace／Create／Edit 等管理 UI |

此處「開發」是使用者在平台設定並驗證自己的 RAG System。部署後仍可經 API 傳入新文件及問題；API only 不代表只能接收 JSON，也不代表 Ingestion 只執行一次。

第一版採固定 Pipeline；不加入通用 DAG 編輯器、自動摘要、多模態向量、Plugin Marketplace 或部署後聊天 UI。Custom Python 可擴充方向保留，尚未納入 Prototype 實作。

## 2. UI 與操作流程

主介面左側切換 Workspace Groups，中間是 RAG System 卡片，右上角提供 **Create RAG System**。Create／Edit 共用設定介面與相依檢查，各操作從同一主介面開啟。

| 操作 | 使用者行為 | 目標行為／目前 Prototype 範圍 |
|---|---|---|
| Create RAG System | 設定 Ingestion／Inference 模組及欄位 | 驗證 Config；Prototype 建立獨立設定物件 |
| Ingest | 上傳檔案或查看 API 範例 | 目標為非同步匯入；Prototype 只模擬完成，不讀取文件內容 |
| Inference | 輸入問題 | 目標回傳答案與引用；Prototype 為示意回答 |
| Evaluation | 提供 QA Dataset | 目標執行評估；Prototype 為固定示意指標 |
| Edit Config | 修改既有 System 設定 | 顯示變更模組／影響；取消不影響現有 Config |
| Export | 補齊自行部署的服務連線 | Prototype 匯出示意 YAML，不含可執行 Engine |

LLM 服務清單在同一個 RAG System 的 Create／Edit 中集中管理。Query Transformation 與 Generation 以 llm_ref 下拉引用，可共用或選不同服務；Embedding／Rerank 因 API 契約不同，保留各自設定。

AI 設定助手採「需求／小型樣本 → 建議差異 → 驗證 → 使用者套用」流程。目前是明示的本機規則模擬，不呼叫 LLM、不自動 Ingestion，不猜測憑證。

## 3. 共用 RAG Engine 與模組契約

### 3.1 已確認的方法與設定

| Pipeline | 模組 | 第一版方法／入口 | 主要設定與卡控 |
|---|---|---|---|
| Ingestion | Import | 檔案／JSON records，可同時支援 | 接收、驗證及保留來源；內容解析屬於 Parsing |
| Ingestion | Parsing | 依資料型態路由至 Parser／欄位映射；OCR 實作待定 | 輸出 Schema、來源欄位 → fields；不同格式可併行，同格式選方法 |
| Ingestion | Chunking | Recursive／Header-aware | 主要切分欄位、複製欄位、metadata；Size／Overlap 使用 Tokens；Tokenizer、分隔符、標題層級 |
| Ingestion | Embedding | DEV test use／Embedding API | fields → vectors mappings；模型、維度、Tokenizer、輸入上限、Batch Size |
| Ingestion | Indexing | Elasticsearch／Local Search（FAISS＋BM25） | fields／vectors 的索引用途與保存欄位；ES 連線；Local Memory／MongoDB |
| Inference | Query Transformation | None／Rewrite／Multi-query | llm_ref、可編輯 Prompt、產生 Query 數量、是否另搜尋原始問題 |
| Inference | Retrieval | 選擇已索引的全文／向量欄位 | 後端由 Indexing 繼承；每路及最終 Top-K；多路用 RRF，依 chunk_id 合併 |
| Inference | Rerank | None／DEV test use／Rerank API | 所選內容欄位、Top-N、API Contract；Top-N 不超過 Retrieval Top-K |
| Inference | Generation | 共用 LLM 清單中的 DEV／OpenAI-compatible API | llm_ref、逐筆 Chunk 模板、回答 Prompt、Temperature、Token Budget |
| 平台測試 | Evaluation | QA Dataset 批次評估 | 指標、Ground Truth、Config／Dataset／Index 版本；不預設加入部署後 Runtime |

Header-aware 需要 Parser 提供可靠標題結構。純全文搜尋可略過 Embedding；Tokenizer 仍需可取得。Retrieval 不另選 Implementation，僅顯示由選取欄位推導的搜尋模式。

Multi-query 的 count 不含原始問題。每個 Query × 搜尋欄位各自取候選，再由 Retrieval 融合；Rerank／Generation 使用原始問題。融合不依賴 Rerank。

### 3.2 資料與執行邊界

- ParsedDocument：document_id、source_revision、fields、metadata、structure。
- Chunk：chunk_id、document_id、source_revision、fields、vectors、metadata。
- fields 放各模組會用到的內容，vectors 放 Embedding 輸出；欄位需有宣告 Schema。Chunk 保留後續需要的資訊，不要求查回 ParsedDocument 才能搜尋或生成。
- 一筆資料可用原文、摘要等多個欄位建立索引；摘要第一版由輸入提供，不自動生成。
- Config、RunContext、Embedding Profile 與 IndexBinding 是控制資訊，不在每個 Chunk 重複。
- Indexing 與 Inference 透過已建立的索引銜接，並非同一次串行函式呼叫。

實作以部門既有 LangChain／LangGraph 生態為基礎，平台自行定義 Pydantic／JSON Schema 契約；框架內部 Document 不直接作為持久化格式。Engine 先使用固定流程，Adapter 封裝各外部服務。

Module Contract 包含 name、version、input_schema、output_schema、config_schema、validate、initialize、run；依需要提供 capabilities／health。Custom Python 未來也需遵守相同契約，優先考慮 Chunking、Query Transformation、Rerank、Evaluation。

Validator 在 UI 與 Engine 共用：檢查欄位來源、型別、向量 Profile、索引能力、LLM 引用與模板變數。失效選項保留顯示，不默默替換；UI 訊息加上 `[Module Name]`，API 另提供結構化 module／code。

### 3.3 Prompt 與服務引用

Rewrite Prompt 支援 {{query}}；Multi-query 另支援 {{count}}。Generation 先逐筆套用 Chunk 模板，組成 {{context}}，再代入回答 Prompt 的 {{query}}／{{context}}。欄位值只替換一次，不執行程式或遞迴解讀文件內的模板。

同一 llm_ref 的 URL、Model、認證及 Timeout 只管理一次，匯出只包含被使用的 LLM。刪除使用中的服務會留下失效引用並阻止儲存。

## 4. 外部服務：測試來源與部署設定

| 依賴 | RAG Builder | 自行部署時必要設定 |
|---|---|---|
| Elasticsearch | DEV test use／自行連線 | URL、認證、Secret Reference、Timeout；索引名稱與 Mapping |
| LLM | DEV test use／OpenAI-compatible API | Base URL、Model ID／版本、認證、Secret Reference、Timeout |
| Embedding | DEV test use／Embedding API | Base URL、Model／版本、維度、Tokenizer／revision、encoding、認證及 Timeout |
| Rerank | None／DEV test use／Rerank API | 啟用時提供 URL、Model、認證、Timeout，並符合平台 Rerank 契約 |
| MongoDB | Local Search 選擇 MongoDB 時提供 DEV／自行連線 | URI、Database、Collection、Secret Reference、Timeout |
| Local Search／Memory | Engine 內的 FAISS＋BM25＋Chunk Store | 不需要 DB；程序重啟後重新 Ingestion |

**DEV test use 僅表示平台提供測試資源。自行部署不能保留未解析的 DEV 綁定或平台內部憑證，也不會自動建立 ES、模型 API 或 MongoDB。**使用單位可以申請企業服務，不一定自行架設，但目標環境必須可連線且有使用權限。

Pipeline 方法、欄位、Prompt 與 Profile 是可版本化的邏輯設定；目標環境的 URL、認證引用與 DB 名稱屬於部署覆寫。匯出覆寫不修改平台測試 Config，不自動回退到 DEV 資源。

Embedding 使用第一版選定的 OpenAI-compatible /embeddings，LLM 使用 /chat/completions；Rerank 使用平台約定的 /rerank request／response。URL 相同不代表 API 格式或模型能力相容；其他格式需 Adapter。

Secret 只保留 secret-name/key 等引用，不將真實帳密寫入 Blueprint 或匯出檔；部署環境自行建立並掛載 Secret。Prototype 目前只驗證格式，真正連線、模型／維度及權限檢查屬於 Engine 實作。

更換 Embedding 模型／版本／維度等 Profile 需重新 Embedding 及建索引；不能只在匯出時改 Model ID。即使沿用同名模型，也需確認 encoding、normalization、維度與版本相容。更換 ES／MongoDB 目標不會搬移測試資料。

若後續 OCR／Parser／LLM Judge 依賴外部服務，也適用同一來源與環境綁定規則；未啟用的功能不要求額外資源。Tokenizer／模型相關檔案亦須在部署環境可取得，不能依賴 RAG Builder 的本機快取。

## 5. Infra 分工與執行模式

### 5.1 RAG Builder

- Control Plane：RAG Builder UI、Builder API／Auth、Config／Run Store、Module Registry、Compatibility Validator、服務設定及 Export。
- Sandbox Data Plane：Runtime API 與共用 Engine，執行 Ingestion／Inference；Evaluation Runner 呼叫相同 Query API，保存測試紀錄及報告。
- 測試服務：可綁定平台 DEV 資源或使用者提供的服務；以 system_id、config_revision、run_id 隔離配置與資料。
- 平台操作紀錄、QA Dataset 及產物保存於平台。Config Store／Artifact Store 的具體 DB 或 Object Storage 選型另定，不代表每個部署 Runtime 都需要同一套儲存服務。

共享 Sandbox 是建議的 MVP 資源策略，Dedicated Sandbox 保留為後續隔離需求；兩者不改變 Runtime API 或 Pipeline 語意。

### 5.2 自行部署

- 對外提供 Ingestion、執行狀態、Query 及健康檢查 API；不包含平台管理 UI／Config 編輯 API。
- 從 ConfigMap／掛載檔案載入已版本化的 Config，從目標環境取得 Secret 與外部服務連線。
- 使用和 Sandbox 相同版本的 Engine Image 與 Module Registry。相同配置具有相同執行語意，但不同模型服務／資料仍需在目標環境驗證。
- 日常執行不需連回 RAG Builder 的 Config Store、Controller 或測試服務；Logs／Metrics／Traces 送至部署環境的觀測工具。
- 文件／records 由 Runtime API 接收。永久保存原始檔與 ParsedDocument 的政策尚待確認，不強制每個 Runtime 都依賴平台 Object Storage。

### 5.3 搜尋後端與持久化

| 模式 | 搜尋位置 | 資料保存／重啟 | 第一版執行限制 |
|---|---|---|---|
| Elasticsearch | ES 全文／向量搜尋 | 目標 ES 保存 Chunk／索引；使用既有相容資料或重新 Ingestion | 可規劃 API／Worker 分離，實作時再驗證更新一致性 |
| Local Search／Memory | Engine 內 FAISS＋BM25 | Chunk／vectors 只在記憶體；程序結束後需重新 Ingestion | 每個 System 的 Ingestion／Inference 共用同一程序；單副本 |
| Local Search／MongoDB | Engine 內 FAISS＋BM25 | MongoDB 保存 Chunk／vectors；重啟時重建搜尋結構 | 同樣先採單副本；MongoDB 不自動同步不同 Pod 的 FAISS |

Infra 圖的 Local Search 表示 Engine 內的能力，不是另一個必需的資料庫服務。不能在 Memory 模式中讓 Ingestion Job 執行完即退出，並假設另一個 Inference Pod 能讀取其記憶體索引。

第一版可用同一個 Runtime API 程序承接非同步 Ingestion。Queue／獨立 Worker、HPA、排程匯入、索引原子切換屬於後續容量需求，不作為 Prototype 的預設部署要求。

## 6. Builder API 與 Runtime API

以下是平台自訂契約提案，Endpoint 與 payload 尚未實作。Builder API 路由處理 System 管理；Runtime 路由處理資料與問題。RAG Builder UI 經 Platform Auth／路由綁定正確 System／Revision，再呼叫相同 Runtime Handler，不另寫一套 UI 專用 Pipeline。

### 6.1 Builder API（Control Plane）

| Method | Path | 用途 |
|---|---|---|
| POST | /api/rag-systems | 在 Group 建立 System |
| POST | /api/rag-systems/{id}/config:validate | Schema／相依驗證，回傳模組錯誤 |
| POST | /api/rag-systems/{id}/revisions | 保存 Config Revision 與變更影響 |
| POST | /api/rag-systems/{id}/evaluation-runs | 用 QA Dataset 啟動平台評估 |
| GET | /api/evaluation-runs/{run_id} | 評估狀態與報告 |
| POST | /api/rag-systems/{id}/exports | 套用部署覆寫、檢查依賴並產生匯出檔 |

Workspace／Group、Dataset 等管理 API 可在實作時補齊，不打包進獨立 Runtime。Prototype 的 /rag-systems/{id}/ingest 是舊示意路由；UI 實接時需對齊以下 Runtime 契約。

### 6.2 Runtime API（兩種情境共用）

獨立 Runtime 以載入的 Config 固定綁定一個 System／Revision；共享 Sandbox 由平台可信路由選擇綁定，不直接相信客戶端任意指定的 Tenant／Revision。

| Method | Path | 輸入／輸出 |
|---|---|---|
| POST | /v1/ingestions | application/json records 或 multipart/form-data files；202 回傳 run_id、status、config_revision |
| GET | /v1/ingestions/{run_id} | queued／running／completed／failed、處理數量、模組錯誤 |
| POST | /v1/queries | query；回傳 answer、citations、request_id、config_revision |
| GET | /health/live | 程序存活狀態 |
| GET | /health/ready | Config／必要資源初始化狀態 |

JSON 與檔案入口都經 Import → Parsing → 相同 Pipeline；上傳檔案不是在瀏覽器完成正式 Parsing。健康檢查與索引可查詢狀態分開：Runtime 可先接收 Ingestion，Query 在索引未就緒或重建中回傳明確狀態，不回傳示意答案。

問答範例：

```json
{"query": "設備多久需要保養？"}
```

```json
{
  "request_id": "req-example-1",
  "config_revision": 3,
  "answer": "依設備規範執行保養。[1]",
  "citations": [
    {"citation_id": "1", "document_id": "doc-1", "chunk_id": "chunk-7"}
  ]
}
```

錯誤統一包含 request_id、code、module、message；例如 module=Embedding、code=SERVICE_TIMEOUT。UI 可顯示為 `[Embedding] ...`，不以例外堆疊取代可理解訊息，也不回傳憑證。

Ingestion 需定義批次部分失敗、重送與文件更新語意；document_id／source_revision 規則沿用資料契約。第一版 Memory 模式的資料與執行狀態在程序重啟後可能遺失；跨重啟的任務恢復及持久化 Job Store 不視為已具備。

Runtime API 的呼叫認證由部署環境提供 API Key／Token 或企業 Gateway，與呼叫模型／DB 的 Secret 分開。Streaming、對話歷史與 Query override 保留為後續需求，第一版不預設加入。

## 7. Config 修改與測試生命週期

| 變更 | 行為 |
|---|---|
| Parsing／Chunking／Embedding／Indexing 有效配置或資料目標 | 標記需重新 Ingestion；完成前不使用新版索引回答 |
| Query Transformation／Retrieval／Rerank／Generation／被引用的 LLM | 不需重新 Ingestion；清除舊示意結果並重新測試／評估 |
| System 顯示名稱 | 不改實體 collection；名稱由建立時的 Workspace＋System 名稱＋穩定 ID 產生 |
| 未啟用服務／未引用 LLM 的草稿設定 | 不影響有效 Pipeline，不因而要求重建 |

操作順序為建立草稿、驗證、Ingestion、問答與評估；效果不符時 Edit Config，再依變更範圍重測。目標 Engine 需管理 Config Revision 與索引就緒狀態，Prototype 目前用狀態旗標模擬，未實作雙版本索引切換。

部署後的 Config 更新由更換配置與重新啟動／部署完成，無須部署 RAG Builder 的設定介面。是否需要線上熱更新、長任務不中斷及新舊版本切換，屬於後續運維設計。

## 8. 匯出與交付

匯出交付的是 RAG Runtime，不是整個 RAG Builder。目標 Bundle 包含：

- 相同 Engine Image 的版本／Digest、Module Version 與 Config Revision／Hash。
- Pipeline Config、使用中的 LLM 清單與目標環境連線覆寫。
- 必要 Secret References、K8s 部署範例及 Local Search 的單副本限制。
- Ingestion／Query API 範例、初始化步驟及資料準備說明。
- 選配的 Evaluation 報告；是否作為強制 Release Gate 另定。

不包含真實憑證、測試文件、Chunk／vectors、平台 DB 或管理 UI，也不建立外部模型／搜尋服務。目標環境需已有相容資料或先執行 Ingestion。

匯出分兩個狀態：

1. 待設定草稿：可保留未解析的 DEV 標記，不能當作已可執行的部署配置。
2. 已填妥配置：必要 URL／Model／Secret 引用及 Schema 已完整；仍需在目標環境驗證連線、認證、模型 Profile、資料與初始化。

目前 Prototype 的 configured_unverified 就是第二種格式檢查結果，不代表已部署成功。YAML 使用示例 Image；尚未包含可執行 Engine、API 說明 Bundle、真正健康檢查或啟動驗證，後續實作需補齊。

使用單位可先依部署範例自行部署，後續整合企業 CI／GitOps。獨立 Runtime 不依賴平台 Controller 持續調度；正式交付流程、核准及自動部署工具仍待確認。

## 9. Evaluation 與 Observability

QA Dataset 最少包含 question、expected_answer；計算 Retrieval 指標需 relevant document／chunk IDs。區分 Retrieval（Recall@K、MRR、nDCG）、回答品質、延遲與失敗率，缺少 Ground Truth 時不宣稱已計算可靠的 Retrieval Metrics。

評估執行綁定 dataset_version、config_revision、index_snapshot 及使用的模型／Judge Profile。若使用外部 LLM Judge，也納入服務來源與環境綁定；目前沒有真實 Judge 或評估實作。

共用 Engine 對各模組產生 request_id／run_id、耗時、錯誤與資源使用紀錄。Dev 由平台查看，部署後可串接使用單位的 Logs／Metrics／Traces。Langfuse 等工具可作整合候選，不強制將平台觀測服務當作每個 Runtime 的必要依賴。

## 10. MVP 範圍與待確認項目

| 階段 | 範圍 | 驗收重點 |
|---|---|---|
| 共用核心 | 固定 Pipeline、資料／Config Schema、Adapter、Validator | 相同 Config 可由 Engine 執行，錯誤可定位模組 |
| 平台實接 | 現有單介面、DEV 資源、Runtime API、Ingestion／Inference | UI 與 API 跑相同流程；依賴卡控與重建規則正確 |
| 測試迭代 | QA Dataset、Evaluation、模組執行紀錄 | 結果可追溯至配置／資料／模型版本 |
| 獨立交付 | 環境覆寫、Runtime Image、API 說明及部署範例 | 目標環境不依賴 RAG Builder，API 匯入後可問答 |

已確認兩個搜尋後端為 ES／Local Search，不再沿用初版「只選一個 Backend」或 OpenSearch 的預設範圍。無額外要求的功能先不加入 Prototype。

仍需確認：首批 Parser／OCR 格式與實作、Local Search 的具體 BM25／斷詞及容量、缺欄位與文件更新政策、原始資料保留方式、Runtime API 認證方案、部署資源申請流程，以及 Evaluation Gate 是否強制。

資料契約 v0.5 與本提案描述目標行為；UI 已實作的部分及限制以 README／Prototype 為準。API 契約、平台／部署環境分工及 Export Bundle 新內容尚待實接，不能將本文件視為已完成的後端功能。

