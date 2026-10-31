# RAG Builder — 開發計畫、驗收與決策追蹤

> 文件同步：2026-10-31 · 開發規格草案（正式 SDK／Config 尚未凍結）
>
> 目的：讓 coding agent 依同一套規格分階段開發，並持續記錄尚不清楚的問題。本文是決策／待決狀態的權威位置；它不把技術建議自動轉成使用者已核可決策。

## 1. 使用方式與狀態

| 狀態 | 意義 | Agent 行為 |
|---|---|---|
| 已確認 | 目前或先前使用者對話明確採用／要求的方向 | 按規格實作；細節未決不重開需求本身 |
| 既有基線 | 本輪整理前 repository 最新文件已記錄的有效設計 | 保留，不回到舊版；遇衝突回報 |
| 建議／待決 | 有候選方案，尚未定案 | 可寫介面／測試替身，不宣稱正式行為已核可 |
| 後續 | 不在目前承諾範圍 | 未被任務指定時不自行開發 |
| 已決 | 某 Q-ID 已完成選擇並同步文件 | 填入決策欄、日期、依據及受影響文件／階段 |

03～07 的 Q-ID 連回本文件。每份文件保留自身待討論清單，完整選項／決策只維護一次。沒有核可的問題不能靠空白 TODO 或聊天記憶隱藏。

現行資料以 IngestionDocument／ParsedDocument／Chunk 三份 Schema 及 13～15 為準；05 為總覽，04／06／07 對齊執行、UI 與 API 邊界。Prototype 與目標規格差異用 backlog／migration 追蹤，原型測試通過不代表 Engine／API 已完成。

