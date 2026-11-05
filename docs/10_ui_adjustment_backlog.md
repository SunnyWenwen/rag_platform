# 10 — UI Prototype 狀態與調整 Backlog

2026-11-03｜Prototype v0.12。這份清單以目前程式及測試為準，取代舊 Generation／歷史推論物件的 UI 待辦。主檔：[01_ui_prototype.html](../01_ui_prototype.html)。

## 1. 已完成的原型能力

單一 Workspace／Group 主畫面，Create／Edit 共用設定介面，提供 Ingest、Inference、檢索 Evaluation、Export。全部為瀏覽器記憶體內操作，重新整理重設；沒有真實 Engine、模型、DB、Registry、服務健康探測或部署控制器。

- Document Schema、CSV column 映射、單筆 IngestionDocument API 範例與平面 ParsedDocument.units。
- Fixed-size／Recursive／Header-aware 的配置、Tokenizer 連動、預設 text／進階多欄位任務，metadata 繼承。
- 全部 Chunk 內容預設保存；全文、向量、Filter 能力分開，失效欄位保留並報錯。
- 推論 QueryContext[]／filters／metadata、兩層融合與四處 Top N；可以回多份分組清單。
- 選填 _rag；Embedding 欄位模板；複製原文欄位與額外原文 Chunk 的獨立設定。
- 內建、Developer Local、已註冊 Remote 的模擬目錄；依描述產生簡單參數表單，連續 Remote Pipeline 鎖定涵蓋模組。
- AI 助手依本機規則產生 Diff，套用前驗證／過期草稿檢查；沒有 LLM 呼叫。

<a id="6-v09-實作細節展示預設與限制"></a>
## 2. 結果處理與有效設定

Retrieval 進階設定預設收合；同 Query 多路、跨 Query 合併預設勾選，時機預設 Retrieval 後，各自可改為 Reranker 後。ES 已內部融合時停用重複融合；單 Query／單路保留草稿意圖。預設平台 RRF，ES 內部預設 Sum Score。權重／RRF k 僅對有效策略驗證。

| 位置 | 作用範圍 |
|---|---|
| Retrieval 搜尋 Top K | 每 Query／每路；ES Hybrid 為每 Query 的一份輸出 |
| Retrieval 後合併 Top N | 該時點處理後的每份清單 |
| Reranker Top N | 每份模型評分清單，預設 3 |
| Reranker 後合併 Top N | 後置處理後的每份清單；None 不取消必要合併 |

ResultSet.key 對應 Config 路徑／群組；items 位置即名次。RRF 可用無 score 的有序結果；Sum Score 需完整且可比分數。Prototype 的推導器只計算流程與候選上限；mockRetrieval 用固定示意候選，不真的搜尋、融合或評分。畫面說明與計畫獨立於 QueryContext JSON，不新增外框或歷史記錄。

原始 Draft 保留停用參數；effectiveConfig 排除它們。Create／Edit／AI 套用／匯出使用同一驗證入口。取消不改已存 System；純 Inference 改動只使舊示意結果失效，Ingestion 模組有效改動提示重跑 Ingestion。

<a id="ui-backlog-pending"></a>
<a id="uib-010-component-catalog"></a>
<a id="uib-011-ingestion-parser-routing"></a>
<a id="uib-013-chunk-contract"></a>
<a id="uib-014-flat-units"></a>
## 3. 累積需求處理狀態

「原型完成」只代表配置／互動／模擬預覽，不代替真實功能驗收。

| 編號 | 需求 | v0.12 狀態 |
|---|---|---|
| UIB-001／002 | Fixed-size 及 Tokens 說明 | 原型已完成；真實 Tokenizer／切分待 Engine |
| UIB-003 | AI 助手串接 M4 核心／API | 待後端整合；目前明示本機規則 |
| UIB-004 | Diff、驗證、套用、取消與過期回應 | 本機模擬完成；真實非同步 API／版本一致性待整合 |
| UIB-005／006 | 全 Chunk 保存、metadata 全繼承 | 原型已完成；儲存 Adapter 待實作 |
| UIB-007／008 | Rewrite 統一生成設定／真實測試與結構化輸出 | **討論提案，尚未核定；未藉本輪實作為既定需求** |
| UIB-009 | Generation 自訂輸出 | D-50 取消 Generation，關閉此待辦 |
| UIB-010 | Component Descriptor 動態表單 | 模擬目錄及基本 Schema／UI hints 表單已完成；完整 12 協定／版本回應及真實 Registry 待整合 |
| UIB-011 | JSON API／多 Parser 自動派送 | 三來源 API 說明、CSV／JSON／明確 Units Adapter 已有；二進位 resolver、能力派送及衝突政策待真實 Parser |
| UIB-012 | text-spans／page-blocks 舊分類 UI | 已由 UIB-014 取代，刪除舊工作項 |
| UIB-013／014 | Chunk 任務及平面 Units | 原型已完成；實際切片／來源追溯仍依 Component |
| UIB-015 | Retrieval 命名與結果呈現 | 已完成；取消 Generation 與強制單清單 Gate |
| UIB-016 | Remote Service／連續 Pipeline | 原型配置／鎖定／部署計畫完成；真實服務管理待後端 |
| UIB-017 | KISS 選填追溯／metadata 提示 | 原型完成；不捏造 _rag；真實 Component 自行支援 |
| UIB-018 | Embedding 前欄位模板 | 字串替換／驗證／Picker／預覽／有效匯出完成；模型 Token 上限仍待真實 Tokenizer |
| UIB-019 | 額外原文 Chunk | 控制、獨立 copy、每 Unit/task 去重示例及變更影響完成；真實切分待 Engine |
| UIB-020 | 簡化推論 Contract | D-54 本輪完成：root QueryContext[]，含 filters／metadata；無歷史物件 |

