> 歷史來源快照：docs/08_implementation_plan.md；來源 commit 916734ac0bbe0631a205bfd52626ce332aa7beb2。2026-11-05 整合後不再作現行規格；相對連結固定到來源版本。現行入口：[README](https://github.com/SunnyWenwen/rag_platform/blob/docs/rag-system-factory/README.md)。

# Retrieval Builder — 開發計畫、驗收與決策追蹤

> 文件同步：2026-11-05 · 開發規格草案（正式 SDK／Config 尚未凍結）
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

**2026-10-16 起的工作方式**：使用者要求後續調整先更新文件；Prototype 所需變更統一記於 [10 UI Backlog](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/10_ui_adjustment_backlog.md#ui-backlog-pending)，待使用者明確要求修改 UI 再實作。文件提交不代表同步開發原型、Engine 或服務。規劃文件仍依既有要求提交目前分支。

## 2. 文件責任與建議閱讀順序

先讀 [03](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/03_architecture_proposal.md)，以 [§3 名詞定義](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/03_architecture_proposal.md#terminology) 統一概念與責任邊界，再讀本計畫；實作依序讀 [05 契約](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/05_data_contracts_search_design.md)、[04 Engine](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/04_module_components_io_contracts.md)、[07 整合](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/07_backend_runtime_integration.md)、[06 UI](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/06_ui_development_spec.md)。

| 權威範圍 | 文件 |
|---|---|
| 正式名詞定義、產品／架構與非目標 | 03 |
| 獨立 Engine、模組組裝／演算法／語意驗證 | 04 |
| 資料流／Config／版本總覽；三份資料 Schema 與語意 | 05；13～15／schemas/ |
| 互動與基本／進階呈現 | 06 |
| HTTP、平台儲存、工作與部署整合 | 07 |
| 決策狀態、階段、驗收／阻擋 | 08 |
| Inference Contract 討論摘要與 UI 整合提案 | 09；欄位以 05、決策以 08 為準 |
| Prototype 待辦／目前狀態 | 10；歷史驗證證據放 history/validation，使用者要求改 UI 時才實作 |
| Component 開發、測試及套件交付流程 | 11；Engine 機制以 04、三份共用資料以 13～15／schemas/ 為準，Config／Inference 見 05 |
| Component 設定描述、UI hints、動態選項與相依規則 | 12；B 的 I/O 細化／六類宣告與逐層相依見 24；共用資料仍以 05／13～15 為準，UI 待辦記於 10 |

同一型別／規則不在多份文件各寫一套。03 定義名詞，05 規範對應的資料結構／版本規則，本文保存現行決策摘要與待決狀態；原始來源及討論過程在 history/，不取代 03 的現行定義。程式 Schema 與文件同步；不能只更新 UI、測試或其中一份規格。

## 3. 已確認方向與保留基線

現行結論集中如下；D-ID 用來追查來源，不要求閱讀歷次討論才能實作。完整原始決策表、當時提案及逐輪變更見 [歷史決策紀錄](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/history/decisions/decision_history.md)。公共 Contract 的精確形狀以主責文件／Schema 為準。

| 主題 | 現行結論 | 來源／主責 |
|---|---|---|
| 產品／範圍 | Retrieval-only；無 Generation，Rewrite／助手仍可用 LLM；Evaluation 保留 M6 | D-50／03、04、21 |
| 管理階層 | Workspace → System；system_id 穩定，名稱／Config Revision／document_id 分開 | D-21／D-31／D-64；03、05、07、21 |
| 輸入與 Parser | JSON-only；IngestionDocument[] 非空 List，每筆與 Parser 共用 Schema；content／base64／uri 三選一；多 Parser 按能力分派 | D-44／45／58；13、21 |
| ParsedDocument／Chunk | ParsedDocument 四鍵＋平面 units；Chunk 六鍵；不跨 Unit 合併／overlap，進階多任務結果相加 | D-47～49；14、15 |
| 追溯與 metadata | _rag／來源／fingerprint／ordinal 由 Component 選擇提供；metadata 可有明確支援的處理提示 | D-52；13～17 |
| Chunk／Embedding 能力 | Fixed-size／Recursive／Header-aware 用 Token；可複製原文欄位、另留原文 Chunk；Embedding 可選模板衍生欄位，兩項新增功能預設關閉 | D-36／48／53；04、15 |
| 保存／搜尋 | 保存完整 Chunk；全文／向量／Filter 能力分開。ES 或 Local Search；Memory／MongoDB 持久化模式屬邏輯 Config，跨環境不任意切換 | D-09／10／33／39；04、05、19 |
| 索引交接 | 每 System 一組邏輯索引；IndexBinding 五鍵，無 index_ref／searchable；Indexing 提供，Retrieval 宣告格式及能力相容 | D-55；19 |
| 推論資料 | 直接傳 QueryContext[]；ResultSet=key/items，ResultItem=chunk/選填score；items 順序即排名，過程寫 Logs | D-54；05、09、17 |
| 結果處理 | 同 Query／跨 Query 兩層融合，各可在 Retrieval／Rerank 後；四個 Top N；RRF／Sum Score；文件去重選代表 Chunk | D-11／12／23／34／35；04、05、09 |
| 共用模型 | System 共用 LLM 名稱清單，Rewrite 以 llm_ref 引用；模型語意與環境連線分開 | D-13／24／30；05、23 |
| I/O 宣告與細化 | B 提供固定或依 Config 細化的資料規格，首版六類純宣告；Engine 逐層推導選項／相依。取消 D 頂層 document_schema；Local／Remote 相同，正式語法待定 | D-67；12、20、24；UIB-021 |
| Component 開發 | 兩 repo 分工：rag_platform 管 Builder，rag_engine 管 SDK／Engine／Components／Runtime API；Admin 核可登錄，既有 System 固定元件版本 | D-40～43；03、11、12、20 |
| Remote 整合 | Local／Remote Image／External；可接管連續多 Module，Manifest 註冊，User 選服務；不加 data_space_id。Image 每 System 獨立服務與必要儲存；External 沿用既有資料空間 | D-51；18 |
| Flow／Config | 共用 Flow／Executor；每次請求及已接受文件固定 Config 快照，各步獨立傳入 Component Config／Context，資源作用域另管 | D-61／62；03、04、07 |
| Config 生效／環境 | 同 System 有 queued／running Ingestion 時僅存草稿，工作結束後才允許新版生效；D 存邏輯值，E 存連線／Secret／目標及 Runtime 限制 | D-29／30／63／64；05、07、22、23 |
| Ingestion 工作 | document_id 完整覆寫、逐文件結果；整批預檢才 202；文件無 partial，Run 可 partial；工作／Queue 留記憶體，重啟 unknown，不續跑、不提供取消 | D-56～58；21 |
| 讀寫／失敗 | 不加 Query 讀寫鎖，接受更新期間混合可見；同文件 queued／running 拒絕重複提交；未知 Remote 寫入不自動重試；資料清理／恢復仍有待決項 | D-59／60；21、Q-008～Q-010／Q-017 |
| 文件管理 | exists、文件摘要與 retire 讀取／管理實際儲存；摘要為 documents[]／next_cursor、document_id／source_revisions[]；retire 同步 200＋deleted 或 not_found，忙碌 409 | D-58／64／65；21 |
| API／認證 | 7 支業務＋2 支 Health；Runtime 暫採一組 Basic 帳密操作服務 API；Builder 登入延後；共用 Runtime 經可信內部 System 路由選 Config | D-60／64；07、21 |
| Runtime 控制 | 接收大小、Queue／併發、Rate／Deadline、終態狀態保存由 Admin／部署者在 E 設定；14 項初始值集中維護 | D-64；22 |
| UI／工作方式 | 單一 Create／Edit、CSV 測試、進階收合與相依卡控；需求先更新文件，UI 只在使用者要求時修改，差異記入 Backlog | D-02／22／26／38／42；06、10 |
| 部署／開發順序 | M0～M7；M4 獨立 AI 助手、M5 Builder 整合、M6 Evaluation、M7 Export；FTEST／ENT 自行部署，Runtime 不依賴 Builder，Export 不搬資料／真實 Secret | D-18／19／37／41／51；03、07、§4 |
| System Config 狀態 | 23 為現行討論稿；D-67 移除頂層 document_schema，舊五案例／機器稿歸檔。先審閱 25 的 B Descriptor／DS 候選，再完成 D；新鍵名／Meta-schema／SDK 均未定案 | D-66／67；23～25、Q-002／Q-028 |

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

Image 建置可在 M3 開始；M7 驗收的是可獨立部署的完整交付，不要求每個 Retrieval System 各建一個 Image。匯出通常引用支援該 Config 的 Runtime Image 版本／Digest，另外交付 Config 與部署設定。M6 的評估純邏輯可在 M1／M2 先做，但不能把早期模組測試當作 M6 整體評估已完成。

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

D-42 補充：M0 以 [12](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/12_component_schema_ui_contract.md) 核定 Descriptor／Schema 子集、規則語意及 fixtures；M1 做共用 Schema 輸出／Registry／設定驗證，M2 擴充各方法能力；M3 提供目錄、Context／動態候選與驗證 API，M4 助手重用，M5 完成動態表單與 SUI-01～14 互動驗收。可用方法、有效 Config 與服務／資料就緒分開檢查；不依 Schema 文件存在就宣告 API 或 UI 已完成。

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

不驗收生成答案。應檢查檢索排名／來源追溯、空命中、錯誤與輸出 Contract；Rewrite／助手另驗結構與語意，不要求 LLM 逐字相同。效能、品質／成本門檻由 Q-018／Q-027 決定，不捏造精確 SLA。

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

- 2026-11-05 Descriptor 格式候選：[25](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/25_component_descriptor_schema_draft.md)／examples/component_descriptor 提供機器 Schema、五組 Descriptor＋Config＋預期 I/O Schema／資料與 DS-01～DS-13。使用者授權提出初版，尚未核定具體鍵名／規則；先審 B 核心再完成 D，不以離線結構／樣本驗證取代完整細化解析器、UI 或 Runtime。

- 已確認：邏輯 Config 與部署設定分離，正式名稱不使用 Blueprint；Workspace → System；Local Search 持久化模式隨 Config 跨環境固定（D-33）；全部 Chunk.fields／metadata 保存與合法 metadata 全繼承（D-39）。不清楚的是 05 建議拼字／枚舉／Default／nullable、array 型別、錯誤 Envelope、SDK、多 Profile；QueryContext[]／ResultSet 業務欄位已依 D-54 確認。仍待核定的是舊保存／繼承投影、原型短名稱／匯出標籤 migration。
- D-62 已確認 B：共用 Flow／Executor，依固定 Config 快照在各 Module 選 Component，並傳入 input／本次 config／Context；不強制所有實例共用。精確 SDK 簽名及 Resolver／資源作用域仍待凍結。
- 2026-10-28 補充：Component SDK 的 Module-specific I/O 包裝、run／初始化／釋放簽名、RunContext、Registry／Factory 與 Config Schema 介面待凍結；Registry 草案改稱 component_id，不直接改寫既有 Config。精確方法／版本引用、舊 module_id 別名與遷移須一致驗證；11 的 Python 程式只作介面示意。
- [23 System Config 討論稿](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/23_system_config_schema_draft.md) 依 D-67 取消頂層 document_schema，資料細節由 B／C＋D 提供；首版六類宣告與相依推導見 [24](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/24_component_io_schema_refinement.md)。規則語法／SDK／解析 API 仍待凍結；D-66 舊機器稿及五案例已歸 [歷史快照](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/history/superseded/system_config_d66/README.md)，不作新功能驗收。前輪校對過程見 [歷史報告](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/history/reviews/2026-11-05_spec_alignment_review.md)。
- 建議：先核定最小完整 Config＋單一公開 Engine interface；Pydantic 匯出 JSON Schema，UI 使用相同來源。用完整欄位路徑；未知別名拒絕。
- 替代：直接沿用 Prototype 全部短名稱；需補齊其缺少型別與執行語意。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 契約凍結。
- 決策：未定；更新 04／05／07、Schema 及完整範例。

<a id="parsed-document-schema-pending"></a>
#### ParsedDocument 實際 Schema（2026-11-02 收斂為 0.2）

- 已確認 D-49：四個頂層鍵 document_id／source_revision／units／metadata；Units 為平面列表，不包 fields、不強制 unit_id。移除 structure 及依結構選 Chunker 的路由。
- Parser 負責解析／展平／決定獨立單位；Chunker 每筆內 Fixed-size／Recursive／Header-aware，不跨筆合併／overlap。預設 text，進階明確選字串欄位；Header-aware 使用當筆 Markdown 標題。
- D-52：Chunk 來源若有提供，採 unit_index＋field＋文字範圍；metadata 全繼承，Unit 其他欄位依 copy 帶入。Schema、範例與來源追溯同步升版，見 [14](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/14_parsed_document_contract.md)、[15](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md)。
- API／Parser Input 仍共用 IngestionDocument，content／base64／uri 不變；上游已解析 Units 經對應 Adapter 驗證，不新增直接 Chunk 輸入。
- 仍待：正式 SDK／發布版、Parser 空內容與表格／圖片政策、Tokenizer／Header-aware 細節、Parser 變更下的 revision／重建與舊資料遷移。UI 調整登錄 UIB-014，未改 Prototype。

<a id="chunk-schema-pending"></a>
#### Chunk 實際 Schema（2026-11-02 更新為 0.2 單位追溯）

- 已確認 D-47：六鍵外層、預設 text 免選欄位、進階多任務／copy、2＋3 結果串接、metadata 追溯與向量 Profile／來源資訊；精確資料見 [15](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md) 與 [JSON Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/chunk.schema.json)。
- D-52：source_refs／chunking、fingerprint／全域序號為選用；保留其標準形狀與參考 ID helper，不當所有 Component 的必填驗收。DenseVector 規則不變；既有 Inference 改引用同一份 Chunk，不重寫向量定義。
- 正式鍵名／nullable／自訂轉換、異質任務下游欄位適用條件、舊向量陣列遷移、跨語言 canonicalization 與 SDK 仍需審閱。身份 Hash 不解決索引原子提交；Q-007～Q-010／Q-015 保持有待決細節。
- Prototype v0.12 已有 [UIB-013／014](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/10_ui_adjustment_backlog.md#uib-013-chunk-contract) 的任務／平面 Units 配置與預覽；真實 Tokenizer／Chunker／DB 未交付，資料測試不代替其驗收。

- 2026-10-30 後續 D-48：多任務預設輸出 text；必要切分欄位缺失／型別錯誤／全空白、必要任務零產出及明確 copy 欄位缺失報錯。D-53 已確認由預設 Embedding Component 提供選用模板組合，不新增 Module；正式設定 Schema 未凍結、尚未實作，見 15 §9。

<a id="q-003"></a>
### Q-003 模型服務與 Adapter 契約

- 不清楚：首組模型、Profile／版本辨識、Tokenizer 取得、Chat 角色／輸出格式、多 Query 解析、Rerank 服務限制。
- 本輪待確認提案：Rewrite／Multi-query 採固定 queries 結構及 1／N 數量、Provider Structured Output／Tool／文字解析能力分級、模組 Schema 與共用 LLM Adapter 分工；格式與語意都由後端重驗。細節見 04 §5.1.1，不因寫入提案就凍結 Provider 或重試／fallback 預設。
- Rewrite 的 count=1／N、Schema 輸出約束提案保留（04 §5.1）；Generation 及其答案格式提案由 D-50 撤銷。
- 既有方向：Embedding API、System Rewrite／助手共用 LLM 的 OpenAI-compatible API、平台約定 Rerank API；原型格式基線為 embeddings／Chat Completions／04 的 rerank。原型基線不等於所有 Provider 相容性都已核定。
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
- 關聯待決：現行 Units 契約的正式版本凍結、Parser 正規化及文字格式能力細節見 [Q-002 子項](#parsed-document-schema-pending)；不恢復已移除的 structure 型別或結構路由。
- 建議：M1 先 Structured JSON，Native text 及其他格式逐一有測資才開放；OCR 服務另驗證。
- 替代：第一期納入全部格式，需增加品質／成本驗收。
- 負責角色：產品＋Engine；阻擋 M2 格式能力，不卡 M1 Structured JSON。
- 決策：未定；更新 03／04／05／06／07。

<a id="q-006"></a>
### Q-006 metadata 保留區、租戶與授權

- D-60：Builder 登入方式延後；Runtime API 暫採一組 HTTP Basic 帳密操作該服務全部 API，首期不做多角色／逐 API 授權，部署採 HTTPS／Secret 引用。D-64 已選可信 Backend 的內部 System 路由；具體部署保護／Secret 注入與 metadata 保留區仍 OPEN。

- 不清楚：保留欄位名稱、ACL 來源、System／Workspace 權限、tSSO／Gateway 驗證、獨立 Runtime 認證。
- 建議：可信 Context 注入租戶與 ACL，保留 metadata 顯式命名且不可覆寫；初期最小權限模型先核定。
- 替代：只先驗單 System 的封閉環境；不得宣稱多租戶安全已完成。
- 負責角色：平台／身分團隊＋Backend＋Engine；阻擋 M1 保留欄位及 M3／M5 多使用者服務。
- 決策：未定；更新 03～07。

<a id="q-007"></a>
### Q-007 文件／Chunk ID 與 source_revision

- 2026-11-03 D-52：必要 chunk_id 仍須有效／清單內唯一，但不強制由 fingerprint／ordinal 計算，也不強制將計算資訊寫入 _rag。SDK helper 可選用；穩定／更新語意按實作及此 Q-ID 核定。
- 2026-10-30 D-47：已同意可重現 ID 方向；15 §5～6 提供有效切分計畫 fingerprint＋文件內全域 ordinal 的 Python 參考演算法。仍不清楚：省略 revision 的生成、檔案拆多文件、CSV 無主鍵、同 revision 不同內容的衝突政策、跨語言 canonicalization 與正式遷移；不能再將穩定 ID 方向全部列為未決。
- D-65 確認文件摘要清單回 document_id＋source_revisions[]，彙整實際儲存 Chunk 的版本；這不凍結省略 revision 的生成規則、衝突政策或版本時序，也不等於持久工作歷史。
- 建議：跨批更新要求穩定 document_id，內容版本與 Config 分開；採明確可重現的衍生 ID 規則。
- 替代：每批當新文件；需接受無法自然更新與重複資料後果。
- 負責角色：Engine＋資料／產品；阻擋 M1 正式 ID 規範及 M2 更新。
- 決策：未定；更新 04／05／06／07。

<a id="q-008"></a>
### Q-008 重送、更新與刪除

- D-56 已確認：同 (System, document_id) 完整覆寫，不存在則新增；成功後清除舊文件不再產出的 Chunk，不做欄位 merge。同文件 queued／running 時拒絕重複提交，終態後可重新提交；Runtime 重啟不恢復工作。
- 仍待：source_revision 衝突／較舊來源、相同內容是否可 no-op、Idempotency-Key／遠端未知結果、retire 的執行／錯誤協定、實體索引替換／舊版清除及保留政策。整批接收前預檢通過才入列已由 D-57 確認；入列後逐文件結果。D-58 已確認單一 List 包裝、文件存在／ID 清單，以及 retire 直接刪除；精確管理介面仍待整理，取消工作首期不做。
- 建議：先不承諾 exactly-once 或未知寫入自動重試，按文件發布與相容機制實作；文件刪除另外定義。
- 負責角色：產品＋Engine＋Backend；阻擋安全重試／正式更新實作。
- 決策狀態：覆寫單位與忙碌拒絕方向已確認，以上其餘細節 OPEN；更新 04／05／07／21。

<a id="q-009"></a>
### Q-009 部分失敗與提交原子性

- D-56 已確認：以 document_id 為更新與成功／失敗單位；Batch 逐文件獨立結果，不要求全 Batch 回滾；文件完整執行成功才標 completed，不接受半份文件為成功；D-60 不加 Query 讀寫鎖，允許更新期間短暫讀不一致，失敗清理／保留舊版機制仍需 backend 落實。
- 仍待：ES／Local／MongoDB／Remote 的 staging／提交與搜尋可見性、崩潰清理；整批預檢與 Run partial／文件無 partial 已確認，counts／精確 Envelope 見 21 API-D01／02。單次 Bulk／Hash 不代表已具有文件原子替換。
- 負責角色：Engine＋Backend；阻擋 M2 更新與 M3 終態／提交驗收。
- 決策狀態：文件級原則已確認，實作與精確 Envelope OPEN；更新 04／05／07／21。

<a id="q-010"></a>
### Q-010 Ingestion／Query 併發與發布

- D-56 已確認：每 System 文件併發可配置、預設 1；不同文件可依上限並行，同 document_id queued／running 時拒絕重複提交。文件完成後完整替換，失敗不得冒充成功；D-60 放寬更新中的讀原子性，不加平台 Query 讀寫鎖。
- D-60 已確認讀寫各自進行，不因寫入阻擋 Query、不加共享讀寫鎖或原子快照；同文件重複提交忙碌拒絕保留。
- D-61／D-62 已確認 Builder 用一組或少數共用 API service／Flow，啟動不綁單份 Config；各請求固定 Config 快照，更新先驗證／解析及準備必要資源，不要求重建專屬 Flow。D-63 已確認該 System Ingestion 結束後才允許新版生效；舊 Query／資源交接仍待決。FTEST／ENT 主 Runtime 一 Pod＋一組 service＋一份 Config。
- 仍待：舊 Query 與 Component／資源回收、未知 Remote 操作判定、Config／資料 Profile 相容、實體 backend 可見性與失敗清理；D-63 已定一般 queued／running Ingestion 結束後才允許新版生效。整體 Query Ready 條件與寫入鎖不同，不因本輪放寬讀一致性就忽略實際錯誤。
- 第一版採已確認的無 Query 讀寫鎖策略；索引版本快照／零停機世代切換不是首期新增需求。
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
- 目前基準：D-54 已確認 QueryContext[]、filters／metadata、key／items 及選填 score，取代舊歷史狀態。09 的兩層合併、四處 Top N 已有 Prototype；正式 Config、同分、正規化與真實 Adapter 支援仍待核定。
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

- D-56 已確認：Runtime 共用有上限 Queue；工作／文件狀態放記憶體，重啟不保留／恢復，不保存斷點續跑。查不到紀錄為 unknown，不等於文件未寫入；終態紀錄可以限量／限時清理，活躍紀錄不提前清除。
- D-64 已確認 Runtime 整體 Deadline／狀態保存初始值與管理方式，集中見 22；A 的成功／錯誤核心欄位已確認。仍待模組／Client Timeout、有限重試／可重試錯誤、中斷及未知遠端副作用處理、正式 Schema／載入方式；取消工作首期不做。
- 建議：Engine 統一執行預算；不自動重試未確認的寫入，重試完整文件且需冪等支援。持久 Queue／自動恢復不屬第一版已確認需求。
- 負責角色：Engine＋Runtime；阻擋 M1 錯誤政策及 M3 工作語意。
- 決策狀態：無恢復與記憶體狀態方向已確認，其餘 OPEN；更新 04／05／07／21。

<a id="q-018"></a>
### Q-018 Evaluation 範圍與 Gate

- 不清楚：首批指標、Dataset／Ground Truth 格式、Judge／Rubric、Chunk／Document 層級、Rerank 前後、公開檢索 Target、Gate 門檻。
- 已移除答案正確性／Faithfulness 與自訂答案 JSON 的驗收；Evaluation 聚焦檢索排名、延遲、Usage／錯誤。
- 建議：先有可驗算的 Retrieval 指標與操作指標，再加明示 Judge；缺資料拒絕或 skipped。
- 替代：先 End-to-end Judge；不得冒充有可靠 Retrieval Ground Truth。
- 負責角色：產品／資料＋Engine＋Backend；阻擋 M6 正式評估／Gate，不卡 Query 主線。
- 決策：未定；更新 03／04／06／07。

<a id="q-019"></a>
### Q-019 API／HTTP Envelope 與呼叫認證

- D-60：Runtime API 暫採 HTTP Basic Auth，一組帳密可操作該 service 全部對外 API（含對外 Health），不做首期角色／逐 API 授權；Builder 登入延後。OpenAPI Security Scheme、驗證位置、Secret／Probe 配置與內部路由的具體部署保護仍待細化，不另加匿名 API 例外。

- 2026-11-05：[21](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/21_runtime_ingestion_inference_api_inventory.md) 盤點更新為 7 支業務＋2 支 Health：D-58 確認統一 List、文件存在／ID 清單與 retire 直接刪除；每筆 IngestionDocument／Query 契約不變。D-57 的整批預檢、Run partial／未知紀錄 HTTP 200 延續；精確文件管理 Path／Envelope／分頁／刪除執行、認證與錯誤仍待整理。

- 仍待：完整 CRUD／助手／管理 API、OpenAPI／完整錯誤碼、檔案 manifest、冪等鍵、內部路由的部署保護、Header／認證接線及暴露 Trace。D-64 已確認核心回應／錯誤、retire 結果、System 路由方向與 22 的初始限制，不再把這些全部視為未決。
- D-41 補充：Builder 與 Runtime 透過 API／Component 目錄合作；需核定目標 Runtime 版本識別、Config Schema／能力目錄、完整 Config 驗證、快取失效與接口相容政策。能力範圍見 07 §5.8，精確端點與 Envelope 仍 OPEN。
- D-42 已按建議規劃描述／Context／選項及驗證關聯值，候選格式見 12；精確路徑、認證、版本識別與公開 Meta-schema 仍 OPEN，不影響既有 Ingest／Query 範例。
- Query API 成功 body 直接回傳 QueryContext[]，只保留目前 key／items／score；排名以陣列順序表示。request／版本進 Headers／Logs；精確 HTTP 版本協商及錯誤待核定。
- D-64 已確認 retire 同步 200＋deleted／not_found、忙碌 409，狀態／錯誤核心欄位與可信內部 System 路由；後續 D-65 已確認 documents[]＋next_cursor 的摘要形式及 source_revisions[]；精確分頁參數／cursor、完整 OpenAPI、Backend 管理 API 與部署保護仍 OPEN；HTTP 與領域錯誤分層。
- 替代：沿用既有企業 API 規範並明確映射。
- 負責角色：Backend＋Runtime＋Frontend／身分團隊；阻擋 M3 Runtime／M4 助手 API／M5 Builder 真實串接。
- 決策：未定；更新 05／06／07、OpenAPI／cURL 範例。

<a id="q-020"></a>
### Q-020 DEV 共享 Runtime 與資源隔離

- D-51 已確認 Local 可同程序／Pod 建多 System；Remote Image 第一版每 System 獨立服務及儲存綁定；External 由 Developer 管理固定資料空間，無 data_space_id。下列快取／配額／清理細節仍 OPEN。

- D-56 已確認：Builder DEV／獨立 Runtime 共用 System Queue／併發與 Inference Rate／併發／Deadline；Runtime 控制總量，Builder 另管理 User／Workspace 配額。上限可配置已確認；放 E 為先前建議，D-57 暫緩管理者／存放位置／Schema 的定案。Worker 是排程概念，不要求每 System 新 Pod。
- D-61：共用 API service 啟動只綁服務／Registry 基礎設定，後續管理多份 System Config，不因每份 UI 設定新增服務；可依 Namespace／資源池分成少數共用服務，精確分組策略尚未選定。
- D-62 已選 B：共用 Flow／Executor，逐請求／已接受文件固定 Config 快照，Module 依設定解析 Component；不要求每份 Config 建立專屬 Flow。Component 實例／資源是否共用依狀態與隔離需求決定。
- 仍待：配置解析快取、Component／資源預載與回收、可信路由與管理 API、舊 Query／資源交接、服務池分組、公平排程、正式參數 Schema／載入方式、實際記憶體 bytes 配額、未知結果清理、未來多 replica 控制與程序安全性；初始上限與終態紀錄保存值已由 D-64 確認並記錄於 22。
- 建議：先有受限共享 Runtime 與明確隔離 Binding；Local Search 每 System 的 Ingest／Query 必須同程序。
- 替代：每 System 獨立 Runtime，增加部署／資源管理成本。
- 負責角色：平台＋Backend／Runtime；阻擋 M5 多 System 服務。
- 決策：未定；更新 03／07。

<a id="q-021"></a>
### Q-021 Export、FTEST／ENT 與 Secret Vault

- D-51：Remote Image 額外匯出遠端 Deployment／Service／設定／Secret 引用 YAML；External 只匯出連線引用。無 Image 本體或資料搬移，Manifest／控制介面連動 Q-028。

- 2026-10-28 D-41 確認：rag_engine 統一建置含 Engine／核可 Components／Runtime API 的完整 Image，rag_platform 建置 Builder Image；採用新版 Engine／Component 時仍需更新 Runtime，接口相容的 Builder 可維持原版。目標 Image 須包含 Config 所需 Component packages 並保存版本；Component 清單／鎖定格式與缺失錯誤仍待決，YAML 不會自動提供 Python 方法程式。建置／發布／部署範圍見 07 §9.4。

- 已確認：同版邏輯 Config 不隨環境改變，環境連線／Secret／資源為部署設定；Memory／MongoDB 模式也跨環境保持一致（D-33），不能只換部署設定切換。不清楚的是 Image／Bundle 包裝、Vault／注入、Secret 型別、K8s 資源／Ingress／Probe 及 CD 流程。
- 建議：版本鎖定 Runtime Image＋有效 Config＋環境覆寫；Local 單副本；明示未帶資料且無 Builder 依賴。
- 替代：使用單位既有 Helm／GitOps 形式；仍需相同可驗證交付內容。
- 負責角色：平台／DevOps＋Backend；阻擋 M7 正式部署交付。
- 決策：未定；更新 03／05／06／07。

<a id="q-022"></a>
### Q-022 自訂程式的交付與隔離

- D-51：下列同 repo 提交流程適用 Local；Remote Developer 可保留私有實作，提供 Manifest＋Image 或自行部署端點，服務註冊不要求提交原始碼／逐 Module ABC。

- 已確認方向：D-40 加入 Module Developer，由公開契約下的 Component 擴充能力供 Builder 使用；不是所有特殊策略都由平台核心開發者實作。2026-10-28 補齊 04 與 11 的規劃，未凍結套件／隔離細節。
- 已確認開發位置（D-41）：使用本機 IDE／SDK，在 rag_engine components 目錄開發並提交 PR；與同 repo 的 Engine／Runtime API 整合測試後交付完整 Runtime Image。公開套件／契約邊界保留，以乾淨環境安裝驗證替代「必須另建 Component repo」的驗收要求。
- D-67：B 的 I/O 細節／六類宣告規則由通用解析器處理；Local／Remote 同等宣告，不因提供 Source Code 與否改變能力；不要求所有 Component 自寫 Schema 解析函式。具體 Meta-schema／未知必要規則與相容測試待核定，見 24。
- D-42 補充：Component 的設定描述與規則是受限 JSON 資料；共用 Schema 輸出與 Registry 驗證，不以瀏覽器腳本或任意 import 擴充 UI。具體能力／控制項名稱登錄、支援子集與契約測試待核定，見 12。
- 建議起步：受控 Registry、核可 Component packages，先明確註冊再評估 entry points；不先建 Web IDE／任意程式上傳，也不要求以跨 repo Image 相依交付每次方法更新。
- 已確認補充：Admin 手動審核登錄／發布 Descriptor／Manifest，第一版不要求新增 Admin 管理 UI；Component 有 implementation_version，既有 System 固定選用版本、不自動升級。Local 仍需目標 Runtime 包含程式，Remote 需支援 Adapter／邊界，只有 Schema 不代表可執行。
- 尚待決：核可權限細分與可信程式範圍、依賴建置／選配套件倉庫、Factory／entry point 解析、SDK 相容矩陣、package／Component 版本對照與精確撤回／升級格式。跨 System 多版本／依賴衝突、目標 Runtime 方法可用性與索引相容另連動 Q-015／Q-020／Q-021。
- 若擴大為不受信任開發者或 UI 上傳：需另核定執行隔離、Secret／網路／資源限制與管理權限；Schema／RunContext 不能代替 Sandbox。未完成該方案前保留共享 Runtime 不任意執行使用者 Python 的限制。
- 負責角色：產品＋Platform／Engine Developer＋Module Developer；M0／M1 核定最小公開介面與載入，進共享 DEV 前核定發布／信任政策；不阻擋本文整理及既定內建路徑的受限開發。
- 決策狀態：角色／擴充需求與兩個 repo 分工已確認，具體技術與發布政策 **OPEN**；更新 03／04／06／07／11，UI 先記 10 UIB-010。本輪不以 repo 決策代替其餘細節核定。

<a id="q-023"></a>
### Q-023 Fallback、無命中與資源上限

- 不清楚：空清單、部分檢索路徑失敗、多 Query／Rerank 失敗降級與候選數／資源上限。
- 建議：錯誤與無命中分開；預設不靜默降級；明確定義空命中與超限回應，保留實際 ResultSets／Trace。
- 替代：可設定 fallback，但需 Trace／warnings 與測試。
- 負責角色：產品＋Engine；阻擋 M1 正式檢索輸出邊界及 M2 降級。
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
- UIB-008 Rewrite 設定提案保留；UIB-009 答案格式提案取消，產品名稱／結果呈現遷移見 UIB-015。
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
- 建議：先建立可重現基準再定門檻，保留 request／run／module Trace。D-56 已確認首期記憶體 Queue，D-64 有初始限制；分散式持久 Queue／HPA 與生產容量承諾另行評估。
- 替代：先採既有企業 SLA，需驗證 Local Memory／模型資源是否能滿足。
- 負責角色：產品＋平台／Engine／QA；阻擋生產容量承諾與 M7 運維驗收。
- 決策：未定；更新 03／04／07／08。

<a id="q-028"></a>
### Q-028 Service Manifest／Remote Pipeline 的具體協定（方向已確認）

- 已確認 D-51：連續範圍替換、Manifest 註冊／User 選服務、可無參數表單、Image 由平台部署／每 System 獨立實例與儲存綁定、External 固定資料空間、不加 data_space_id；含 Indexing 要相容 Retrieval。
- 尚待核定：Manifest／Deployment Descriptor Meta-schema、服務識別／版本及目錄包裝、範圍選擇與成對綁定欄位、邊界批次／部分失敗包裝、啟動設定檔及 per-call 參數協定；不另造三份共用資料型別、不變更 QueryContext／Rerank Contract。
- 部署／維運細節：控制器與管理 API、更新／停止／刪除／失敗回收、儲存保留、服務健康與配置版本查核；沿用 Q-008～Q-010／Q-017／Q-020／Q-021 的重試、冪等與狀態決策，不以一般 HTTP 重試保證 Indexing 可安全重送。
- 負責角色：Platform／Engine／Backend／Frontend Developer、Remote Developer 與部署管理者。
- 分階段：M0 核定宣告與協定；M1～M2 編譯／Adapter／範圍驗證；M3 目錄與管理整合；M5 UI／DEV 部署；M7 Remote Image YAML 與 External 綁定交付。不改 M0～M7 原有順序，不聲稱本輪已完成這些能力。
- 驗收：依 18 §7 及 UIB-016，包括只呼叫一次、輸出語意、索引讀寫配對、固定服務無表單、實例／儲存隔離及 Export 差異。
- 狀態：產品方向已確認，精確格式及控制介面 OPEN；主責文件 [18](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/18_remote_service_pipeline_integration.md)。

## 7. 優先討論順序

2026-11-05 更新：Ingestion／Query 的業務資料、共用 Flow、Runtime API 主線與限制已經收斂；完整 OpenAPI 仍須整理，但不再把已確認的單一 List、記憶體狀態、Basic、無 Query 讀寫鎖等重新列為待選。以下為建議討論順序，不是新增已定案的技術選擇或變更 M0～M7：

| 建議順序 | 主題／Q-ID | 這輪需要收斂什麼 | 建議產出 |
|---|---|---|---|
| 1 | 最小完整 System Config 與環境綁定／Q-002、Q-015 | component_id／版本／parameters／服務引用如何放在 D，E 如何提供連線及 Runtime 設定；不把完整 Descriptor 複製進 Config | 一份可人工閱讀的 Local Memory Config，及切換 Remote Parser 的對照；機器 Schema 再按核定內容產出 |
| 2 | Developer 交付 Descriptor／Service Manifest／Q-022、Q-028 | Local／Remote Image／External 必填資訊、連續多 Module 涵蓋範圍、可調參數及部署宣告 | 最小 Descriptor／Manifest 格式與各模式交付清單；動態 UI Meta-schema 另案，不視為已凍結 |
| 3 | Component SDK／Context 與資源生命週期／Q-002、Q-017、Q-020 | B 的 run(input, config, context)、初始化／關閉、Resolver 取得正確 System Client／IndexBinding、有狀態實例的作用範圍 | 一組 Local Parser／Remote Adapter 的 SDK 示意與契約驗收；不為每個 System 組裝專屬 Flow |
| 4 | 資料更新／索引讀寫與恢復／Q-007～Q-015 | revision 生成／衝突、失敗清理與 Remote unknown、ES／Local 格式、MongoDB 恢復、Filter／融合的可驗算規則 | backend 更新／清理與管理操作的具體約定；沿用完整覆寫、不續跑、無查詢讀寫鎖等已確認方向 |
| 5 | 最小可執行技術與驗收基線／Q-001、Q-003、Q-004、Q-011、Q-026 | 具體框架／套件版本、可實測模型 API、Tokenizer／搜尋實作與測資；既有 M1 範圍不重新擴張 | Structured JSON／Recursive／Dense／Local Memory 的真實 ingest→query，以及成功、失敗與多 System 隔離驗收 |

優先用第 1 項完整 Config 驗證第 2～3 項是否足夠串接，再依 M1／M2 所需的第 4～5 項收斂。Builder 管理 API／動態 UI、AI 助手與 Export／部署仍依既有 M4～M7 階段補齊；Builder 登入繼續延後。技術與驗收基線可平行準備，不要求等整張待決清單全部關閉才開始受限的 M1 開發。

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

目前可審閱的交付為 03～23 的現行規格／討論稿、共用 JSON Schema、契約資料／參考驗證器、模擬 Prototype 及架構圖。三份 Ingestion 資料以 13～15 為準；Inference 的 ResultItem 引用共用 Chunk。

- 資料驗證：examples/parsed_document、examples/chunk 與 examples/inference；完整限制與執行方式見 14／15。
- Parser 對照：現行映射與驗收界線見 14 §5；舊版供應者對照／試驗保存在 history/superseded，不等同目前契約的完整 Parser 驗收。範例通過不表示已交付 Engine Component。
- Prototype v0.12：現行原型完成／提案／後端待辦以 10 §1～7 為準。不可再把 UIB-001～013 全列未實作；多項已完成模擬，UIB-007／008 仍未核定，UIB-021～023 等累積項仍待改 UI／正式整合。
- 優先決策：正式共用契約／SDK、模型與 Tokenizer、ID／更新／發布政策，再按 M0～M7 推進。D-53 的 Chunk 後模板組合與額外原文 Chunk 已確認需求，尚待實作及凍結具體設定格式，見 15 §9。

歷史決策來源、過時提案、驗證及校對過程集中於 [history/](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/history/README.md)，包括 D-01～D-66 的來源與演變。Q-001～Q-028 及 SC-01～SC-10 仍是現行待決／討論項目；文件歸檔不代表功能驗收完成。