**2026-10-16 起的工作方式**：使用者要求後續調整先更新文件；Prototype 所需變更統一記於 [10 UI Backlog](10_ui_adjustment_backlog.md#ui-backlog-pending)，待使用者明確要求修改 UI 再實作。文件提交不代表同步開發原型、Engine 或服務。規劃文件仍依既有要求提交目前分支。

## 2. 文件責任與建議閱讀順序

先讀 [03](../03_architecture_proposal.md)，以 [§3 名詞定義](../03_architecture_proposal.md#terminology) 統一概念與責任邊界，再讀本計畫；實作依序讀 [05 契約](05_data_contracts_search_design.md)、[04 Engine](04_module_components_io_contracts.md)、[07 整合](07_backend_runtime_integration.md)、[06 UI](06_ui_development_spec.md)。

| 權威範圍 | 文件 |
|---|---|
| 正式名詞定義、產品／架構與非目標 | 03 |
| 獨立 Engine、模組組裝／演算法／語意驗證 | 04 |
| 資料流／Config／版本總覽；三份資料 Schema 與語意 | 05；13～15／schemas/ |
| 互動與基本／進階呈現 | 06 |
| HTTP、平台儲存、工作與部署整合 | 07 |
| 決策狀態、階段、驗收／阻擋 | 08 |
| Inference Contract 討論摘要與 UI 整合提案 | 09；欄位以 05、決策以 08 為準 |
| Prototype 待辦與歷史完成證據 | 10；使用者要求改 UI 時才實作 |
| Component 開發、測試及套件交付流程 | 11；Engine 機制以 04、三份共用資料以 13～15／schemas/ 為準，Config／Inference 見 05 |
| Component 設定描述、UI hints、動態選項與相依規則 | 12；設定介面草案，I/O 仍以 05 為準，互動待辦記於 10 |

同一型別／規則不在多份文件各寫一套。03 定義名詞，05 規範對應的資料結構／版本規則，本文保存決策來源及狀態；決策摘要不取代 03 的現行定義。程式 Schema 與文件同步；不能只更新 UI、測試或其中一份規格。

## 3. 已確認方向與保留基線

| ID | 方向 | 依據／狀態 | 主責文件 |
|---|---|---|---|
| D-01 | 03 概覽；04 獨立 Engine；05 資料／Config；06 UI；07 Backend；08 開發與決策 | 2026-10-15 對話／已確認 | 03～08 |
| D-02 | 同一系統支援新手與熟悉 RAG 者；AI 設定、CSV 起始、進階收合 | 2026-10-15 使用者提出／已確認 | 03／06 |
| D-03 | 手寫 Config 可直接執行 Engine；UI 產生 Config，不另生成一套 Engine 程式 | 2026-10-15 對話／已確認 | 04／05 |
| D-04 | 固定 Ingestion／Inference；Builder 與獨立 API Runtime 使用同一 Engine | 舊 03 v0.8／既有基線 | 03／04／07 |
| D-05 | ParsedDocument 五個、Chunk 六個頂層 key；vectors 位於 Chunk | 既有五／六鍵方向；D-46／47 具體化 | 13～15／schemas/ |
| D-06 | fields／metadata 宣告 Schema；CSV 每列映射一次為 IngestionDocument（D-44／45 明確輸入格式） | 舊 05 §15～16／既有基線 | 05／06 |
| D-07 | Recursive／Header-aware、Token 計量；Fixed-size 見 D-36；預設 text 與進階多任務／copy 依 D-47／48 | 舊 05 §13.1／既有基線，新增 Component 不取消原方法 | 04 |
| D-08 | Embedding fields→vectors；摘要先由輸入提供；文字 Dense 優先 | 舊 05 §6／既有基線 | 04／05 |
| D-09 | ES／Local Search（FAISS＋BM25）；Local Memory／MongoDB | 舊 05 §8／既有基線 | 03／04 |
| D-10 | Local Search 同程序／單副本；MongoDB 只持久化並支援重建 | 舊 03 §5.3／既有基線 | 04／07 |
| D-11 | 結果處理採兩層合併時點設定／四處 Top N；Prototype 已有設定與預覽，Engine 未實作 | 2026-10-15 已確認 UI 與原型更新；現行紀錄見 10 | 04／05／10 |
| D-12 | Sum Score 不自動正規化；RRF 預設 k=60；兩種策略有效參數分開 | 舊 05 §17／既有基線 | 04／05 |
| D-13 | System 共用 LLM 清單；Rewrite／Generation 以 llm_ref 引用 | 舊 05 §14／既有基線 | 05／06 |
| D-14 | 原始問題保留；Rerank 使用平台約定 API；Generation 兩層單次模板替換 | 舊 05 §13～14／既有基線 | 04／05 |
| D-15 | Filter 區分可過濾欄位／預設條件／本次條件；eq／in 字串、全部與 ACL AND、Top-K 前限制 | 舊 05 §15／既有基線 | 04／05／07 |
| D-16 | Ingestion 有效配置變動需重建；Inference 變動重測；未啟用草稿不影響執行 | 舊 05 §13.7／既有基線 | 05／07 |
| D-17 | 助手建議需驗證及使用者套用，不自動執行 Ingestion／猜憑證 | 舊 05 §13.7／既有基線 | 06／07 |
| D-18 | DEV 服務只供測試；部署覆寫不改測試 Config；只輸出 Secret 引用，不搬資料 | 舊 03 §4／§8／既有基線 | 03／07 |
| D-19 | FTEST／ENT 由使用單位自行 K8s 部署，Runtime 不依賴 Builder 管理 UI | 舊 03 與最新圖／既有基線 | 03／07 |
| D-20 | Evaluation 重用相同查詢／檢索，版本與缺標註需可追蹤；首批指標與 Gate 待定 | 舊 04／03／既有基線 | 04／07 |
| D-21 | collection 由 Workspace＋System 名稱自動產生，不要求手填；穩定 ID 防重，改名不換實體 | 2026-10-14 09:31（台北）使用者要求／已確認 | 05／06／07 |
| D-22 | Parsing 只顯示結構化 JSON；其他格式及所有相關設定預設收合 | 2026-10-14 17:09 使用者要求／已確認 | 06 |
| D-23 | 使用者可配置融合策略及在哪個合法處理步驟後合併；先釐清 Inference 傳遞物件／多路分數，再核定具體 stages／兩層／預設 | 2026-10-14 要求及 2026-10-15 11:03 釐清／需求已確認，細節 Q-014 | 03／04／05／06／07 |
| D-24 | 共用 LLM、可編輯 Query Prompt、Generation 模板範例／套用按鈕與 Rerank 格式說明 | 2026-10-14 10:44～11:00 對話／已確認方向 | 04／05／06 |
| D-25 | L1／Infra 的框、標籤、方向、圖示及省略線依使用者既有修改保留 | 2026-10-14～15 對話與基準圖／已確認 | 03 §4／既有圖面 |
| D-26 | Ingest／Inference 的 API 端點說明隨時可看，包含未 Ingestion 狀態 | 2026-10-14 13:11 使用者要求／已確認 | 06／07 |
| D-27 | 以部門 LangChain／LangGraph 生態為技術背景；Haystack 未被使用者選定 | 2026-10-12 15:58 對話核對／已確認偏好 | 03／04／Q-001 |
| D-28 | Engine 是模組組裝／執行核心，Runtime 加 API，System 是套用 Config 的具體應用；可直接 SDK 建立 | 2026-10-15 名詞對齊／已確認方向 | 03 §3、04、07 |
| D-29 | 正式 Config 指模組 Component／參數與邏輯；Blueprint 是助理引入的名稱，移出正式領域模型 | 2026-10-15 10:06 使用者釐清／已確認 | 03／05／06／07 |
| D-30 | 同一 System 同版 Config 在不同環境保持相同；部署設定可不同 | 2026-10-15 10:06 使用者確認／已確認 | 03／05／07／Q-015／Q-021 |
| D-31 | 正式階層為 Workspace → System，無額外 Group 層 | 2026-10-15 10:06 使用者確認／已確認 | 03／05／06／07 |
| D-32 | 名詞定義集中在 03 §3，05 統整資料／版本規則，三份資料細節見 13～15，08 保留決策紀錄；其餘引用主責文件 | 2026-10-15 10:22～10:24 建議後由使用者確認撰寫／已確認 | 03 §3、04～08／README |
| D-33 | Memory／MongoDB 模式隨 Config 跨環境固定；DEV 用 Memory，FTEST／ENT 也用 Memory，不能只以部署覆寫切換 | 2026-10-15 11:03 使用者確認／已確認 | 03／05／06／07 |
| D-34 | ResultSet 後處理只有去重＆合併、取 Top N、新模型算分三類；Fusion 為合併策略 | 2026-10-15 14:24 使用者提出、14:28 延續／已確認方向 | 04／05；討論記錄 09 |
| D-35 | 排序與 rank 更新抽成共同處理，三類操作輸出皆有序；rank=1 最好且連續 | 2026-10-15 14:28 使用者要求、14:31 要求記錄／已確認方向 | 04／05；UI 提案 09 |
| D-36 | Chunking 新增 Fixed-size，沿用 Token 計量；保留 Recursive／Header-aware | 2026-10-16 09:42 使用者要求／方法已確認，精確 Token 邊界 Q-004 | 04／05／06；UI 待辦 10 |
| D-37 | 階段重排 M0～M7；M4 獨立 AI 設定助手，M5 Builder 前後端與助手 UI 整合，M6 評估，M7 獨立交付 | 2026-10-16 09:31～09:45 討論及使用者修正／已確認方向 | 03／06／07／08 |
| D-38 | 後續需求先更新文件；Prototype 調整記入 backlog，使用者要求改 UI 時才實作 | 2026-10-16 09:42／09:45 使用者要求／已確認 | README／03／06／08／10 |
| D-39 | Indexing 保存全部 Chunk.fields／metadata，移除「儲存內容」；只選全文／向量／過濾索引；Chunking 預設繼承全部有效 metadata，排除功能有需求再規劃 | 2026-10-16 10:05 使用者確認前述三點／已確認，UI 尚未改 | 03／04／05／06；UIB-005／006 |
| D-40 | 新增 Module Developer，依公開 Module 契約開發 Component，讓 Builder User 選用；04 維護 Engine 擴充規格，11 維護開發指南 | 2026-10-28 使用者提出角色／修改 L1，並要求依前述討論調整文件／需求方向；具體介面、套件與發布政策仍待決 | 03／04／11；Q-001／Q-002／Q-022；UIB-010 |
| D-41 | 固定兩個 repo：rag_platform 放 Builder 前後端與管理整合；rag_engine 放 SDK、Engine、Components／Adapters 與 Runtime API。Module Developer 在同 repo 提交 Component，整合測試後交付完整 Runtime Image；接口相容時 Builder／Runtime 可各自升級 | 2026-10-28 使用者確認 Builder 與 Engine＋擴充實作分為兩個 repo，並要求調整文件／已確認；精確套件／接口／CI 細節仍待決 | 03 §3.7／04／07／11；Q-001／Q-019／Q-021／Q-022；UIB-010 |
| D-42 | 採 Schema 驅動 Component 設定表單：共用 Schema 輸出、UI hints、動態選項與 Engine 相依驗證；不相容選項可見且停用、無關欄位隱藏、進階收合、失效選擇保留報錯、未知必要控制項明示不支援 | 2026-10-28 使用者回覆「好，按照你的建議規劃」／方向與操作行為已確認；component-ui-0.1-draft 的鍵名、Meta-schema、工具與 API 仍待 M0 起分階段核定 | 04 §7.6／06／07 §5.8／11／12；Q-001／Q-002／Q-019／Q-022／Q-025；UIB-010 |
| D-43 | 可擴充實作統一稱 Component；Module 為功能分類／契約，Component Instance 為配置後的實例。同步 component_id、SDK 類別、目錄／套件／entry point、Descriptor 及文件／L1 圖 | 2026-10-29 使用者確認「Component 好了，有疊積木的感覺」並要求更新相關文件／命名已確認；不改模組分工或執行行為 | 03 §3.8 為權威對照；04～12／README／L1；Q-002 遷移，UIB-010 |
| D-44 | Engine JSON-only Ingestion；扁平 document_id＋content／base64／uri 三選一；Builder／呼叫端負責上傳轉換；原始／已解析資料需相容 Parser，多 Parser 自動路由 | 2026-10-29 使用者確認全部支援、自動路由、扁平格式並要求保存 Schema；共用 Parser 輸入後依 D-45 確認；批次及輸出結構仍為草案 | 13／schemas/ingestion_document.schema.json；04～07；Q-002／Q-005／Q-019；UIB-011 |
| D-45 | API 單筆文件與 Parser Input 共用相同 IngestionDocument Schema；content／base64／uri 三選一保留，不另建 ParserInput；取得內容使用 SDK 共用能力，Context 不屬 API body | 2026-10-29 使用者確認「api schema 跟 parser 的 Input 都是相同 schema」並要求記錄；共用契約已確認，SDK／Context 精確簽名仍待決 | 13 §2／§4、schemas/ingestion_document.schema.json；04／05／07；Q-002／Q-016／Q-017；UIB-011 |
| D-46 | ParsedDocument 先提供五鍵外層、文字基線／全文標註／Page-Block 與註冊擴充的可驗證草案；資料能力與 Chunker 實作分開，引用單一共用定義；用固定 Docling／MinerU 輸出實際比對 | 2026-10-30 使用者要求先按前述建議寫 Schema 並實際比對；草案產出與驗證範圍已授權，具體擴充／子結構／版本與 SDK 尚未凍結 | 14／schemas/parsed_document.schema.json／examples/parsed_document；04～07／13；Q-002／Q-005／Q-006／Q-016；UIB-012 |
| D-47 | Chunk 六鍵共用草案；預設直接切 text、不選欄位，進階才多任務／複製；來源追溯放 metadata._rag，向量項目記錄 Profile／來源；可重現 fingerprint＋全域 ordinal | 2026-10-30 使用者確認前述方向並要求 Schema／文件；語意方向已確認，精確格式／SDK 與索引發布仍為草案 | 15／schemas/chunk.schema.json／examples/chunk；04～12；Q-002／Q-003／Q-004／Q-006／Q-007～Q-010／Q-015；UIB-013 |
| D-48 | 多欄位切分任務預設各自輸出 fields.text；完整來源需明確複製到不衝突名稱。第一版必要切分欄位缺失／型別錯誤／全空白、必要任務零產出及明確 copy 缺失均報錯 | 2026-10-30 使用者回覆「24 照你建議 OK」；concat／固定文字另討論，精確 Schema／SDK 未凍結 | 15 §2／§9；04／05／06／UIB-013；Q-002／Q-004／Q-009 |

兩層合併預設勾選且在 Retrieval 後已確認，Prototype 的設定／預覽狀態見 10；不能把展示能力當作 Engine 已實作。Q-014 仍負責正式支援路徑、stage 命名及執行契約等剩餘細節。

## 4. 開發階段與驗收

下列為 2026-10-16 確認的 **M0～M7 階段編排**；個別 Schema、版本、方法細節及執行政策仍依 Q-ID 核定。能力是同一產品分批交付，不代表把後面的已確認能力刪除。階段完成需留下可實際執行的成果；本輪只更新規劃，未將任何 Engine／服務階段標示完成。

| 階段 | 範圍／依賴 | 交付 | 驗收 |
|---|---|---|---|
| M0 契約與專案基礎 | 先定 Q-001／Q-002；未決問題可獨立起草 | 版本鎖、程式結構、Pydantic／JSON Schema、完整範例及錯誤例 | 從乾淨環境可安裝；範例通過 Schema，錯誤可定位；無需 Builder |
| M1 最小獨立 Engine | Structured JSON／Recursive／Dense／Local Memory／Query；依賴模型、Token、索引與失敗政策 | 可直接 Python／CLI 操作的 Engine；真實 Adapter＋隔離測試替身 | 手寫 Config ingest→query；檢索真的使用資料；引用可對回；程序重啟後正確不就緒 |
| M2 Engine 方法與能力擴充 | Fixed-size／Header-aware、多欄位、BM25／融合、Rewrite／Multi-query、Rerank、ES／MongoDB；Parser 依 Q-005，Fusion Plan 依 Q-014 分批 | Adapter／Registry、Manifest、方法／合併時點配置、各模式範例與契約測試 | Fixed-size 邊界可重現；ES／Local 契約一致；MongoDB 恢復不重跑 Embedding；Filter／融合可驗算；設定改變真實路徑 |
| M3 Runtime API | 包裝已可用 Engine；定 API／工作／認證／併發 | OpenAPI、Runtime 服務、Job Store 政策、SDK／cURL 範例 | SDK／HTTP 相容；202 可查結果；失敗／重送／重啟行為有證據 |
| M4 獨立 AI 設定助手 | 使用 M0～M2 的 Schema／Registry／Validator，提供不依賴 Builder 的 Python／API 入口；Q-024 | 真實助手核心、需求／樣本輸入、Config 草稿／Diff／缺少設定與可定位驗證結果 | 不開 Builder 可取得支援範圍內的 Config；具備所需設定者由驗收腳本透過 Engine／Runtime 跑通；資訊不足明列缺項，不造方法／憑證或自動 Ingestion |
| M5 Builder 前後端與 AI 助手整合 | 管理儲存、Create／Edit、CSV／Schema、漸進式 UI，串接同一 Runtime 與 M4 助手 | 正式 Frontend／Backend、System／Revision／Binding、UI 草稿與建議 Diff／套用流程 | UI 可建立／匯入／查詢；助手讀取當前草稿及樣本，建議與控制項正確對應；過期建議不覆蓋人工修改，取消不改 Config，變更影響及版本衝突正確 |
| M6 Evaluation | Q-018；Dataset／Runner／指標／報告與版本追蹤 | 可由 SDK／API 及 Builder 使用的評估流程、逐題結果與報告 | 固定測資可重現計算依據；缺標註不造分；報告綁 Config／資料／模型版本，可比較配置差異 |
| M7 獨立部署交付 | Q-021／Q-027；核心 Runtime 已真實可用，完成目標環境交付 | Runtime Image 版本／Digest、FTEST／ENT Bundle、部署／Secret／資料準備與運維說明 | 新環境無 Builder 可用 YAML 啟動；API Ingest→Query；外部依賴故障可定位；不含測試資料與憑證 |

M1 先跑 IngestionDocument.content object → Structured JSON Parser → ParsedDocument → Recursive → Chunk 的最小路徑；Fixed-size 已列入方法需求，於 M2 擴充驗收，不因增加方法而要求 M1 同時完成所有能力。CSV 由映射產生相同輸入。M2 按子任務交付，不必全部方法完成才開始 M3；Runtime 可先包裝已可用 Engine，再逐步增加能力。M4 只能建議當前 Registry 已支援的方法。

Image 建置可在 M3 開始；M7 驗收的是可獨立部署的完整交付，不要求每個 RAG System 各建一個 Image。匯出通常引用支援該 Config 的 Runtime Image 版本／Digest，另外交付 Config 與部署設定。M6 的評估純邏輯可在 M1／M2 先做，但不能把早期模組測試當作 M6 整體評估已完成。

2026-10-28 D-41 補充：M0 規劃兩個 repo 及套件邊界；M1～M3 的 Engine／Components／Runtime API 在 rag_engine 開發，M5 Builder 在 rag_platform 開發。M4 獨立助手核心的目錄建議置於 rag_engine，保留無 Builder 的 Python／API 入口，M5 另做 UI 整合；實際包裝見 07 §2。M7 交付由 rag_engine 建置的完整 Runtime Image，不要求另一個 Components repo 進行 Image 二次組裝。階段順序與已確認功能範圍維持不變。

### 4.1 階段決策 Gate

| 開始的工作 | 必須先明確的問題 | 尚可先做 |
|---|---|---|
| 正式契約／公開 SDK | Q-001／Q-002 | 需求整理、Schema 候選、型別範例 |
| 真實 Token／Embedding／搜尋 | Q-003／Q-004／Q-011；安全最小範圍 Q-006 | Fake Adapter、欄位映射與純函式 |
| 對既存文件更新／partial 寫入 | Q-007／Q-008／Q-009／Q-010 | 純新增、不重複 ID 的受限流程及明確拒絕 |
| MongoDB 恢復 | Q-012／Q-015 | Store 介面與小型 Manifest 草案 |
| HTTP／工作服務 | Q-017／Q-019／Q-020；資料保存 Q-016 | Engine SDK 及 Client／Repository interface |
| M4 獨立助手 | Q-002／Q-003／Q-024；可用 Registry／Validator | 無 Builder 的需求／樣本與結構化建議測試；Mock 明示 |
| M5 Builder 與助手整合 | Q-015／Q-019／Q-020／Q-025；M4 建議契約 | Draft／Diff／過期建議與控制項對應測試，不宣稱真實助手已串接 |
| M6 評估／M7 交付 | 各自 Q-018／Q-021，容量及運維 Q-027 | 獨立 Mock／驗證流程並標記未實接 |

只阻擋受影響功能；不要求所有 Q-ID 全部解決才能開發。未核定正式政策時，受限實驗必須明示範圍，不能成為隱藏產品預設。

### 4.2 M4 與 M5 的助手驗收分界

| 驗收情境 | M4：獨立使用 | M5：Builder 使用 |
|---|---|---|
| 建立設定 | 需求＋明確允許的 CSV／JSON 樣本＋可用服務資訊，回傳 Config 草稿及缺項 | 帶入當前 Workspace／System 草稿、Schema、映射與服務選擇，呈現建議 |
| 修改設定 | 已有 Config＋需求，回傳相對該 Config 的結構化 Diff；非 Builder 呼叫不需 Builder DB／System ID | 以 UI 草稿基準比對、只在使用者套用後改草稿；Create／Save 前不改 active Config |
| 驗證與能力 | 同一 Schema／Registry／Validator；不支援方法明確拒絕，缺連線／服務回可定位問題 | 相同規則顯示到控制項，含收合設定、失效欄位／服務、Fixed-size 相依與重建影響 |
| 狀態與取消 | 不隱含持有 UI 狀態，不自動執行 Ingestion | 建議產生後人工修改、取消、重新產生、過期回應及版本衝突不覆蓋使用者變更 |
| 執行與品質 | 使用者／驗收腳本明確提交合法且完整的 Config，透過 Engine／Runtime 執行；Schema 合法不等於品質達標 | AI 套用與手動設定的有效 Config 語意一致，再用現有 Ingest／Inference／Evaluation 操作驗證 |

實際 UI 樣式、選擇性套用／撤銷及服務契約拼字仍依 Q-024／Q-025 核定。M4 與 M5 各自需要真實整合證據；規則助手或 Mock 可驗證互動，不能完成真實 AI 驗收。

<a id="method-development-plan"></a>
<a id="component-development-plan"></a>

### 4.3 Module Developer 配套的分階段補充（2026-10-28）

沿用 M0～M7 次序與既有方法範圍；下列是對 D-40／D-41 的規劃分工，不表示對應 SDK／服務已交付。Component 擴充不能依賴 Engine 私有實作，故最小公開邊界安排於 M0／M1；SDK／Engine／Components 集中同 repo 不取消套件與契約邊界，正式建置發布細節留相關 Q-ID。

| 階段 | 補充工作 | 驗收重點 |
|---|---|---|
| M0 | Module I/O／Config 與 SDK 邊界、component_id／版本、能力相依；界定首批可擴充 Module | 契約有正反例，Pending Schema 不被當正式 API；Q-001／Q-002／Q-022 依實際工作逐項核定 |
| M1 | 最小 SDK／Registry／受控明確註冊；rag_engine components 中的內建 Recursive 與自訂示範 Chunker 遵循同一契約 | 建置 package 後在乾淨環境安裝並接入最小 Engine 路徑，不依賴原始碼路徑／私有介面；衝突／錯版／非法輸出可定位 |
| M2 | 依 Component 擴充提供其他 Module 介面、能力／artifact 相容檢查、套件測試與受控交付；entry points 為候選 | Parser／Chunker、Indexing／Retrieval 成對方法可整合；未支援組合明確失敗，發布版本可追溯 |
| M3 | Runtime 呈現實際可用方法／版本、Schema、Config 驗證與初始化錯誤；精確 API 留 Q-019 | 目錄／驗證對回相同目標 Runtime；Image 已發布但執行環境未更新時不宣稱新方法可用；無執行期任意下載／安裝 |
| M4 | 獨立助手使用目標 Engine 的可用目錄、Schema 與相依規則 | 不捏造 component_id／版本，不推薦目標環境不支援的方法 |
| M5 | Builder 透過公開 API 使用目標 Runtime 的 Component 目錄／Schema／驗證，呈現版本與不可用原因；UIB-010 | 相容的新方法在更新 Runtime 後可供既有表單選用，Builder 不內嵌全部方法；Edit 不靜默換版，手動／AI／匯出語意一致 |
| M6 | Evaluation 方法沿用公開擴充／測試規則，報告可追溯方法與版本 | 新評估方法不繞過 Dataset／指標語意檢查；不是提早宣稱任意自訂評估已完成 |
| M7 | rag_engine 統一交付 Engine＋核可 Components＋Runtime API Image；rag_platform 的 Builder 分開建置／部署 | 無 Builder 環境可依 YAML＋Image 執行相同方法；契約相容可各自升級，缺失方法／錯版及索引不相容可定位 |

兩個 repo 的分工已依 D-41 確認；精確內部目錄與建置工具仍可逐步核定。正式動工前的優先順序是：共用契約／最小 SDK（Q-002）→ 同 repo 可安裝範本與載入細節（Q-001／Q-022）→ 進共享 DEV 的發布與信任政策（Q-022）→ 既有 System 升級及交付鎖定（Q-015／Q-021）。不要求所有 Q-ID 一次決完。

D-42 補充：M0 以 [12](12_component_schema_ui_contract.md) 核定 Descriptor／Schema 子集、規則語意及 fixtures；M1 做共用 Schema 輸出／Registry／設定驗證，M2 擴充各方法能力；M3 提供目錄、Context／動態候選與驗證 API，M4 助手重用，M5 完成動態表單與 SUI-01～14 互動驗收。可用方法、有效 Config 與服務／資料就緒分開檢查；不依 Schema 文件存在就宣告 API 或 UI 已完成。

## 5. 驗收材料與完成定義

### 5.1 必備材料（在開發階段建立，並非本輪已存在）

| 材料 | 最小內容 |
|---|---|
| examples/configs | 完整 Local Memory、ES、Local MongoDB 配置；必要服務／Secret 設定說明 |
| fixtures | CSV 映射／IngestionDocument、ParsedDocument／Chunk、已知文字與標題、Fixed-size 的零 overlap／短文／整塊／末塊、Unicode／長文字、合法／無效欄位、同 ID 更新與 Filter 測資 |
| retrieval fixtures | 固定小向量／詞項與人工路徑排名，可計算 Top-K／RRF／Sum Score／去重 |
| provider fakes | 合法回應、Timeout、429、缺項、錯誤維度、非法 Rerank index、未知引用 |
| usage examples | 直接 Engine、HTTP、CSV 映射、工作輪詢、部署後首次 Ingestion |
| assistant cases | M4 無 Builder 的新建／修改 Config、缺服務／未知方法；M5 的同一建議與 UI 控制項對照、Diff／取消／過期草稿案例 |
| component package cases | rag_engine components 的 package 在乾淨環境安裝、單一 Component／整合測試、衝突／錯版／能力不足案例、完整 Runtime Image Component 清單與 Builder 契約測試；詳見 11 |
| component schema／UI cases | 12 的 SUI-01～14；Schema／Python 設定一致、動態選項、相依失效與不適用分支、未知必要控制項、多實例定位、版本過期、UI／AI／Python／HTTP 同規則 |
| env／commands | 不含 Secret 的環境範例；安裝、測試、啟動與 integration 指令 |

13～15 與 schemas/ 提供可驗證資料；05 §7 對照設定責任。完整 Engine Config／部署設定及 SDK 仍待 Q-002 核定，不能把參考切分 spec 當成完整可執行 Config。

### 5.2 測試分層

1. 契約：型別、欄位來源／相依、無效引用、維度與未知欄位。
2. 模組：真實切分／位置、Query 保存、Filter 候選、融合、Rerank 對照、模板替換。
3. Adapter：ES／Local 共同能力測試與不支援能力拒絕。
4. 整合：真實模型／搜尋環境的 ingest→query、持久化恢復與錯誤。
5. UI：基本／進階、CSV、AI Diff、取消、Edit 影響與 API 端對端。
6. 部署：無 Builder 的乾淨目標環境啟動、Ingest／Query 與健康檢查。

不要要求 LLM 回答逐字相同。應檢查引用來自實際 Context、未知引用處理、資料不足政策及輸出 Contract。效能、品質／成本門檻由 Q-018／Q-027 決定，不捏造精確 SLA。

每個交付記錄：變更與對應規格、重現指令、實際執行結果、使用 Fake 或真實服務、未完成部分／Q-ID。不能用 Mock 通過宣稱真實模型／DB 已驗證；不能只測試實作自我重複的函式。

## 6. 待討論與決策登錄

以下 Q-ID 均仍有 **OPEN／待決細節**，不代表各項上位需求未被確認。尤其 Q-014 的時點配置、Q-025 的 Parsing 預設收合已有明確方向，只核定餘下細節。負責角色是建議協作對象；每項保留決策欄，確認後填日期、依據與受影響文件，實作驗收完成後才關閉。

<a id="q-001"></a>
### Q-001 技術棧、版本與相容矩陣

- 已有方向：使用部門 LangChain／LangGraph 生態，並以 Python／Typed Contract 進行設計；不重新把 Haystack 當成已選框架。不清楚的是套件版本、Web／前端框架、ES 版本／授權及 BM25／Tokenizer。
- 2026-10-28 已確認 D-41：rag_platform 管理 Builder，rag_engine 集中 SDK／Engine／Components／Runtime API。仍待定的是 repo 內可獨立安裝的套件名稱／精確目錄、Python／SDK／Engine 相容矩陣與建置工具；目錄草案見 07／11，發布政策見 Q-022，不能再將 repo 邊界列為未決。
- 建議：沿用 Python／既有生態；選最小必要套件並鎖定。Web Framework／前端沿用部門標準；具體版本要實測再鎖。
- 替代：以專案獨立技術棧開發，需增加維運／整合評估。
- 負責角色：技術負責人＋Engine／前後端；阻擋 M0 正式依賴及 M2 ES 選型。
- 決策：未定；更新 03／04／07 及 dependency lock。

<a id="q-002"></a>
### Q-002 共用 Schema、Config、SDK 與版本凍結

- 已確認：邏輯 Config 與部署設定分離，正式名稱不使用 Blueprint；Workspace → System；Local Search 持久化模式隨 Config 跨環境固定（D-33）；全部 Chunk.fields／metadata 保存與合法 metadata 全繼承（D-39）。不清楚的是 05 建議拼字／枚舉／Default／nullable、array 型別、錯誤 Envelope、SDK、多 Profile、InferenceState／QueryContext／ResultSet 草案，以及舊保存／繼承投影、原型短名稱／匯出標籤 migration。
- 2026-10-28 補充：Component SDK 的 Module-specific I/O 包裝、run／初始化／釋放簽名、RunContext、Registry／Factory 與 Config Schema 介面待凍結；Registry 草案改稱 component_id，不直接改寫既有 Config。精確方法／版本引用、舊 module_id 別名與遷移須一致驗證；11 的 Python 程式只作介面示意。
- 建議：先核定最小完整 Config＋單一公開 Engine interface；Pydantic 匯出 JSON Schema，UI 使用相同來源。用完整欄位路徑；未知別名拒絕。
- 替代：直接沿用 Prototype 全部短名稱；需補齊其缺少型別與執行語意。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 契約凍結。
- 決策：未定；更新 04／05／07、Schema 及完整範例。

<a id="parsed-document-schema-pending"></a>
#### ParsedDocument 實際 Schema（2026-10-28 加入；2026-10-30 已產出 0.1 草案）

- 狀態：**已有可驗證草案，仍待審閱／凍結**。使用者於 2026-10-30 要求按前述建議產出 Schema 並比對 Docling／MinerU，見 [14](14_parsed_document_contract.md) 與 [JSON Schema](../schemas/parsed_document.schema.json)。五個頂層 key 保留；text-spans／page-blocks、extension、位置與共同語意已具體化供核定，不代表正式 SDK 或所有 Parser／Chunker 已實作。
- 欄位契約：各欄位的精確型別、必填／選填、預設值、空值及未知欄位政策，以及完整 Schema／驗證範例。
- 結構表示：現行草案採無結構 {}、text-spans／page-blocks 及顯式註冊擴充；14 與 Schema 已定義 fields 對應、offset、階層與頁面規則。剩餘取捨為正式版本凍結、表格／圖片標準內容、擴充登錄及遷移，不重新退回無指定結構的 blocks。
- 位置與來源：討論頁面與章節的關係、跨頁區塊／多位置表示、閱讀順序、文字正規化後的位置映射，以及既有 Unicode code point／0-based 半開區間規則如何驗證及由外部 Parser 轉換。保留頁碼不等於已決定新增 Page-aware Chunking。
- 模組相容：定義 Parser 能產出的共用結構、各 Chunking 方法需要的結構、自訂結構的名稱／版本／Schema，以及 Adapter、相容性驗證與缺少結構時的處理；具體方法與首批 Parser 範圍仍連動 Q-004／Q-005。
- 輸入邊界（2026-10-29 更新）：已確認可接受原始與上游已解析資料，Engine 以扁平 JSON 的 content／base64／uri 三選一接收，仍需相容 Parser／Adapter，見 [13](13_ingestion_parser_input_contract.md)。D-45 已確認 API／Parser 共用 IngestionDocument，不另設 ParserInput；已解析內容依相容 Adapter 映射為 14 的結構；其 content schema_id／profile 命名與 Context／SDK 介面仍待定，直接匯入 Chunk／vectors 未核可。
- 後續：定案後同步 05 ParsedDocument 定義與範例、04 模組契約及 07 Ingestion API；必要 UI 變更依既有工作方式登錄 10 backlog，待明確要求修改 UI 再實作。

<a id="chunk-schema-pending"></a>
#### Chunk 實際 Schema（2026-10-30 已產出 0.1 草案）

- 已確認 D-47：六鍵外層、預設 text 免選欄位、進階多任務／copy、2＋3 結果串接、metadata 追溯與向量 Profile／來源資訊；精確資料見 [15](15_chunk_contract.md) 與 [JSON Schema](../schemas/chunk.schema.json)。
- 本輪具體化 source_refs／chunking、DenseVector 物件、有效計畫 fingerprint／全域序號及參考 ID；既有 Inference 改引用同一份 Chunk，不重寫向量定義。
- 正式鍵名／nullable／自訂轉換、異質任務下游欄位適用條件、舊向量陣列遷移、跨語言 canonicalization 與 SDK 仍需審閱。身份 Hash 不解決索引原子提交；Q-007～Q-010／Q-015 保持有待決細節。
- UI 僅記 [UIB-013](10_ui_adjustment_backlog.md#uib-013-chunk-contract)，未實作；來源範例與資料測試不等於 Tokenizer／Chunker／DB 驗收。

- 2026-10-30 後續 D-48：多任務預設輸出 text；必要切分欄位缺失／型別錯誤／全空白、必要任務零產出及明確 copy 欄位缺失報錯。concat／固定文字組裝仍待討論，沒有新增 Module 或修改執行 Schema。

<a id="q-003"></a>
### Q-003 模型服務與 Adapter 契約

- 不清楚：首組模型、Profile／版本辨識、Tokenizer 取得、Chat 角色／輸出格式、多 Query 解析、Rerank 服務限制。
- 本輪待確認提案：Rewrite／Multi-query 採固定 queries 結構及 1／N 數量、Provider Structured Output／Tool／文字解析能力分級、模組 Schema 與共用 LLM Adapter 分工；格式與語意都由後端重驗。細節見 04 §5.1.1，不因寫入提案就凍結 Provider 或重試／fallback 預設。
- 10:22 延續提案：Rewrite／Multi-query 可合併為一種啟用方法，以 count=1／N 區分；count 動態產生 Schema，Prompt 控制內容而不覆寫格式／筆數。Generation 另提預設格式＋收合的自訂 JSON Schema；支援能力、回傳 Schema 子集與拒答／截斷處理仍待核定，見 04 §5.1.2／§5.4.1。
- 既有方向：Embedding API、System 共用 LLM 的 OpenAI-compatible API、平台約定 Rerank API；原型格式基線為 embeddings／Chat Completions／04 的 rerank。原型基線不等於所有 Provider 相容性都已核定。
- 建議：先選一組可實測的 Adapter／服務及 Profile，各有 Fake 與真實契約測試；不同格式顯式 Adapter。
- 替代：第一期支援多 Provider 格式，增加測試矩陣。
- 負責角色：Engine＋模型服務提供方；阻擋 M1 真實服務。
- 決策：未定；更新 04／05／07。

<a id="q-004"></a>
### Q-004 Token 計量、切分邊界與溢位

- 已確認：Fixed-size／Recursive／Header-aware 均用 Token 計量；Fixed-size 固定視窗、不依標題／分隔符切分。待定：Token 計數版本、prefix／特殊 Token、Unicode 安全邊界／原文 offsets、重新編碼計數、單塊超長與複製欄位、overlap／fallback、Tokenizer 離線檔案。
- 建議：固定 Tokenizer／revision，以實際模型輸入檢查；超限回可定位錯誤，截斷需明示。
- 替代：自動切分／截斷，需定義來源與警告語意。
- 負責角色：Engine；阻擋 M1 Token／模型上限驗收。
- 決策：未定；更新 04／05、Unicode／長文字 fixtures。

<a id="q-005"></a>
### Q-005 Parser／OCR 首批格式

- 不清楚：PDF／PPTX／圖片／TXT／MD 哪些第一期支援；套件／外部 OCR、表格／標題 Schema、加密／損壞處理。
- 關聯待決：現行 ParsedDocument 草案的正式版本凍結、擴充登錄及 Parser／Chunking 相容細節見 [Q-002 子項](#parsed-document-schema-pending)；本節不自行凍結 `structure` 形狀或新增切分方法。
- 建議：M1 先 Structured JSON，Native text 及其他格式逐一有測資才開放；OCR 服務另驗證。
- 替代：第一期納入全部格式，需增加品質／成本驗收。
- 負責角色：產品＋Engine；阻擋 M2 格式能力，不卡 M1 Structured JSON。
- 決策：未定；更新 03／04／05／06／07。

<a id="q-006"></a>
### Q-006 metadata 保留區、租戶與授權

- 不清楚：保留欄位名稱、ACL 來源、System／Workspace 權限、tSSO／Gateway 驗證、獨立 Runtime 認證。
- 建議：可信 Context 注入租戶與 ACL，保留 metadata 顯式命名且不可覆寫；初期最小權限模型先核定。
- 替代：只先驗單 System 的封閉環境；不得宣稱多租戶安全已完成。
- 負責角色：平台／身分團隊＋Backend＋Engine；阻擋 M1 保留欄位及 M3／M5 多使用者服務。
- 決策：未定；更新 03～07。

<a id="q-007"></a>
### Q-007 文件／Chunk ID 與 source_revision

- 2026-10-30 D-47：已同意可重現 ID 方向；15 §5～6 提供有效切分計畫 fingerprint＋文件內全域 ordinal 的 Python 參考演算法。仍不清楚：省略 revision 的生成、檔案拆多文件、CSV 無主鍵、同 revision 不同內容的衝突政策、跨語言 canonicalization 與正式遷移；不能再將穩定 ID 方向全部列為未決。
- 建議：跨批更新要求穩定 document_id，內容版本與 Config 分開；採明確可重現的衍生 ID 規則。
- 替代：每批當新文件；需接受無法自然更新與重複資料後果。
- 負責角色：Engine＋資料／產品；阻擋 M1 正式 ID 規範及 M2 更新。
- 決策：未定；更新 04／05／06／07。

<a id="q-008"></a>
### Q-008 重送、更新與刪除

- 不清楚：相同 ID／revision 是否 no-op；較舊版本、同 ID 不同內容、批內重複、刪除 API／保留期限。
- 建議：版本明確檢查、相同重送冪等；更新與刪除分開定義，文件替換需配合 Q-009。
- 替代：第一期純新增且重複拒絕；限制需對外明示。
- 負責角色：產品＋Engine＋Backend；阻擋更新／安全重試，不阻擋受限純新增。
- 決策：未定；更新 04／05／07。

<a id="q-009"></a>
### Q-009 部分失敗與提交原子性

- 不清楚：批次／文件／Chunk 哪一層可 partial；部分 Embedding 成功、舊 Chunk 清除點、partial 終態。
- 建議：文件級成功再發布，失敗文件保留可用舊版；逐文件結果可追蹤。需衡量記憶體／ES／MongoDB 實作成本。
- 替代：全批失敗回滾，或允許明示 partial 文件；要定義資料可見性。
- 負責角色：Engine＋Backend；阻擋 M2 更新與 M3 終態契約。
- 決策：未定；更新 04／05／07。

<a id="q-010"></a>
### Q-010 Ingestion／Query 併發與發布

- 不清楚：重建期間 Query 使用舊版、阻擋或可見半批；同 System 多 Ingestion 的順序。
- 建議：第一期選明確簡化策略，例如重建期間阻擋新版 Query；若要舊版服務需穩定 Binding／切換。
- 替代：原子世代切換以維持舊版服務，增加雙份資源／一致性成本。
- 負責角色：Engine＋Backend；阻擋 M2／M3 併發正式行為。
- 決策：未定；更新 04／05／06／07。

<a id="q-011"></a>
### Q-011 FAISS／BM25 與分數定義

- 不清楚：FAISS index 類型、metric／normalization、距離到 relevance、中文斷詞、BM25 參數／套件。
- 建議：先用可精確驗算的小規模索引作基準，再評估 ANN；全文逐欄位建索引並固定斷詞。
- 替代：直接 ANN，需先定 Recall／容量目標。
- 負責角色：Engine；阻擋 M1 搜尋語意及 M2 效能優化。
- 決策：未定；更新 04／05、測試小向量與詞項資料。

<a id="q-012"></a>
### Q-012 MongoDB Manifest 與恢復

- 不清楚：Collection／Manifest 形狀、索引版本、完整性／Profile 驗證、DB 中斷、恢復期間讀寫。
- 建議：保存完整 Chunk／vectors 及可驗證的設定／資料版本；重建完成才發布 Local Index。
- 替代：另保存 FAISS 檔案與快照，增加檔案版本及同步機制。
- 負責角色：Engine＋Backend／DB；阻擋 M2 持久化恢復。
- 決策：未定；更新 04／05／07。

<a id="q-013"></a>
### Q-013 精確 Filter 的候選與缺值語意

- 不清楚：缺欄位／null／多值如何匹配；FAISS 合法候選搜尋策略、ES Mapping 相容矩陣。
- 建議：固定字串 eq／in、各路取 Top-K 前限制；用有／無命中與 ACL 測資驗證。
- 替代：未具備可靠 pre-filter 的組合先停用，不能偷偷 post-filter。
- 負責角色：Engine＋授權設計；阻擋 M2 過濾與多租戶驗收。
- 決策：未定；更新 04／05／07。

<a id="q-014"></a>
### Q-014 融合計畫、合併時點與分組細節

- 已有需求：使用者要求可配置融合策略及「在哪一步合併」，並提出逐 Query Score Sum→跨 Query RRF 情境；D-23 已記錄，不能只當可做可不做的助理建議。2026-10-15 再次明確可自行決定融合位置，且應先釐清 Inference 物件如何記錄多 Query／多 Index／多階段分數。
- 已補確認：後處理三類（D-34）與共同排序（D-35）；不再把是否需要這些語意列為未決。餘下不清楚的是支援的合法路徑、scope／stage 精確 Schema、預設、每階段 K／N、Rerank Query、同分、文件代表、分數語意與 UI 整合。
- 情境例：同 Query 融合→跨 Query 融合→Rerank、同 Query 融合→逐 Query Rerank→跨 Query 融合、ES 已內部融合。Config 需能選擇合法融合位置，不能只接受固定 Plan A／B；正式 Config 拼字及 Adapter 能力仍待核定；兩層預設勾選且在 Retrieval 後已確認，不再列為未定。
- 最新草案：05 §4.6 的 inference-0.2-draft 與五份例子同步三類操作、有效整數 rank、多欄位來源及 ES 已融合情境；具體欄位仍未凍結。[09](09_inference_contract_ui_plan.md) 提供順序卡片、來源選取及 UI-01～03 討論選項，尚未取得使用者對版面／預設的核定。
- 建議：先定可驗證的有限計畫及共同 route 型別，保留 query／route identity；Rerank=None 及非法組合須顯式驗證。文件分組另定，不與 chunk_id 去重混同。
- 負責角色：產品＋Engine＋Frontend；阻擋目標時點配置的契約／驗收，可先維持舊基線做迭代但不宣稱需求完成。
- 決策：配置能力的需求已確認；具體計畫／預設／Schema 未定。同步更新 03～07 與範例。

<a id="q-015"></a>
### Q-015 Revision、有效 Config Hash 與 Index 版本

- 已確認：同一 System 的同版邏輯 Config 跨環境相同，部署設定分開；文件 source_revision 與 index_generation 概念分開。不清楚的是保存／生效時點、Hash、草稿衝突、CSV mapping 歸屬、環境部署識別／資料版本及快照切換。
- 2026-10-28 補充：需定 Component／package／Engine 解析版本保存位置、如何納入可重現執行與相容判定、更新 Component 後的重測／重建與回復政策；新版發布不自動升級既有 System，僅看版本號不能判定索引相容。
- 建議：分開保存版本與執行綁定；Hash 只納有效配置並保留有語意順序，使用樂觀版本檢查。
- 替代：單一 active revision，改配置後阻擋到準備完成；仍須避免 lost update。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 Hash 凍結及 M5 版本操作。
- 決策：未定；更新 05／06／07。

<a id="q-016"></a>
### Q-016 平台儲存、原始資料與保留

- 不清楚：Config／Run／Dataset／Report DB、原始檔／ParsedDocument 是否保存、Trace 原文、期限／刪除、獨立 Runtime 儲存。
- 建議：管理資料與搜尋 Chunk Store 分離；可用 Store interface 分環境替換；只保存明確必要資料。
- 替代：統一平台 DB／Object Store；獨立 Runtime 的外部依賴與成本需交代。
- 負責角色：Backend＋平台／資料負責人；阻擋 M3／M5 正式持久化與資料政策。
- 決策：未定；更新 03／05／06／07。

<a id="q-017"></a>
### Q-017 Timeout、重試、取消與工作恢復

- 不清楚：總 Deadline、模組 Timeout、重試上限／可重試錯誤、Client 中斷、取消與崩潰後 Run 處理。
- 建議：Engine 統一執行預算，副作用需冪等；初期可先不自動重試，明示失敗及未知結果。
- 替代：從一開始提供持久 Queue／Worker／恢復，需同時解決 Local Memory 程序綁定。
- 負責角色：Engine＋Runtime；阻擋 M1 錯誤政策及 M3 工作語意。
- 決策：未定；更新 04／05／07。

<a id="q-018"></a>
### Q-018 Evaluation 範圍與 Gate

- 不清楚：首批指標、Dataset／Ground Truth 格式、Judge／Rubric、Chunk／Document 層級、Rerank 前後、公開檢索 Target、Gate 門檻。
- Generation 自訂 JSON 若採用，還需核定主要回答文字欄位映射、無文字 payload 時哪些指標不適用，以及 UI／Dataset 相容性；不得把未定的整個 JSON 序列化成答案後宣稱完成既有評估。
- 建議：先有可驗算的 Retrieval 指標與操作指標，再加明示 Judge；缺資料拒絕或 skipped。
- 替代：先 End-to-end Judge；不得冒充有可靠 Retrieval Ground Truth。
- 負責角色：產品／資料＋Engine＋Backend；阻擋 M6 正式評估／Gate，不卡 Query 主線。
- 決策：未定；更新 03／04／06／07。

<a id="q-019"></a>
### Q-019 API／HTTP Envelope 與呼叫認證

- 不清楚：完整 CRUD／助手／管理 API、OpenAPI、錯誤碼／狀態、上傳限制、manifest、冪等鍵、DEV 路由、認證及暴露 Trace。
- D-41 補充：Builder 與 Runtime 透過 API／Component 目錄合作；需核定目標 Runtime 版本識別、Config Schema／能力目錄、完整 Config 驗證、快取失效與接口相容政策。能力範圍見 07 §5.8，精確端點與 Envelope 仍 OPEN。
- D-42 已按建議規劃描述／Context／選項及驗證關聯值，候選格式見 12；精確路徑、認證、版本識別與公開 Meta-schema 仍 OPEN，不影響既有 Ingest／Query 範例。
- 10:22 的 Generation 自訂 JSON 提案只針對業務內容；HTTP envelope 的平台欄位、payload 容器、answer 字串相容性、SDK 型別、錯誤／Streaming 需另核定。當前 07 範例不因提案而變動。
- 建議：沿用 07 的 Endpoint 草案，先凍結 Ingestion／Status／Query，補齊 Backend API；HTTP 與領域錯誤分層。
- 替代：沿用既有企業 API 規範並明確映射。
- 負責角色：Backend＋Runtime＋Frontend／身分團隊；阻擋 M3 Runtime／M4 助手 API／M5 Builder 真實串接。
- 決策：未定；更新 05／06／07、OpenAPI／cURL 範例。

<a id="q-020"></a>
### Q-020 DEV 共享 Runtime 與資源隔離

- 不清楚：每 System 實例快取、Tenant／System 路由、同時工作、記憶體配額、回收、是否獨立程序。
- 建議：先有受限共享 Runtime 與明確隔離 Binding；Local Search 每 System 的 Ingest／Query 必須同程序。
- 替代：每 System 獨立 Runtime，增加部署／資源管理成本。
- 負責角色：平台＋Backend／Runtime；阻擋 M5 多 System 服務。
- 決策：未定；更新 03／07。

<a id="q-021"></a>
### Q-021 Export、FTEST／ENT 與 Secret Vault

- 2026-10-28 D-41 確認：rag_engine 統一建置含 Engine／核可 Components／Runtime API 的完整 Image，rag_platform 建置 Builder Image；採用新版 Engine／Component 時仍需更新 Runtime，接口相容的 Builder 可維持原版。目標 Image 須包含 Config 所需 Component packages 並保存版本；Component 清單／鎖定格式與缺失錯誤仍待決，YAML 不會自動提供 Python 方法程式。建置／發布／部署範圍見 07 §9.4。

- 已確認：同版邏輯 Config 不隨環境改變，環境連線／Secret／資源為部署設定；Memory／MongoDB 模式也跨環境保持一致（D-33），不能只換部署設定切換。不清楚的是 Image／Bundle 包裝、Vault／注入、Secret 型別、K8s 資源／Ingress／Probe 及 CD 流程。
- 建議：版本鎖定 Runtime Image＋有效 Config＋環境覆寫；Local 單副本；明示未帶資料且無 Builder 依賴。
- 替代：使用單位既有 Helm／GitOps 形式；仍需相同可驗證交付內容。
- 負責角色：平台／DevOps＋Backend；阻擋 M7 正式部署交付。
- 決策：未定；更新 03／05／06／07。

<a id="q-022"></a>
### Q-022 自訂程式的交付與隔離

- 已確認方向：D-40 加入 Module Developer，由公開契約下的 Component 擴充能力供 Builder 使用；不是所有特殊策略都由平台核心開發者實作。2026-10-28 補齊 04 與 11 的規劃，未凍結套件／隔離細節。
- 已確認開發位置（D-41）：使用本機 IDE／SDK，在 rag_engine components 目錄開發並提交 PR；與同 repo 的 Engine／Runtime API 整合測試後交付完整 Runtime Image。公開套件／契約邊界保留，以乾淨環境安裝驗證替代「必須另建 Component repo」的驗收要求。
- D-42 補充：Component 的設定描述與規則是受限 JSON 資料；共用 Schema 輸出與 Registry 驗證，不以瀏覽器腳本或任意 import 擴充 UI。具體能力／控制項名稱登錄、支援子集與契約測試待核定，見 12。
- 建議起步：受控 Registry、核可 Component packages，先明確註冊再評估 entry points；不先建 Web IDE／任意程式上傳，也不要求以跨 repo Image 相依交付每次方法更新。
- 尚待決：核可／發布角色與可信程式範圍、依賴建置／選配套件倉庫、Factory／entry point 解析、SDK 相容矩陣、package／Component 版本對照與撤回／升級。跨 System 多版本／依賴衝突、目標 Runtime 方法可用性與索引相容另連動 Q-015／Q-020／Q-021。
- 若擴大為不受信任開發者或 UI 上傳：需另核定執行隔離、Secret／網路／資源限制與管理權限；Schema／RunContext 不能代替 Sandbox。未完成該方案前保留共享 Runtime 不任意執行使用者 Python 的限制。
- 負責角色：產品＋Platform／Engine Developer＋Module Developer；M0／M1 核定最小公開介面與載入，進共享 DEV 前核定發布／信任政策；不阻擋本文整理及既定內建路徑的受限開發。
- 決策狀態：角色／擴充需求與兩個 repo 分工已確認，具體技術與發布政策 **OPEN**；更新 03／04／06／07／11，UI 先記 10 UIB-010。本輪不以 repo 決策代替其餘細節核定。

<a id="q-023"></a>
### Q-023 Fallback、無資料、Budget 與引用

- 不清楚：無 Context 是否一律 abstain、Context 截斷順序、未知引用、多 Query／Rerank 失敗降級、生成回應格式。
- 建議：錯誤與無命中分開；預設不靜默降級；明確定義無資料與超限回應，保留實際 Context。
- 替代：可設定 fallback，但需 Trace／warnings 與測試。
- 負責角色：產品＋Engine；阻擋 M1 正式回答邊界及 M2 降級。
- 決策：未定；更新 04／05／06／07。

<a id="q-024"></a>
### Q-024 真實 AI 設定助手

- 已確認：可不開 Builder 由 Python／API 產生或修改 Config，且必須於 Builder 中使用相同助手核心並驗收 UI 草稿操作；正式服務及 Schema 不反向依賴 Builder DB。不清楚：模型／Prompt／成本、樣本抽取與保存、結構化輸出、Diff／Patch、過期建議、選擇性套用與撤銷。
- D-41 下的目錄建議：獨立助手核心放 rag_engine，使用同一 Registry／Validator；rag_platform 負責 Builder UI／Backend 整合。此為套件配置建議，HTTP 宿主、可選依賴與 Image 包裝仍待核定，不使 FTEST／ENT Runtime 必須啟用助手。
- 建議：限制 Schema／Registry、只用明確樣本、先顯示差異並驗證；以 Draft 基準防止覆蓋人工改動。
- 替代：先保留規則助手，清楚標示 Mock；不得聲稱已由 LLM 理解資料。
- 負責角色：產品＋Engine／Contracts＋Backend／AI；M5 另含 Frontend。阻擋 M4 真實獨立助手及 M5 的助手 UI 整合，不卡手動配置。
- 決策：M4 獨立核心、M5 Builder 整合與兩階段分開驗收已於 2026-10-16 確認；模型、結構化建議／Diff、過期建議及其餘具體政策仍未定。更新 03／05／06／07／08。

<a id="q-025"></a>
### Q-025 漸進式 UI、範本與小量試跑

- 已確認：Parsing 初始只顯示結構化 JSON，其他格式／設定全在預設關閉進階區；LLM／Prompt／範例及 API 說明要求見 06 §3.2。待定的是其餘基本／進階分組、展開記憶、改動摘要、範本、真實試跑與診斷範圍。
- 2026-10-16 討論提案：在 Rewrite／Multi-query 旁提供不需 Ingestion 的單模組測試，使用當前草稿與相同 Engine／Adapter，顯示實際 Query 與格式驗證；是否採用及展示細節待確認，UIB-007 保持提案狀態，不擴張成所有模組都要試跑。
- 後續提案 UIB-008／009：Rewrite 兩方法合併為 1／N 同一組設定，Generation 預設格式與預設收合的進階 JSON 輸出設定。均為待確認提案，不能覆蓋原型／既有 Config 或自動勾選為已實作。
- D-41／UIB-010 補充：方法選單／設定依目標 Runtime 的目錄與 Schema，需定動態表單支援範圍、目錄更新／過期狀態及不相容 UI 提示；相容新增 Component 不要求每次重建 Builder。特殊控制項仍需前端配合，不承諾任意 Schema 均可自動呈現。
- D-42 已確認固定 Builder 流程搭配動態 Component 參數表單，以及 12 §1 的五項操作行為；不再把這些方向列為未決。12 提供欄位／服務選擇器、相依狀態與 SUI-01～14 草案；具體控制項樣式、支援版本與其餘範本／試跑範圍仍待核定。
- 建議：保留已確認互動，再核定其餘分組；必填錯誤可定位，保持同一 Config。試跑與範本逐項啟用。
- 替代：單獨新手／專家入口，但兩者仍需共享 Config／驗證。
- 負責角色：產品＋Frontend；阻擋 M5 正式 UX 凍結，不卡 Schema／Engine。
- 決策：既有明確互動照定案保留；其餘分組／試跑／範本未定。更新 03／06。

<a id="q-026"></a>
### Q-026 測資、環境與測試工具

- 不清楚：可使用的真實模型／ES／MongoDB、測試 Secret 供應、固定語料、CI／integration 執行條件、允許外連。
- 建議：Fake／Contract 與真實 integration 分開；測資可重現且不含敏感資訊，工具／指令正式鎖定。
- 替代：開發機手動驗證，仍需留下可重現紀錄，不能以未執行當通過。
- 負責角色：技術負責人＋開發／QA；阻擋各階段真實整合驗收。
- 決策：未定；更新 08、環境／測試說明。

<a id="q-027"></a>
### Q-027 效能、容量、成本與觀測目標

- 不清楚：資料量、平均長度、並發、回應時間、重建啟動時間、模型成本、Trace 內容與監控工具。
- 建議：先建立可重現基準再定門檻；保留 request／run／module Trace，避免過早加入 HPA／Queue。
- 替代：先採既有企業 SLA，需驗證 Local Memory／模型資源是否能滿足。
- 負責角色：產品＋平台／Engine／QA；阻擋生產容量承諾與 M7 運維驗收。
- 決策：未定；更新 03／04／07／08。

## 7. 優先討論順序

第一輪先討論 Q-001／Q-002（技術與契約）、Q-003／Q-004／Q-011（可跑的模型／搜尋基線）、Q-007～Q-010（資料更新及可見性）。第二輪處理 API／儲存／Runtime，再依 M4 獨立 AI 助手、M5 Builder 與助手 UI、M6 評估、M7 交付的順序決策。

不需要一次解完所有問題。每次討論完成，更新相應 Q-ID、權威規格、範例與驗收。暫不做的選項標為後續，不能讓同一問題長期以多種互斥建議存在。

## 8. Coding agent 任務模板與紀錄

建議每個任務包含：

```text
目標／階段：
讀取文件與章節：
已確認決策／相關 Q-ID：
本次範圍與不做項目：
輸入／輸出及完整範例：
預期檔案／模組邊界：
驗收與實際執行指令：
允許的測試替身／需要真實服務：
未決問題對本任務的限制：
完成證據與尚未驗證部分：
```

當前使用者要求以文件規劃為主：任務若只是討論／調整規格，先更新主責文件，所有所需 UI 變更登錄 10 的未完成項目；收到明確修改 UI 的指示才開始原型實作。這不阻止已授權的文件驗證、提交及推送。

Agent 可自行選局部 helper／內部名稱等可逆細節；公共 Contract、資料遺失／安全語意、外部依賴與範圍變動需回報或記成 Q-ID，不能偷偷做成產品決策。遇一項阻擋時先完成可獨立驗收的部分，再提出具體選項。

後續開始程式開發時建議加入根目錄 AGENTS.md，引用本文與 03～07，記錄建置／驗證指令；本輪只交付規格，不新增未經確認的開發自動化規則。

## 9. 目前交付狀態與下一步

目前可審閱的交付為 03～15 規格、共用 JSON Schema、契約資料／參考驗證器、模擬 Prototype 及架構圖。三份 Ingestion 資料以 13～15 為準；Inference 的 ResultItem 引用共用 Chunk。

- 資料驗證：examples/parsed_document、examples/chunk 與 examples/inference；完整限制與執行方式見 14／15。
- Parser 對照：Docling／MinerU 固定官方輸出映射，以及 MarkItDown／PyMuPDF4LLM 的已記錄本地解析證據，見 14 §5／§5.1。範例通過不表示已交付 Engine Component。
- Prototype：結果處理既有能力見 10 §1～6；後續 UIB-001～013 尚未實作，三份新 Schema 的 UI 遷移集中於 UIB-011～013。
- 優先決策：正式共用契約／SDK、模型與 Tokenizer、ID／更新／發布政策，再按 M0～M7 推進。Chunk 後 concat／固定文字組裝保持待討論，見 15 §9。

已被取代的格式、臨時交接核對及逐輪交付流水帳不再佔用現行規格；歷史可由 Git 查閱。D-01～D-48 保留決策依據，Q-001～Q-027 保留剩餘取捨與階段 Gate，不能把文件整理視為功能驗收完成。
