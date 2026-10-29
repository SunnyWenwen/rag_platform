# RAG Builder — 開發計畫、驗收與決策追蹤

> 文件集 v0.19 · 2026-10-16 · 開發規格草案
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

本輪基準為 `cf4dfdc0e29acc91a2fe63b1993f867c8facaf6d`。新架構／介面提案與該版本 Prototype 的差異，要以 migration 明確處理。03～08 是開發規格草案；原型測試通過不代表 Engine／API 已完成。v0.11 已追加名詞決策；v0.12 將正式定義集中到 03 §3。v0.9 的初始基準仍保留以追蹤來源。

v0.13 從 `e52c4d74a469522155d814f0ff51fddf8946f957` 核對交接文件、本串可見決策、已提交原型與圖面；補齊傳遞／互動規則並記錄仍需討論的邊界，見 §12。

**2026-10-16 起的工作方式**：使用者要求後續調整先更新文件；Prototype 所需變更統一記於 [10 UI Backlog](10_ui_adjustment_backlog.md#ui-backlog-pending)，待使用者明確要求修改 UI 再實作。文件提交不代表同步開發原型、Engine 或服務。規劃文件仍依既有要求提交目前分支。

## 2. 文件責任與建議閱讀順序

先讀 [03](../03_architecture_proposal.md)，以 [§3 名詞定義](../03_architecture_proposal.md#terminology) 統一概念與責任邊界，再讀本計畫；實作依序讀 [05 契約](05_data_contracts_search_design.md)、[04 Engine](04_module_components_io_contracts.md)、[07 整合](07_backend_runtime_integration.md)、[06 UI](06_ui_development_spec.md)。

| 權威範圍 | 文件 |
|---|---|
| 正式名詞定義、產品／架構與非目標 | 03 |
| 獨立 Engine、模組組裝／演算法／語意驗證 | 04 |
| 共用資料、Config 及欄位型別 | 05 |
| 互動與基本／進階呈現 | 06 |
| HTTP、平台儲存、工作與部署整合 | 07 |
| 決策狀態、階段、驗收／阻擋 | 08 |
| Inference Contract 討論摘要與 UI 整合提案 | 09；欄位以 05、決策以 08 為準 |
| Prototype 待辦與歷史完成證據 | 10；使用者要求改 UI 時才實作 |
| Component 開發、測試及套件交付流程 | 11；Engine 機制以 04、資料契約以 05 為準 |
| Component 設定描述、UI hints、動態選項與相依規則 | 12；設定介面草案，I/O 仍以 05 為準，互動待辦記於 10 |

同一型別／規則不在多份文件各寫一套。03 定義名詞，05 規範對應的資料結構／版本規則，本文保存決策來源及狀態；決策摘要不取代 03 的現行定義。程式 Schema 與文件同步；不能只更新 UI、測試或其中一份規格。

## 3. 已確認方向與保留基線

| ID | 方向 | 依據／狀態 | 主責文件 |
|---|---|---|---|
| D-01 | 03 概覽；04 獨立 Engine；05 資料／Config；06 UI；07 Backend；08 開發與決策 | 2026-10-15 對話／已確認 | 03～08 |
| D-02 | 同一系統支援新手與熟悉 RAG 者；AI 設定、CSV 起始、進階收合 | 2026-10-15 使用者提出／已確認 | 03／06 |
| D-03 | 手寫 Config 可直接執行 Engine；UI 產生 Config，不另生成一套 Engine 程式 | 2026-10-15 對話／已確認 | 04／05 |
| D-04 | 固定 Ingestion／Inference；Builder 與獨立 API Runtime 使用同一 Engine | 舊 03 v0.8／既有基線 | 03／04／07 |
| D-05 | ParsedDocument 五個、Chunk 六個頂層 key；vectors 位於 Chunk | 舊 05 §3～4／既有基線 | 05 |
| D-06 | fields／metadata 宣告 Schema；CSV 每列映射一次為標準 records | 舊 05 §15～16／既有基線 | 05／06 |
| D-07 | 原有 Recursive／Header-aware、一個主要切分欄位、Token 計量；Fixed-size 擴充見 D-36 | 舊 05 §13.1／既有基線，新增 Component 不取消原方法 | 04 |
| D-08 | Embedding fields→vectors；摘要先由輸入提供；文字 Dense 優先 | 舊 05 §6／既有基線 | 04／05 |
| D-09 | ES／Local Search（FAISS＋BM25）；Local Memory／MongoDB | 舊 05 §8／既有基線 | 03／04 |
| D-10 | Local Search 同程序／單副本；MongoDB 只持久化並支援重建 | 舊 03 §5.3／既有基線 | 04／07 |
| D-11 | v0.8 Prototype 的單層、Rerank 前 Sum Score／RRF 為歷史基線；v0.9 已有兩層時點設定／預覽，Engine 未實作 | 舊 05 §17＋2026-10-15 原型更新，見 §17 | 04／05／10 |
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
| D-32 | 名詞定義集中在 03 §3，05 保留資料／版本規則，08 保留決策紀錄；其他規格引用 03 | 2026-10-15 10:22～10:24 建議後由使用者確認撰寫／已確認 | 03 §3、04～08／README |
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

「既有基線」不代表已涵蓋後續需求。D-23 的合併時點配置是使用者已提出的目標，不能以 D-11 的舊 Prototype 限制否決；兩層合併預設勾選並在 Retrieval 後的 UI 已於 2026-10-15 確認／實作，見 10 的歷史完成紀錄。Q-014 仍負責正式支援路徑、stage 命名及執行契約等剩餘細節。

## 4. 開發階段與驗收

下列為 2026-10-16 確認的 **M0～M7 階段編排**；個別 Schema、版本、方法細節及執行政策仍依 Q-ID 核定。能力是同一產品分批交付，不代表把後面的已確認能力刪除。階段完成需留下可實際執行的成果；本輪只更新規劃，未將任何 Engine／服務階段標示完成。

| 階段 | 範圍／依賴 | 交付 | 驗收 |
|---|---|---|---|
| M0 契約與專案基礎 | 先定 Q-001／Q-002；未決問題可獨立起草 | 版本鎖、程式結構、Pydantic／JSON Schema、完整範例及錯誤例 | 從乾淨環境可安裝；範例通過 Schema，錯誤可定位；無需 Builder |
| M1 最小獨立 Engine | Structured records／Recursive／Dense／Local Memory／Query；依賴模型、Token、索引與失敗政策 | 可直接 Python／CLI 操作的 Engine；真實 Adapter＋隔離測試替身 | 手寫 Config ingest→query；檢索真的使用資料；引用可對回；程序重啟後正確不就緒 |
| M2 Engine 方法與能力擴充 | Fixed-size／Header-aware、多欄位、BM25／融合、Rewrite／Multi-query、Rerank、ES／MongoDB；Parser 依 Q-005，Fusion Plan 依 Q-014 分批 | Adapter／Registry、Manifest、方法／合併時點配置、各模式範例與契約測試 | Fixed-size 邊界可重現；ES／Local 契約一致；MongoDB 恢復不重跑 Embedding；Filter／融合可驗算；設定改變真實路徑 |
| M3 Runtime API | 包裝已可用 Engine；定 API／工作／認證／併發 | OpenAPI、Runtime 服務、Job Store 政策、SDK／cURL 範例 | SDK／HTTP 相容；202 可查結果；失敗／重送／重啟行為有證據 |
| M4 獨立 AI 設定助手 | 使用 M0～M2 的 Schema／Registry／Validator，提供不依賴 Builder 的 Python／API 入口；Q-024 | 真實助手核心、需求／樣本輸入、Config 草稿／Diff／缺少設定與可定位驗證結果 | 不開 Builder 可取得支援範圍內的 Config；具備所需設定者由驗收腳本透過 Engine／Runtime 跑通；資訊不足明列缺項，不造方法／憑證或自動 Ingestion |
| M5 Builder 前後端與 AI 助手整合 | 管理儲存、Create／Edit、CSV／Schema、漸進式 UI，串接同一 Runtime 與 M4 助手 | 正式 Frontend／Backend、System／Revision／Binding、UI 草稿與建議 Diff／套用流程 | UI 可建立／匯入／查詢；助手讀取當前草稿及樣本，建議與控制項正確對應；過期建議不覆蓋人工修改，取消不改 Config，變更影響及版本衝突正確 |
| M6 Evaluation | Q-018；Dataset／Runner／指標／報告與版本追蹤 | 可由 SDK／API 及 Builder 使用的評估流程、逐題結果與報告 | 固定測資可重現計算依據；缺標註不造分；報告綁 Config／資料／模型版本，可比較配置差異 |
| M7 獨立部署交付 | Q-021／Q-027；核心 Runtime 已真實可用，完成目標環境交付 | Runtime Image 版本／Digest、FTEST／ENT Bundle、部署／Secret／資料準備與運維說明 | 新環境無 Builder 可用 YAML 啟動；API Ingest→Query；外部依賴故障可定位；不含測試資料與憑證 |

M1 先跑標準 records 與既定的 Recursive 最小路徑；Fixed-size 已列入方法需求，於 M2 擴充驗收，不因增加方法而要求 M1 同時完成所有能力。CSV 由映射產生相同輸入。M2 按子任務交付，不必全部方法完成才開始 M3；Runtime 可先包裝已可用 Engine，再逐步增加能力。M4 只能建議當前 Registry 已支援的方法。

Image 建置可在 M3 開始；M7 驗收的是可獨立部署的完整交付，不要求每個 RAG System 各建一個 Image。匯出通常引用支援該 Config 的 Runtime Image 版本／Digest，另外交付 Config 與部署設定。M6 的評估純邏輯可在 M1／M2 先做，但不能把早期模組測試當作 M6 整體評估已完成。

2026-10-28 D-41 補充：M0 規劃兩個 repo 及套件邊界；M1～M3 的 Engine／Components／Runtime API 在 rag_engine 開發，M5 Builder 在 rag_platform 開發。M4 獨立助手核心的目錄建議置於 rag_engine，保留無 Builder 的 Python／API 入口，M5 另做 UI 整合；實際包裝見 07 §2。M7 交付由 rag_engine 建置的完整 Runtime Image，不要求另一個 Components repo 進行 Image 二次組裝。階段順序與已確認功能範圍維持不變。

### 新舊階段對照

| 舊編號（歷史） | 本版對應 |
|---|---|
| M0～M3 | 沿用原編號與核心責任 |
| 舊 M5 的 AI 助手核心／先前討論的 M3.5 | M4：獨立 AI 設定助手 |
| 舊 M4 的 Builder ＋舊 M5 的助手畫面 | M5：Builder 前後端與 AI 助手整合 |
| 舊 M5 的 Evaluation | M6：Evaluation |
| 舊 M6 的獨立交付 | M7：獨立部署交付 |

§10 以後的歷史記錄保留當時用語；當前開發與 Q-ID 的階段依賴以本節及 §6 為準。

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
| fixtures | CSV／records、已知文字與標題、Fixed-size 的零 overlap／短文／整塊／末塊、Unicode／長文字、合法／無效欄位、同 ID 更新與 Filter 測資 |
| retrieval fixtures | 固定小向量／詞項與人工路徑排名，可計算 Top-K／RRF／Sum Score／去重 |
| provider fakes | 合法回應、Timeout、429、缺項、錯誤維度、非法 Rerank index、未知引用 |
| usage examples | 直接 Engine、HTTP、CSV 映射、工作輪詢、部署後首次 Ingestion |
| assistant cases | M4 無 Builder 的新建／修改 Config、缺服務／未知方法；M5 的同一建議與 UI 控制項對照、Diff／取消／過期草稿案例 |
| component package cases | rag_engine components 的 package 在乾淨環境安裝、單一 Component／整合測試、衝突／錯版／能力不足案例、完整 Runtime Image Component 清單與 Builder 契約測試；詳見 11 |
| component schema／UI cases | 12 的 SUI-01～14；Schema／Python 設定一致、動態選項、相依失效與不適用分支、未知必要控制項、多實例定位、版本過期、UI／AI／Python／HTTP 同規則 |
| env／commands | 不含 Secret 的環境範例；安裝、測試、啟動與 integration 指令 |

05 有可解析的完整 YAML 草案，但正式 Schema／Engine 尚未實作，不能宣稱它現在已能運行。

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
#### ParsedDocument 實際 Schema（2026-10-28 加入待討論）

- 狀態：**待討論／延後定案**。使用者要求 ParsedDocument 的實際 Schema 之後再決定；本次只登錄待決事項。既有五個頂層 key 方向保留，不把討論中的細部結構或例子視為已核可的正式契約。
- 欄位契約：各欄位的精確型別、必填／選填、預設值、空值及未知欄位政策，以及完整 Schema／驗證範例。
- 結構表示：評估「完整文字＋位置標註」與 Element／樹狀模型等表示方式；`structure.<field_name>.blocks` 是目前草案，不是業界通用格式，也尚未定案。需釐清它與 `fields` 的對應方式，以及標題層級、段落、page／slide／表格等結構的必要範圍。
- 位置與來源：討論頁面與章節的關係、跨頁區塊／多位置表示、閱讀順序、文字正規化後的位置映射，以及既有 Unicode code point／0-based 半開區間規則如何驗證及由外部 Parser 轉換。保留頁碼不等於已決定新增 Page-aware Chunking。
- 模組相容：定義 Parser 能產出的共用結構、各 Chunking 方法需要的結構、自訂結構的名稱／版本／Schema，以及 Adapter、相容性驗證與缺少結構時的處理；具體方法與首批 Parser 範圍仍連動 Q-004／Q-005。
- 輸入邊界：是否及如何接受上游已解析資料（含頁碼／結構），與原始資料由平台解析的輸入契約一起討論。目前 JSON records 不接受 `structure`；新增輸入模式、直接匯入 Chunk／vectors 均未因此核可。
- 後續：定案後同步 05 ParsedDocument 定義與範例、04 模組契約及 07 Ingestion API；必要 UI 變更依既有工作方式登錄 10 backlog，待明確要求修改 UI 再實作。

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
- 關聯待決：ParsedDocument 實際 Schema、共用／自訂結構及 Parser／Chunking 相容契約見 [Q-002 子項](#parsed-document-schema-pending)；本節不自行凍結 `structure` 形狀或新增切分方法。
- 建議：M1 先 structured records，Native text 及其他格式逐一有測資才開放；OCR 服務另驗證。
- 替代：第一期納入全部格式，需增加品質／成本驗收。
- 負責角色：產品＋Engine；阻擋 M2 格式能力，不卡 M1 records。
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

- 不清楚：省略 revision 的生成、檔案拆多文件、CSV 無主鍵、內容 Hash、切分 signature 的穩定算法。
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
- 情境例：同 Query 融合→跨 Query 融合→Rerank、同 Query 融合→逐 Query Rerank→跨 Query 融合、舊單層基線。Config 需能選擇合法融合位置，不能只接受固定 Plan A／B；具體步驟配置及 `fusion.stages[]` 仍待核定，不自動選助理推薦當預設。
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

## 9. 本輪交付與尚未完成

初版交付（文件集 v0.9）：重整 03～05、新增 06～08、更新 README，登錄 27 項未決問題。歷史核對版（v0.10）補正需求／基線／建議的界線，見 §10；名詞釐清版（v0.11）統一 Config／部署設定、Workspace → System 及版本概念；名詞集中版（v0.12）整理 03 §3 並補齊其他文件引用，見 §11。Q-ID 維持 27 項，不以重新編號掩蓋修正。上述歷史輪次只交付文件；後來的 Prototype v0.9 完成紀錄見 §17／10，最新文件規劃見 §18，Engine／API 仍未實作。

2026-10-15 曾新增跨對話交接摘要；使用者已回到本串接續規劃。v0.13 讀取後將必要資訊併入既有主責文件及 §12，依指示刪除臨時 handoff；原交接內容保留於上述核對起點的 Git 歷史。

## 10. 2026-10-15 歷史對話與決策核對

### 10.1 範圍與證據分級

本次以 2026-10-12～15 的專案對話、目前對話、核對前遠端 `5c49dde0d30e6eade24de944ee6b3ca5f1cb46e0` 及原型／圖面比對。以下是可取得記錄的涵蓋對照，不宣稱已取得每段歷史逐字全文。

- **U**：找到使用者直接要求或後續確認。
- **B**：在既有已提交規格／Prototype／圖面中可確認的基線；不單憑助理宣稱升級成 U。
- **P**：助理提出的技術建議；沒有後續確認則維持待決。
- **O**：沒有找到足夠證據完成決策；記為 OPEN，不能用建議填成定案。

日期／時間均以 Asia/Taipei 記錄；只列確實可對應的時間，其他以日期／主題表示。repo 內的 Prototype 實作限制與產品需求分開記錄，避免用已實作部分否決後續使用者要求。

### 10.2 主要歷史來源

| 來源 | 記錄 | 核對重點 |
|---|---|---|
| H-01 | 10/12 框架／自訂模組；15:58 使用者說部門使用 LangChain／LangGraph | 既有生態偏好；Haystack 是助理早期候選 |
| H-02 | 10/13 ParsedDocument／Chunk／fields／vectors 討論 | 五／六個 key、Embedding 寫向量、後續沿用 Chunk |
| H-03 | 10/14 09:09、09:31 設定修正 | DEV／自訂 API、collection 自動帶入、Retrieval 不選 Implementation |
| H-04 | 10/14 10:44～11:00 LLM／Prompt 討論及 Generation 範例要求 | LLM 集中、Query Prompt、雙層模板及範例說明 |
| H-05 | 10/14 13:11、13:34 API／Filter 討論 | 可隨時看端點、Indexing 欄位與 Retrieval 詞值、eq／in／AND |
| H-06 | 10/14 13:59～14:18 Infra 修正與後續圖面 | Control Plane、Frontend／Backend、tSSO、Runtime 邊界、Vault／YAML／Store 線 |
| H-07 | 10/14 16:14 CSV 入口、16:39 Document Schema | 先 Config／先 CSV、每列映射、型別／必填／預設 |
| H-08 | 10/14 17:09 Parsing UI 指示 | 只顯示結構化 JSON，其餘設定預設收合 |
| H-09 | 10/14 17:17 策略選擇；17:41～17:42 融合位置追問 | 「在哪一步合併」是目標要求；助理候選 Plan／預設未定 |
| H-10 | 10/14～15 L1 圖修正、基準 SVG／Mermaid | 左到右、1～5 框內、6 框外、實體名稱與虛線 |
| H-11 | 10/15 本對話的核心定位、03～08 分工、coding agent 目標 | 新手／進階、04＋05 獨立 Engine、逐項待決與驗收 |
| H-12 | 10/15 09:57～10:06 名詞釐清 | Engine／Runtime／System、Config、移除 Blueprint、Workspace → System、跨環境部署與版本問題 |
| H-13 | 10/15 10:22～10:24 名詞文件定位與撰寫確認 | 正式名詞集中在 03，05 保留資料／版本細則，08 記錄決策與待決事項 |

只有問題或助理回答的主題，不直接視為使用者核定了所有底層選項。例：曾討論 class 不代表 Runtime Validation 自動成立；曾提出 Rerank 後融合不代表具體 Plan／預設已確認。

### 10.3 要求與文件涵蓋矩陣

| 項目 | 對話／決策要求 | 證據 | 文件位置／本輪結果 |
|---|---|---|---|
| A-01 | UI Config 建立模組化 RAG、測試與匯出 | H-11／B | 03 §2～6、04／07；已覆蓋 |
| A-02 | 以部門 LangChain／LangGraph 生態為背景 | H-01／U | 03 §3、08 D-27／Q-001；補強已定方向與待選版本的界線 |
| A-03 | ParsedDocument 固定五個 key | H-02／U+B | 05 §4.2；已覆蓋 |
| A-04 | Chunk 固定六個 key，新增 vectors | H-02／U+B | 05 §4.3；已覆蓋 |
| A-05 | 下游主要傳 Chunk，不強制回查 ParsedDocument | H-02／U+B | 04 I/O、05 §4.3；已覆蓋 |
| A-06 | Document Schema 宣告型別／必填／預設／來源 | H-07／U | 05 §3、06 §3；已覆蓋；null／migration 仍待 Q-002 |
| A-07 | CSV／Import 做映射，Parsing 不重映射 JSON | H-02／H-07／U+B | 04 Import／Parsing、05 §4.1、06 §4；已覆蓋 |
| A-08 | CSV 每列一份文件、兩種起始入口 | H-07／U | 03 §2、06 §4；已覆蓋 |
| A-09 | Recursive／Header-aware、Token 計量 | H-03／B | 04 §4.3、05 §6；已覆蓋；Tokenizer 演算法待 Q-004 |
| A-10 | 從 fields 選來源，寫入具名 vectors | H-02／U+B | 04 §4.4、05 §4／§6；已覆蓋 |
| A-11 | 保存、全文、向量與 Filter 用途分開 | H-02／B | 04 §4.5、05 §6；已覆蓋 |
| A-12 | ES＋Local Search；Adapter 隱藏 index 數量差異 | H-02／B | 03 §5、04 §4.5；已覆蓋 |
| A-13 | Local Memory／MongoDB，重啟重匯或重建 | H-03／U+B | 03 §5、07 §7；已覆蓋；多 Pod 不假裝共享 |
| A-14 | 多欄位可分別選 Embedding／搜尋／Rerank／Generation | H-02／B | 04 各模組、05 §6；已覆蓋 |
| A-15 | Retrieval 移除 Implementation，按欄位推導模式 | H-03／U | 04 §5.2、06 §3.2；補為明確已確認 UI 要求 |
| A-16 | 可選 Sum Score／RRF | H-09／U+B | 04 §5.2、05 §6；已覆蓋；原始分數加總為現有基線 |
| A-17 | 需要能配置「在哪一步合併」 | H-09／U | 03～07、08 D-23／Q-014；修正原版誤列為可選擴充 |
| A-18 | 同 Query Score Sum→跨 Query RRF、Rerank 前後路徑 | H-09／U+P | 04 §5.2、05 §6、Q-014；保留情境，具體 Plan／預設未定 |
| A-19 | 共用 LLM 清單、下拉 llm_ref | H-04／U | 05 §6、06 §3.2；已覆蓋 |
| A-20 | Rewrite／Multi-query Prompt 可編輯、變數與預覽 | H-04／U+B | 04 §5.1、06 §3.2；補齊明確 UI 動作 |
| A-21 | Generation 兩層模板、說明／範例／套用按鈕 | H-03／H-04／U+B | 04 §5.4、06 §3.2；補回被概述掉的按鈕要求 |
| A-22 | Rerank 平台格式與可查看 Request／Response | H-04／B | 04 §5.3、06 §3.2；補強 UI 展示及候選 index 說明 |
| A-23 | DEV／自行提供；依模式才展開服務連線 | H-03／U | 03 §6、06 §3.3、07 Export；已覆蓋 |
| A-24 | collection 自動命名且穩定，不要求手填 | H-03／U+B | 05 §2.2、06 §3.2、07 §4；補回公式方向與唯讀要求 |
| A-25 | Indexing 選 Filter 欄位，Retrieval／Query 設詞值 | H-05／U | 05 §6.5、07 Query；已覆蓋 eq／in、AND 與 ACL |
| A-26 | 未 Ingestion 也可看 Ingest／Inference API 說明 | H-05／U | 06 §6、07 §5；補齊 Base URL／認證／cURL／輪詢內容 |
| A-27 | Edit Ingestion 需重匯，只改 Inference 重測 | H-11／B | 05 §8、06 §7、07 §4；已覆蓋，版本發布細節待定 |
| A-28 | 新手／進階、AI 助手、從 CSV 開始、進階收合 | H-11／U | 03 §2、06 §3～4；已覆蓋 |
| A-29 | Parsing 只顯示 JSON，其餘預設關閉 | H-08／U | 06 §3.2、08 D-22／Q-025；修正原版誤列為建議 |
| A-30 | Export 給 FTEST／ENT、部署不帶 Builder／資料／Secret | H-06／B | 03 §4～6、07 §9；已覆蓋，Bundle／Vault 細節待決 |
| A-31 | L1 固定橫向、框、名稱、回圈與部署虛線 | H-10／U+B | 03 §4、既有 SVG／Mermaid；補回文字約束，圖面未改 |
| A-32 | Infra 前後端、Runtime 邊界、圖示、外部依賴與省略線 | H-06／U+B | 03 §4、07 §1／9／10；補回圖面省略不等於刪除功能的區別 |
| A-33 | 04＋05 可獨立跑 Engine，07 才串 Builder／API | H-11／U | 03 §3、04 §1～2、07 §1；已覆蓋 |
| A-34 | 03～08 各有未決清單，供 coding agent 分階段開發 | H-11／U | 每份結尾＋08 §4／6；已覆蓋，本次補對話證據與反向追蹤 |
| A-35 | Engine／Runtime／System 的核心責任區分 | H-12／U | 03 §3、04 入口、07 邊界；已統一 |
| A-36 | Config 是模組／邏輯設定，Blueprint 非使用者術語 | H-12／U | 03、05 §6、06 Export；正式名詞移除，原型遷移另記 |
| A-37 | 同一 System 同版 Config 相同，部署設定不同 | H-12／U | 05 §6～7、07 儲存／Export；分開範例與環境綁定 |
| A-38 | Workspace → System | H-12／U | 03／05／06／07；移除額外 Group 層 |
| A-39 | 文件內容版本與索引資料版本的差別 | H-12 問題＋B | 05 §2.1；加入例子，具體版本生成／發布仍待 Q-007／Q-015 |
| A-40 | 名詞定義集中在 03，其他規格分工引用 | H-13／U | 03 §3、04～08／README；新增固定錨點，區分定義、契約與決策紀錄 |

### 10.4 修正與仍待決的界線

本輪修正：融合時點需求不可被 Prototype 基線降級；Parsing 收合不可重列為建議；補強 collection、範例按鈕／API 說明與圖面約束。這是文件補正，不是 UI／Engine 已新增能力。

下列沒有找到足夠的使用者定案證據，因此維持待決：套件精確版本、正式前端／平台 DB、來源 ID／revision 演算法、更新／刪除原子性、重試／取消／併發／恢復政策、原始檔保留、評估門檻、AI 真實模型／樣本政策、Vault 產品，以及 Fusion Plan 具體 stages／預設。若後續找到較新的明確決策，按 Q-ID 更新，保留決策來源與修正紀錄。

### 10.5 本輪檢查證據

對照表累計 40 項（v0.10 原為 34 項，v0.11 增加名詞釐清，v0.12 增加名詞文件定位）。文件更新時檢查跨文件連結／錨點、Q-ID、JSON／YAML 範例語法、資料頂層 key、未修改 Prototype／圖面，以及遠端版本後再提交。這些是文件一致性驗證，不取代日後 Schema／Engine／Runtime 的功能測試。

## 11. 名詞相關決策紀錄

正式名詞定義以 [03 §3](../03_architecture_proposal.md#terminology) 為準；本節保留討論結果、來源與待決邊界，供追蹤變更。

### 11.1 2026-10-15 10:06 名詞釐清

| 主題 | 決策調整 | 現行定義 | 仍待決細節 |
|---|---|---|---|
| Config | 將邏輯處理設定與環境部署設定分開 | [03 §3.3](../03_architecture_proposal.md#config-terms) | 正式 Schema 拼字、CLI 載入與檔案包裝 Q-002 |
| Blueprint | 確認為助理引入的名稱，移出正式領域模型 | [03 §3.3](../03_architecture_proposal.md#config-terms) | 舊 Prototype 匯出標籤及檔名 migration Q-002 |
| System 跨環境 | 同版邏輯 Config 一致，環境差異收在部署綁定 | [03 §3.3](../03_architecture_proposal.md#config-terms) | deployment_id／綁定版本／資料目標識別 Q-015／Q-021 |
| 管理階層 | 採用 Workspace → System，不設額外 Group | [03 §3.1](../03_architecture_proposal.md#system-terms) | 權限矩陣／CRUD API Q-006／Q-019 |
| Engine／Runtime／System | 區分核心框架、API 服務及具體應用，保留直接 SDK 入口 | [03 §3.1](../03_architecture_proposal.md#system-terms) | 資源生命週期／多實例策略 Q-017／Q-020 |

使用者對 source_revision／index_generation 的提問，已在 05 §2.1 加變更例子，概念定義集中到 [03 §3.4](../03_architecture_proposal.md#version-terms)；這不是核可了快照儲存、生成 ID 或發布原子性。未決政策保留原 Q-ID。

### 11.2 2026-10-15 10:24 名詞文件定位

- 使用者確認將名詞併入 03，不另開名詞文件；現有 §3 擴充為「名詞定義與元件責任」。
- 03 統一定義系統組成、模組／流程、Config／部署設定及版本概念；04～07 以連結引用，05 保留欄位、規則與範例，08 保留決策及待決狀態。
- 此分工讓 coding agent 先取得一致語意，再按任務讀取詳細規格；後續改名詞須同步權威定義及受影響文件。
- 未決 Schema、生命週期、權限及索引版本政策沿用原 Q-ID，不因整理名詞而視為已定案；不新增技術選型。

v0.11／v0.12 均只修改規格與 README；未修改 HTML Prototype／API／Engine。舊原型 Groups／RAGBlueprint 仍需在正式實作時依新名詞遷移，不能把新文件當成程式已更新。

## 12. 2026-10-15 回到原規劃對話的整合核對（v0.13）

### 12.1 來源與保留原則

- 起點為 `e52c4d74a469522155d814f0ff51fddf8946f957` 的 03～08／README／「畫userflow」交接摘要；逐項比對原 RAG Builder 規劃對話可見的模組、UI、資料契約、服務及圖面要求。
- 另核對到 10/15 10:06 的使用者確認：同一 System 的 Config 相同、部署設定可不同；Workspace → System；Blueprint 並非使用者指定。沿用 D-29～D-32，不回到早期額外 Group 的命名。
- 這次亦核對原型 Blob `0cc835ef686136b920d46714d604d797462f250f`：目前為 v0.8，仍只有單層融合、舊 Groups／RAGBlueprint 名稱。正式規格與原型的遷移範圍繼續分開記錄。
- 本次未取得其他對話逐字全文；以前的證據限制仍見 §10.1。v0.13 核對時持久化歸屬為 OPEN；後續 v0.14 已由使用者確認，見 D-33／§13。
- 後續在本串繼續規劃；正式名詞、規則與決策分別由 03、04～07、本文維護，不再需要臨時 handoff。

### 12.2 直接補正的小幅差異

| 項目 | 補正 | 主責位置 |
|---|---|---|
| Inference I/O 接線 | Retrieval、Rerank 的 I／O 明列原始問題；None 也持續傳遞；include_original 只控制搜尋清單 | 04 §3.1 |
| Parser 多路 | 同一 System 可同時啟用不同格式路由，同格式選有效策略；CSV／records 不重複映射 | 04 §4.2 |
| UI 入口與編輯 | 明列單一主畫面、左側 Workspace、中央卡片、右上 Create RAG System；Edit 重用表單 | 06 §1 |
| 服務來源選項 | 恢復 Embedding／ES／Local MongoDB／共用 LLM／Rerank 的明確 DEV 與自行提供選項 | 06 §3.2.1 |
| 相依卡控 | 補具體上游→下游案例，停用原因、失效引用保留及定位方式 | 06 §3.3 |
| API 與 Schema | Ingestion 範例註明先宣告的 Schema；引用範例帶來源版本及位置，Revision 與 05 使用同一示意值 | 07 §5.3／5.6 |
| 基線與目標分開 | 原型 Provider 格式標為基線；Retrieval 提前 Top-K 與 Rerank 全域上限只適用既有單層路徑，多階段依 Q-014 驗證 | 04 §4.4／5.2／5.4、05 §6.4、Q-003 |

ParsedDocument 五個 key、Chunk 六個 key、fields→vectors、多欄位用途、Local Search 的搜尋／持久化分工、CSV 兩種入口、LLM／Prompt、Filter、獨立 API Runtime、YAML 交付與已確認圖面要求均保留。這次只修改文件，未修改 Prototype 或圖面、未實作 Engine／API。

### 12.3 需要使用者討論的實作邊界

| 問題 | 可選方向及影響 | 追蹤／狀態 |
|---|---|---|
| Local Memory／MongoDB 的歸屬 | v0.13 曾列兩種歸屬；v0.14 使用者確認模式隨 Config 跨環境固定，DEV Memory 則 FTEST／ENT 也為 Memory。已同步主責規格，具體欄位與模式變更的資料重用仍另決 | 此子題已決，見 D-33；Q-002／Q-021 其餘細節仍 OPEN |
| Fusion 路徑 | 既有原型把所有 Query×欄位在 Rerank 前做一次 Sum Score／RRF；目標另有同 Query／跨 Query、Rerank 前／後的配置需求。v0.14 進一步釐清先討論候選／分數 Contract，再定可配置的合法融合點及各階段 K／N，見 §13 | Q-014；需求已確認、資料草案／具體配置 OPEN |
| Config 變更後的資料可見性 | 簡化為重建完成前阻擋 Query，或維持舊 Config＋舊 Index 服務直到切換；兩者影響版本、任務、UI 與資料保存。來源文件版本／索引版本的概念已區分，快照、歷史回復與零停機仍需明確核可 | Q-010／Q-015；OPEN |

以上為優先影響契約及端對端行為的項目；不因本次核對而選定方案，也不要求先解完所有 27 項問題才能開發。每次確認後同步主責規格、範例及相應 Q-ID。

### 12.4 本輪文件驗證

03～08 與 README 共 7 份文件：108 個相對連結、69 個錨點、12 段 JSON、3 段 YAML 及 1 段 Python 範例語法檢查通過；維持 27 個 Q-ID、32 個 D-ID 及 40 項既有要求對照。檢查 handoff 已移除且無失效引用、YAML 範例解析語意不變、既有 Mermaid 未變動。Python 只檢查語法，不執行尚未存在的 Engine。Prototype／Runtime／模型／DB／K8s 本輪沒有新增功能驗收。

## 13. 2026-10-15 11:03 持久化確認與 Inference 資料討論（v0.14）

### 13.1 已確認與尚待討論的界線

- **已確認 D-33**：DEV 用 Memory，FTEST／ENT 也用 Memory。持久化模式屬邏輯 Config，不能由 Export 的環境覆寫任意切換；連線／Secret 等部署綁定仍分環境提供。只關閉此子題，不因此關閉 Q-002／Q-021 的所有細節。
- **已確認 D-23 的配置方向**：使用者自行選擇在哪個合法步驟後融合。先定義 Inference 如何傳遞候選與記錄分數，才能討論後續處理；不得以固定 Plan A／B 限制位置選擇。
- **v0.14 歷史資料草案**：當時提出 InferenceState／RankedList：共用 Chunk 內容、多份 Query×路徑及各階段排序、分數來源／方向／rank、輸入結果關聯及下一步選用清單。v0.15 已依後續討論改為 [05 §4.6](05_data_contracts_search_design.md#inference-state-draft) 的 QueryContext／ResultSet／ResultItem，見 §14；具體欄位仍為待確認草案。
- **重建範圍釐清**：新增／單文件更新、因切分／Embedding 等配置改變而重處理既有資料、Memory 重啟後重匯，以及 MongoDB 恢復索引分開。先前 Query 可見性問題主要針對既有資料重建；各情境的發布／鎖定政策仍待 Q-008～Q-010／Q-015。

### 13.2 下一步討論順序

1. 確認 Chunk 內容、評分記錄與排序清單的責任／必填欄位，不先凍結程式命名。
2. 確認逐 Query／跨 Query／Rerank 的清單輸入與輸出，及 Fusion 的可配置位置。
3. 再定各階段 Top-K／Top-N、分數轉換／權重、丟棄候選與記錄保留方式。
4. 另釐清新增／更新／整批重建期間的 Query 可見性；資料型別討論不代替發布政策。

本輪只更新文件與新增討論草案，不宣稱 Prototype 已有多階段融合或 Engine 已實作這些型別。

文件驗證：7 份文件的 111 個相對連結、72 個錨點、13 段 JSON、3 段 YAML 與 1 段 Python 範例語法通過；InferenceState 示例的 Chunk 六個 key、清單引用與 rank／score 可檢查。D-ID 增至 33，Q-ID 維持 27；YAML 解析語意與圖面未變。這些檢查不代表草案已經型別凍結或可執行。

## 14. 2026-10-15 具體 Inference Schema 與例子（v0.15）

- 使用者要求列出實際 Schema 與例子，據此把 05 §4.6 更新為 QueryContext → ResultSet → ResultItem；保留 InferenceState 作多 Query 外框，取代舊全域 rankings 展示形狀。此為審閱草案，不代表使用者已確認所有欄位。
- 新增 [JSON Schema](../schemas/inference_context.schema.json) 及 05 §4.6.6 所列四份自包含快照：三路 Retrieval、3→4 候選篩選、Rerank 新分數／排序、跨 Query RRF 合併。
- 明列 active_query_ids／active_result_set_ids、直接輸入清單、逐項 source_refs，以及評分問題／模型／參數；Chunk 仍為六個 key，來源可暫存在同次執行，沒有新增永久 Trace Store 的承諾。
- 資料驗證與執行能力分開：Schema 檢查形狀；引用／rank／分數／融合語意與方法能力仍由 Engine 驗證。Filter 範例是候選後處理，不取代 Top-K 前授權限制。
- Q-002／Q-014 維持 OPEN；本輪僅具體化討論資料與例子，未凍結方法、融合位置／預設、Top-K／Top-N 或 Trace 保留政策，也未修改 Prototype／Engine。

本輪驗證：Draft 2020-12 Schema 本身與四份完整例子通過；另檢查 Query／ResultSet／Chunk 引用、來源無環、原始問題、rank／score、篩選保分及 RRF 重算，六份刻意破壞的資料皆被拒絕。文件檢查涵蓋 7 份文件、118 個相對連結、72 個錨點及 12 段 JSON／3 段 YAML／1 段 Python 範例。上述為草案資料與文件檢查，沒有測試真實模型、搜尋服務或 Runtime。

## 15. 2026-10-15 14:31 Contract 記錄與 UI 整合草案（v0.16）

- 來源：14:10 ES Sum Score 回傳形狀；14:17 metadata 與運算資料責任；14:24 三種操作；14:28 共同排序；14:31 要求整理文件並討論 UI。時間均為 Asia/Taipei。
- 新增 D-34／D-35，只確認操作分類與共同排序語意；不把助理建議的欄位拼字、順序卡片或預設升格為定案。
- 新增 [09](09_inference_contract_ui_plan.md)，集中 UI 提案與案例；05 維持型別主責，04 維持執行主責，06／07／03 交叉引用並對齊。
- 更新 inference-0.2-draft：來源 field_paths、三類操作的 stage 草案、Top N 例子及 ES Hybrid 例子，保留五／六個資料頂層 key、Query 原始問題與 active／provenance 語意。
- 原 02_filter.json 已由 02_top_n.json 取代；舊版可由 Git 歷史追溯。業務 Filter／ACL 保留，候選分數 Filter 不另增加為第四類結果操作。
- Q-002／Q-003／Q-014／Q-025 其餘細節維持 OPEN；未新增通用 DAG、正式 Engine、HTTP 服務或部署行為，未修改 Prototype／圖面。

本輪檢查：Draft 2020-12 Schema 與五份 JSON 通過，12 份刻意破壞的資料被拒絕；Python 型別欄位與 Schema 對齊，正／反向排序、rank、空輸入、來源不被覆寫及 Top N 範例均通過。8 份文件的 139 個相對連結、78 個錨點、12 段 JSON／3 段 YAML／2 段 Python 語法通過；原 YAML 語意未變。這些是文件與示例資料檢查，沒有驗證真實 ES／模型或 Runtime。

## 16. 2026-10-15 15:53 UI 待辦記錄，暫不實作

最新 UI 方向與完整待辦集中於 [10_ui_adjustment_backlog.md](10_ui_adjustment_backlog.md)：基本／進階共用設定、Retrieval 後預設合併、同 Query 多路／跨 Query 預設勾選、四處動作後 Top N，以及預選 fields.* 的 Reranker 評分內容。明確區分 Chunk 內容欄位與 Query 問題來源，取代 09 早期以獨立 Top N／任意順序卡片為主的呈現方案。

使用者明確要求先不改 UI，晚點與其他需求併批修改；本輪只增加清單與導引，不修改 Prototype、Schema、Python 範例或 Engine。Q-002／Q-003／Q-014／Q-025 仍保留尚未核定的 Config／Adapter／遷移細節，不將尚未執行的驗收待辦勾選為完成。

## 17. 2026-10-15 18:55 要求實作結果處理 UI（Prototype v0.9）

- 依使用者「幫我按照需求調整 UI」開始實作 [10](10_ui_adjustment_backlog.md)，不再停留於待辦。保留現有單檔、單一 Create／Edit 及模型／資料庫模擬界線。
- 同 Query 多路／跨 Query 合併預設勾選，各自選 Retrieval 後或 Reranker 後；ES 內部 Hybrid 與平台結果合併分開；同一套有效計畫推導服務於摘要、驗證、Edit 影響及 Export。
- 四處 Top K／N 各自驗證，不強制遞減；Reranker 預選一個合法 fields.* 文字欄位、Top 3，提問來源另列。關閉模型不跳過必要的後置合併。
- 文件去重可用於單份清單；最終去重應在最後一次合併後。原型 Generation 仍限單一 ResultSet，不隱含拼接多份清單。
- Config 拼字 `retrieval.processing`／`ui-0.9-draft` 是原型表單草案，不等於正式公共介面。新增的 RRF 預設、轉換規則與其他上限初值為展示值，見 10 §6；不新增 D-ID、不關閉 Q-002／Q-003／Q-014／Q-025。
- 驗證：56 項既有 VM 規則、23 項新增結果處理規則（含兩種後端×四種時點組合），以及既有 jsdom 流程與 13 組新增 DOM 操作通過；沒有頁面腳本錯誤。沒有執行真實 ES／模型／Runtime，也未重跑瀏覽器視覺／手機版面檢查。

Inference Schema／五份 JSON／Python 範例、圖面及其他服務實作均未變更；UI 測試不表示 Engine 已實作融合、分數轉換或引用鏈。

## 18. 2026-10-16 Fixed-size、階段重排與文件優先

- 09:31 討論開發與驗收；09:42 要求新增 fix chunk 且後續先更新文件；09:45 指定 UI 需求記入 backlog、M5 包含 Builder 內 AI 助手操作，階段完整重排為 M0～M7。時間均為 Asia/Taipei。
- D-36 新增 Fixed-size Token Chunking，不刪 Recursive／Header-aware；方法語意與邊界驗收更新 04，Config／有效參數更新 05。精確 Tokenizer 與 Unicode／offset 策略仍由 Q-004 核定。
- D-37 將獨立助手排 M4、Builder 前後端與助手互動排 M5、Evaluation 排 M6、獨立部署排 M7；§4／§4.2 與所有當前 Q-ID 階段依賴同步，保留歷史章節原編號並提供對照。
- D-38 確認文件優先，新增 UI 需求以 [10 §7](10_ui_adjustment_backlog.md#ui-backlog-pending) 為單一 backlog；Fixed-size 表單與助手整合均尚未修改 Prototype。
- 本輪文件集更新 v0.17；新增三筆決策，Q-ID 維持 27 項、既有 A-ID 40 項來源對照維持。已確認需求不因 Q-ID 的剩餘細節而回退為未提出。
- 只更新規劃文件；Prototype 仍 v0.9。Engine、Runtime、JSON Schema、五份 Inference JSON／Python 範例、測試程式及圖面維持原版本。文件驗證與 Git blob 比對不表示新方法／助手已開發。

## 19. 2026-10-16 10:05 內容保存確認與 Rewrite 輸出討論

- D-39 確認三點：保存全部 Chunk.fields／metadata，移除 Indexing「儲存內容」；只選全文／向量／Filter 能力；Chunking 預設繼承全部有效 metadata，排除有需求再規劃。完整 metadata 不放寬 Schema／ACL，也不自動對全部欄位建立搜尋能力。
- 04／05 更新模組、有效設定與驗收，05 的目標 YAML 範例只移除 metadata_fields／stored_fields；不改其他執行參數，原型舊配置仍待正式遷移。
- 使用者提出 Rewrite 的 UI 試跑及如何固定 Query 數量／LLM 輸出。04 §5.1.1／06 §3.3.1 記錄 Structured Output＋後端驗證＋有限失敗處理與單模組試跑的提案；不是已確認預設，不新增 D-ID 代替使用者決策。Provider／格式／去重／重試／fallback 分別留 Q-003／Q-017／Q-023；接口細節留 Q-019。
- 10 新增 UIB-005／006 已確認待 UI 實作、UIB-007 提案待確認。沒有新增畫面、呼叫模型或建立測試端點，Prototype 仍 v0.9。
- 文件集 v0.18，D-ID 共 39、Q-ID 27、既有 A-ID 40。新規則與舊版 UI 完成紀錄分開；JSON Schema、Inference 範例、程式／測試、圖面未變。文件與 Python 示範驗證不能代替真實 Provider／Engine 驗收。

## 20. 2026-10-16 10:22 Rewrite 合併與 Generation 格式提案

- 使用者詢問 Rewrite 是否等於 Multi-query=1、是否合併，以及 count／Schema／自由 Prompt 的分工。核對原型為兩種選項與兩份 Prompt；建議合成一種啟用方法，以 N 控制單／多 Query，保持原始問題及設定遷移，見 04 §5.1.2／06 §3.3.2。
- count 由平台動態帶入 queries Schema；Prompt 描述改寫語意，不能繞過格式／筆數驗證。格式正確仍不代表語意／多樣性正確。原生限制依服務能力，不支持時走已核定策略／明確錯誤，不能宣稱所有 OpenAI-compatible 服務都相同。
- 使用者提出 Generation 可自訂 JSON、預設格式與收合進階設定。04 §5.4.1／06 §3.5 整理推薦設計，區分業務內容 Schema、平台回應／可信引用、主要回答文字路徑與完整回傳／Streaming。現有 QueryResult.answer 字串與 HTTP 範例未改；payload 容器／版本相容留 Q-002／Q-019，評估相容留 Q-018。
- 以上為本輪提問後的討論提案，待使用者確認；不新增 D-ID、不把 Schema／預設值／UI 細節升格為定案。10 UIB-008／009 保持未完成，既有 007 試跑提案也不因此視為已核可。
- 文件集 v0.19；M0～M7、D-ID 39、Q-ID 27、A-ID 40 維持。只更新九份 Markdown；Prototype v0.9、公開 Schema、Config YAML／HTTP JSON 範例與其他可執行產物未變。

## 21. 2026-10-28 Module Developer 與文件分工

- 使用者新增 Module Developer 需求，已要求 L1 呈現 Engine／開發關係；接續討論 SDK、Component 識別、repo／套件及 import。此次依前述討論整理文件，D-40 記錄角色與擴充需求，不把套件命名、載入 API、Schema 或發布政策視為已全部核定。
- 04 補齊 SDK／Engine／Component package 責任、component_id／版本、安裝／註冊／執行、語意與能力驗證、配套方法、Builder 與部署邊界。原 Registry 草案的 module_id 用語改為 component_id；正式 Config／既有 UI 的遷移留 Q-002，沒有批次改動可執行範例。
- 新增 11 開發指南，以 Python 介面示意與套件流程解釋開發者工作；引用 05 的資料契約，ParsedDocument 實際 Schema 繼續待討論。不新增已可執行 SDK／Runner 的宣稱。
- 03 同步角色及套件名詞，README 補閱讀導引；本文 §4.3 將配套分配至既有 M0～M7，Q-022 保持 OPEN。10 新增 UIB-010 Component 目錄／設定／相依卡控待辦，Prototype 維持 v0.9。
- 本輪只調整文件，保留所有既有圖面、公共 Schema、Inference JSON／Python 範例與測試；D-ID 增至 40、Q-ID 維持 27。正式動工前需決定的事項見 §4.3 與 11 §8；沒有要求本次先決定全部技術細節。
- 文件檢查：10 份 Markdown 的 179 個相對連結（含 102 個錨點連結）、15 段 JSON、3 段 YAML、5 段 Python 語法及 1 段 TOML 均通過；ParsedDocument 待決段落完整保留。Python 只解析語法，未執行尚未存在的 SDK；此紀錄不代表 Engine／UI／部署驗收。

## 22. 2026-10-28 確認 Builder／Engine 兩個 repo

- D-41 記錄使用者對發布相依的討論與確認：rag_platform 管理 Builder；rag_engine 集中 SDK、Engine、Components／Adapters 與 Runtime API，Module Developer 在同 repo 提交 PR。此決策取代先前平台＋獨立 Component repo 的預設規劃。
- 03 新增 repo／Image／服務邊界的權威定義；04／11 同步同 repo 開發、公開 SDK 邊界、乾淨環境 package 測試及完整 Runtime 交付。七項 Component 配套與 ParsedDocument 實際 Schema 待決狀態保留。
- 07 明列目標程式分工、Runtime Component 目錄／Config 驗證能力，以及 Builder、Component、Engine 改動時的建置／部署範圍。新版本發布不自動升級所有 System，API／Schema 相容才可各自升級；不承諾 Component 熱插拔或零停機。
- 06／10 同步相容 Component 目錄與表單整合待辦；UIB-010 維持未實作。README／本計畫補 D-41 與 M0～M7 的 repo 分工，Q-001／Q-019／Q-021／Q-022 只將已確認子題落定，其餘細節維持 OPEN。
- 本輪只更新規劃文件，尚未建立 rag_engine repo、搬移程式、建置 Image 或修改 Prototype／圖面；D-ID 共 41、Q-ID 27、歷史 A-ID 40。M4 獨立助手／M5 Builder 整合的責任與順序保留，助手核心的目錄／Image 配置仍明示為建議。

## 23. 2026-10-28 Component 設定描述與動態 UI 規劃

- D-42 記錄使用者同意依建議規劃 Schema、UI hints 與相依規則；新增 12 作為設定描述的單一草案來源，區分 Module I/O、Component Config 與呈現資訊。
- 規劃共用父類別從 config_type 產生 Schema；Component 補充動態選項、能力、規則及必要 UI feature。以 Fixed-size 提供 Python／JSON 設定描述範例，定義 Engine 相依驗證與可定位問題，不強迫每個 Component 重寫 Schema 產生方法。
- 確認相依停用可見、無關欄位隱藏、進階收合、失效引用保留報錯及未知必要控制項不假裝可用。區分 applicability 排除分支與 constraint 阻擋錯誤；UI 收合不能跳過驗證，正式建立／儲存／套用依同一 Engine 規則。
- 04／06／07／11 增補責任及導引，UIB-010 細化並列入 14 個未執行的開發驗收案例；M0～M7 次序不變。README／本計畫更新 D-ID 為 42，Q-ID 仍 27、歷史 A-ID 仍 40。
- component-ui-0.1-draft 的精確協定與 SDK／API 仍待核定；本輪只改文件，不修改 Prototype、公開 I/O Schema、既有 Inference／HTTP 範例或圖面。ParsedDocument 實際 Schema 待討論段落及七項 Component 交付要求保留。

## 24. 2026-10-29 Component 命名統一

- 使用者確認 Component 的元件／積木概念；D-43 採用 Component 作為可註冊實作的正式名稱。Module Developer 角色保留，Module／Component／Component Instance 的區別與舊名對照統一於 03 §3.8。
- 全文件的擴充單位與歷史敘述採現行術語，決策日期、原意與實作狀態不變。Registry／Descriptor／錯誤的識別欄位改為 component_id，範例 ID 值與 implementation_version 不變；ABC、套件／目錄與 entry point 示意一併更新，沒有建立新 repo 或搬移真實程式。
- 04／11／12 檔名改為 module_components／component，所有文件內連結同步；08／10 舊錨點保留相容別名，正式引用用新錨點。七項交付、14 個 SUI 案例與 ParsedDocument 待討論項目內容保留。
- 05 的新 ModuleConfig 目標引用 component_id；舊完整 YAML／Prototype 的 method 選擇欄位明示需依版本遷移。ResultSet／融合演算法 method、Python／HTTP method 保留，不全域替換公共 I/O 欄位；不得在未實作前宣稱支援舊別名。
- L1 MMD／SVG／PNG 同步 Component 標籤，保留既有版面與連線。Prototype 名詞／內部設定遷移補在 UIB-010，沒有改動 UI 程式、Infra、Inference 公共 Schema 或其測試。D-ID 共 43、Q-ID 27、歷史 A-ID 40；里程碑仍為 M0～M7。

## 25. 2026-10-29 Developer 四步流程與 Module／Component 示意圖

- 依使用者要求，將 L1 開發區簡化為 D1 選 Module／讀契約 → D2 開發 Component → D3 測試與 PR 審查 → D4 發布並更新 Runtime。保留上方 Builder 測試、框外部署與中間 Engine 的版面／關係，D4 更新目標 Runtime 後才提供新元件選用。
- 新增 [03 Module／Component 概念圖](../diagrams/03_module_component_concept.png)，含同名 MMD／SVG。以 Parsing、Chunking、Indexing 示意預設內建與 Developer 自訂元件；其他 Module 同理，元件遵循相同契約／Registry，由 Builder 依 Schema 與能力選用。
- 預設提供不代表全部同時執行，也不表示目前已實作；自訂元件需測試、PR 審查、核可及目標 Runtime 更新。四步是既有流程摘要，D3／D4 權限由審查、CI／發布與部署角色分工；沒有新增直接上傳程式、任意熱載入或自動升級承諾。
- README／03／11 同步說明與導引。本輪是既有 D-40～43 的展示與文件補充，不新增功能決策或修改 M0～M7；D-ID 43、Q-ID 27、歷史 A-ID 40 維持，Prototype／Infra／公開 I/O Schema 及執行程式未變。
