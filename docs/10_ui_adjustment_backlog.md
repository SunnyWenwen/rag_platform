# 10 — UI Prototype 狀態與調整 Backlog

2026-11-03｜Prototype v0.12。這份清單以目前程式及測試為準，取代舊 Generation／歷史推論物件的 UI 待辦。主檔：[01_ui_prototype.html](../01_ui_prototype.html)。

## 1. 已完成的原型能力

單一 Workspace／Group 主畫面，Create／Edit 共用設定介面，提供 Ingest、Inference、檢索 Evaluation、Export。全部為瀏覽器記憶體內操作，重新整理重設；沒有真實 Engine、模型、DB、Registry、服務健康探測或部署控制器。

- 舊版 Document Schema 編輯、CSV column 映射、單筆 IngestionDocument API 範例與平面 ParsedDocument.units；D-67 的 Parser 驅動規格尚待 UIB-021。
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
| UIB-021 | Descriptor 驅動 I/O 資料規格與逐層相依 | D-67 新增，僅文件／待實作；取代獨立全域 Document Schema，見文末 |

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

內建 Chunker 的示例可讀 metadata.chunking_mode="passthrough"，逐 Unit／task 完整轉 Chunk；預設無提示時正常切分。D-67 目標是在適用 Parser／Component 的資料規格與參數中宣告此字串，CSV 映射到 metadata；現有 Prototype 仍用舊 Document Schema，待 UIB-021 調整。這不是任意 Config／ACL 覆寫；其他 Component 的支援由其宣告決定。

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

現行驗收要求與未完成整合如下；歷次瀏覽器／契約驗證結果見 [歷史驗證紀錄](history/validation/2026-11-03_prototype_v0.12.md)。

- [ ] 真實 SDK／Config Schema／Registry 與 12 的完整動態 UI 協定。
- [ ] 真實 Tokenizer、Parser／Resolver、多 Parser 路由、Embedding／ES／Rerank API 與品質驗收。
- [ ] 真實 Image 啟停／健康狀態／失敗清理、Secret／儲存隔離、正式 FTEST／ENT Export。
- [ ] 真實 AI 助手 API、目錄／Draft 版本一致性；UIB-007／008 先決策再實作。

這些未完成工作不阻止展示已確認的 UI 設定流程，但不可當作 Engine／部署里程碑完成證據。後續需求先記文件；使用者要求改 UI 時再更新原型。

<a id="uib-021-index-binding"></a>
## UIB-021：D-55 單組 IndexBinding／索引格式配對（已確認，待改 UI）

- [ ] 保持每 System 一組索引，不增加 index_ref、多組選擇或資源引用填寫表單。
- [ ] 讀取 Runtime 已驗證的 artifact_type／target／全文／Filter／向量能力；展示可用欄位，失效引用保留並報錯。
- [ ] Retrieval 候選依支援的索引格式／版本停用不相容項，顯示原因；僅有相同 JSON 外層不足以接線。
- [ ] Binding 與 target 為唯讀交接資訊，不把 RunContext、Client、Secret 或 Runtime searchable 狀態當使用者參數。
- [ ] 正式串接後 Create／Edit／AI／匯出共用驗證，SDK／HTTP 拒絕未宣告能力；目前 mock 不算真實後端驗收。


<a id="uib-022-runtime-ingestion-status"></a>
## UIB-022：D-56 非同步 Ingestion／文件狀態與 Runtime 控制（已確認，待改 UI）

- [ ] API 說明呈現 202 僅代表接收，顯示 run_id 及可用的狀態查詢入口；精確 Batch 路徑／Envelope 待 21 核定。
- [ ] 依文件顯示 queued／running／completed／failed／unknown 與可知 Module／錯誤；Batch 顯示逐文件結果，不以固定計時器假造進度。
- [ ] 同文件 queued／running 時顯示忙碌原因，不重複提交；完成／失敗後才可重新覆寫。
- [ ] Runtime 重啟／紀錄消失時顯示 unknown 並結束無止境輪詢，不憑舊索引或 Builder 舊畫面宣稱本次已成功。
- [ ] Ingestion Queue 額滿、Inference Rate／併發／Timeout 有可理解提示；不在每次文件／Query 表單加入環境上限設定。
- [ ] 區分文件工作狀態、索引是否可查與 Runtime Health；Local／Remote 的未知結果不冒充可安全重試。


<a id="uib-023-document-management"></a>
## UIB-023：D-58 統一 List 與文件管理 API（API 方向確認，UI 待規劃）

- [ ] Ingestion API 說明與產生的 payload 改為非空 List，單份亦包 List；CSV 逐列映射仍產生單份 IngestionDocument，再組合提交。
- [ ] API 說明區分工作狀態與實際文件存在／ID 清單，retire 是直接刪除，不是取消工作或保留資料的停用。
- [ ] 文件 ID 清單／存在查詢／retire 在 UI 的操作位置、分頁、確認與錯誤呈現，待需求及 21 的精確介面對齊後規劃；本輪不先實作面板或刪除按鈕。
- [ ] 需由 Runtime／backend 實際查詢及刪除，不用前端記憶體列表或 Ingestion 成功紀錄假裝資料來源。