<a id="uib-010-component-selection"></a>
## 4. Component 與 Remote 的原型範圍

模擬目錄包含內建 Component、Developer Paragraph Chunker、Remote 單模組、Parsing→Chunking→Embedding Image Pipeline、Query Transformation→Retrieval→Rerank External Pipeline，以及不可用服務／缺少相容 Retrieval 的 Indexing 案例。可選服務由程式內固定的 Descriptor／Manifest 示意提供，**不是已核定的 Manifest Meta-schema**。

表單支援 string／integer／boolean／enum、預設值、基本限制與 advanced 分組；不執行 Developer 前端腳本。版本失效保留引用並報錯。完整 field_picker／service_picker、多版本回應、required_ui_features 及 12 的全部驗收案例仍待正式 Registry／Engine，不宣稱本機目錄等同完整 Renderer。

<a id="uib-016-remote-service-pipeline"></a>
整段從第一個 Module 選；被管理模組保持可見且鎖定，本地設定不進有效計畫。重疊選擇報錯，切回內建恢復原草稿。缺少相容 Retrieval 的 Remote Indexing 以停用原因顯示，不只因 JSON 同形就放行。一般 User 不填 Developer Service URL／Path／Header；既有模型／ES／MongoDB BYO 資源表單照常保留。

Image Export 示意附每 System 的 Deployment／Service／參數 ConfigMap／健康檢查與資料綁定引用；External 只有管理者提供的目標環境 endpoint_ref，不輸出該服務的 Deployment。Image、Endpoint、資料綁定都是 placeholder，沒有建立 Pod／Volume 或隔離真實資料。服務狀態一律標示模擬；外部服務可共用其既有資料，第一版不新增 data_space_id 或 shared 開關。

<a id="uib-017-optional-provenance"></a>
## 5. 選填追溯與文件提示

內建預覽預設沒有 _rag，不以缺少 source_refs／fingerprint／ordinal 阻擋儲存或執行。Component 未提供來源就不捏造。Chunk.metadata._rag 保留為選填擴充；ResultItem 不另帶分數血緣，流程診斷交 Logs。

內建 Chunker 的示例可讀 metadata.chunking_mode="passthrough"，逐 Unit／task 完整轉 Chunk；預設無提示時正常切分。請在 Document Schema 宣告此字串，CSV 映射到 metadata。這不是任意 Config／ACL 覆寫；其他 Component 的支援由其宣告決定。

<a id="uib-018-embedding-composition"></a>
## 6. 欄位組合與原文 Chunk

| 功能 | Prototype 草案設定 | 行為 |
|---|---|---|
| 模板組合 | embedding.composition.enabled／template／output_field | 預設關閉；產生獨立 fields.embedding_text；固定文字＋fields.* 字串變數 |
| 向量來源 | embedding.mappings | 明確選 embedding_text→vectors.text，source_field 記 embedding_text |
| 原文欄位 | chunking.preserve_original | 預設單任務複製到 original_text；進階任務自行 copy，避免重名 |
| 原文 Chunk | chunking.include_original_chunk | 每 Unit／task 額外一筆完整來源；相同完整片段已存在就不新增 |

欄位組合在預設 Embedding 的前處理，不新增 Module。模板缺變數、來源非字串、缺欄位、語法錯誤或輸出撞名時阻止保存／樣本預覽；不執行 Python／LLM。衍生欄位出現在 Embedding／全文 Indexing／Filter／Rerank Picker。關閉保留草稿但不進有效設定；有效改動需重新 Ingestion。

<a id="uib-019-original-chunk"></a>
兩頁示例為 7／15 字元，每 10 字元、overlap=0：關閉 3 筆、開啟 4 筆，短頁不重複。不同 Unit／task 不互相去重，也不跨 Unit 合併。完整原文走同樣的模板、Embedding、Indexing；真實 Component 必須驗證最終模型輸入長度，包含 Profile 前綴／特殊 Token。**原型只做字元教學示例，不計算真實 Token，也不宣稱零向量有效。**

## 7. 驗證與剩餘整合

