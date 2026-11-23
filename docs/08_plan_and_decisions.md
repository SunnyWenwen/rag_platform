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


> 文件同步日期為 2026-11-23 · 開發規格草案（正式 SDK／Config 尚未凍結）
>
> 目的：讓 coding agent 依同一套規格分階段開發，並持續記錄尚不清楚的問題。本文是決策／待決狀態的權威位置；它不把技術建議自動轉成使用者已核可決策。

<a id="user-remote-api-decision"></a>
## 2026-11-11 已確認：User Remote API、單一 Document、Admin 模板

- User 直接設定外部 API。Admin 管理全域模板版本，Builder 只提供選用，套用時複製至草稿。平台團隊維護內建方法與 Schema 描述。
- 共用資料物件定名為 `Document`。Ingestion 以非空 `documents` 與選填批次 `parameters` 接收，Parser 前拆成逐文件工作。檢索候選放在 `ResultItem.data`。
- Remote Retrieval 的候選遵守 Ingestion 設定推導的有效 System Document Schema。外部資料可直接查詢，無須執行平台 Ingestion 或建立平台索引。
- 各 Module 共用 `{{KEYNAME}}` 引用。一般參數優先使用已驗證的 Request 值，缺值依 [共用引用語法](05_system_config.md#parameter-references)讀取 System 設定。Remote 認證只從 `config.secret` 取值並注入 Header。

- Component Descriptor 與發布的 System Config 用 `component_id`／`component_version` 固定元件版本。節點由 Component ID 選擇格式，`remote_api` 為平台保留的共用 Adapter。2026-11-23 起外部服務的網址、認證與版本直接設定在 Remote 節點，見 [Remote 節點設定](05_system_config.md#remote-node-settings)。

取代 D-40／51 的 Developer 交付、Manifest 目錄與 Remote Image 流程，更新 D-47～49 的外層資料形狀、D-54 的候選資料鍵、D-58 的 Request 封裝及 D-67 的規格來源。保留 D-67 的內建 Schema 細化能力和 D-58 的單端點、整批預檢及逐文件工作。舊來源見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。

## 2026-11-12 已確認：Inference 結果處理

- 同 Query 多路融合與當步 `group_by` 歸 Retrieval。每條路先取 `per_route_k`，有多路時須選 RRF 或 Sum Score，每 Query 交付一份清單。策略各自開放的參數待逐 Component 定義。Rerank 在模型重新排序後做自己的分組，各步在分組後取各自的 Top N。
- 跨 Query 控制放在 Query Transformation。能產生多個 Query 時開放設定，使用者選 Retrieval 或 Rerank 完成後執行，可選分組及跨 Query Top N。最高分規則見 [Q-014](#q-014)。
- `group_by` 可多選。開啟時預選 `document_id`，多欄用組合鍵，每組保留當時排名最高的候選。任一欄缺值時獨立保留。見[設定規格](05_system_config.md#inference-result-processing)。
- Remote 區段負責其內部的結果處理。整段 Query Transformation → Rerank 交由 Remote 時，平台驗證結果後按 Remote 排名交付。

## 2026-11-12 已確認：Chunking 來源與 Ingestion 後續議題

- 正式 Chunking 設定只選一個切分來源欄位，每個解析 Unit 使用同一欄位。可另行複製其他欄位或保留該欄原文。
- Ingestion 進度呈現延後討論。排隊或執行中的文件可依[批量取消契約](06_runtime_api_and_deployment.md#ingestion-cancel-api)操作。

## 2026-11-13 已確認：單一 Rewrite Component

- 內建 Query Transformation 使用 `rewrite` 支援單筆與多筆改寫，以 `count` 設定改寫數量。`none` 沿用原始問題。模型回應、重試及錯誤政策依 [Engine 規格](03_engine_and_components.md#src-04-51-query-transformation) 追蹤。

## 2026-11-13 已確認：Retrieval System 生命週期

- Builder DEV 以獨立 Runtime 承載多個 System，透過內部 API 套用、列出、查詢及卸載。單組 Config 獨立部署由 Runtime 啟動時載入，管理 API 關閉。Engine 使用共用 LangGraph 執行。
- Runtime 以 `system_id` 管理一份生效 Config，按 System 判斷管理操作與 Ingestion 是否忙碌。每個請求與已接受的文件工作固定 Config Revision。Ingestion Queue 採記憶體，重啟後不續跑。工作紀錄依 [Runtime 工作保留規格](06_runtime_api_and_deployment.md#ingestion-job-records)保存在受理 Pod。
- 初始化或重連時驗證索引歸屬及相容性。明確更新遇到不相容索引時先刪再建，Builder 重新匯入。明確卸載移除該 System 的受管理索引及資料。操作前置條件按[同版本恢復決策](#system-index-recovery-decision)細分。

## 2026-11-13 已確認：Elasticsearch 文件覆寫

- 本輪先以 Elasticsearch 為文件覆寫的後端。索引存取層產生內部 `write_id`，同一次寫入的 Chunk 共用此值，並以獨立 ES `_id` 保存。
- 新 Chunk 全部寫入並可搜尋後才刪舊。新版失敗時，按本次 `write_id` 清理並保留舊資料。更新期間可查到新舊 Chunk。Bulk 逾時的重匯規則依 [Q-008](#q-008)。
- `write_id` 與來源 `source_revision` 分開。ES 寫入、可見性與清理案例見 [Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。
- 覆寫以同 System 的 `document_id` 為準，`source_revision` 僅供來源追溯。Runtime 重啟後依 [工作紀錄規則](06_runtime_api_and_deployment.md#ingestion-job-records)從空的狀態開始。

## 2026-11-13 已確認：索引重建的原始資料

- Builder 保存並管理原始資料。Runtime 建好新索引並啟用 Config 後，Builder 以保存的原始資料重新提交 Ingestion。儲存方式、保留與管理流程由 Builder 後續規劃，見 [Q-016](#q-016)。重匯入後的查詢開放規則見下節。

## 2026-11-13 已確認：Inference 失敗及文件權限

- 首版 Inference 所需的 Query、搜尋路徑及節點均成功才回結果。任一最終失敗就回整次錯誤。查無命中回成功空候選。見 [Q-023](#q-023)。
- 文件／檔案級 ACL 延後討論。Runtime 依既有 System 及工具權限限制呼叫。見 [Q-006](#q-006)。

## 2026-11-13 已確認：查詢開放、CSV 替換與 Elasticsearch 驗收

- Runtime 的 Elasticsearch 索引可查且必要依賴就緒時接受 Inference，空索引回成功空候選。Builder 等初次預定資料全部匯入且可搜尋後才開放其查詢入口，後續一般新增不停止查詢。
- Builder 的 CSV 資料上傳以整批替換為語意，每列對應一份 Document，預檢後清除目標 System 的既有索引資料，再匯入全份 CSV。具體管理流程由 Builder 規劃。
- M1 首條端到端流程使用 Elasticsearch。

## 2026-11-13 已確認：索引相容性指紋

- 由有效 Config 推導影響索引內容、向量與搜尋能力的設定，正規化後計算 SHA-256。ES `mappings._meta` 保存部署環境、System 歸屬、指紋及指紋規則版本。完整 Config 由 Builder 保存。見 [索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle)。

## 2026-11-16 已確認：Data Meta Schema 與 Filter

- Import 宣告 structdata 欄位，處理模組推導實際輸出，Indexing 只可覆寫 searchable／filterable。metadata 以 JSON object 隨文件保存、傳遞和回傳。
- 首版支援 string、string_array、integer、number、boolean、date、datetime，group_by 可選 document_id 及有效 structdata 的 string 欄位。缺省、日期時間與各型別能力見 [欄位總表](02_data_contracts.md#data-meta-schema)。
- 保留固定與動態 Filter。外層 AND 搭配一層 any，運算子按型別驗證。先 Filter 再取 Top-K 是內建 Retrieval 的責任。Remote 接收有效 QueryContext.filters，自行決定查詢行為。
- Config 使用 structdata_overrides 與 fixed_filters。無效的使用中欄位引用保留於草稿並阻擋發布。見 [Config 與發布驗證](05_system_config.md#data-schema-config)。

<a id="ingestion-queue-and-es-write-decision"></a>
## 2026-11-16 已確認的 Ingestion Queue 與 ES 寫入規則

- ES 持久化工作紀錄的前版方向已由 [Pod 內工作紀錄決策](#pod-local-ingestion-decision)取代。
- 首版 System 生命週期由 [Builder 的 System 紀錄及部署流程](06_runtime_api_and_deployment.md#system-lifecycle-records) 管理。ES 保存檢索資料及其歸屬、相容性與建立操作標記。
- 2026-11-20 確認 ES Bulk 等待逾時以 `failed` 結案並允許重新匯入，按 `write_id` 清理舊批次。見 [ES 寫入與清理](06_runtime_api_and_deployment.md#es-write-control-record)。

<a id="system-index-recovery-decision"></a>
## 2026-11-19 已確認：同版本 ES 索引恢復

- 共用 DEV Runtime 的管理操作使用既有 PUT／DELETE。首次或正式卸載後用 `initialize`；接回相容索引用 `reload`；套用新版用 `update`。重新載入及相容更新沿用索引世代，首次建立及重建則分配新世代。
- DEV 已發布部署的索引確認遺失時先回報異常，待使用者確認後才由 Builder 發起 `recover_index`。適用於 Config 已載入或未載入。保持原 Config Revision，建立新空索引世代，由 Builder 重新匯入。首次部署與遺失恢復依 Builder 發布紀錄及 Runtime 可確認的綁定區分。
- DEV 由 Builder 保存生效版本、索引綁定、目標及待確認操作並管理重啟後補載。FTEST／ENT 由部署流程保存並提供 Config Revision 及索引綁定。
- [生命週期與 HTTP 契約](06_runtime_api_and_deployment.md#system-lifecycle-api)定義預檢、更新和卸載前置條件及操作重送。Config 未載入但既有受管索引可確認時，Builder 可直接發起 DELETE，由 Runtime 關閉入口、排空並清除索引。獨立部署的索引建立策略及操作入口由 [Q-021](#q-021) 追蹤。仍須驗證 ES 無法查證與管理操作中斷情境。

<a id="pod-local-ingestion-decision"></a>
## 2026-11-23 已確認：Ingestion 文件占用採 Pod 內記憶體

首版的文件占用、Queue、Run 收件、工作結果及清理進度都由受理 Pod 在記憶體保存。程序終止後一併遺失。Run 保留及清理見 [Runtime 工作紀錄](06_runtime_api_and_deployment.md#ingestion-job-records)，跨 Pod 文件鎖列入 [Todo Enhance](todo_enhance.md)。

<a id="builder-runtime-contract-decision"></a>
## 2026-11-23 已確認：Remote 節點、查詢回應、MCP 與 DEV 存取

- **Remote 節點設定。** 使用者在選用 Remote API 的節點直接設定服務網址、認證、服務版本、業務參數與輸出宣告。`connection.url` 一律引用 Builder 自動建立的 Variable，Token 只引用 Secret，Header 不可引用 Secret。Ingestion 必填固定的 `revision`，作為指紋的 `implementation_revision`；網址、Header、逾時與認證不參與指紋。取代 `service_ref`。見 [Remote 節點設定](05_system_config.md#remote-node-settings)。Embedding、LLM 與 Rerank 是否改由平台統一提供另行討論。
- **Inference 回應。** `contexts` 恰好一份最終 Context，`query` 等於 `ori_query`，唯一 ResultSet 的 `key` 為 `final`。外層 `query_variants` 依序列出實際搜尋的 Query。流程中仍可有多份 Context，逐 Query 清單留給後續診斷。Remote 區段涵蓋到最後模組時須回一份 Context。見 [Inference API](06_runtime_api_and_deployment.md#inference-api)。
- **MCP 查詢工具。** 每個 System 的 Inference 提供一個只做查詢的 MCP 工具，使用 Streamable HTTP 的無狀態用法，沿用 Inference Basic 帳密，結果與 `/queries` 相同。OAuth 列為後續。見 [MCP 查詢工具](06_runtime_api_and_deployment.md#inference-mcp)。
- **DEV Runtime。** v1 只部署一個 DEV Runtime，使用 `replicas: 1` 的 StatefulSet，Builder 以一次操作套用兩條流程。多 Runtime、分開部署與跨 Runtime 排空列為[後續](todo_enhance.md#dev-multi-runtime)。DEV Runtime 不限制呼叫來源，持有對應帳密即可連線，管理帳密只交給 Builder。見 [DEV Runtime 的直接存取](06_runtime_api_and_deployment.md#dev-runtime-direct-access)。
- **取消狀態。** 已取得寫入權的文件取消後為非終態 `cancelling`，結算後轉為 `completed` 或 `cancelled`。見 [批量取消](06_runtime_api_and_deployment.md#ingestion-cancel-api)。
- **請求追蹤。** Builder 為每個操作及背景呼叫產生 UUIDv4 的 `X-Request-Id`，Runtime 回傳實際值並寫入錯誤物件。見 [請求追蹤](06_runtime_api_and_deployment.md#runtime-request-id)。
- **延後。** Ingestion 的 `Idempotency-Key` 列為[後續增強](todo_enhance.md#ingestion-idempotency-key)。

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
| [Descriptor](04_component_descriptor.md) | 參數細化、動態選項與 Descriptor 表單 |
| [System Config](05_system_config.md) | Config 版本、有效設定與變更影響 |
| [Runtime API／部署](06_runtime_api_and_deployment.md) | 管理／業務／Health API、Queue／狀態、控制預設、環境與 Export |
| [Builder UI](07_builder_ui.md) | 表單、模板及測試操作，附 Prototype 實作狀態 |
| 本文件 | 已確認基線、M0～M7、Q-001～Q-028、驗收與狀態 |

[schemas/](../schemas/README.md) 是機器可讀契約的定義位置。主責手冊依契約解釋目前的執行行為，範例與驗證工具引用該定義。決策編號、待議選項與驗收集中在本手冊，歷史原文保存在 [history/](history/README.md)。

## 3. 已確認方向與保留基線

現行結論集中如下；D-ID 用來追查來源，不要求閱讀歷次討論才能實作。完整原始決策表、當時提案及逐輪變更見 [歷史決策紀錄](history/decisions/decision_history.md)。公共契約的精確形狀以 [schemas/](../schemas/README.md) 為準。

| 主題 | 現行結論 | 來源／主責 |
|---|---|---|
| 產品／範圍 | Retrieval-only；無 Generation，Rewrite／助手仍可用 LLM；Evaluation 保留 M6 | D-50／03、Engine／Component手冊、21 |
| 管理階層 | Workspace → System；system_id 穩定，名稱／Config Revision／document_id 分開 | D-21／D-31／D-64；03、資料契約手冊、Runtime／部署手冊、21 |
| 輸入與 Parser | documents 批次提交與共用 parameters，Parser 前逐文件拆分；內建 Parser 單選 | 2026-11-11；02、06 |
| Document | 各模組共用 Document，以有效 Schema 區分階段，切分後加 data_id | 2026-11-11；02 |
| 追溯與 metadata | _rag／來源／fingerprint／ordinal 由 Component 選擇提供；metadata 可有明確支援的處理提示 | D-52；13～17 |
| Chunk／Embedding 能力 | Fixed-size／Recursive／Header-aware 用 Token；可複製原文欄位、另留原文 Chunk；Embedding 可選模板衍生欄位，兩項新增功能預設關閉 | D-36／48／53；04、15 |
| 保存／搜尋 | 保存完整 Chunk；全文／向量／Filter 能力分開。首版以 ES 交付及驗收；Local Search 的 Memory／MongoDB 列為後續 | D-09／10／33／39；04、資料契約手冊、19 |
| 索引交接 | 平台管理索引以單組 IndexBinding 銜接；外部 Retrieval 使用 System 候選 Schema | D-55、2026-11-11；02 |
| 推論資料 | QueryContext[]；ResultSet=key/items，ResultItem=data/選填 score | D-54、2026-11-11；02 |
| 結果處理 | 內建 Retrieval 每路取 `per_route_k`，多路以 RRF／Sum Score 融成每 Query 一份；跨 Query 在所選步驟後依 `data_id` 取最高分，分組亦取各組最高分 | 2026-11-23；[Engine](03_engine_and_components.md#result-processing)、[Builder](07_builder_ui.md#src-09-3-現行-ui-規劃) |
| 共用模型 | System 共用 LLM 名稱清單，Rewrite 以 llm_ref 引用；模型語意與環境連線分開 | D-13／Schema 細化手冊／30；資料契約手冊、System Config手冊 |
| I/O 宣告與細化 | 平台維護內建描述。Remote Request 由上游推導，Ingestion 輸出由 User 宣告 | D-67、2026-11-11；04 |
| 內建方法 | rag_platform 管 Builder，rag_engine 管 Engine／Runtime 與平台內建方法 | 01、03 |
| Remote 整合 | User 直連，支援單節點與連續區段；Admin 管理全域模板 | 2026-11-11；03、05 |
| Flow／Config | 共用 Flow／Executor；每次請求及已接受文件固定 Config 快照，各步獨立傳入 Component Config／Context，資源作用域另管 | D-61／62；03、Engine／Component手冊、07 |
| Config 生效／環境 | 依 System 固定生效版本並判斷忙碌；相容更新沿用索引，明確不相容更新先刪再建；獨立部署啟動時載入單一 Config | D-29／30／63／64；[Runtime 生命週期](06_runtime_api_and_deployment.md#src-07-4-systemrevision-與-engine-生命週期) |
| Ingestion 工作 | document_id 完整覆寫、逐文件結果；整批預檢才 202；文件無 partial，Run 可 partial；Queue 和狀態由受理 Pod 在記憶體保存，重啟後清空；支援按 Run 批量取消 `queued`／`running` 文件 | D-56～58；[Pod 內工作紀錄](#pod-local-ingestion-decision) · [批量取消](06_runtime_api_and_deployment.md#ingestion-cancel-api) |
| 讀寫／失敗 | ES 先寫新再刪舊，以 `write_id` 定位清理範圍；查詢允許混合可見；Pod 內同文件有有效占用時拒絕重送，Bulk 逾時結案後可重匯 | D-59／60；[Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)、Q-008～Q-010／Q-017 |
| 文件管理 | exists、文件摘要與 retire 讀取／管理實際儲存；摘要為 documents[]／next_cursor、document_id／source_revisions[]；retire 同步 200＋deleted 或 not_found，忙碌 409 | D-58／64／65；21 |
| API／認證 | 8 支業務＋2 支 Health；Basic 帳密依 Builder 入口、DEV 管理與 System 流程區分；共用 Runtime 經可信內部 System 路由選 Config | D-60／64；[Runtime API 清單](06_runtime_api_and_deployment.md#data-lifecycle-api) |
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
- 決策：2026-11-23 定案 Runtime 技術選型：Python 3.12、uv、FastAPI 單一程序、LangGraph、Elasticsearch 8.19（IK＋stconvert）、bge-m3 由獨立 Embedding 服務提供、官方 MCP SDK。版本鎖與理由見 [Runtime 技術選型](../code/rag_engine/docs/tech_stack.md)，可執行骨架見 [code/rag_engine](../code/rag_engine/README.md)。部門的 Python 版本、PyPI 映像、base image 與 CI 待確認後套用。

<a id="q-002"></a>
### Q-002 共用 Schema、Config、SDK 與版本凍結

- 平台內部描述規則沿用 D-67 的相依推導。W1 使用現行 `0.2-draft` Meta-schema，正式版本及遷移政策待核定。見 [Component Descriptor](04_component_descriptor.md#descriptor-fields)。

- 已確認：Workspace → System，邏輯 Config 與部署設定分離。後續的 Local Search 持久化模式隨 Config 跨環境固定（D-33）。Document 的 `structdata` 與 `metadata` 保存規則沿用 D-39，QueryContext[]／ResultSet 欄位沿用 D-54。W1 Config 鍵名及 HTTP 錯誤 Envelope 分別以 [Config 草案](05_system_config.md#config-fields)和 [Runtime 錯誤格式](06_runtime_api_and_deployment.md#runtime-http-errors)為準。正式版本的相容性、SDK、多 Profile 及原型舊欄位遷移仍待核定。
- D-62 已確認選項 B（共用 Flow）：共用 Flow／Executor，依固定 Config 快照在各 Module 選 Component，並傳入 input／本次 config／Context；不強制所有實例共用。精確 SDK 簽名及 Resolver／資源作用域仍待凍結。
- 2026-10-28 補充：Component SDK 的 Module-specific I/O 包裝、run／初始化／釋放簽名、RunContext、Registry／Factory 與 Config Schema 介面待凍結；Registry 草案改稱 component_id，不直接改寫既有 Config。精確方法／版本引用、舊 module_id 別名與遷移須一致驗證；11 的 Python 程式只作介面示意。
- [System Config：System Config 討論稿](05_system_config.md#草稿有效設定與部署) 依 D-67 取消頂層 document_schema，資料細節由 B／C＋D 提供；首版六類宣告與相依推導見 [Descriptor](04_component_descriptor.md)。規則語法／SDK／解析 API 仍待凍結；D-66 舊機器稿及五案例已歸 [歷史快照](history/superseded/system_config_d66/README.md)，不作新功能驗收。前輪校對過程見 [歷史報告](history/reviews/2026-11-05_spec_alignment_review.md)。
- 建議：先核定最小完整 Config＋單一公開 Engine interface；Pydantic 匯出 JSON Schema，UI 使用相同來源。用完整欄位路徑；未知別名拒絕。
- 替代：直接沿用 Prototype 全部短名稱；需補齊其缺少型別與執行語意。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 契約凍結。
- 決策：未定；更新 Engine／資料契約手冊／Runtime／部署手冊、Schema 及完整範例。

#### Document 與共用契約

現行邊界見 [Document](02_data_contracts.md) 與 [JSON Schema](../schemas/README.md)。Python Runtime 型別封裝與正式 Config 語法仍待核定。原型與離線測試用於契約驗證，真實 Parser、Tokenizer、模型與 DB 另做整合驗收。

#### 設定列舉的穩定代碼

已確認首版開發前統一採用穩定代碼。因尚無需要載入的已儲存或匯出 Config，範例與測試直接採用首版代碼。欄位及合法值以 [Config 列舉 Schema](../schemas/config_enums.schema.json) 為準。

<a id="q-003"></a>
### Q-003 模型服務與 Adapter 契約

- 不清楚：首組模型、Profile／版本辨識、Tokenizer 取得、Chat 角色／輸出格式、多 Query 解析、Rerank 服務限制。
- 模型契約草案：Rewrite 採固定 queries 結構，依 count 驗證筆數、Provider Structured Output／Tool／文字解析能力分級、模組 Schema 與共用 LLM Adapter 分工；格式與語意都由後端重驗。細節見 [Engine／Component 開發](#rewrite-output-proposal)，不因寫入提案就凍結 Provider 或重試／fallback 預設。
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
- 關聯待決：現行 Document 與有效 `structdata` 契約的正式版本凍結、Parser 正規化及文字格式能力細節見 [Q-002 子項](#document-與共用契約)；不恢復已移除的 structure 型別或結構路由。
- 建議：M1 先 Structured JSON，Native text 及其他格式逐一有測資才開放；OCR 服務另驗證。
- 替代：第一期納入全部格式，需增加品質／成本驗收。
- 負責角色：產品＋Engine；阻擋 M2 格式能力，不卡 M1 Structured JSON。
- 決策：未定；更新 架構手冊／Engine／資料契約手冊／UI手冊／Runtime／部署手冊。

<a id="q-006"></a>
### Q-006 metadata 保留區、租戶與授權

- 首版 Runtime 的管理與業務 API 採 HTTP Basic，驗證位置與帳密範圍見 [Builder 與 Runtime 的驗證及授權](06_runtime_api_and_deployment.md#runtime-basic-authentication)。D-64 的可信 Backend 路由及 Istio 傳輸設定沿用。

- 已確認：文件／檔案級 ACL 延後。第一版依 System 的執行範圍隔離資料。2026-11-23 確認 [MCP 查詢工具](06_runtime_api_and_deployment.md#inference-mcp)沿用該 System 的 Inference Basic 帳密，OAuth 列為[後續規劃](todo_enhance.md#mcp-oauth)。
- Builder Backend 是判斷使用者能否存取 Workspace／System 或執行管理操作的授權邊界。DEV Runtime 不限制呼叫來源，依帳密驗證；管理帳密只交給 Builder，System 業務 API 與 MCP 可供持有流程帳密的呼叫端使用。Builder 依既有的參照做法實作使用者身分、角色權限與 Workspace 成員管理，本規格不另行規劃。另待平台保留欄位與 Gateway 的實機接線驗收。
- 負責角色：平台／身分團隊＋Backend＋Engine。
- 決策狀態：首版文件存取範圍及 Builder 授權分工已確認，其他平台授權與保留欄位細節另議。

<a id="q-007"></a>
### Q-007 文件／Chunk ID 與 source_revision

- 2026-11-23 已確認 [文件與切片識別規則](02_data_contracts.md#document-identities)、[Builder 的 CSV／檔案主鍵](07_builder_ui.md#builder-source-document-id)與 [ES 寫入批次識別](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。更新沿用同一 `document_id`，Engine 對內建切分產生可重現的 ID，Remote Chunking 自行產生唯一 ID。
- D-65 的來源版本及文件摘要保留現行規則，見 [Document](02_data_contracts.md#document)與[文件清單](06_runtime_api_and_deployment.md#src-21-93-文件摘要清單d-65-已確認核心)。
- 待驗收：多文件主鍵碰撞、跨語言序列化一致性、Remote Chunking 與同一文件重切分後的覆寫。

<a id="q-008"></a>
### Q-008 重送、更新與刪除

- D-56 已確認：同 (System, document_id) 完整覆寫，不存在則新增；成功後清除舊文件不再產出的 Chunk。同一 Pod 以本機文件占用判斷重複提交。重啟處理見 [工作紀錄](06_runtime_api_and_deployment.md#ingestion-job-records)。
- 已確認：整批在受理 Pod 檢查文件占用，忙碌時回 `409 DOCUMENT_BUSY` 並列出當次的本機衝突。見 [Ingestion 文件占用衝突](06_runtime_api_and_deployment.md#ingestion-document-busy)。
- 已確認：ES 以 `write_id` 保存新舊批次，新版全部可搜尋後刪除舊批次。確認寫入失敗時僅清理本次批次。見 [Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。
- 已確認：`source_revision` 僅供追溯。Builder 可按逐文件狀態重新提交已結案的失敗文件。相同內容是否可 no-op，以及 Builder 的重送操作仍待定。整批預檢與逐文件結果沿用 D-57；文件管理與 Retire 沿用 D-58。精確錯誤協定和 Ingestion 進度管控依 Q-017／Q-019。
- 提交回應遺失時，首版由文件 `ingestion-status` 取得最近一次 `run_id`，再查該 Run 的文件清單。Ingestion 的 `Idempotency-Key` 延後，見 [Todo Enhance](todo_enhance.md#ingestion-idempotency-key)。System 的 Run 清單留待需求確認。管理操作沿用 Q-019 的重送規則。
- 已確認：ES Bulk 等待逾時時登記 `failed` 並釋放占用，可重新提交。`cancelling` 的工作結案為 `cancelled` 並釋放占用。依原 `write_id` 清理逾時批次，持續失敗或有晚到殘留時人工查核。清舊或 Retire 的查核與清理依各自規則。
- 負責角色：產品＋Engine＋Backend；阻擋安全重試／正式更新實作。
- 決策狀態：覆寫單位與忙碌拒絕方向已確認，以上其餘細節 OPEN；更新 Engine／資料契約手冊／Runtime／部署手冊／Runtime API手冊。

<a id="q-009"></a>
### Q-009 部分失敗與提交原子性

- D-56 已確認：以 document_id 為更新與成功／失敗單位；Batch 逐文件獨立結果，不要求全 Batch 回滾；文件完整執行成功才標 completed，不接受半份文件為成功；D-60 不加 Query 讀寫鎖，允許更新期間短暫讀不一致，失敗清理／保留舊版機制仍需 backend 落實。
- ES 在新版全數可搜尋及舊批次清理後標文件 `completed`。更新與清理期間可查到新舊混合。Bulk 逾時以 `ES_BULK_TIMEOUT` 結案，晚到寫入與殘留清理需整合驗收。非 ES 後端的提交行為另議。Run partial／文件無 partial 依 API-D01／02。
- 負責角色：Engine＋Backend；阻擋 M2 更新與 M3 終態／提交驗收。
- 決策狀態：文件級原則已確認，實作與精確 Envelope OPEN；更新 Engine／資料契約手冊／Runtime／部署手冊／Runtime API手冊。

<a id="q-010"></a>
### Q-010 Ingestion／Query 併發與發布

- D-56 已確認：每 Pod 內每 System 的文件併發可配置、預設 1。同一 Pod 的不同文件可依上限並行。Bulk 逾時結案後可重匯，詳見 Q-008。D-60 允許查詢和寫入併行。
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

- 已確認欄位與運算子矩陣、缺欄位／null／多值語意、固定與動態 Filter，以及各內建路徑先過濾再取 Top-K。見 [Filter 契約](02_data_contracts.md#filter-semantics)。
- Elasticsearch mapping／Query DSL 和實際 ES 測資由 Engine 負責 M2 整合驗收。Local／FAISS 的候選策略及後端驗收列為後續。

<a id="q-014"></a>
### Q-014 融合計畫、合併時點與分組細節

- 已確認：內建 Retrieval 先依 `per_route_k` 限制每 Query／每路，多路時須以所選 RRF 或 Sum Score 融合，每 Query 交付一份。跨 Query 可選 Retrieval 或 Rerank 完成後，並可再分組及截斷。
- 已確認：分組可選多個候選 Document 單值欄位，開啟時預選 `document_id`。Rerank=None 時仍可執行後置跨 Query 規則。
- 2026-11-23 確認：RRF 與 Sum Score 只用於單一 Query 的多路召回。跨 Query 依 `data_id` 保留最高分，Group By 保留各組最高分。Query Transformation 設定合併時點與選填分組、Top N。見 [Engine 執行規則](03_engine_and_components.md#result-processing)及 [發布格式](05_system_config.md#inference-result-processing)。
- 待實作與驗收：RRF／Sum Score 的專屬參數、可驗算的融合分數與同分順序、ES Adapter，以及 Remote Query Transformation 將多 Query 交給平台處理時的節點設定。真實資料與服務的整合驗收留在 M2，涵蓋 ES 原生融合的命中識別、同文件不同切片、不同寫入批次及跨 Query。Local Search Adapter 列為後續。

<a id="q-015"></a>
### Q-015 Revision、有效 Config Hash 與 Index 版本

- 已確認：同一 System 的同版邏輯 Config 跨環境相同，部署設定分開；文件 source_revision 與 index_generation 概念分開。保存／生效時點、草稿衝突、CSV mapping 歸屬、環境部署識別／資料版本及快照切換仍待定。
- 2026-10-28 補充：需定 Component／package／Engine 解析版本保存位置、如何納入可重現執行與相容判定、更新 Component 後的重測／重建與回復政策；新版發布不自動升級既有 System，僅看版本號不能判定索引相容。
- 已確認：Runtime 從會影響索引的有效設定推導並正規化後計算 SHA-256，與實際 mapping／Profile 一併驗證。ES 將部署環境、System 歸屬、指紋及指紋規則版本存入 `mappings._meta`。[指紋 v1](06_runtime_api_and_deployment.md#index-fingerprint-v1-proposal) 定義投影、序列化及 metadata Schema。無指紋索引的遷移、依賴版本解析及後續規則升版仍須整合確認。
- 已確認 Config Hash 的範圍：以同版有效邏輯設定為準，包含 Ingestion、Indexing 的 mapping／欄位與 Inference 邏輯，排除部署環境綁定。ES 的 `service_source`、`es_number`、`account`、`password` 及其匯出時產生的 Secret 引用均屬環境綁定。DEV 原快照與 FTEST／ENT 匯出檔的序列化內容可以不同，仍對應同一邏輯 Config。見 [ES 匯出規格](05_system_config.md#elasticsearch-service-source)。正規化、保存時點及樂觀版本檢查的細節待定。
- 替代：單一 active revision，改配置後阻擋到準備完成；仍須避免 lost update。
- 負責角色：Engine＋Backend＋Frontend；阻擋 M0 Hash 凍結及 M5 版本操作。
- 決策狀態：索引指紋與邏輯 Config Hash 的用途及範圍已確認，其餘版本管理細節仍待定。

<a id="q-016"></a>
### Q-016 平台儲存、原始資料與保留

- 已確認：Builder 保存及管理原始檔與結構化來源資料，供受管理 System 索引重建後重新匯入。Runtime 負責索引與 Ingestion 執行。[DEV 首版以 Base64 傳送原始檔案](06_runtime_api_and_deployment.md#src-07-54-builder-上傳與自行部署)。
- 仍待：Builder 的儲存後端、來源版本、權限、保留／刪除與重匯入流程。Config／Run／Dataset／Report 的管理資料庫、解析結果與 Trace 原文的保留政策，以及獨立 Runtime 儲存另議。
- 建議：管理資料與搜尋 Chunk Store 分離；可用 Store interface 分環境替換；只保存明確必要資料。
- 替代：統一平台 DB／Object Store；獨立 Runtime 的外部依賴與成本需交代。
- 負責角色：Backend＋平台／資料負責人；阻擋 M3／M5 正式持久化與資料政策。
- 決策狀態：Builder 原始資料管理責任已確認，具體方案待 Builder 規劃。

<a id="q-017"></a>
### Q-017 Timeout、重試、取消與工作恢復

- 首版的 Queue、取消與 Run 查詢由受理 Pod 的記憶體處理。預設保留期限和容量見 [終態紀錄清理](06_runtime_api_and_deployment.md#ingestion-status-retention)。
- D-64 已確認 Runtime 整體 Deadline／狀態保存初始值與管理方式，集中見 Runtime API／部署手冊；A 的成功／錯誤核心欄位已確認。仍待排隊等待上限、模組／Client Timeout、有限重試／可重試錯誤、中斷及未知遠端副作用處理、正式 Schema／載入方式。
- 2026-11-20 已確認同一個 Run 使用 `POST /ingestions/{run_id}/cancel` 傳入 `document_ids`。尚未取得寫入權的 `queued`／`running` 文件直接回報 `cancelled`，已完成的文件回報原狀態。2026-11-23 補充：已取得寫入權的文件回報非終態 `cancelling`，Worker 保留原占用到結案，成功時改為 `completed`，失敗或 Bulk 逾時時改為 `cancelled`。Run 彙總將 `cancelling` 視為進行中。Run 與單份文件查詢顯示同一狀態。2026-11-23 補充活躍取消的 Runtime 路由與重啟後的查無紀錄行為。Active Run 清單、人工查核端點延後。見 [Runtime 批量取消契約](06_runtime_api_and_deployment.md#ingestion-cancel-api)。
- 已確認 Ingestion 失敗或重啟中斷後，由呼叫方決定是否重新提交完整文件。ES Bulk 逾時與原批次清理見 [ES 寫入與清理](06_runtime_api_and_deployment.md#es-write-control-record)。模組內部的執行預算與重試條件另議。
- 負責角色：Engine＋Runtime；阻擋 M1 錯誤政策及 M3 工作語意。
- 記憶體 Queue、工作紀錄與重啟後不續跑的行為已確認。其餘由 [Runtime 規格](06_runtime_api_and_deployment.md#ingestion-job-records) 追蹤。

<a id="q-018"></a>
### Q-018 Evaluation 範圍與 Gate

- 不清楚：首批指標及精確公式、Dataset Schema、Judge／Rubric、原文片段比對、Rerank 前後、公開檢索 Target、Gate 門檻。
- 已移除答案正確性／Faithfulness 與自訂答案 JSON 的驗收；Evaluation 聚焦檢索排名、延遲、Usage／錯誤。2026-11-23 確認以 `document_id` 標註並依[唯一文件排名](03_engine_and_components.md#document-level-evaluation)評估。
- 建議：先有可驗算的 Retrieval 指標與操作指標，再加明示 Judge；缺資料拒絕或 skipped。
- 替代：先 End-to-end Judge；不得冒充有可靠 Retrieval Ground Truth。
- 負責角色：產品／資料＋Engine＋Backend；阻擋 M6 正式評估／Gate，不卡 Query 主線。
- 文件標註與排名單位已定。完整評估格式與門檻在 M6 定案。

<a id="q-019"></a>
### Q-019 API／HTTP Envelope 與呼叫認證

- [Runtime API 規格](06_runtime_api_and_deployment.md)定義 W1 HTTP 契約。[Builder 開發契約索引](09_w1_builder_runtime_contract.md)提供所需規格、Schema 與 Mock 入口。
- D-60 的 Basic Auth、D-64 的可信 System 路由與錯誤核心、D-65 的文件摘要格式沿用。D-42 的欄位選項由 Builder 依 Catalog 與草稿推導。2026-11-23 定案 [Query 成功物件](06_runtime_api_and_deployment.md#inference-api)：`contexts` 只有一份最終 Context，外層附 `query_variants`，所用快照以 body 及 Header 交付。同日確認 [MCP 查詢工具](06_runtime_api_and_deployment.md#inference-mcp)及 [`X-Request-Id`](06_runtime_api_and_deployment.md#runtime-request-id)：Builder 產生 UUIDv4，Runtime 回傳實際值並寫入錯誤物件。
- 已確認應用服務使用 HTTP，Pod 間由 Istio 強制 mTLS，對外由 Gateway 提供 HTTPS。部署與開發接線見 [Istio 傳輸與服務入口](06_runtime_api_and_deployment.md#istio-http-transport)。
- Builder 依 [Q-006](#q-006) 驗證及授權使用者。Runtime Health 免 Basic，System GET 使用只交給 Builder 的 DEV 管理帳密，System 業務流程與 MCP 使用各自的 [固定 Config Secret 欄位](05_system_config.md#system-api-secret-fields)。
- 管理請求逾時沿用同一 `Idempotency-Key` 查核或重送。已結束的操作結果只需覆蓋 Builder 的重送與查核窗口，初始候選為可配置的 1 小時。尚未結束或結果待查的操作保留至安全結算。結果過期時先查 System 狀態和原操作，查證後才能重新發起變更。正式期限與過期時的查核細節待定。
- Builder 實作管理請求的有限重試與失敗回報，並自行選擇次數、等待時間和可重試條件。查不到結果時保留原操作供查核，詳見 [生命週期 API](06_runtime_api_and_deployment.md#system-lifecycle-api)。
- 首版以同一份 [System Config Schema](../schemas/system_config.draft.schema.json) 及引用檔隨 Builder、Runtime 交付。Runtime 透過現有 Catalog 提供元件與資源，並使用 `config:validate` 做最終預檢。詳見 [Config 驗證邊界](06_runtime_api_and_deployment.md#runtime-capability-contract)。
- 已確認：卸載某 System 在目標 Runtime 的 Ingestion 後，該目標暫停該 System 的歷史 Run 查詢。ES 保留規則沿用，首版透過已載入同一綁定的 Ingestion 查詢。
- Builder → DEV Runtime 已提供 [OpenAPI、Mock 及 HTTP 情境測試](09_w1_builder_runtime_contract.md#builder-runtime-quickstart)。仍待正式環境部署接線、Builder 自有 CRUD／助手／檔案 manifest、資料保留、Trace 及版本相容政策。W1 DEV Runtime 的 HTTP、ES 與模型還需整合驗收。
- 負責角色為 Backend、Runtime、Frontend 與身分團隊。以 W1 Mock 開發，真實串接按 M3／M5 驗收。

<a id="q-020"></a>
### Q-020 DEV 共享 Runtime 與資源隔離

- Builder DEV 共用 Runtime，外部 API 由服務提供者維運，資源隔離與配額另行驗證。
- 2026-11-23 確認 v1 DEV 只部署一個 Runtime，Builder 以一次操作套用兩條流程；以下多 Runtime 與分開部署的規則保留 API，於[後續規劃](todo_enhance.md#dev-multi-runtime)啟用。
- 2026-11-20 確認：DEV 可在同一 Runtime 或受管 ES 的不同 Pod 分別啟用 Ingestion 與 Inference。Builder 以 `runtime_ref` 選 Runtime，透過同一組生命週期 API 的 `pipeline` 選流程。Ingestion 管理共用索引與生效版本，Inference 使用 `reload` 接回，兩條流程均回報自身載入／就緒狀態並可獨立卸載。見 [流程部署契約](06_runtime_api_and_deployment.md#runtime-pipeline-deployment)。
- DEV 以穩定 `runtime_ref` 保存部署目標。Pod 故障隔離與寫入接手由部署方負責。Builder 顯示失聯並保留部署意圖，服務恢復後查核並補載。DEV Runtime 使用 `replicas: 1` 的 StatefulSet。FTEST／ENT 的 `runtime_ref` 選填，控制器選型與寫入排空由各環境部署流程決定。[接手與部署選項](06_runtime_api_and_deployment.md#system-ingestion-drain)
- 後加入的 DEV Runtime 由 Builder `reload` 指定版本與綁定。重建或刪除前由 Builder 協調各 Runtime 排空。逐流程 `detach` 保留索引。[排空規格](06_runtime_api_and_deployment.md#builder-query-drain)
- Builder 使用既有 System GET 定期查核部署意圖、Config Revision 和索引世代。預設每 60 秒，可由 Builder 部署設定調整，Builder 啟動及 Runtime 恢復連線後也查核。預期上線但快照缺失或過期時預檢及 `reload`，暫時性錯誤按 Q-019 處理。
- 已確認允許切版期間暫停新查詢。Ingestion 提交共用版本後，Builder 逐目標補載 Inference；舊快照未就緒時回 `503 PIPELINE_NOT_READY`，核對新版與索引世代就緒後恢復。新版已提交但補載失敗時，Builder 顯示發布及各目標的補載結果，依 Q-019 處理有限重試。回復舊版的政策待定。僅變更 Inference 仍走共用版本發布。

- D-56／D-64 已確認：Builder DEV／獨立 Runtime 共用 System Queue、併發、Inference Rate 及 Deadline。初始限制由部署管理者在 Runtime 環境設定 E 提供，正式載入格式與機器 Schema 待定。Runtime 控制總量，Builder 另管理 User／Workspace 配額。Worker 為排程單位。
- D-61：共用 API service 啟動只綁服務／Registry 基礎設定，後續管理多份 System Config，不因每份 UI 設定新增服務；可依 Namespace／資源池分成少數共用服務，精確分組策略尚未選定。
- D-62 已選 B：共用 Flow／Executor，逐請求／已接受文件固定 Config 快照，Module 依設定解析 Component；不要求每份 Config 建立專屬 Flow。Component 實例／資源是否共用依狀態與隔離需求決定。
- 仍待：配置與 Component 快取、資源預載與釋放策略、管理 API 的部署接線與實機驗收、服務池分組、公平排程、正式參數 Schema、實際記憶體上限。若部署方式讓不同 Runtime 同時服務同一 System 並共用受管 ES 索引，須按 [Pod 內管控與分流](06_runtime_api_and_deployment.md#pod-local-ingestion-control)驗收部署行為。Runtime 管理行為見 [生命週期](06_runtime_api_and_deployment.md#system-lifecycle-api)。
- 建議：先有受限共享 Runtime 與明確隔離 Binding。首版以受管 ES 為準。
- 替代：每 System 獨立 Runtime，增加部署／資源管理成本。
- 負責角色：平台＋Backend／Runtime；阻擋 M5 多 System 服務。
- 決策：Builder 主動管理並逐流程部署。DEV 由 Builder 保存權威索引綁定及管理操作計畫。首版由部署方更換 Runtime Pod，[Builder 的 Runtime 維護入口](todo_enhance.md#builder-runtime-maintenance)列為後續增強。Builder 保存介面與資源隔離策略待實作及實機驗收。

<a id="q-021"></a>
### Q-021 Export、FTEST／ENT 與 Secret Vault

- Export 交付 Runtime 設定、環境連線及 `config.variable`、`config.secret` 的 Key 與部署注入。外部服務由其提供者維運。

- 2026-10-28 D-41 確認：rag_engine 統一建置含 Engine／核可 Components／Runtime API 的完整 Image，rag_platform 建置 Builder Image；採用新版 Engine／Component 時仍需更新 Runtime，接口相容的 Builder 可維持原版。目標 Image 須包含 Config 所需 Component packages 並保存版本；Component 清單／鎖定格式與缺失錯誤仍待決，YAML 不會自動提供 Python 方法程式。建置／發布／部署範圍見 [Runtime API／部署](06_runtime_api_and_deployment.md#src-07-94-建置發布與部署的變更範圍)。

- 已確認：DEV／FTEST／ENT 首版以 ES 為部署基準。跨環境沿用同版邏輯 Config，由部署設定提供連線與資源。Local Search 列為後續，Memory／MongoDB 模式仍適用 D-33。System Secret 使用字串 KV，匯出保留 Key，正式 Runtime 啟動時讀取同名環境變數。待定為 Image／Bundle 包裝、外部 Vault 供應、DEV 憑證保存期限、K8s 資源／Ingress／Probe 及 CD 流程。
- [D-30](history/decisions/decision_history.md#d-30) 的同版一致適用於 System 邏輯設定。部署用 System Config 保留原 Revision，匯出時將 DEV 的 `dev_test` 自動轉成 `pled_es`，目標環境透過 Secret 提供 ES 編號、帳號與密碼。[Elasticsearch 匯出規格](05_system_config.md#elasticsearch-service-source)
- FTEST／ENT 由部署方管理版本、綁定、排空與切換。缺少資料索引時，建立授權、部署操作入口與如何查核前次部署紀錄待 M7 確認。見[FTEST／ENT 首次建立索引](todo_enhance.md#standalone-index-initialization)（建議方向，待 M7 確認）。獨立 Runtime 的管理 HTTP 停用。
- 分 Pod 使用同一 Runtime Image 與 Config，環境部署設定選擇 `pipeline`。Export 的設定載體、Service／Probe 接線、角色所需 Secret 與資源的最小範圍，以及滾動切換順序待定。
- 建議：版本鎖定 Runtime Image＋有效 Config＋環境覆寫；由目標環境提供 ES 及原始資料，獨立 Runtime 直接啟動。
- 替代：使用單位既有 Helm／GitOps 形式；仍需相同可驗證交付內容。
- 負責角色：平台／DevOps＋Backend；阻擋 M7 正式部署交付。
- 決策：未定；更新 架構／資料契約手冊／UI手冊／Runtime／部署手冊。

<a id="q-022"></a>
### Q-022 內建方法交付與外部服務隔離

- 內建方法由平台團隊隨 Runtime 版本維護。外部實作由 User 選擇及部署，接入時遵守 Remote API 契約。
- 待核定：[DEV Runtime 允許的出站目的地](todo_enhance.md#dev-runtime-egress-allowlist)、資源隔離、授權與憑證範圍、租戶配額及相容版本驗收。

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

- 已確認：支援連續區段、固定 HTTP 封裝、上游推導 Request、輸出欄位與向量宣告、共用 QueryContext[]、外部候選符合有效 System Schema。Remote 可使用傳入的 filters，自行決定過濾、排序與截斷。Bearer 認證以 `{{KEY}}` 取用同一 System 的啟動設定，由 Adapter 組成 Header。
- 2026-11-23 已確認 [Remote 節點設定](05_system_config.md#remote-node-settings)：網址以 Variable 引用、逾時與自訂 Header 在進階區，Ingestion 以 `revision` 標示服務版本並參與指紋。
- 2026-11-23 已確認 [Remote v1](03_engine_and_components.md#remote-api) 及 [OpenAPI](../examples/user_remote_api/openapi.json)。Config 固定 Wire 版本，封裝含實際區段，Header 提供呼叫追蹤，失敗提供重試提示。
- 待核定：連線驗證、實際逾時及重試預算、錯誤觀測與容量門檻、未來同時支援多版本的遷移期限。
- 驗收：同區段呼叫一次、無重疊、驗證失敗可定位、內建與 Remote 切換、外部 Retrieval 與下游相容、匯出可解析部署綁定。見 [Engine](03_engine_and_components.md#remote-api)。

## 決策與待辦的唯一登錄位置

| 登錄 | 數量／狀態 | 主責 |
|---|---|---|
| Q-001～Q-028 | 每項保留已確認方向與 OPEN 細節 | 本手冊 |
| DS-01～DS-13 | 平台內部描述候選，舊 DS 表見歷史 | [歷史決策紀錄](history/decisions/decision_history.md) |
| SC-01～SC-10 | D 的具體表示；Import 和有效設定推導 Document，舊 SC 候選見歷史 | [歷史決策紀錄](history/decisions/decision_history.md) |
| API-D01～API-D07 | 已確認核心／待完成協定逐列保留 | [Runtime API 決策](#runtime-api-decisions) |
| UIB | 依原型、正式整合及驗收進度更新；021 索引、022 工作、023 文件管理、024 Descriptor | [UI Backlog](07_builder_ui.md#ui-backlog-pending) |

<a id="runtime-api-decisions"></a>
<a id="src-21-7-非必備端點與本輪待討論"></a>
### Runtime API 的待決範圍與驗收

<a id="src-21-71-首期不納入後續能力"></a>
#### 後續能力與待議範圍

| 能力 | 狀態 | 後續界線 |
|---|---|---|
| Ingestion 進度管控 | 延後討論 | Active Run 清單及人工觸發寫入查核。首版提供[批量取消](06_runtime_api_and_deployment.md#ingestion-cancel-api)。 |
| 整份文件／Chunk 內容查詢 | 先延後 | document_id 清單與存在查詢已納入；不因此提供內容、向量或任意 DB 查詢 |
| 索引詳細狀態／容量資訊 | 可作後續管理診斷 | index-ready／恢復／統計來源，不用 Health／最後 Run 反推 |
| Rewrite／Rerank 單步測試、async Inference／streaming | 目前不納入 | 有明確需求再定義，不重新引入 Generation |

Retire 已確認為直接刪除，不做 soft delete／restore API；再次使用同 document_id 需重新 Ingestion。D-64 已確認同步結果／忙碌拒絕／重複刪除的不同結果；Remote／儲存清理與未知結果等後端細節見 [Runtime API相關章節](06_runtime_api_and_deployment.md#src-21-9-文件資料查詢與直接刪除)／API-D03。

<a id="src-21-72-決策狀態與剩餘討論"></a>
#### API-D01～API-D07

| ID | 已確認 | 仍待確認／建議 | 關聯 |
|---|---|---|---|
| API-D01 | 單一 POST、批次物件的非空 documents、單筆也置於 documents；整批預檢通過才 202；逐文件結果 | Rate／Queue 與特殊來源的實際測試 | Q-019／Q-009 |
| API-D02 | 提供 Run／文件查詢。Run 可為 `partial`，查無紀錄回 200＋`unknown`。受理 Pod 保存收件及逐文件結果 | 驗證兩種狀態查詢、到期、容量回收及重啟後查無紀錄 | Q-019／Q-017 |
| API-D03 | Retire 同步回 200＋`document_id` 和 `result`，同文件在受理 Pod 有有效占用時回 409 | 後端完整刪除能力、部分刪除／未知結果與重試清理協定仍待核定 | Q-008／Q-017／Q-028 |
| API-D04 | D-64 確認 22 的初始預設與管理方式：E 的 Runtime 環境設定，由 Admin／部署管理者提供；Query 額滿直接拒絕 | 候選參數路徑、正式機器 Schema／載入方式、排程／計數算法與實際容量驗證；不新增單次請求覆寫 | Q-017／Q-020／Q-027 |
| API-D05 | 固定 Config 快照，按 System 判斷忙碌。Builder DEV 以定期查核補載，索引確認遺失時走人工確認的恢復流程。ES Bulk 逾時結案後可重匯 | ES 晚到寫入及殘留清理的整合驗收、獨立部署的索引建立方式 | Q-008～010／Q-015／Q-017／Q-019／Q-021／Q-028 |
| API-D06 | [Builder 驗證與授權](#q-006)使用者，Runtime 依 [HTTP Basic 分工](06_runtime_api_and_deployment.md#runtime-basic-authentication)驗證管理操作及各 System 流程 | 對外入口及內部路由依 [Istio 規格](06_runtime_api_and_deployment.md#istio-http-transport)；認證的 Secret 注入與 Probe 由部署驗收 | Q-006／Q-019／Q-020 |
| API-D07 | 查 document_id 是否存在；D-65 文件清單回 documents[]＋next_cursor，每筆 document_id／source_revisions[]，讀取實際 Chunk 而非工作表 | Remote 讀取操作與實際分頁一致性驗收 | Q-019／Q-028 |

HTTP 範例見 [Runtime HTTP 測資](../examples/system_config/README.md#runtime-http-examples)。實作待辦依上表的 Q-ID 追蹤。

實作驗收涵蓋單筆／Batch 接收、文件忙碌衝突、Queue 滿、逐文件 partial、兩種狀態查詢、到期及重啟後查無工作紀錄、同 ID 完整替換、Query 無命中／不就緒／限流、Inference 路徑或 Rerank 失敗，以及已授權 System 隔離。

<a id="rewrite-output-proposal"></a>
<a id="src-04-511-討論提案rewrite-的結構化輸出與共用-llm-邊界"></a>
### 討論提案：Rewrite 的結構化輸出與共用 LLM 邊界

**狀態：2026-10-16 提案，待使用者確認及 Q-003／Q-017／Q-023 核定；不是已實作或已凍結的公共 Contract。** 建議 UI 加單模組試跑，見 Builder UI／Backlog手冊／UI Backlog手冊；輸出形狀與數量由平台提供，Prompt 主要描述如何改寫，不讓使用者每次重寫機器可讀契約。

Rewrite 的模型回應草案為 `{queries: [...]}`，由 `count` 決定所需筆數。原始問題及 include_original 由平台處理，與模型要求生成的數量分開。ori_query、filters、metadata 由 Runtime 保留／複製，LLM 只生成 query 文字，不負責授權或結果物件。

以下 Python／Pydantic 例子只示範按 n 產生 Schema 及驗證形狀／型別／數量，不會呼叫 LLM；可將匯出的 JSON Schema 交給支援的 Provider。正式類別名稱與 Adapter 格式仍待決：

```python
from pydantic import ConfigDict, Field, StrictStr, create_model

def rewrite_result_schema(n: int):
    if n < 1:
        raise ValueError("n must be positive")
    return create_model(
        f"RewriteResult{n}",
        __config__=ConfigDict(extra="forbid"),
        queries=(list[StrictStr], Field(..., min_length=n, max_length=n)),
    )

Result = rewrite_result_schema(3)
schema = Result.model_json_schema()  # queries: minItems=3, maxItems=3
result = Result.model_validate({"queries": [
    "設備的建議清潔週期為何？",
    "多久應清潔一次設備？",
    "設備清潔保養的頻率是什麼？",
]})
```

建議的處理責任：

1. **模組定義輸出 Schema**：固定 key、型別與要求筆數；使用者改 Prompt 不改這個契約。
2. **共用 LLM Adapter 選擇能力**：優先使用 Provider 原生 Structured Output；支援工具呼叫者可用指定的結構化回傳工具；僅有文字／JSON mode 時解析後嚴格驗證，不宣稱同等約束。OpenAI-compatible URL 不代表服務／模型支援相同功能，須實測 Profile／能力；不支援時明確報錯或用已核定策略，不靜默換模式。
3. **Engine 做語意驗證**：解析、額外 key、實際筆數、去除首尾空白後非空、重複及原始問題政策。上例沒有自動完成非空／重複檢查；正規化後仍須符合目標筆數。是否允許與原始問題相同、等價重複與最終 Query 去重規則仍由 Q-003／Q-023 核定，不用補複製 Query 或任意截掉多餘結果來假裝符合數量。
4. **失敗政策**：格式錯誤可在核定次數、時間及成本上限內重試或修正。拒答、回應截斷、Timeout 分開處理，若最終失敗則回可定位的模組錯誤。

這套邊界可共用，但每個用途的輸出 Schema 不同：

| 用途 | 建議模型輸出 | 後端驗證 |
|---|---|---|
| Rewrite | queries 的 count 筆字串清單 | 數量、非空、重複、原始問題保存 |
| AI 設定助手 | Config 草稿、建議／Diff、缺項 | Schema、Registry、欄位相依與草稿基準 |

服務連線與模型引用集中管理，Schema 由每次模組呼叫傳入，不在同一 LLM 服務上固定一種輸出格式。使用 LangChain 時可採其 Model structured-output 介面，不需要為單次 Rewrite 引入完整 Agent。

官方依據（查核 2026-10-16）：[JSON Schema 的陣列長度限制](https://json-schema.org/understanding-json-schema/reference/array#length)；[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 說明 Schema 約束與 JSON mode 的區別、支援子集及拒答／不完整回應；[LangChain Models](https://docs.langchain.com/oss/python/langchain/models)／[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output) 說明 Provider／Tool 策略與驗證。來源提供技術依據，不直接核定本專案的 Provider、類別、重試數或 fallback 預設。

<a id="rewrite-test-proposal"></a>
<a id="src-06-331-討論提案query-rewrite-單模組測試"></a>
### 討論提案：Query Rewrite 單模組測試

**待使用者確認，尚未改 UI。** 建議在 Query Transformation 放「測試 Rewrite」：輸入一個問題，用當前草稿的 Prompt／LLM／count 執行該模組，不要求先建立／保存 System 或 Ingestion，也不執行 Retrieval／Rerank／檢索結果消費端。

測試前驗證本模組與引用服務的必要設定，不以其他無關模組未填完阻擋。顯示實際生成的 Prompt、要求筆數、解析後 Query 清單、原始問題是否另外加入及格式／筆數／非空／重複驗證；原始回應可收合，耗時／Token 用量僅顯示實際可取得數據。None 不呼叫 LLM。

測試使用與正式執行相同的 Engine 模組、Adapter、Schema 與驗證；LLM 輸出策略提案見 [Engine／Component](03_engine_and_components.md#remote-api)。未接真實服務則明示模擬。修改 Prompt／LLM／count／保留原始問題或測試輸入後，舊結果標示過期；過期非同步回應不覆蓋新測試。試跑結果不自動套用／保存 Config，也不新增「必須先測試才能儲存」的 Gate。

## 歷史名稱與遷移對照

使用者確認將原先表示「Module 下的可替換實作」的 Method 統一稱為 **Component（元件）**。平台團隊依 Module 契約維護內建 Component。Implementation 可作「具體實作」的敘述，不另增一個架構層級。Node 若用於圖面／配置引用，表示具體位置或實例，不與 component_id 混用。

| 舊稱／草案 | 新稱／草案 | 調整範圍 |
|---|---|---|
| Method／Method package | Component／Component package | 文件中的擴充單位與交付套件 |
| method_id | component_id | Registry、Descriptor、Config 目標識別與錯誤定位；範例 ID 值維持不變 |
| BaseMethod／ChunkingMethod | BaseComponent／ChunkingComponent | SDK 類別示意，尚未存在正式 SDK |
| methods/、rag_methods、rag-methods | components/、rag_components、rag-components | rag_engine 內的建議目錄、import package、distribution 名稱；不新增 repo |
| rag_engine.methods | rag_engine.components | 候選 entry point group；精確載入協定仍待核定 |
| method-ui-0.1-draft、目錄 methods、target.kind=method | component-ui-0.1-draft、目錄 components、target.kind=component | 尚未實作的設定描述協定同步改名 |

`module_type`、`implementation_version`、`config_type`、`node_ref` 可在舊草案中查到。現行 Component 識別與版本見 [Descriptor 頂層欄位](04_component_descriptor.md#descriptor-fields)。W1 HTTP 錯誤定位使用 `module` 和 `path`。 [Runtime 錯誤格式](06_runtime_api_and_deployment.md#runtime-http-errors)

Python 的 method／`@classmethod`／abstract method、HTTP method，以及融合 Config 中表示演算法的 `method` 保留原義。Prototype 仍使用部分 `method` 選擇欄位，屬明確標示的待遷移草案；不是新 Component Registry 的 component_id。正式 Config 遷移由 Q-002／Q-015 處理，需按格式版本明確映射與檢查衝突，不能全域替換所有 method 或宣稱 Runtime 已接受舊別名。

Engine手冊／Engine／Descriptor 手冊 檔名同步使用 components／component，所有文件內引用更新；歷史敘述中的擴充單位採現行術語，原決策日期與功能狀態保留。L1 的 MMD／SVG／PNG 同步改標籤並保持既有版面與連線；Prototype 的實際介面及內部欄位留待 UIB-010 遷移。

## 7. 優先討論順序

優先對齊批次 Request、Document、Remote I/O 與有效設定，再收斂部署及執行細節。

| 建議順序 | 主題／Q-ID | 這輪需要收斂什麼 | 建議產出 |
|---|---|---|---|
| 1 | 最小完整 System Config 與環境綁定／Q-002、Q-015 | component_id／版本／parameters／服務引用如何放在 D，E 如何提供連線及 Runtime 設定；不把完整 Descriptor 複製進 Config | 一份可人工閱讀的 Elasticsearch Config，及切換 Remote Parser 的對照；機器 Schema 再按核定內容產出 |
| 2 | User Remote API／Q-022、Q-028 | 邊界驗證、呼叫失敗與認證解析 | 完整 Remote 連續區段範例 |
| 3 | Component SDK／Context 與資源生命週期／Q-002、Q-017、Q-020 | B 的 run(input, config, context)、初始化／關閉、Resolver 取得正確 System Client／IndexBinding、有狀態實例的作用範圍 | 一組 Local Parser／Remote Adapter 的 SDK 示意與契約驗收；不為每個 System 組裝專屬 Flow |
| 4 | 資料更新／索引讀寫與恢復／Q-007～Q-015 | 來源版本傳遞、失敗清理與 Remote unknown、ES mapping、Filter／融合的可驗算規則 | backend 更新／清理與管理操作的具體約定；沿用完整覆寫、不續跑、無查詢讀寫鎖等已確認方向 |
| 5 | 最小可執行技術與驗收基線／Q-001、Q-003、Q-004、Q-011、Q-026 | 具體框架／套件版本、可實測模型 API、Tokenizer／搜尋實作與測資；既有 M1 範圍不重新擴張 | Structured JSON／Recursive／Dense／Elasticsearch 的真實 ingest→query，以及成功、失敗與多 System 隔離驗收 |

優先用第 1 項完整 Config 驗證第 2～3 項是否足夠串接，再依 M1／M2 所需的第 4～5 項收斂。Builder 管理 API／動態 UI、AI 助手與 Export／部署仍依既有 M4～M7 階段補齊。技術與驗收基線可平行準備，不要求等整張待決清單全部關閉才開始受限的 M1 開發。

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

目前交付包含 01～08 主責手冊、W1 開發索引、JSON Schema、契約範例與離線驗證器、Prototype 及架構圖。Ingestion 使用共用 `Document`，Inference 候選為 `ResultItem.data`。見 [共用資料契約](02_data_contracts.md)。

- 資料驗證：[System Config／Descriptor](../examples/system_config/README.md) 與 [Document／Remote API](../examples/user_remote_api/README.md)。[測試入口](../tests/README.md)另列 UI prototype 回歸。
- Parser 對照：現行映射與驗收界線見 [資料契約](02_data_contracts.md#data-flow)；舊版供應者對照／試驗保存在 history/superseded，不等同目前契約的完整 Parser 驗收。範例通過不表示已交付 Engine Component。
- 原型能力、提案與後端整合進度見 [Builder UI／Backlog](07_builder_ui.md#src-10-1-已完成的原型能力)。
- 優先決策：正式共用契約／SDK、模型與 Tokenizer、ID／更新／發布政策，再按 M0～M7 推進。D-53 的 Chunk 後模板組合與額外原文 Chunk 已確認需求，尚待實作及凍結具體設定格式，見 [資料契約](02_data_contracts.md#data-flow)。

<a id="w1-contract-readiness"></a>
### W1 開發基準與待決邊界

Builder 可按 [W1 開發契約索引](09_w1_builder_runtime_contract.md) 實作表單、API Client 與 Mock。本機 Mock 透過 HTTP 重播 Catalog、Config 預檢與發布、匯入與查詢，以及分開部署、切版、取消和逾時重匯。正式 Runtime、ES 和模型由 DEV 串接驗收。

| 要進入的開發範圍 | 還需要定清楚的契約 |
|---|---|
| DEV 正式接線與授權 | HTTP Client 可依 [OpenAPI](../openapi/runtime.dev.v1.json) 使用各路由指定的 Basic 帳密及 `X-Request-Id`。仍需定 Builder 啟動設定的機器格式，並完成部署 Secret、Istio 及 Gateway 的實機接線。見 [Q-019](#q-019) 和 [Q-020](#q-020)。 |
| 管理操作復原 | Builder 使用既有 GET、`reload` 和每 60 秒的補載查核，並自行配置有限重試及失敗回報。Runtime 管理操作結果的保存期限、過期查核及多目標發布部分成功時的回退策略仍待議。見 [Q-019](#q-019) 和 [Q-020](#q-020)。 |
| 跨 Query 合併的發布與執行 | Query Transformation 位置與多 Query 必須啟用已確認。內建 Rewrite 的 [發布格式](05_system_config.md#inference-result-processing)可供 Builder 開發，Remote 節點設定及 M2 真實執行驗收見 [Q-014](#q-014)。 |
| 模型服務發布與 PLED ES 接線 | 模型服務仍需確認環境綁定及 Profile。PLED ES 已定三個輸入與 Secret，實際 `es_number` 到服務的解析方式及登入流程由 PLED 整合驗收。見 [Q-003](#q-003)、[Q-021](#q-021) 與 [參數適用範圍](04_component_descriptor.md#component-parameter-scope)。 |
| Variable 與 Secret | [System 設定](05_system_config.md#system-secret)已定義 DEV 測試值、部署注入與 Module 引用；實際 Builder／Runtime 串接依 [Q-021](#q-021)／[Q-028](#q-028) 驗收。 |
| 真實 Ingestion 的識別與追溯 | W1 Mock 可帶明確 `document_id` 並模擬候選的 `data_id`。來源版本可省略或原樣保留字串及 `null`。識別規則已定，真實 Chunking、Remote 唯一性及 ES 覆寫依 [Q-007](#q-007) 驗收。 |
| Runtime 重新啟動後沿用既有 ES 索引 | [指紋 v1](06_runtime_api_and_deployment.md#index-fingerprint-v1-proposal) 已有 JSON Schema、序列化規則和可驗證範例。既有索引遷移與實際 ES 整合依 [Q-015](#q-015) 驗收。 |
| 多個 Runtime 共用同一 System 的 ES 索引（DEV 列為後續） | 以實際 ES 驗證 [Pod 內整批受理](06_runtime_api_and_deployment.md#pod-local-ingestion-control)、取消與首次寫入競爭、逾時重匯及舊批次清理。另驗證獨立的 Inference Pod 可讀同一索引，以及管理操作遵循 [System 排空條件](06_runtime_api_and_deployment.md#system-ingestion-drain)。 |
| FTEST／ENT 獨立部署 | Export 的設定載體、服務與探針接線、索引不存在時的建立入口及滾動切換順序。見 [Q-021](#q-021)。 |

歷史決策來源、過時提案、驗證及校對過程集中於 [history/](history/README.md)，包括 D-01～D-68 的來源與演變。現行待決事項依 Q-001～Q-028 與各項 SC 的最新說明追蹤。跨 Pod 文件鎖見 [Todo Enhance](todo_enhance.md)。