### D-60：讀寫並行與暫定驗證方式補充

- [ ] 不因有 Ingestion／retire 寫入就禁用 Inference 或顯示等待讀寫鎖；索引實際未就緒／限流／錯誤仍按 Runtime 回應呈現。
- [ ] API 說明暫採單一 Basic 帳密操作全部 Runtime API，憑證不寫進業務 payload；不因此新增 Builder 登入或角色權限 UI。
- [ ] 更新期間 Query 可反映不同時點的資料，不在 UI 宣稱原子快照；同文件 queued／running 重複提交仍保留忙碌提示。


### D-63／D-64：設定啟用、刪除結果與錯誤補充（待改 UI）

- [ ] 設定可保存草稿，但該 System 有 queued／running Ingestion 時不啟用新版；工作結束後才允許套用，不影響其他 System，也不因此禁用 Query。
- [ ] API 說明將 retire 更新為同步 200，顯示 deleted／not_found 的不同結果；忙碌文件顯示 409，後端異常不冒充不存在／成功。UI 刪除按鈕與確認流程位置仍待規劃。
- [ ] 工作失敗呈現 status=failed、module 與 error；HTTP 請求錯誤讀取 error 外框，驗證位置使用 path。兩者不混同，Runtime 記錄失效仍顯示 unknown。
- [ ] API／部署說明引用 22 的 Runtime 可調參數，不在單次業務表單加入環境上限或 Admin 控制頁。
- [ ] System 操作使用穩定 system_id；不將名稱、Config Revision 或 document_id 當成該識別碼，也不在業務 body 塞入整份 Config。


### D-65：文件摘要清單（UI 位置仍待規劃）

- [ ] API 說明將文件清單回應更新為 documents[]＋next_cursor，每筆顯示 document_id／source_revisions[]，不再只列 document_ids[]。
- [ ] 來源版本取實際儲存；多版可代表更新中／失敗後混合，不將其標為成功歷史或自行挑選最新。最近工作結果仍使用 ingestion-status。

沿用 UIB-023，不新增文件內容、版本回復或清理按鈕。分頁參數與實際面板位置後續整理；本輪未修改 Prototype。


### D-66：System Config 整合草案（先記錄，待討論／改 UI）

- [ ] 正式 Config 定稿後，將目前 Prototype 短名稱映射到核定的 Component 引用、profiles／tasks 與結果處理位置；不直接將 mock Descriptor／Manifest 當成最終規格。
- [ ] UI Draft 保留停用選擇；Engine 編譯出有效參數／引用並做共同驗證，錯誤仍以 Module／欄位定位。具體正規化與 Hash 依 23 的 SC-08 討論。
- [ ] Runtime 限制、URL／Secret／實體目標在 E 的資源／部署區處理，模型語意與演算法參數留 D；不增加每次 Request 任意覆寫或一般 User 的 Admin 控制頁。

分頁精確參數、實際文件管理面板位置及 System Config 遷移仍依 21～23／SC 決策；原型未接通真實服務。需求先記待辦，收到改 UI 指示後再實作。逐輪文件整理說明見 [歷史 UI 記錄](history/changes/ui_backlog_notes.md)。

<a id="uib-021-io-schema-refinement"></a>
## UIB-021：Descriptor 驅動 I/O 規格與逐層相依（D-67）

2026-11-05｜**待實作，本輪不改 Prototype。**責任與六類宣告能力以 [24](24_component_io_schema_refinement.md) 為準；[25](25_component_descriptor_schema_draft.md) 提供可重複 A→B 表單／路徑等具體候選，尚未核定 Meta-schema／API，不以離線範例當正式 Renderer。

- [ ] Create／Edit 取消要求先填獨立全域 Document Schema；在 Parser 設定顯示當前輸入／輸出欄位摘要。
- [ ] 僅在 Parser 開放此能力時顯示資料欄位定義／映射與 metadata 限制；固定輸出不重複填寫。
- [ ] 透過 Engine 同一份解析結果連動 Parser→Chunker→Embedding→Indexing→Retrieval 的候選／停用原因；不硬編碼第二套規則。
- [ ] 支援首版固定、命名、清單映射、copy、條件分支、固定型別衍生欄位的規格顯示；未知必要規則明示不支援。
- [ ] 上游改名／移除／條件切換時保留失效值並定位報錯；防止過期目錄／解析回應覆蓋最新草稿。
- [ ] 多 Parser／多任務顯示分支與欄位可用性；Sample 僅供建議／確認，不以第一筆／候選聯集作為全體保證。
- [ ] Create／Edit／AI Diff／CSV 映射／驗證／有效匯出共用 Component 參數與推導規格；舊原型 documentSchema 草稿的遷移方式另定，不冒充正式 Config。
- [ ] API 說明區分 202 前可完成的共用＋Parser 預檢與背景實際內容驗證；提供 Local／Remote 同等宣告與錯誤示例。