回歸測試涵蓋既有設定／DOM、QueryContext 新 JSON、模板／重名、原文 3／4 筆、passthrough、Component 參數／失效版本、Remote 覆蓋／重疊／Export 差異、Save／Cancel／AI Draft。Chromium 153.0.8010.0 已通過 1440×1000 桌面及 390×844 手機互動／水平溢出檢查，無頁面 JavaScript 錯誤；已實際檢視桌面模板、Remote 鎖定及手機畫面。

- [ ] 真實 SDK／Config Schema／Registry 與 12 的完整動態 UI 協定。
- [ ] 真實 Tokenizer、Parser／Resolver、多 Parser 路由、Embedding／ES／Rerank API 與品質驗收。
- [ ] 真實 Image 啟停／健康狀態／失敗清理、Secret／儲存隔離、正式 FTEST／ENT Export。
- [ ] 真實 AI 助手 API、目錄／Draft 版本一致性；UIB-007／008 先決策再實作。

這些未完成工作不阻止展示已確認的 UI 設定流程，但不可當作 Engine／部署里程碑完成證據。後續需求先記文件；使用者要求改 UI 時再更新原型。

### 2026-11-03 驗證紀錄

- Pydantic 12 項、Chunk 10 項通過；ParsedDocument 6 個正例／12 個反例通過；五份 Inference JSON 通過新版共用 Schema。RRF 以陣列名次驗算，舊 wrapper 明確拒絕。
- 既有 56 項 Prototype、23 項結果處理、5 項 Schema UI 檢查通過；DOM 回歸及新增 12 組 v0.12 流程通過。
- Chromium 真實互動涵蓋 Create／Edit／取消、CSV 映射、QueryContext 呈現、API 說明、Export、欄位模板、原文 3／4 筆示例、Remote 鎖定／External 固定設定，以及手機版面。Source SVG／MMD／PNG 已同步 QueryContext[]，保留 03 原版型。
- 瀏覽器套件下載曾緩慢，補齊下載後以本地 Chromium 成功驗證；使用 Noto Sans TC 作中文畫面及圖檔輸出。測試可用既有 Playwright Chromium，或設定 CHROMIUM_EXECUTABLE 與選填 CHROMIUM_ARGS_JSON；外部套件未加入產品頁依賴。

以上為契約、瀏覽器配置與模擬操作驗證，沒有呼叫真實模型／DB／Remote API，也沒有建立 Pod 或發布服務。

<a id="uib-021-index-binding"></a>
## UIB-021：D-55 單組 IndexBinding／索引格式配對（已確認，待改 UI）

- [ ] 保持每 System 一組索引，不增加 index_ref、多組選擇或資源引用填寫表單。
- [ ] 讀取 Runtime 已驗證的 artifact_type／target／全文／Filter／向量能力；展示可用欄位，失效引用保留並報錯。
- [ ] Retrieval 候選依支援的索引格式／版本停用不相容項，顯示原因；僅有相同 JSON 外層不足以接線。
- [ ] Binding 與 target 為唯讀交接資訊，不把 RunContext、Client、Secret 或 Runtime searchable 狀態當使用者參數。
- [ ] 正式串接後 Create／Edit／AI／匯出共用驗證，SDK／HTTP 拒絕未宣告能力；目前 mock 不算真實後端驗收。

本輪只同步文件／契約範例；Prototype v0.12 不變。規格見 19，Registry／動態 UI／真實服務整合仍在既有待辦。


<a id="uib-022-runtime-ingestion-status"></a>
## UIB-022：D-56 非同步 Ingestion／文件狀態與 Runtime 控制（已確認，待改 UI）

- [ ] API 說明呈現 202 僅代表接收，顯示 run_id 及可用的狀態查詢入口；精確 Batch 路徑／Envelope 待 21 核定。
- [ ] 依文件顯示 queued／running／completed／failed／unknown 與可知 Module／錯誤；Batch 顯示逐文件結果，不以固定計時器假造進度。
- [ ] 同文件 queued／running 時顯示忙碌原因，不重複提交；完成／失敗後才可重新覆寫。
- [ ] Runtime 重啟／紀錄消失時顯示 unknown 並結束無止境輪詢，不憑舊索引或 Builder 舊畫面宣稱本次已成功。
- [ ] Ingestion Queue 額滿、Inference Rate／併發／Timeout 有可理解提示；不在每次文件／Query 表單加入環境上限設定。
- [ ] 區分文件工作狀態、索引是否可查與 Runtime Health；Local／Remote 的未知結果不冒充可安全重試。

本輪只更新文件／Backlog，Prototype v0.12 不變。D-57 已確認 Run partial、未知紀錄 HTTP 200 與整批預檢；工作狀態精確欄位、統一 List 提交／retire 語意等仍待核定。Retire API 列首期必要，UI 操作另盤點；首期不做工作取消，不新增管理 UI 或凍結動態 UI Meta-schema。
