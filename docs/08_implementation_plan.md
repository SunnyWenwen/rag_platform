# RAG Builder — 開發計畫、驗收與決策追蹤

> 文件集 v0.12 · 2026-10-15 · 開發規格草案
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

## 2. 文件責任與建議閱讀順序

先讀 [03](../03_architecture_proposal.md)，以 [§3 名詞定義](../03_architecture_proposal.md#terminology) 統一概念與責任邊界，再讀本計畫；實作依序讀 [05 契約](05_data_contracts_search_design.md)、[04 Engine](04_module_methods_io_contracts.md)、[07 整合](07_backend_runtime_integration.md)、[06 UI](06_ui_development_spec.md)。

| 權威範圍 | 文件 |
|---|---|
| 正式名詞定義、產品／架構與非目標 | 03 |
| 獨立 Engine、模組組裝／演算法／語意驗證 | 04 |
| 共用資料、Config 及欄位型別 | 05 |
| 互動與基本／進階呈現 | 06 |
| HTTP、平台儲存、工作與部署整合 | 07 |
| 決策狀態、階段、驗收／阻擋 | 08 |

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
| D-07 | Recursive／Header-aware、一個主要切分欄位、Token 計量 | 舊 05 §13.1／既有基線 | 04 |
| D-08 | Embedding fields→vectors；摘要先由輸入提供；文字 Dense 優先 | 舊 05 §6／既有基線 | 04／05 |
| D-09 | ES／Local Search（FAISS＋BM25）；Local Memory／MongoDB | 舊 05 §8／既有基線 | 03／04 |
| D-10 | Local Search 同程序／單副本；MongoDB 只持久化並支援重建 | 舊 03 §5.3／既有基線 | 04／07 |
| D-11 | 現有 Prototype 為單層、Rerank 前、Sum Score／RRF；這是既有實作基線，不限制可配置合併時點的目標 | 舊 05 §17＋2026-10-15 歷史核對 | 04／05 |
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
| D-23 | 目標需可配置融合策略與「在哪一步合併」；具體 stages／兩層／預設計畫尚待 Q-014 | 2026-10-14 17:41～17:42 使用者追問／需求已確認 | 03／04／05／06／07 |
| D-24 | 共用 LLM、可編輯 Query Prompt、Generation 模板範例／套用按鈕與 Rerank 格式說明 | 2026-10-14 10:44～11:00 對話／已確認方向 | 04／05／06 |
| D-25 | L1／Infra 的框、標籤、方向、圖示及省略線依使用者既有修改保留 | 2026-10-14～15 對話與基準圖／已確認 | 03 §4／既有圖面 |
| D-26 | Ingest／Inference 的 API 端點說明隨時可看，包含未 Ingestion 狀態 | 2026-10-14 13:11 使用者要求／已確認 | 06／07 |
| D-27 | 以部門 LangChain／LangGraph 生態為技術背景；Haystack 未被使用者選定 | 2026-10-12 15:58 對話核對／已確認偏好 | 03／04／Q-001 |
| D-28 | Engine 是模組組裝／執行核心，Runtime 加 API，System 是套用 Config 的具體應用；可直接 SDK 建立 | 2026-10-15 名詞對齊／已確認方向 | 03 §3、04、07 |
| D-29 | 正式 Config 指模組 Method／參數與邏輯；Blueprint 是助理引入的名稱，移出正式領域模型 | 2026-10-15 10:06 使用者釐清／已確認 | 03／05／06／07 |
| D-30 | 同一 System 同版 Config 在不同環境保持相同；部署設定可不同 | 2026-10-15 10:06 使用者確認／已確認 | 03／05／07／Q-015／Q-021 |
| D-31 | 正式階層為 Workspace → System，無額外 Group 層 | 2026-10-15 10:06 使用者確認／已確認 | 03／05／06／07 |
| D-32 | 名詞定義集中在 03 §3，05 保留資料／版本規則，08 保留決策紀錄；其他規格引用 03 | 2026-10-15 10:22～10:24 建議後由使用者確認撰寫／已確認 | 03 §3、04～08／README |

「既有基線」不代表已涵蓋後續需求。D-23 的合併時點配置是使用者已提出的目標，不能以 D-11 的 Prototype 限制否決；Q-014 負責核定實際支援路徑及契約，不再討論是否記錄這項需求。助理建議的預設兩層計畫及 stage 命名則仍未定案。

## 4. 開發階段與驗收

下列為**建議執行順序**；能力是同一產品分批交付，不代表把後面的已確認能力刪除。階段完成需留下可實際執行的成果。

| 階段 | 範圍／依賴 | 交付 | 驗收 |
|---|---|---|---|
| M0 契約與專案基礎 | 先定 Q-001／Q-002；未決問題可獨立起草 | 版本鎖、程式結構、Pydantic／JSON Schema、完整範例及錯誤例 | 從乾淨環境可安裝；範例通過 Schema，錯誤可定位；無需 Builder |
| M1 最小獨立 Engine | Structured records／Recursive／Dense／Local Memory／Query；依賴模型、Token、索引與失敗政策 | 可直接 Python／CLI 操作的 Engine；真實 Adapter＋隔離測試替身 | 手寫 Config ingest→query；檢索真的使用資料；引用可對回；程序重啟後正確不就緒 |
| M2 能力與後端 | 多欄位、BM25／融合、Rewrite／Multi-query、Rerank、ES／MongoDB；Parser 依 Q-005，Fusion Plan 依 Q-014 分批 | Adapter／Registry、Manifest、合併時點與策略配置、各模式範例與契約測試 | ES／Local 契約一致；MongoDB 恢復不重跑 Embedding；Filter／多路融合可驗算；核定時點改變真實路徑 |
| M3 Runtime API | 包裝已可用 Engine；定 API／工作／認證／併發 | OpenAPI、Runtime 服務、Job Store 政策、SDK／cURL 範例 | SDK／HTTP 相容；202 可查結果；失敗／重送／重啟行為有證據 |
| M4 Builder 串接 | 管理儲存、Create／Edit、CSV／Schema、漸進式 UI | Backend、正式 Frontend、System／Revision／Binding | UI 呼叫相同 Runtime；取消不改配置；變更影響正確；可處理版本衝突 |
| M5 評估與 AI 助手 | Q-018／Q-024；可先用規則或 Fake 驗證流程 | Dataset／Runner、報告、真實助手及結構化建議／Diff | 無標註不造分；報告綁版本；助手不直接改 active Config，不執行 Ingestion |
| M6 獨立交付 | Q-021／Q-027；核心 Runtime 已真實可用 | Image、FTEST／ENT Bundle、部署／Secret／資料準備說明 | 新環境無 Builder 可啟動；API Ingest→Query；外部依賴故障可定位；不含測試資料與憑證 |

M1 先跑標準 records，CSV 由映射產生相同輸入；不要為了完成第一條流程同時實作所有 Parser／UI／AI。M2 不預設一次交付全部能力，按核定子任務逐項驗收。M5 的評估純邏輯可在 M1／M2 先做，平台排程不需提前完成。

### 4.1 階段決策 Gate

| 開始的工作 | 必須先明確的問題 | 尚可先做 |
|---|---|---|
| 正式契約／公開 SDK | Q-001／Q-002 | 需求整理、Schema 候選、型別範例 |
| 真實 Token／Embedding／搜尋 | Q-003／Q-004／Q-011；安全最小範圍 Q-006 | Fake Adapter、欄位映射與純函式 |
| 對既存文件更新／partial 寫入 | Q-007／Q-008／Q-009／Q-010 | 純新增、不重複 ID 的受限流程及明確拒絕 |
| MongoDB 恢復 | Q-012／Q-015 | Store 介面與小型 Manifest 草案 |
| HTTP／工作服務 | Q-017／Q-019／Q-020；資料保存 Q-016 | Engine SDK 及 Client／Repository interface |
| 正式 UI、AI、評估、交付 | 各自 Q-025／Q-024／Q-018／Q-021 | 獨立 Mock／驗證流程並標記未實接 |

只阻擋受影響功能；不要求所有 Q-ID 全部解決才能開發。未核定正式政策時，受限實驗必須明示範圍，不能成為隱藏產品預設。

## 5. 驗收材料與完成定義

### 5.1 必備材料（在開發階段建立，並非本輪已存在）

| 材料 | 最小內容 |
|---|---|
| examples/configs | 完整 Local Memory、ES、Local MongoDB 配置；必要服務／Secret 設定說明 |
| fixtures | CSV／records、已知文字與標題、Unicode／長文字、合法／無效欄位、同 ID 更新與 Filter 測資 |
| retrieval fixtures | 固定小向量／詞項與人工路徑排名，可計算 Top-K／RRF／Sum Score／去重 |
| provider fakes | 合法回應、Timeout、429、缺項、錯誤維度、非法 Rerank index、未知引用 |
| usage examples | 直接 Engine、HTTP、CSV 映射、工作輪詢、部署後首次 Ingestion |
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
- 建議：沿用 Python／既有生態；選最小必要套件並鎖定。Web Framework／前端沿用部門標準；具體版本要實測再鎖。
- 替代：以專案獨立技術棧開發，需增加維運／整合評估。
- 負責角色：技術負責人＋Engine／前後端；阻擋 M0 正式依賴及 M2 ES 選型。
- 決策：未定；更新 03／04／07 及 dependency lock。

<a id="q-002"></a>
### Q-002 共用 Schema、Config、SDK 與版本凍結

- 已確認：邏輯 Config 與部署設定分離，正式名稱不使用 Blueprint；Workspace → System。不清楚的是 05 建議拼字／枚舉／Default／nullable、array 型別、錯誤 Envelope、SDK、多 Profile 及原型短名稱／匯出標籤 migration。
- 建議：先核定最小完整 Config＋單一公開 Engine interface；Pydantic 匯出 JSON Schema，UI 使用相同來源。用完整欄位路徑；未知別名拒絕。
- 替代：直接沿用 Prototype 全部短名稱；需補齊其缺少型別與執行語意。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 契約凍結。
- 決策：未定；更新 04／05／07、Schema 及完整範例。

<a id="q-003"></a>
### Q-003 模型服務與 Adapter 契約

- 不清楚：首組模型、Profile／版本辨識、Tokenizer 取得、Chat 角色／輸出格式、多 Query 解析、Rerank 服務限制。
- 建議：先落實已選的 embeddings／Chat Completions／平台 rerank 格式，各有 Fake 與真實契約測試；不同格式顯式 Adapter。
- 替代：第一期支援多 Provider 格式，增加測試矩陣。
- 負責角色：Engine＋模型服務提供方；阻擋 M1 真實服務。
- 決策：未定；更新 04／05／07。

<a id="q-004"></a>
### Q-004 Token 計量、切分邊界與溢位

- 不清楚：Token 計數版本、prefix／特殊 Token、單塊超長與複製欄位、overlap／fallback、Tokenizer 離線檔案。
- 建議：固定 Tokenizer／revision，以實際模型輸入檢查；超限回可定位錯誤，截斷需明示。
- 替代：自動切分／截斷，需定義來源與警告語意。
- 負責角色：Engine；阻擋 M1 Token／模型上限驗收。
- 決策：未定；更新 04／05、Unicode／長文字 fixtures。

<a id="q-005"></a>
### Q-005 Parser／OCR 首批格式

- 不清楚：PDF／PPTX／圖片／TXT／MD 哪些第一期支援；套件／外部 OCR、表格／標題 Schema、加密／損壞處理。
- 建議：M1 先 structured records，Native text 及其他格式逐一有測資才開放；OCR 服務另驗證。
- 替代：第一期納入全部格式，需增加品質／成本驗收。
- 負責角色：產品＋Engine；阻擋 M2 格式能力，不卡 M1 records。
- 決策：未定；更新 03／04／05／06／07。

<a id="q-006"></a>
### Q-006 metadata 保留區、租戶與授權

- 不清楚：保留欄位名稱、ACL 來源、System／Workspace 權限、tSSO／Gateway 驗證、獨立 Runtime 認證。
- 建議：可信 Context 注入租戶與 ACL，保留 metadata 顯式命名且不可覆寫；初期最小權限模型先核定。
- 替代：只先驗單 System 的封閉環境；不得宣稱多租戶安全已完成。
- 負責角色：平台／身分團隊＋Backend＋Engine；阻擋 M1 保留欄位及 M3／M4 多使用者服務。
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

- 已有需求：使用者要求可配置融合策略及「在哪一步合併」，並提出逐 Query Score Sum→跨 Query RRF 情境；D-23 已記錄，不能只當可做可不做的助理建議。
- 不清楚：正式支援哪些前／後 Rerank 路徑、單層／兩層、scope／stage Schema、預設計畫、每階段 K／N、Rerank Query、同分／重複候選、分組與分數語意。
- 候選：受控 Plan A（同 Query 融合→跨 Query 融合→Rerank）、Plan B（同 Query 融合→逐 Query Rerank→跨 Query 融合）、舊單層基線。這些具體組合與 `fusion.stages[]` 都需核定；不自動選助理推薦當預設。
- 建議：先定可驗證的有限計畫及共同 route 型別，保留 query／route identity；Rerank=None 及非法組合須顯式驗證。文件分組另定，不與 chunk_id 去重混同。
- 負責角色：產品＋Engine＋Frontend；阻擋目標時點配置的契約／驗收，可先維持舊基線做迭代但不宣稱需求完成。
- 決策：配置能力的需求已確認；具體計畫／預設／Schema 未定。同步更新 03～07 與範例。

<a id="q-015"></a>
### Q-015 Revision、有效 Config Hash 與 Index 版本

- 已確認：同一 System 的同版邏輯 Config 跨環境相同，部署設定分開；文件 source_revision 與 index_generation 概念分開。不清楚的是保存／生效時點、Hash、草稿衝突、CSV mapping 歸屬、環境部署識別／資料版本及快照切換。
- 建議：分開保存版本與執行綁定；Hash 只納有效配置並保留有語意順序，使用樂觀版本檢查。
- 替代：單一 active revision，改配置後阻擋到準備完成；仍須避免 lost update。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 Hash 凍結及 M4 版本操作。
- 決策：未定；更新 05／06／07。

<a id="q-016"></a>
### Q-016 平台儲存、原始資料與保留

- 不清楚：Config／Run／Dataset／Report DB、原始檔／ParsedDocument 是否保存、Trace 原文、期限／刪除、獨立 Runtime 儲存。
- 建議：管理資料與搜尋 Chunk Store 分離；可用 Store interface 分環境替換；只保存明確必要資料。
- 替代：統一平台 DB／Object Store；獨立 Runtime 的外部依賴與成本需交代。
- 負責角色：Backend＋平台／資料負責人；阻擋 M3／M4 正式持久化與資料政策。
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
- 建議：先有可驗算的 Retrieval 指標與操作指標，再加明示 Judge；缺資料拒絕或 skipped。
- 替代：先 End-to-end Judge；不得冒充有可靠 Retrieval Ground Truth。
- 負責角色：產品／資料＋Engine＋Backend；阻擋 M5 正式評估／Gate，不卡 Query 主線。
- 決策：未定；更新 03／04／06／07。

<a id="q-019"></a>
### Q-019 API／HTTP Envelope 與呼叫認證

- 不清楚：完整 CRUD／助手／管理 API、OpenAPI、錯誤碼／狀態、上傳限制、manifest、冪等鍵、DEV 路由、認證及暴露 Trace。
- 建議：沿用 07 的 Endpoint 草案，先凍結 Ingestion／Status／Query，補齊 Backend API；HTTP 與領域錯誤分層。
- 替代：沿用既有企業 API 規範並明確映射。
- 負責角色：Backend＋Runtime＋Frontend／身分團隊；阻擋 M3／M4 真實串接。
- 決策：未定；更新 05／06／07、OpenAPI／cURL 範例。

<a id="q-020"></a>
### Q-020 DEV 共享 Runtime 與資源隔離

- 不清楚：每 System 實例快取、Tenant／System 路由、同時工作、記憶體配額、回收、是否獨立程序。
- 建議：先有受限共享 Runtime 與明確隔離 Binding；Local Search 每 System 的 Ingest／Query 必須同程序。
- 替代：每 System 獨立 Runtime，增加部署／資源管理成本。
- 負責角色：平台＋Backend／Runtime；阻擋 M4 多 System 服務。
- 決策：未定；更新 03／07。

<a id="q-021"></a>
### Q-021 Export、FTEST／ENT 與 Secret Vault

- 已確認：同版邏輯 Config 不隨環境改變，環境連線／Secret／資源為部署設定。不清楚的是 Image／Bundle 包裝、Vault／注入、Secret 型別、K8s 資源／Ingress／Probe 及 CD 流程。
- 建議：版本鎖定 Runtime Image＋有效 Config＋環境覆寫；Local 單副本；明示未帶資料且無 Builder 依賴。
- 替代：使用單位既有 Helm／GitOps 形式；仍需相同可驗證交付內容。
- 負責角色：平台／DevOps＋Backend；阻擋 M6 正式部署交付。
- 決策：未定；更新 03／05／06／07。

<a id="q-022"></a>
### Q-022 自訂程式的交付與隔離

- 不清楚：第一期僅核可套件還是 UI 上傳；依賴建置、Sandbox、Secret／網路、權限與版本測試。
- 建議：先受控 Registry／核可 Adapter，保留固定 Contract；未完成隔離前不執行任意使用者 Python。
- 替代：UI 上傳＋隔離試跑，需獨立安全與資源規格。
- 負責角色：產品＋平台／Engine；阻擋自訂程式正式能力，不卡內建模組。
- 決策：未定；更新 03／04／06／07。

<a id="q-023"></a>
### Q-023 Fallback、無資料、Budget 與引用

- 不清楚：無 Context 是否一律 abstain、Context 截斷順序、未知引用、多 Query／Rerank 失敗降級、生成回應格式。
- 建議：錯誤與無命中分開；預設不靜默降級；明確定義無資料與超限回應，保留實際 Context。
- 替代：可設定 fallback，但需 Trace／warnings 與測試。
- 負責角色：產品＋Engine；阻擋 M1 正式回答邊界及 M2 降級。
- 決策：未定；更新 04／05／06／07。

<a id="q-024"></a>
### Q-024 真實 AI 設定助手

- 不清楚：模型／Prompt／成本、樣本抽取與保存、結構化輸出、Diff／Patch、過期建議、選擇性套用與撤銷。
- 建議：限制 Schema／Registry、只用明確樣本、先顯示差異並驗證；以 Draft 基準防止覆蓋人工改動。
- 替代：先保留規則助手，清楚標示 Mock；不得聲稱已由 LLM 理解資料。
- 負責角色：產品＋Frontend＋Backend／AI；阻擋 M5 真實助手，不卡手動配置。
- 決策：未定；更新 03／06／07。

<a id="q-025"></a>
### Q-025 漸進式 UI、範本與小量試跑

- 已確認：Parsing 初始只顯示結構化 JSON，其他格式／設定全在預設關閉進階區；LLM／Prompt／範例及 API 說明要求見 06 §3.2。待定的是其餘基本／進階分組、展開記憶、改動摘要、範本、真實試跑與診斷範圍。
- 建議：保留已確認互動，再核定其餘分組；必填錯誤可定位，保持同一 Config。試跑與範本逐項啟用。
- 替代：單獨新手／專家入口，但兩者仍需共享 Config／驗證。
- 負責角色：產品＋Frontend；阻擋 M4 正式 UX 凍結，不卡 Schema／Engine。
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
- 負責角色：產品＋平台／Engine／QA；阻擋生產容量承諾與 M6 運維驗收。
- 決策：未定；更新 03／04／07／08。

## 7. 優先討論順序

第一輪先討論 Q-001／Q-002（技術與契約）、Q-003／Q-004／Q-011（可跑的模型／搜尋基線）、Q-007～Q-010（資料更新及可見性）。第二輪處理 API／儲存／Runtime，再依 UI、AI、評估及交付階段決策。

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

Agent 可自行選局部 helper／內部名稱等可逆細節；公共 Contract、資料遺失／安全語意、外部依賴與範圍變動需回報或記成 Q-ID，不能偷偷做成產品決策。遇一項阻擋時先完成可獨立驗收的部分，再提出具體選項。

後續開始程式開發時建議加入根目錄 AGENTS.md，引用本文與 03～07，記錄建置／驗證指令；本輪只交付規格，不新增未經確認的開發自動化規則。

## 9. 本輪交付與尚未完成

初版交付（v0.9）：重整 03～05、新增 06～08、更新 README，登錄 27 項未決問題。歷史核對版（v0.10）補正需求／基線／建議的界線，見 §10；名詞釐清版（v0.11）統一 Config／部署設定、Workspace → System 及版本概念；名詞集中版（v0.12）整理 03 §3 並補齊其他文件引用，見 §11。Q-ID 維持 27 項，不以重新編號掩蓋修正。仍只交付文件，不宣稱 Engine、API 或合併時點 UI 已實作。

2026-10-15 依使用者要求新增 [開發文件交接](documentation_handoff.md)，整理跨對話接續所需的目標、分工、重要決策、待決事項、歷史核對限制及 GitHub 入口；沿用 v0.12 規格語意，未增加產品技術決策。

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
