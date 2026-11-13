# 開發計畫、決策登錄與驗收

## 閱讀目錄

- [1. 使用方式與狀態](#1-使用方式與狀態)
- [2. 文件責任與建議閱讀順序](#2-文件責任與建議閱讀順序)
- [3. 已確認方向與保留基線](#3-已確認方向與保留基線)
- [4. 開發階段與驗收](#4-開發階段與驗收)
- [5. 驗收材料與完成定義](#5-驗收材料與完成定義)
- [6. 待討論與決策登錄](#6-待討論與決策登錄)
- [7. 優先討論順序](#7-優先討論順序)
- [8. Coding agent 任務模板與紀錄](#8-coding-agent-任務模板與紀錄)
- [9. 目前交付狀態與下一步](#9-目前交付狀態與下一步)


> 文件同步：2026-11-05 · 開發規格草案（正式 SDK／Config 尚未凍結）
>
> 目的：讓 coding agent 依同一套規格分階段開發，並持續記錄尚不清楚的問題。本文是決策／待決狀態的權威位置；它不把技術建議自動轉成使用者已核可決策。

<a id="user-remote-api-decision"></a>
## 2026-11-11 已確認：User Remote API、單一 Document、Admin 模板

- User 直接設定外部 API。Admin 管理全域模板版本，Builder 只提供選用，套用時複製至草稿。平台團隊維護內建方法與 Schema 描述。
- 共用資料物件定名為 `Document`。Ingestion 以非空 `documents` 與選填批次 `parameters` 接收，Parser 前拆成逐文件工作。檢索候選放在 `ResultItem.data`。
- Remote Retrieval 的候選遵守 Ingestion 設定推導的有效 System Document Schema。外部資料可直接查詢，無須執行平台 Ingestion 或建立平台索引。
- Remote 認證設定支援固定 Secret reference 或參數引用，由 Runtime 在呼叫前解析後注入 Header。

- Component Descriptor 與發布的 System Config 用 `component_id`／`component_version` 固定元件版本。節點由 Component ID 選擇格式，`remote_api` 為平台保留的共用 Adapter，外部服務由 `service_ref` 選擇。

取代 D-40／51 的 Developer 交付、Manifest 目錄與 Remote Image 流程，更新 D-47～49 的外層資料形狀、D-54 的候選資料鍵、D-58 的 Request 封裝及 D-67 的規格來源。保留 D-67 的內建 Schema 細化能力和 D-58 的單端點、整批預檢及逐文件工作。舊來源見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。

## 2026-11-12 已確認：Inference 結果處理

- 同 Query 多路融合與當步 `group_by` 歸 Retrieval。每條路先取 `per_route_k`，有多路時須選 RRF 或 Sum Score，每 Query 交付一份清單。策略各自開放的參數待逐 Component 定義。Rerank 在模型重新排序後做自己的分組，各步在分組後取各自的 Top N。
- 跨 Query 控制放在 Query Transformation。能產生多個 Query 時開放設定，使用者選 Retrieval 或 Rerank 完成後執行，再選融合方法、可選 `group_by` 及跨 Query Top N。
- `group_by` 可多選。開啟時預選 `document_id`，多欄用組合鍵，每組保留當時排名最高的候選。任一欄缺值時獨立保留。見[設定規格](05_system_config.md#inference-result-processing)。
- Remote 區段負責其內部的結果處理。整段 Query Transformation → Rerank 交由 Remote 時，平台驗證結果後按 Remote 排名交付。

## 2026-11-12 已確認：Chunking 來源與 Ingestion 後續議題

- 正式 Chunking 設定只選一個切分來源欄位，每個解析 Unit 使用同一欄位。可另行複製其他欄位或保留該欄原文。
- Builder 登入方式及 Ingestion 進度管控延後討論。進度呈現與工作操作（含取消）由後續規格決定。

## 2026-11-13 已確認：單一 Rewrite Component

- 內建 Query Transformation 使用 `rewrite` 支援單筆與多筆改寫，以 `count` 設定改寫數量。`none` 沿用原始問題。模型回應、重試及錯誤政策依 [Engine 規格](03_engine_and_components.md#src-04-51-query-transformation) 追蹤。

## 2026-11-13 已確認：Retrieval System 生命週期

- Builder DEV 以獨立 Runtime 承載多個 System，透過內部 API 套用、列出、查詢及卸載。單組 Config 獨立部署由 Runtime 啟動時載入，管理 API 關閉。Engine 使用共用 LangGraph 執行。
- Runtime 以 `system_id` 管理一份生效 Config，按 System 判斷管理操作與 Ingestion 是否忙碌。每個請求與已接受的文件工作固定 Config Revision。Ingestion Queue 與工作狀態採記憶體，重啟後不續跑。
- 初始化或重連時驗證索引歸屬及相容性。明確更新遇到不相容索引時先刪再建，Builder 重新匯入。明確卸載移除該 System 的受管理索引及資料。規則與 API 草案見 [Runtime 生命週期](06_runtime_api_and_deployment.md#src-07-4-systemrevision-與-engine-生命週期)。

## 2026-11-13 已確認：Elasticsearch 文件覆寫

- 本輪先以 Elasticsearch 為文件覆寫的後端。索引存取層產生內部 `write_id`，同一次寫入的 Chunk 共用此值，並以獨立 ES `_id` 保存。
- 新 Chunk 全部寫入並可搜尋後才刪舊。新版確認失敗時，清理本次 `write_id` 並保留舊資料。更新期間可短暫查到新舊 Chunk；結果不明先查核，再決定是否重送。
- `write_id` 與來源 `source_revision` 分開。ES 寫入、可見性與清理案例見 [Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。
- 覆寫以同 System 的 `document_id` 為準，`source_revision` 僅供來源追溯。Runtime 重啟後，由 Builder 重新提交原始資料，完整寫入成功後清理舊批次及中斷殘留。

## 2026-11-13 已確認：索引重建的原始資料

- Builder 保存並管理原始資料。Runtime 建好新索引並啟用 Config 後，Builder 以保存的原始資料重新提交 Ingestion。儲存方式、保留與管理流程由 Builder 後續規劃，見 [Q-016](#q-016)。重匯入後的查詢開放規則見下節。

## 2026-11-13 已確認：Inference 失敗及文件權限

- 首版 Inference 所需的 Query、搜尋路徑及節點均成功才回結果。任一最終失敗就回整次錯誤。查無命中回成功空候選。見 [Q-023](#q-023)。
- 文件／檔案級 ACL 延後討論。Runtime 依既有 System 及工具權限限制呼叫。見 [Q-006](#q-006)。

## 2026-11-13 已確認：查詢開放、CSV 替換與 Elasticsearch 驗收

- Runtime 的 Elasticsearch 索引可查且必要依賴就緒時接受 Inference，空索引回成功空候選。Builder 等初次預定資料全部匯入且可搜尋後才開放其查詢入口，後續一般新增不停止查詢。
- Builder 的 CSV 資料上傳以整批替換為語意，每列對應一份 Document，預檢後清除目標 System 的既有索引資料，再匯入全份 CSV。具體管理流程由 Builder 規劃。
- M1 首條端到端流程使用 Elasticsearch。Data Column 型別與能力另行討論。

## 2026-11-13 已確認：索引相容性指紋

- 由有效 Config 推導影響索引內容、向量與搜尋能力的設定，正規化後計算 SHA-256。ES `mappings._meta` 保存 System 歸屬、指紋及指紋規則版本。完整 Config 由 Builder 保存。見 [索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle)。

## 1. 使用方式與狀態

| 狀態 | 意義 | Agent 行為 |
|---|---|---|
| 已確認 | 目前或先前使用者對話明確採用／要求的方向 | 按規格實作；細節未決不重開需求本身 |
| 既有基線 | 本輪整理前 repository 最新文件已記錄的有效設計 | 保留，不回到舊版；遇衝突回報 |
| 建議／待決 | 有候選方案，尚未定案 | 可寫介面／測試替身，不宣稱正式行為已核可 |
| 後續 | 不在目前承諾範圍 | 未被任務指定時不自行開發 |
| 已決 | 某 Q-ID 已完成選擇並同步文件 | 填入決策欄、日期、依據及受影響文件／階段 |

架構、資料、Engine、Runtime 與 UI 手冊 的 Q-ID 連回本文件。每份文件保留自身待討論清單，完整選項／決策只維護一次。沒有核可的問題不能靠空白 TODO 或聊天記憶隱藏。

現行資料以共用 Document Schema 與資料契約手冊為準；05 為總覽，Engine、UI 與 Runtime 手冊 對齊執行、UI 與 API 邊界。Prototype 與目標規格差異用 backlog／migration 追蹤，原型測試通過不代表 Engine／API 已完成。

**2026-10-16 起的工作方式**：使用者要求後續調整先更新文件；Prototype 所需變更統一記於 [UI Backlog：UI Backlog](07_builder_ui.md#src-10-3-累積需求處理狀態)，待使用者明確要求修改 UI 再實作。文件提交不代表同步開發原型、Engine 或服務。規劃文件仍依既有要求提交目前分支。

## 2. 文件責任與建議閱讀順序

閱讀入口：[README](../README.md)。現行規格整為八份手冊，每個議題只在下表主責位置維護；純歷史／原始來源放 history/。

| 手冊 | 主責 |
|---|---|
| [架構與責任](01_architecture.md) | 名詞、產品邊界、A～E 大盤、角色、環境模式與圖面 |
| [資料契約](02_data_contracts.md) | 共用 DTO／語意、Parser 相容、IndexBinding、Python 連續範例 |
| [Engine／Component](03_engine_and_components.md) | 執行、方法、SDK、開發／發布、Local／Remote 教學 |
| [Descriptor](04_component_descriptor.md) | B 的細化／動態選項／表單、候選 Schema、DS-01～DS-13 |
| [System Config](05_system_config.md) | D 的版本、有效設定、變更影響與 SC-01～SC-10 |
| [Runtime API／部署](06_runtime_api_and_deployment.md) | 九支 API、Queue／狀態、14 項控制預設、環境與 Export |
| [Builder UI／Backlog](07_builder_ui.md) | 目標互動、v0.12 現況、UIB 待辦；修改 UI 時才實作 |
| 本文件 | 已確認基線、M0～M7、Q-001～Q-028、驗收與狀態 |

完整 DS／SC／API-D 選項表各留在主責手冊，本文件只索引，不重複保存另一份決策建議。資料 schemas/、程式範例與 Profile 均維持既有來源，不因文件搬移而更改業務格式。

## 3. 已確認方向與保留基線

現行結論集中如下；D-ID 用來追查來源，不要求閱讀歷次討論才能實作。完整原始決策表、當時提案及逐輪變更見 [歷史決策紀錄](history/decisions/decision_history.md)。公共 Contract 的精確形狀以主責文件／Schema 為準。

| 主題 | 現行結論 | 來源／主責 |
|---|---|---|
| 產品／範圍 | Retrieval-only；無 Generation，Rewrite／助手仍可用 LLM；Evaluation 保留 M6 | D-50／03、Engine／Component手冊、21 |
| 管理階層 | Workspace → System；system_id 穩定，名稱／Config Revision／document_id 分開 | D-21／D-31／D-64；03、資料契約手冊、Runtime／部署手冊、21 |
| 輸入與 Parser | documents 批次提交與共用 parameters，Parser 前逐文件拆分；內建 Parser 單選 | 2026-11-11；02、06 |
| Document | 各模組共用 Document，以有效 Schema 區分階段，切分後加 data_id | 2026-11-11；02 |
| 追溯與 metadata | _rag／來源／fingerprint／ordinal 由 Component 選擇提供；metadata 可有明確支援的處理提示 | D-52；13～17 |
| Chunk／Embedding 能力 | Fixed-size／Recursive／Header-aware 用 Token；可複製原文欄位、另留原文 Chunk；Embedding 可選模板衍生欄位，兩項新增功能預設關閉 | D-36／48／53；04、15 |
| 保存／搜尋 | 保存完整 Chunk；全文／向量／Filter 能力分開。ES 或 Local Search；Memory／MongoDB 持久化模式屬邏輯 Config，跨環境不任意切換 | D-09／10／33／39；04、資料契約手冊、19 |
| 索引交接 | 平台管理索引以單組 IndexBinding 銜接；外部 Retrieval 使用 System 候選 Schema | D-55、2026-11-11；02 |
| 推論資料 | QueryContext[]；ResultSet=key/items，ResultItem=data/選填 score | D-54、2026-11-11；02 |
| 結果處理 | 內建 Retrieval 每路取 `per_route_k`，多路以 RRF／Sum Score 融成每 Query 一份；跨 Query 在 Retrieval／Rerank 完成後 | 2026-11-12；[Engine](03_engine_and_components.md#result-processing)、[Builder](07_builder_ui.md#src-09-3-現行-ui-規劃) |
| 共用模型 | System 共用 LLM 名稱清單，Rewrite 以 llm_ref 引用；模型語意與環境連線分開 | D-13／Schema 細化手冊／30；資料契約手冊、System Config手冊 |
| I/O 宣告與細化 | 平台維護內建描述。Remote Request 由上游推導，Ingestion 輸出由 User 宣告 | D-67、2026-11-11；04 |
| 內建方法 | rag_platform 管 Builder，rag_engine 管 Engine／Runtime 與平台內建方法 | 01、03 |
| Remote 整合 | User 直連，支援單節點與連續區段；Admin 管理全域模板 | 2026-11-11；03、05 |
| Flow／Config | 共用 Flow／Executor；每次請求及已接受文件固定 Config 快照，各步獨立傳入 Component Config／Context，資源作用域另管 | D-61／62；03、Engine／Component手冊、07 |
| Config 生效／環境 | 依 System 固定生效版本並判斷忙碌；相容更新沿用索引，明確不相容更新先刪再建；獨立部署啟動時載入單一 Config | D-29／30／63／64；[Runtime 生命週期](06_runtime_api_and_deployment.md#src-07-4-systemrevision-與-engine-生命週期) |
| Ingestion 工作 | document_id 完整覆寫、逐文件結果；整批預檢才 202；文件無 partial，Run 可 partial；工作／Queue 留記憶體，重啟 unknown；進度管控及取消延後討論 | D-56～58；21、2026-11-12 |
| 讀寫／失敗 | ES 先寫新再刪舊，以 `write_id` 定位清理範圍；允許短暫混合；同文件 queued／running 拒絕重複提交；未知寫入先查核 | D-59／60；[Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)、Q-008～Q-010／Q-017 |
| 文件管理 | exists、文件摘要與 retire 讀取／管理實際儲存；摘要為 documents[]／next_cursor、document_id／source_revisions[]；retire 同步 200＋deleted 或 not_found，忙碌 409 | D-58／64／65；21 |
| API／認證 | 7 支業務＋2 支 Health；Runtime 暫採一組 Basic 帳密操作服務 API；Builder 登入延後；共用 Runtime 經可信內部 System 路由選 Config | D-60／64；07、21 |
| Runtime 控制 | 接收大小、Queue／併發、Rate／Deadline、終態狀態保存由 Admin／部署者在 E 設定；14 項初始值集中維護 | D-64；22 |
| UI／工作方式 | 單一 Create／Edit、CSV 測試、進階收合與相依卡控；需求先更新文件，UI 只在使用者要求時修改，差異記入 Backlog | D-02／Runtime 控制手冊／26／38／42；UI手冊、UI Backlog手冊 |
| 部署／開發順序 | M0～M7；M4 獨立 AI 助手、M5 Builder 整合、M6 Evaluation、M7 Export；FTEST／ENT 自行部署，Runtime 不依賴 Builder，Export 不搬資料／真實 Secret | D-18／19／37／41／51；03、Runtime／部署手冊、§4 |
| System Config 狀態 | 邏輯 Config 與環境綁定分離；機器序列化仍待凍結 | 05、Q-002 |

## 4. 開發階段與驗收

下列為 2026-10-16 確認的 **M0～M7 階段編排**；個別 Schema、版本、方法細節及執行政策仍依 Q-ID 核定。能力是同一產品分批交付，不代表把後面的已確認能力刪除。階段完成需留下可實際執行的成果；本輪只更新規劃，未將任何 Engine／服務階段標示完成。

| 階段 | 範圍／依賴 | 交付 | 驗收 |
|---|---|---|---|
| M0 契約與專案基礎 | 先定 Q-001／Q-002；未決問題可獨立起草 | 版本鎖、程式結構、Pydantic／JSON Schema、完整範例及錯誤例 | 從乾淨環境可安裝；範例通過 Schema，錯誤可定位；無需 Builder |
| M1 最小獨立 Engine | Structured JSON／Recursive／Dense／Elasticsearch／Query；依賴模型、Token、ES 版本、索引與失敗政策 | 可直接 Python／CLI 操作的 Engine；真實 Elasticsearch 索引存取與隔離測試替身 | 真實 ES ingest→query；空索引回成功空候選；命中可對回來源；重啟後接回相容索引 |
| M2 Engine 方法與能力擴充 | Fixed-size／Header-aware 單欄位切分、BM25／融合、單筆／多筆 Rewrite、Rerank、ES 進階搜尋；Parser 依 Q-005，Fusion Plan 依 Q-014 分批 | Remote Adapter／Registry、方法／合併時點配置、各模式範例與契約測試 | Fixed-size 邊界可重現；ES Filter／融合可驗算；設定改變真實路徑 |
| M3 Runtime API | 包裝已可用 Engine；定 API／工作／認證／併發 | OpenAPI、Runtime 服務、Job Store 政策、SDK／cURL 範例 | SDK／HTTP 相容；202 可查結果；失敗／重送／重啟行為有證據 |
| M4 獨立 AI 設定助手 | 使用 M0～M2 的 Schema／Registry／Validator，提供不依賴 Builder 的 Python／API 入口；Q-024 | 真實助手核心、需求／樣本輸入、Config 草稿／Diff／缺少設定與可定位驗證結果 | 不開 Builder 可取得支援範圍內的 Config；具備所需設定者由驗收腳本透過 Engine／Runtime 跑通；資訊不足明列缺項，不造方法／憑證或自動 Ingestion |
| M5 Builder 前後端與 AI 助手整合 | 管理儲存、Create／Edit、CSV／Schema、漸進式 UI，串接同一 Runtime 與 M4 助手 | 正式 Frontend／Backend、System／Revision／Binding、UI 草稿與建議 Diff／套用流程 | UI 可建立／匯入／查詢，驗證初次匯入的查詢開放與 CSV 整批替換；助手讀取當前草稿及樣本，建議與控制項正確對應；過期建議不覆蓋人工修改，取消不改 Config，變更影響及版本衝突正確 |
| M6 Evaluation | Q-018；Dataset／Runner／指標／報告與版本追蹤 | 可由 SDK／API 及 Builder 使用的評估流程、逐題結果與報告 | 固定測資可重現計算依據；缺標註不造分；報告綁 Config／資料／模型版本，可比較配置差異 |
| M7 獨立部署交付 | Q-021／Q-027；核心 Runtime 已真實可用，完成目標環境交付 | Runtime Image 版本／Digest、FTEST／ENT Bundle、部署／Secret／資料準備與運維說明 | 新環境無 Builder 可用 YAML 啟動；API Ingest→Query；外部依賴故障可定位；不含測試資料與憑證 |

M1 先驗結構化 Document → 直傳 Parsing → Recursive → Embedding → Elasticsearch Index → Retrieval。Fixed-size 與其他方法於 M2 擴充。Local Memory、FAISS 與 MongoDB 的交付階段另議。

Image 建置可在 M3 開始；M7 驗收的是可獨立部署的完整交付，不要求每個 Retrieval System 各建一個 Image。匯出通常引用支援該 Config 的 Runtime Image 版本／Digest，另外交付 Config 與部署設定。M6 的評估純邏輯可在 M1／M2 先做，但不能把早期模組測試當作 M6 整體評估已完成。

2026-10-28 D-41 補充：M0 規劃兩個 repo 及套件邊界；M1～M3 的 Engine／Components／Runtime API 在 rag_engine 開發，M5 Builder 在 rag_platform 開發。M4 獨立助手核心的目錄建議置於 rag_engine，保留無 Builder 的 Python／API 入口，M5 另做 UI 整合；實際包裝見 [Runtime API／部署](06_runtime_api_and_deployment.md#src-07-3-平台管理資料與儲存)。M7 交付由 rag_engine 建置的完整 Runtime Image，不要求另一個 Components repo 進行 Image 二次組裝。階段順序與已確認功能範圍維持不變。

### 4.1 階段決策 Gate

| 開始的工作 | 必須先明確的問題 | 尚可先做 |
|---|---|---|
| 正式契約／公開 SDK | Q-001／Q-002 | 需求整理、Schema 候選、型別範例 |
| 真實 Token／Embedding／搜尋 | Q-003／Q-004／Q-011；安全最小範圍 Q-006 | Fake Adapter、欄位映射與純函式 |
| 對既存文件更新／partial 寫入 | Q-007／Q-008／Q-009／Q-010 | 純新增、不重複 ID 的受限流程及明確拒絕 |
| 其他儲存後端的恢復（後續） | Q-012／Q-015 | Store 介面與小型 Manifest 草案 |
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

### 4.3 Remote API 與模板驗收

M0 凍結 Document、批次 Request、Remote I/O、有效參數與候選規則。M1～M2 驗證有效設定、單節點與連續範圍執行。M3 驗證 Runtime 逐文件工作與認證。M5 驗證 Builder 顯示契約及 Admin 模板唯讀選用。M7 驗證外部服務綁定可在獨立 Runtime 使用。

## 5. 驗收材料與完成定義

### 5.1 必備材料（在開發階段建立，並非本輪已存在）

| 材料 | 最小內容 |
|---|---|
| examples/configs | 首版 ES 配置及必要服務／Secret 設定說明 |
| fixtures | CSV 映射／各階段 Document、已知文字與標題、Fixed-size 的零 overlap／短文／整塊／末塊、Unicode／長文字、合法／無效欄位、同 ID 更新與 Filter 測資 |
| retrieval fixtures | 固定小向量／詞項與人工路徑排名，可計算 Top-K／RRF／Sum Score／去重 |
| provider fakes | 合法回應、Timeout、429、缺項、錯誤維度、非法 Rerank index、未知引用 |
| usage examples | 直接 Engine、HTTP、CSV 映射、工作輪詢、部署後首次 Ingestion |
| assistant cases | M4 無 Builder 的新建／修改 Config、缺服務／未知方法；M5 的同一建議與 UI 控制項對照、Diff／取消／過期草稿案例 |
| component package cases | rag_engine components 的 package 在乾淨環境安裝、單一 Component／整合測試、衝突／錯版／能力不足案例、完整 Runtime Image Component 清單與 Builder 契約測試；詳見 Engine／Component 開發手冊 |
| component schema／UI cases | 12 的 SUI-01～14；Schema／Python 設定一致、動態選項、相依失效與不適用分支、未知必要控制項、多實例定位、版本過期、UI／AI／Python／HTTP 同規則 |
| env／commands | 不含 Secret 的環境範例；安裝、測試、啟動與 integration 指令 |

資料契約手冊 與 schemas/ 提供可驗證資料；[System Config](05_system_config.md#設定位置) 對照設定責任。完整 Engine Config／部署設定及 SDK 仍待 Q-002 核定，不能把參考切分 spec 當成完整可執行 Config。

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
- 2026-10-28 已確認 D-41：rag_platform 管理 Builder，rag_engine 集中 SDK／Engine／Components／Runtime API。仍待定的是 repo 內可獨立安裝的套件名稱／精確目錄、Python／SDK／Engine 相容矩陣與建置工具；目錄草案見 Runtime API／部署手冊／Component 開發手冊，發布政策見 Q-022，不能再將 repo 邊界列為未決。
- 建議：沿用 Python／既有生態；選最小必要套件並鎖定。Web Framework／前端沿用部門標準；具體版本要實測再鎖。
- 替代：以專案獨立技術棧開發，需增加維運／整合評估。
- 負責角色：技術負責人＋Engine／前後端；阻擋 M0 正式依賴及 M1 ES 選型。
- 決策：未定；更新 架構／Engine 手冊／Runtime／部署手冊 及 dependency lock。

<a id="q-002"></a>
### Q-002 共用 Schema、Config、SDK 與版本凍結

- 平台內部描述規則沿用 D-67 的相依推導，精確 Meta-schema 待核定。舊例見歷史索引。

- 已確認：邏輯 Config 與部署設定分離，正式名稱不使用 Blueprint；Workspace → System；Local Search 持久化模式隨 Config 跨環境固定（D-33）；全部 Document.structdata／metadata 保存與合法 metadata 全繼承（D-39）。不清楚的是 05 建議拼字／枚舉／Default／nullable、array 型別、錯誤 Envelope、SDK、多 Profile；QueryContext[]／ResultSet 業務欄位已依 D-54 確認。仍待核定的是舊保存／繼承投影、原型短名稱／匯出標籤 migration。
- D-62 已確認選項 B（共用 Flow）：共用 Flow／Executor，依固定 Config 快照在各 Module 選 Component，並傳入 input／本次 config／Context；不強制所有實例共用。精確 SDK 簽名及 Resolver／資源作用域仍待凍結。
- 2026-10-28 補充：Component SDK 的 Module-specific I/O 包裝、run／初始化／釋放簽名、RunContext、Registry／Factory 與 Config Schema 介面待凍結；Registry 草案改稱 component_id，不直接改寫既有 Config。精確方法／版本引用、舊 module_id 別名與遷移須一致驗證；11 的 Python 程式只作介面示意。
- [System Config：System Config 討論稿](05_system_config.md#草稿有效設定與部署) 依 D-67 取消頂層 document_schema，資料細節由 B／C＋D 提供；首版六類宣告與相依推導見 [Descriptor](04_component_descriptor.md)。規則語法／SDK／解析 API 仍待凍結；D-66 舊機器稿及五案例已歸 [歷史快照](history/superseded/system_config_d66/README.md)，不作新功能驗收。前輪校對過程見 [歷史報告](history/reviews/2026-11-05_spec_alignment_review.md)。
- 建議：先核定最小完整 Config＋單一公開 Engine interface；Pydantic 匯出 JSON Schema，UI 使用相同來源。用完整欄位路徑；未知別名拒絕。
- 替代：直接沿用 Prototype 全部短名稱；需補齊其缺少型別與執行語意。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 契約凍結。
- 決策：未定；更新 Engine／資料契約手冊／Runtime／部署手冊、Schema 及完整範例。

#### Document 與共用契約

現行邊界見 [Document](02_data_contracts.md) 與 [JSON Schema](../schemas/README.md)。Python Runtime 型別封裝與正式 Config 語法仍待核定。原型與離線測試用於契約驗證，真實 Parser、Tokenizer、模型與 DB 另做整合驗收。

<a id="q-003"></a>
### Q-003 模型服務與 Adapter 契約

- 不清楚：首組模型、Profile／版本辨識、Tokenizer 取得、Chat 角色／輸出格式、多 Query 解析、Rerank 服務限制。
- 模型契約草案：Rewrite 採固定 queries 結構，依 count 驗證筆數、Provider Structured Output／Tool／文字解析能力分級、模組 Schema 與共用 LLM Adapter 分工；格式與語意都由後端重驗。細節見 [Engine／Component 開發](03_engine_and_components.md#src-04-511-討論提案rewrite-的結構化輸出與共用-llm-邊界)，不因寫入提案就凍結 Provider 或重試／fallback 預設。
- Rewrite 的 count=1／N、Schema 輸出約束提案保留（[Engine／Component 開發](03_engine_and_components.md#src-04-51-query-transformation)）；Generation 及其答案格式提案由 D-50 撤銷。
- 既有方向：Embedding API、System Rewrite／助手共用 LLM 的 OpenAI-compatible API、平台約定 Rerank API；原型格式基線為 embeddings／Chat Completions／04 的 rerank。原型基線不等於所有 Provider 相容性都已核定。
- 建議：先選一組可實測的 Adapter／服務及 Profile，各有 Fake 與真實契約測試；不同格式顯式 Adapter。
- 替代：第一期支援多 Provider 格式，增加測試矩陣。
- 負責角色：Engine＋模型服務提供方；阻擋 M1 真實服務。
- 決策：未定；更新 Engine／資料契約手冊／Runtime／部署手冊。

<a id="q-004"></a>
### Q-004 Token 計量、切分邊界與溢位

- 已確認：Fixed-size／Recursive／Header-aware 均用 Token 計量；Fixed-size 固定視窗、不依標題／分隔符切分。待定：Token 計數版本、prefix／特殊 Token、Unicode 安全邊界／原文 offsets、重新編碼計數、單塊超長與複製欄位、overlap／fallback、Tokenizer 離線檔案。
- 建議：固定 Tokenizer／revision，以實際模型輸入檢查；超限回可定位錯誤，截斷需明示。
- 替代：自動切分／截斷，需定義來源與警告語意。
- 負責角色：Engine；阻擋 M1 Token／模型上限驗收。
- 決策：未定；更新 Engine／資料契約手冊、Unicode／長文字 fixtures。

<a id="q-005"></a>
### Q-005 Parser／OCR 首批格式

- 不清楚：PDF／PPTX／圖片／TXT／MD 哪些第一期支援；套件／外部 OCR、表格／標題 Schema、加密／損壞處理。
- 關聯待決：現行 Units 契約的正式版本凍結、Parser 正規化及文字格式能力細節見 [Q-002 子項](#document-與共用契約)；不恢復已移除的 structure 型別或結構路由。
- 建議：M1 先 Structured JSON，Native text 及其他格式逐一有測資才開放；OCR 服務另驗證。
- 替代：第一期納入全部格式，需增加品質／成本驗收。
- 負責角色：產品＋Engine；阻擋 M2 格式能力，不卡 M1 Structured JSON。
- 決策：未定；更新 架構手冊／Engine／資料契約手冊／UI手冊／Runtime／部署手冊。

<a id="q-006"></a>
### Q-006 metadata 保留區、租戶與授權

- D-60：Builder 登入方式延後；Runtime API 暫採一組 HTTP Basic 帳密操作該服務全部 API，首期不做多角色／逐 API 授權，部署採 HTTPS／Secret 引用。D-64 已選可信 Backend 的內部 System 路由；具體部署保護／Secret 注入與 metadata 保留區仍 OPEN。

- 已確認：文件／檔案級 ACL 延後。第一版依 System 的執行範圍隔離資料，MCP API key 授權到 System 與工具。
- 仍待：平台保留欄位名稱、Workspace 權限、Builder 登入與 Gateway 接線、獨立 Runtime 認證設定。
- 負責角色：平台／身分團隊＋Backend＋Engine。
- 決策狀態：首版文件存取範圍已確認，其他授權與保留欄位細節另議。

<a id="q-007"></a>
### Q-007 文件／Chunk ID 與 source_revision

- 2026-11-03 D-52：必要 data_id 仍須有效／清單內唯一，但不強制由 fingerprint／ordinal 計算，也不強制將計算資訊寫入 _rag。SDK helper 可選用；穩定／更新語意按實作及此 Q-ID 核定。
- 2026-10-30 D-47：已同意可重現 ID 方向；[資料契約](02_data_contracts.md#data-flow)～6 提供有效切分計畫 fingerprint＋文件內全域 ordinal 的 Python 參考演算法。仍待省略 revision 的生成、檔案拆多文件、CSV 整批替換的 ID 生成、跨語言 canonicalization 與正式遷移。
- D-65 確認文件摘要清單回 document_id＋source_revisions[]，彙整實際儲存 Chunk 的版本。覆寫以 `document_id` 為準，接受相同 `source_revision` 帶入新內容；來源版本僅供追溯。
- 建議：跨批更新要求穩定 document_id，內容版本與 Config 分開；採明確可重現的衍生 ID 規則。
- 替代：每批當新文件；需接受無法自然更新與重複資料後果。
- 負責角色：Engine＋資料／產品；阻擋 M1 正式 ID 規範及 M2 更新。
- 決策：未定；更新 Engine／資料契約手冊／UI手冊／Runtime／部署手冊。

<a id="q-008"></a>
### Q-008 重送、更新與刪除

- D-56 已確認：同 (System, document_id) 完整覆寫，不存在則新增；成功後清除舊文件不再產出的 Chunk，不做欄位 merge。同文件 queued／running 時拒絕重複提交，終態後可重新提交；Runtime 重啟不恢復工作。
- 已確認：ES 以 `write_id` 保存新舊批次，新版全部可搜尋後刪除舊批次。確認寫入失敗時僅清理本次批次。見 [Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。
- 已確認：`source_revision` 不作版本衝突或新舊順序判斷。Runtime 重啟後的復原由 Builder 重送整份文件觸發。仍待相同內容是否可 no-op、跨請求 Idempotency-Key、確認先前 ES 寫入已結束的方式，以及 Builder 識別需重送的文件。整批預檢與逐文件結果沿用 D-57；文件管理與 retire 沿用 D-58。精確錯誤協定、Ingestion 進度管控與取消另議。
- 建議：先不承諾 exactly-once 或未知寫入自動重試，按文件發布與相容機制實作；文件刪除另外定義。
- 負責角色：產品＋Engine＋Backend；阻擋安全重試／正式更新實作。
- 決策狀態：覆寫單位與忙碌拒絕方向已確認，以上其餘細節 OPEN；更新 Engine／資料契約手冊／Runtime／部署手冊／Runtime API手冊。

<a id="q-009"></a>
### Q-009 部分失敗與提交原子性

- D-56 已確認：以 document_id 為更新與成功／失敗單位；Batch 逐文件獨立結果，不要求全 Batch 回滾；文件完整執行成功才標 completed，不接受半份文件為成功；D-60 不加 Query 讀寫鎖，允許更新期間短暫讀不一致，失敗清理／保留舊版機制仍需 backend 落實。
- ES 在新版全數可搜尋及舊批次清理後標文件 `completed`。更新與清理期間可查到新舊混合。重啟後由 Builder 重送整份文件並依正常覆寫流程清理殘留。逾時後的查核及精確錯誤碼仍待定，非 ES 後端的提交行為另議。Run partial／文件無 partial 依 API-D01／02。
- 負責角色：Engine＋Backend；阻擋 M2 更新與 M3 終態／提交驗收。
- 決策狀態：文件級原則已確認，實作與精確 Envelope OPEN；更新 Engine／資料契約手冊／Runtime／部署手冊／Runtime API手冊。

<a id="q-010"></a>
### Q-010 Ingestion／Query 併發與發布

- D-56 已確認：每 System 文件併發可配置、預設 1；不同文件可依上限並行，同 document_id queued／running 時拒絕重複提交。文件完成後完整替換，失敗不得冒充成功；D-60 放寬更新中的讀原子性，不加平台 Query 讀寫鎖。
- D-60 已確認讀寫各自進行，不因寫入阻擋 Query、不加共享讀寫鎖或原子快照；同文件重複提交忙碌拒絕保留。
- D-61～D-63：Builder DEV 使用共用 Runtime 與 LangGraph。每次執行固定 Config 快照，更新須等該 System 已接受的 Ingestion 完成。相容更新讓舊查詢跑完；索引重建與卸載須先排空。見 [Runtime 生命週期](06_runtime_api_and_deployment.md#src-07-4-systemrevision-與-engine-生命週期)。
- 仍待：未知 Remote 操作、實體後端寫入可見性、失敗清理及跨重啟的生命週期失敗處理。
- 第一版採已確認的無 Query 讀寫鎖策略；索引版本快照／零停機世代切換不是首期新增需求。
- 負責角色：Engine＋Backend；阻擋 M2／M3 併發正式行為。
- 決策：未定；更新 Engine／資料契約手冊／UI手冊／Runtime／部署手冊。

<a id="q-011"></a>
### Q-011 Elasticsearch／BM25 與分數定義

- 首版以 Elasticsearch 為準。待定：向量 similarity、分數轉換、中文 analyzer 與 BM25 參數。FAISS 相關選型後續討論。
- 建議：先用可精確驗算的小規模索引作基準，再評估 ANN；全文逐欄位建索引並固定斷詞。
- 替代：直接 ANN，需先定 Recall／容量目標。
- 負責角色：Engine；阻擋 M1 搜尋語意及 M2 效能優化。
- 決策：未定；更新 Engine／資料契約手冊、測試小向量與詞項資料。

<a id="q-012"></a>
### Q-012 MongoDB Manifest 與恢復

- 不清楚：Collection／Manifest 形狀、索引版本、完整性／Profile 驗證、DB 中斷、恢復期間讀寫。
- 建議：保存完整 Chunk／vectors 及可驗證的設定／資料版本；重建完成才發布 Local Index。
- 替代：另保存 FAISS 檔案與快照，增加檔案版本及同步機制。
- 負責角色：Engine＋Backend／DB；MongoDB 恢復的交付階段另議。
- 決策：未定；更新 Engine／資料契約手冊／Runtime／部署手冊。

<a id="q-013"></a>
### Q-013 精確 Filter 的候選與缺值語意

- 不清楚：缺欄位／null／多值如何匹配；FAISS 合法候選搜尋策略、ES Mapping 相容矩陣。
- 建議：以宣告型別檢查 eq／in，各路取 Top-K 前套用業務過濾；用有／無命中與缺值測資驗證。
- 替代：未具備可靠 pre-filter 的組合先停用，不能偷偷 post-filter。
- 負責角色：Engine；阻擋 M2 過濾驗收。
- 決策：未定；更新 Engine／資料契約手冊／Runtime／部署手冊。

<a id="q-014"></a>
### Q-014 融合計畫、合併時點與分組細節

- 已確認：內建 Retrieval 先依 `per_route_k` 限制每 Query／每路，多路時須以所選 RRF 或 Sum Score 融合，每 Query 交付一份。跨 Query 可選 Retrieval 或 Rerank 完成後，並可再分組及截斷。
- 已確認：融合以 `data_id` 對齊。分組可選多個候選 Document 單值欄位，每組留目前排名最高的候選。開啟時預選 `document_id`。Rerank=None 時仍可執行後置跨 Query 規則。
- 待實作與驗收：逐 Component 參數（含 RRF／Sum Score 各自開放的參數與預設值）、正式 Config 序列化與動態候選欄位來源。需用人工可驗算資料驗證 RRF／Sum Score、分數可比性、同分順序、ES／Local Search Adapter 與完整 Remote 邊界。
- 決策：2026-11-12 確認流程與 UI 責任，可開始逐 Component 參數設計。真實資料與服務的整合驗收留在 M2。

<a id="q-015"></a>
### Q-015 Revision、有效 Config Hash 與 Index 版本

- 已確認：同一 System 的同版邏輯 Config 跨環境相同，部署設定分開；文件 source_revision 與 index_generation 概念分開。不清楚的是保存／生效時點、Hash、草稿衝突、CSV mapping 歸屬、環境部署識別／資料版本及快照切換。
- 2026-10-28 補充：需定 Component／package／Engine 解析版本保存位置、如何納入可重現執行與相容判定、更新 Component 後的重測／重建與回復政策；新版發布不自動升級既有 System，僅看版本號不能判定索引相容。
- 已確認：Runtime 從會影響索引的有效設定推導並正規化後計算 SHA-256，與實際 mapping／Profile 一併驗證。ES 將 System 歸屬、指紋及指紋規則版本存入 `mappings._meta`。精確輸入欄位、序列化及規則升版處理仍待定。
- 建議：分開保存版本與執行綁定；Hash 只納有效配置並保留有語意順序，使用樂觀版本檢查。
- 替代：單一 active revision，改配置後阻擋到準備完成；仍須避免 lost update。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 Hash 凍結及 M5 版本操作。
- 決策狀態：索引指紋的用途與計算方向已確認，其餘版本管理細節仍待定。

<a id="q-016"></a>
### Q-016 平台儲存、原始資料與保留

- 已確認：Builder 保存及管理原始檔與結構化來源資料，供受管理 System 索引重建後重新匯入。Runtime 負責索引與 Ingestion 執行。
- 仍待：Builder 的儲存後端、來源版本、權限、保留／刪除與重匯入流程。Config／Run／Dataset／Report 的管理資料庫、解析結果與 Trace 原文的保留政策，以及獨立 Runtime 儲存另議。
- 建議：管理資料與搜尋 Chunk Store 分離；可用 Store interface 分環境替換；只保存明確必要資料。
- 替代：統一平台 DB／Object Store；獨立 Runtime 的外部依賴與成本需交代。
- 負責角色：Backend＋平台／資料負責人；阻擋 M3／M5 正式持久化與資料政策。
- 決策狀態：Builder 原始資料管理責任已確認，具體方案待 Builder 規劃。

<a id="q-017"></a>
### Q-017 Timeout、重試、取消與工作恢復

- D-56 已確認：Runtime 共用有上限 Queue；工作／文件狀態放記憶體，重啟不保留／恢復，不保存斷點續跑。查不到紀錄為 unknown，不等於文件未寫入；終態紀錄可以限量／限時清理，活躍紀錄不提前清除。
- D-64 已確認 Runtime 整體 Deadline／狀態保存初始值與管理方式，集中見 Runtime API／部署手冊；A 的成功／錯誤核心欄位已確認。仍待模組／Client Timeout、有限重試／可重試錯誤、中斷及未知遠端副作用處理、正式 Schema／載入方式。Ingestion 進度管控與取消延後討論。
- 建議：Engine 統一執行預算；不自動重試未確認的寫入，重試完整文件且需冪等支援。持久 Queue／自動恢復不屬第一版已確認需求。
- 負責角色：Engine＋Runtime；阻擋 M1 錯誤政策及 M3 工作語意。
- 決策狀態：無恢復與記憶體狀態方向已確認，其餘 OPEN；更新 Engine／資料契約手冊／Runtime／部署手冊／Runtime API手冊。

<a id="q-018"></a>
### Q-018 Evaluation 範圍與 Gate

- 不清楚：首批指標、Dataset／Ground Truth 格式、Judge／Rubric、Chunk／Document 層級、Rerank 前後、公開檢索 Target、Gate 門檻。
- 已移除答案正確性／Faithfulness 與自訂答案 JSON 的驗收；Evaluation 聚焦檢索排名、延遲、Usage／錯誤。
- 建議：先有可驗算的 Retrieval 指標與操作指標，再加明示 Judge；缺資料拒絕或 skipped。
- 替代：先 End-to-end Judge；不得冒充有可靠 Retrieval Ground Truth。
- 負責角色：產品／資料＋Engine＋Backend；阻擋 M6 正式評估／Gate，不卡 Query 主線。
- 決策：未定；更新 架構／Engine 手冊／UI手冊／Runtime／部署手冊。

<a id="q-019"></a>
### Q-019 API／HTTP Envelope 與呼叫認證

- D-60：Runtime API 暫採 HTTP Basic Auth，一組帳密可操作該 service 全部對外 API（含對外 Health），不做首期角色／逐 API 授權；Builder 登入延後。OpenAPI Security Scheme、驗證位置、Secret／Probe 配置與內部路由的具體部署保護仍待細化，不另加匿名 API 例外。

- Ingestion 使用單一批次端點與逐文件工作，工作狀態、文件管理及認證見 [Runtime API](06_runtime_api_and_deployment.md)。

- 仍待：完整 CRUD／助手／管理 API、OpenAPI／完整錯誤碼、檔案 manifest、冪等鍵、內部路由的部署保護、Header／認證接線及暴露 Trace。D-64 已確認核心回應／錯誤、retire 結果、System 路由方向與 22 的初始限制，不再把這些全部視為未決。
- D-41 補充：Builder 與 Runtime 透過 API／Component 目錄合作；需核定目標 Runtime 版本識別、Config Schema／能力目錄、完整 Config 驗證、快取失效與接口相容政策。能力範圍見 [Runtime API／部署](06_runtime_api_and_deployment.md#src-07-58-runtime-component-目錄與-config-驗證邊界)，精確端點與 Envelope 仍 OPEN。
- D-42 已按建議規劃描述／Context／選項及驗證關聯值，候選格式見 Descriptor手冊；精確路徑、認證、版本識別與公開 Meta-schema 仍 OPEN，不影響既有 Ingest／Query 範例。
- Query API 成功 body 直接回傳 QueryContext[]，只保留目前 key／items／score；排名以陣列順序表示。request／版本進 Headers／Logs；精確 HTTP 版本協商及錯誤待核定。
- D-64 已確認 retire 同步 200＋deleted／not_found、忙碌 409，狀態／錯誤核心欄位與可信內部 System 路由；後續 D-65 已確認 documents[]＋next_cursor 的摘要形式及 source_revisions[]；精確分頁參數／cursor、完整 OpenAPI、Backend 管理 API 與部署保護仍 OPEN；HTTP 與領域錯誤分層。
- 替代：沿用既有企業 API 規範並明確映射。
- 負責角色：Backend＋Runtime＋Frontend／身分團隊；阻擋 M3 Runtime／M4 助手 API／M5 Builder 真實串接。
- 決策：未定；更新 資料、UI 與 Runtime 手冊、OpenAPI／cURL 範例。

<a id="q-020"></a>
### Q-020 DEV 共享 Runtime 與資源隔離

- Builder DEV 共用 Runtime，外部 API 由服務提供者維運，資源隔離與配額另行驗證。

- D-56 已確認：Builder DEV／獨立 Runtime 共用 System Queue／併發與 Inference Rate／併發／Deadline；Runtime 控制總量，Builder 另管理 User／Workspace 配額。上限可配置已確認；放 E 為先前建議，D-57 暫緩管理者／存放位置／Schema 的定案。Worker 是排程概念，不要求每 System 新 Pod。
- D-61：共用 API service 啟動只綁服務／Registry 基礎設定，後續管理多份 System Config，不因每份 UI 設定新增服務；可依 Namespace／資源池分成少數共用服務，精確分組策略尚未選定。
- D-62 已選 B：共用 Flow／Executor，逐請求／已接受文件固定 Config 快照，Module 依設定解析 Component；不要求每份 Config 建立專屬 Flow。Component 實例／資源是否共用依狀態與隔離需求決定。
- 仍待：配置與 Component 快取、資源預載與釋放策略、管理 API 的正式協定、服務池分組、公平排程、正式參數 Schema、實際記憶體上限及多副本協調。Runtime 管理行為見 [生命週期](06_runtime_api_and_deployment.md#src-07-4-systemrevision-與-engine-生命週期)。
- 建議：先有受限共享 Runtime 與明確隔離 Binding；Local Search 每 System 的 Ingest／Query 必須同程序。
- 替代：每 System 獨立 Runtime，增加部署／資源管理成本。
- 負責角色：平台＋Backend／Runtime；阻擋 M5 多 System 服務。
- 決策：未定；更新 架構手冊／Runtime／部署手冊。

<a id="q-021"></a>
### Q-021 Export、FTEST／ENT 與 Secret Vault

- Export 交付 Runtime 設定、環境連線及 Secret 引用，外部服務由其提供者維運。

- 2026-10-28 D-41 確認：rag_engine 統一建置含 Engine／核可 Components／Runtime API 的完整 Image，rag_platform 建置 Builder Image；採用新版 Engine／Component 時仍需更新 Runtime，接口相容的 Builder 可維持原版。目標 Image 須包含 Config 所需 Component packages 並保存版本；Component 清單／鎖定格式與缺失錯誤仍待決，YAML 不會自動提供 Python 方法程式。建置／發布／部署範圍見 [Runtime API／部署](06_runtime_api_and_deployment.md#src-07-94-建置發布與部署的變更範圍)。

- 已確認：同版邏輯 Config 不隨環境改變，環境連線／Secret／資源為部署設定；Memory／MongoDB 模式也跨環境保持一致（D-33），不能只換部署設定切換。不清楚的是 Image／Bundle 包裝、Vault／注入、Secret 型別、K8s 資源／Ingress／Probe 及 CD 流程。
- 建議：版本鎖定 Runtime Image＋有效 Config＋環境覆寫；Local 單副本；明示未帶資料且無 Builder 依賴。
- 替代：使用單位既有 Helm／GitOps 形式；仍需相同可驗證交付內容。
- 負責角色：平台／DevOps＋Backend；阻擋 M7 正式部署交付。
- 決策：未定；更新 架構／資料契約手冊／UI手冊／Runtime／部署手冊。

<a id="q-022"></a>
### Q-022 內建方法交付與外部服務隔離

- 內建方法由平台團隊隨 Runtime 版本維護。外部實作由 User 選擇及部署，接入時遵守 Remote API 契約。
- 待核定：允許的出站目的地、資源隔離、授權與憑證範圍、租戶配額及相容版本驗收。

<a id="q-023"></a>
### Q-023 Inference 失敗、無命中與資源上限

- 已確認：首版任一必要 Query、搜尋路徑或 Rerank 等節點最終失敗，整次回可定位錯誤。全部必要操作成功但查無命中時，回成功空候選。見 [Runtime Inference](06_runtime_api_and_deployment.md#src-21-5-inference)。
- 待定：候選數與資源上限、超限錯誤及各服務的重試條件。重試另見 Q-017，部分結果與降級留待後續討論。
- 負責角色：產品＋Engine。
- 決策狀態：首版回應語意已確認，細節待實作及驗收。

<a id="q-024"></a>
### Q-024 真實 AI 設定助手

- 已確認：可不開 Builder 由 Python／API 產生或修改 Config，且必須於 Builder 中使用相同助手核心並驗收 UI 草稿操作；正式服務及 Schema 不反向依賴 Builder DB。不清楚：模型／Prompt／成本、樣本抽取與保存、結構化輸出、Diff／Patch、過期建議、選擇性套用與撤銷。
- D-41 下的目錄建議：獨立助手核心放 rag_engine，使用同一 Registry／Validator；rag_platform 負責 Builder UI／Backend 整合。此為套件配置建議，HTTP 宿主、可選依賴與 Image 包裝仍待核定，不使 FTEST／ENT Runtime 必須啟用助手。
- 建議：限制 Schema／Registry、只用明確樣本、先顯示差異並驗證；以 Draft 基準防止覆蓋人工改動。
- 替代：先保留規則助手，清楚標示 Mock；不得聲稱已由 LLM 理解資料。
- 負責角色：產品＋Engine／Contracts＋Backend／AI；M5 另含 Frontend。阻擋 M4 真實獨立助手及 M5 的助手 UI 整合，不卡手動配置。
- 決策：M4 獨立核心、M5 Builder 整合與兩階段分開驗收已於 2026-10-16 確認；模型、結構化建議／Diff、過期建議及其餘具體政策仍未定。更新 架構／資料契約手冊／UI手冊／Runtime／部署手冊／計畫手冊。

<a id="q-025"></a>
### Q-025 漸進式 UI、範本與小量試跑

- 已確認：Parsing 初始只顯示結構化 JSON，其他格式／設定全在預設關閉進階區；LLM／Prompt／範例及 API 說明要求見 [Builder UI／Backlog](07_builder_ui.md#src-06-32-已確認互動與基本進階分組)。待定的是其餘基本／進階分組、展開記憶、改動摘要、範本、真實試跑與診斷範圍。
- 2026-10-16 討論提案：在 Rewrite 旁提供不需 Ingestion 的單模組測試，使用當前草稿與相同 Engine／Adapter，顯示實際 Query 與格式驗證；是否採用及展示細節待確認，UIB-007 保持提案狀態，不擴張成所有模組都要試跑。
- UIB-008 Rewrite 設定提案保留；UIB-009 答案格式提案取消，產品名稱／結果呈現遷移見 UIB-015。
- D-41／UIB-010 補充：方法選單／設定依目標 Runtime 的目錄與 Schema，需定動態表單支援範圍、目錄更新／過期狀態及不相容 UI 提示；相容新增 Component 不要求每次重建 Builder。特殊控制項仍需前端配合，不承諾任意 Schema 均可自動呈現。
- D-42 已確認固定 Builder 流程搭配動態 Component 參數表單，以及 [Descriptor](04_component_descriptor.md) 的五項操作行為；不再把這些方向列為未決。12 提供欄位／服務選擇器、相依狀態與 SUI-01～14 草案；具體控制項樣式、支援版本與其餘範本／試跑範圍仍待核定。
- 建議：保留已確認互動，再核定其餘分組；必填錯誤可定位，保持同一 Config。試跑與範本逐項啟用。
- 替代：單獨新手／專家入口，但兩者仍需共享 Config／驗證。
- 負責角色：產品＋Frontend；阻擋 M5 正式 UX 凍結，不卡 Schema／Engine。
- 決策：既有明確互動照定案保留；其餘分組／試跑／範本未定。更新 架構手冊／UI手冊。

<a id="q-026"></a>
### Q-026 測資、環境與測試工具

- 不清楚：可使用的真實模型／ES／MongoDB、測試 Secret 供應、固定語料、CI／integration 執行條件、允許外連。
- 建議：Fake／Contract 與真實 integration 分開；測資可重現且不含敏感資訊，工具／指令正式鎖定。
- 替代：開發機手動驗證，仍需留下可重現紀錄，不能以未執行當通過。
- 負責角色：技術負責人＋開發／QA；阻擋各階段真實整合驗收。
- 決策：未定；更新 計畫手冊、環境／測試說明。

<a id="q-027"></a>
### Q-027 效能、容量、成本與觀測目標

- 不清楚：資料量、平均長度、並發、回應時間、重建啟動時間、模型成本、Trace 內容與監控工具。
- 建議：先建立可重現基準再定門檻，保留 request／run／module Trace。D-56 已確認首期記憶體 Queue，D-64 有初始限制；分散式持久 Queue／HPA 與生產容量承諾另行評估。
- 替代：先採既有企業 SLA，需驗證 Elasticsearch／模型資源是否能滿足。
- 負責角色：產品＋平台／Engine／QA；阻擋生產容量承諾與 M7 運維驗收。
- 決策：未定；更新 架構／Engine 手冊／Runtime／部署手冊／計畫手冊。

<a id="q-028"></a>
### Q-028 User Remote API 整合

- 已確認：支援連續區段、固定 HTTP 封裝、上游推導 Request、輸出欄位與向量宣告、共用 QueryContext[]、外部資料符合 System Schema。
- 待核定：正式 Config 序列化、連線驗證、逾時及重試政策、錯誤觀測與容量門檻。
- 驗收：同區段呼叫一次、無重疊、驗證失敗可定位、內建與 Remote 切換、外部 Retrieval 與下游相容、匯出可解析部署綁定。見 [Engine](03_engine_and_components.md#remote-api)。

## 決策與待辦的唯一登錄位置

| 登錄 | 數量／狀態 | 主責 |
|---|---|---|
| Q-001～Q-028 | 每項保留已確認方向與 OPEN 細節 | 本手冊 |
| DS-01～DS-13 | 平台內部描述候選，舊 DS 表見歷史 | [Descriptor 決策表](04_component_descriptor.md) |
| SC-01～SC-10 | D 的具體表示；Import 和有效設定推導 Document，舊 SC 候選見歷史 | [System Config 決策表](05_system_config.md) |
| API-D01～API-D07 | 已確認核心／待完成協定逐列保留 | [Runtime API 狀態表](06_runtime_api_and_deployment.md#src-21-72-決策狀態與剩餘討論) |
| UIB | 所有 40 個未勾選工作項保留；021 索引、022 工作、023 文件管理、024 Descriptor | [UI Backlog](07_builder_ui.md#ui-backlog-pending) |

## 7. 優先討論順序

優先對齊批次 Request、Document、Remote I/O 與有效設定，再收斂部署及執行細節。

| 建議順序 | 主題／Q-ID | 這輪需要收斂什麼 | 建議產出 |
|---|---|---|---|
| 1 | 最小完整 System Config 與環境綁定／Q-002、Q-015 | component_id／版本／parameters／服務引用如何放在 D，E 如何提供連線及 Runtime 設定；不把完整 Descriptor 複製進 Config | 一份可人工閱讀的 Elasticsearch Config，及切換 Remote Parser 的對照；機器 Schema 再按核定內容產出 |
| 2 | User Remote API／Q-022、Q-028 | 邊界驗證、呼叫失敗與認證解析 | 完整 Remote 連續區段範例 |
| 3 | Component SDK／Context 與資源生命週期／Q-002、Q-017、Q-020 | B 的 run(input, config, context)、初始化／關閉、Resolver 取得正確 System Client／IndexBinding、有狀態實例的作用範圍 | 一組 Local Parser／Remote Adapter 的 SDK 示意與契約驗收；不為每個 System 組裝專屬 Flow |
| 4 | 資料更新／索引讀寫與恢復／Q-007～Q-015 | revision 生成／衝突、失敗清理與 Remote unknown、ES mapping、Filter／融合的可驗算規則 | backend 更新／清理與管理操作的具體約定；沿用完整覆寫、不續跑、無查詢讀寫鎖等已確認方向 |
| 5 | 最小可執行技術與驗收基線／Q-001、Q-003、Q-004、Q-011、Q-026 | 具體框架／套件版本、可實測模型 API、Tokenizer／搜尋實作與測資；既有 M1 範圍不重新擴張 | Structured JSON／Recursive／Dense／Elasticsearch 的真實 ingest→query，以及成功、失敗與多 System 隔離驗收 |

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

後續開始程式開發時建議加入根目錄 AGENTS.md，引用本文與 架構、資料、Engine、Runtime 與 UI 手冊，記錄建置／驗證指令；本輪只交付規格，不新增未經確認的開發自動化規則。

## 9. 目前交付狀態與下一步

目前可審閱的交付為 03～23 的現行規格／討論稿、共用 JSON Schema、契約資料／參考驗證器、模擬 Prototype 及架構圖。三份 Ingestion 資料以 資料契約手冊 為準；Inference 的 ResultItem 引用共用 Chunk。

- 資料驗證：examples/parsed_document、examples/chunk 與 examples/inference；完整限制與執行方式見 資料契約手冊／Chunk手冊。
- Parser 對照：現行映射與驗收界線見 [資料契約](02_data_contracts.md#data-flow)；舊版供應者對照／試驗保存在 history/superseded，不等同目前契約的完整 Parser 驗收。範例通過不表示已交付 Engine Component。
- Prototype v0.12：現行原型完成／提案／後端待辦以 [Builder UI／Backlog](07_builder_ui.md#src-10-1-已完成的原型能力)相關章節為準。不可再把 UIB-001～013 全列未實作；多項已完成模擬，UIB-007／008 仍未核定，UIB-021～024 等累積項仍待改 UI／正式整合。
- 優先決策：正式共用契約／SDK、模型與 Tokenizer、ID／更新／發布政策，再按 M0～M7 推進。D-53 的 Chunk 後模板組合與額外原文 Chunk 已確認需求，尚待實作及凍結具體設定格式，見 [資料契約](02_data_contracts.md#data-flow)。

歷史決策來源、過時提案、驗證及校對過程集中於 [history/](history/README.md)，包括 D-01～D-66 的來源與演變。Q-001～Q-028 及 SC-01～SC-10 仍是現行待決／討論項目；文件歸檔不代表功能驗收完成。
