# System Config、版本與變更影響

## 閱讀目錄

- [識別、版本、collection 與作用域](#src-05-2-識別版本與作用域)
- [草稿、有效設定與環境綁定](#src-05-6-config-結構與有效設定)
- [設定與執行資料的對照](#src-05-7-共用契約與設定的對照)
- [變更影響與重新 Ingestion 的範圍](#src-05-8-config-變更影響矩陣)
- [這次要定義什麼](#src-23-1-這次要定義什麼)
- [共同骨架初版](#src-23-2-共同骨架初版)
- [D-66 歷史案例與待同步範圍](#src-23-3-d-66-歷史案例與待同步範圍)
- [驗證順序與目前驗證範圍](#src-23-4-驗證順序與目前驗證範圍)
- [需要討論的選擇與建議](#src-23-5-需要討論的選擇與建議)
- [本稿未改變的決策](#src-23-6-本稿未改變的決策)


更新：2026-11-05。本手冊是 D 的唯一設定整合草案。先討論 B 的 Descriptor 核心，再完成 SC-01～SC-10；D 保存 ID／版本／參數，不內嵌完整 Descriptor／Manifest，也不新增獨立頂層 document_schema。

Schema 的 contract_version、某份設定的 config_revision、Component implementation_version、文件 source_revision 與索引資料版本是不同概念。實際 URL／Secret／實體目標及 Runtime 控制屬 E，不混入演算法參數。

<a id="identity-versions"></a>

<a id="src-05-2-識別版本與作用域"></a>
## 識別、版本、collection 與作用域

版本概念的正式定義見 [架構與責任](01_architecture.md#src-03-31-系統組成與管理階層)。下表是對應的欄位用途與未決實作政策；其中 source_revision 指匯入 Retrieval 的來源文件內容，不是本 repository 的 Markdown 規格版本。

| 欄位／概念 | 語意 | 狀態 |
|---|---|---|
| workspace_id／system_id | Workspace → System；System 的邏輯識別跨環境不因部署設定不同而另改 Config，授權由可信 Context 決定 | 階層／邏輯方向已確認；格式與部署識別待決 |
| document_id | 同一 System 中邏輯文件的穩定識別，不能用 Chunk ID 取代 | 已確認；產生演算法 Q-007 |
| source_revision | 文件內容版本，與 Config Revision 不同 | 已確認；省略時的生成／比較 Q-007 |
| chunk_id | Component 產生必要非空識別；fingerprint／ordinal 的可重現衍生 ID 是選用參考工具 | D-52 不強制共同 Hash 演算法；穩定／更新語意 Q-007 |
| config_revision | 平台保存的設定版本 | 已確認；草稿／生效語意 Q-015 |
| index_generation | 可追蹤的索引資料版本，不能把可變 alias 當 immutable snapshot | 已確認方向；切換 Q-010／Q-015 |
| contract_version | 資料／Config 契約版本 | 建議；遷移 Q-002 |
| run_id／request_id／trace_id | 批次工作、單次請求及追蹤識別 | 已確認方向；線上包裝 Q-019 |

CSV 每列是邏輯文件。跨批更新需映射穩定鍵；Prototype 的批次自動 ID 不能宣稱可跨次穩定。檔案拆為多份文件時保留來源資產關聯，不能讓所有列沿用同一 document_id。

<a id="src-05-21-版本變更範例與規則"></a>
### 版本變更範例與規則

以下用同一 System 的兩份來源文件 A／B，示範 03 定義的三種業務版本如何分別變動：

| 成功完成的變更 | 文件 A／B | Config Revision | 索引資料版本 |
|---|---|---|---|
| 初次匯入 | A:v1、B:v1 | C1 | I1 |
| A 原文修改並成功更新索引 | A:v2、B:v1 | C1 | I2 |
| 原文不變，改 Chunk Size 並重建 | A:v2、B:v1 | C2 | I3 |
| 只改 Query Rewrite Prompt | A:v2、B:v1 | C3 | 仍可沿用 I3 |

以上 I1～I3 是說明概念的識別，不是已選定快照實作。即使 source_revision 不變，重切／重新 Embedding／索引重建也可能形成新索引資料版本；新文件尚未成功發布時，不能先把現有索引說成已含新版內容。兩者不一對一。

不同環境的資料可不同，故相同 Config 不保證 index_generation／文件集合相同。是否保留實體不可變快照、何時生成 ID 與原子切換仍由 Q-010／Q-015 核定；此處不新增已完成的版本管理承諾。

<a id="src-05-22-collection-命名已確認方向"></a>
### collection 命名（已確認方向）

Builder 由 Workspace＋Retrieval System 名稱自動產生邏輯 collection，使用者不用手填。既有實作附穩定 System ID，避免同名及正規化碰撞；建立後改顯示名稱不重命名既有目標。UI 的邏輯名稱唯讀；各環境的 DB／實體索引目標由部署綁定及 Adapter 管理，不因實體目標不同修改處理 Config。正規化演算法、長度與匯入既有集合的權限規則仍屬 Q-007／Q-019，不重開「是否自動命名」的方向。直接 Engine 則使用 Config／可信 Binding 中明確的集合，不依賴 Builder 才可運作。

<a id="config-spec"></a>

<a id="src-05-6-config-結構與有效設定"></a>
## 草稿、有效設定與環境綁定

<a id="src-05-61-config-與部署設定的契約邊界"></a>
### Config 與部署設定的契約邊界

名詞定義及跨環境原則見 [架構與責任](01_architecture.md#src-03-31-系統組成與管理階層)。正式 Schema 需將邏輯設定與環境部署綁定拆開：前者保存方法、參數、Schema／欄位／Prompt、模型語意及邏輯引用，後者解析服務端點、Secret 引用、DB／實體索引與資源設定。

同一 System、同一 Config Revision 的邏輯設定跨環境一致。若要改處理方法、模型／維度／Encoding 等語意，需建立新 Config Revision 並依影響重建，不用環境覆寫掩蓋邏輯差異。不同環境仍需檢查實際模型 Profile 相容性。

原型曾把服務 URL／Secret 引用與 Pipeline 放在同一物件，需明確 migration。具體型別與檔案包裝 Q-002 未凍結，但分離方向已確認。依 03 的正式用語，正式契約不新增 Blueprint 領域物件；舊匯出型別／檔名的遷移見 Builder UI／Backlog手冊。

D-64：Runtime 的大小、Queue／並行、Rate、Deadline 及工作狀態保存設定歸 E，由 Admin／部署管理者控制，不混入每次業務 body 或 D 的演算法參數。初始預設與可調項集中在 [Runtime API／部署](06_runtime_api_and_deployment.md)；候選參數路徑與正式機器 Schema 不等同，尚未交付實作。

<a id="src-05-611-remote-pipeline-與固定服務"></a>
### Remote Pipeline 與固定服務

有效 Config 保存核可服務識別／版本與開放參數；連續範圍／邊界 Contract 由 B／C 推導，不在 D 重複維護；segments 的具體包裝仍是 SC／Q-028 候選。UI 使用第一個 Module 當入口，不因此在 Parser 私有 Config 複製整段設定。編譯時排除涵蓋 Module 的本地草稿，並拒絕重複／重疊執行。

服務 Manifest 與各環境 Endpoint／Secret／儲存綁定分開。演算法參數即使由啟動設定檔載入仍屬邏輯 Config；External 的固定模型／索引語意記入服務版本與相容資料，不把無參數表單當成無版本要求。第一版不加入 data_space_id 或 shared 開關，不修改 資料契約手冊／Inference Schema。External 固定資料空間由 Developer 管理，可能多 System 共用；平台管理的 Image 實例以啟動綁定分配獨立儲存範圍。詳見 [Engine／Component 開發](03_engine_and_components.md)。

<a id="src-05-612-文件-metadata-處理提示d-52"></a>
### 文件 metadata 處理提示（D-52）

metadata 不只供描述／過濾，也可傳遞 Component 明確約定的文件層提示，例如 chunking_mode=passthrough。遵守共用 Contract 及適用 Component 的 metadata 細節宣告／設定，並由 Component 說明鍵名、型別、允許值、缺省／未知值處理；不是任意參數都自動生效。固定演算法／模型／服務設定仍在 Config／環境綁定，不放 Secret 或授權指令。第一版不新增全域控制欄位／規則引擎；ParsedDocument 與 Chunk 根結構不變。見 [Chunk](02_data_contracts.md#src-15-1-共用物件)。

<a id="src-05-62-草稿有效-config-與部署綁定"></a>
### 草稿、有效 Config 與部署綁定

- UI Draft 保存基本／進階欄位及未啟用方法的草稿；不是所有欄位都參與執行。
- Effective Config 僅包含使用中的方法、參數、服務及欄位；AI 與手動入口共用編譯／驗證。
- 部署設定／環境覆寫只替換允許的連線／Secret／目標／運行資源，不修改 System 的邏輯 Config。
- 更換 Embedding 語意 Profile 不能當作純環境覆寫，必須重新 Embedding／Indexing。
- 使用相同服務的兩個模組引用同一 llm_ref；匯出只包含實際引用的服務。

整合初版集中見 [System Config：System Config Schema 草案](#src-23-2-共同骨架初版)：D-67 後候選根結構為 contract_version、llms、pipelines.ingestion／inference；資料規格由 Component 宣告＋Config 推導，不再獨立頂層 document_schema。先前 execution 名稱沒有凍結，不再作為同時包含流程與 Runtime 限制的模糊容器；結果處理計畫放 inference，Queue／Rate／Deadline 等依 D-64 歸 E／Runtime 控制手冊。Component 引用用 component_id＋implementation_version，由 Registry 取得 Descriptor.config_schema 驗證 parameters；不把完整 Descriptor／Manifest 複製進 D。System ID／Revision／IndexBinding 由可信管理與 Context 提供，完整型別／Profile／部署包裝仍待 SC 決策。

<a id="src-05-63-模組設定詞彙"></a>
### 模組設定詞彙

下表列出語意與設定責任；精確 Config 拼字仍待凍結。資料契約採用 資料契約手冊，切分計畫與欄位路徑層次見 [資料契約相關章節](#src-05-7-共用契約與設定的對照)。

| 模組 | 已確認語意 | 本版建議 Config 欄位 |
|---|---|---|
| Import | JSON IngestionDocument；三種來源共用外層驗證與內容取得 | 來源限制／resolver 政策；CSV 映射屬 Builder |
| Parsing | Structured JSON 預設；相容 Parser／Adapter 自動路由 | 已啟用 Component／profile、media_type／schema_id 能力、內容映射 |
| Chunking | Fixed-size／Recursive／Header-aware；預設 text、不選欄位；進階多任務／複製；metadata 全繼承 | split_field／output_field／copy 映射與有序 tasks 草案見 資料契約手冊；size／overlap／tokenizer 及有效方法參數，無 metadata_fields |
| Embedding | 預設 fields.text → vectors.text；命名向量包含 Profile 識別與來源欄位 | profile、mappings（source_field、output_name）；命名可設定，預設向量名稱 text |
| Indexing | 全部 fields／metadata 保存，搜尋與過濾另外選；持久化模式跨環境固定 | Component 選擇決定後端；parameters 保存 fulltext_fields、vector_fields、filter_fields、persistence／metric 等所支援參數；無 stored_fields，collection 在 E／Binding |
| Query Transformation | None／Rewrite／Multi-query | 共同 Component 引用＋自身 parameters，例如 llm_ref／prompt／count／include_original；1／N 統一表示仍是提案 |
| Retrieval／Fusion Plan | 選已索引欄位、推導模式；可配置策略及合併時點 | fulltext_fields、vector_fields、per_route_k、top_k、filters、fusion；stages／scope／placement 具體 Schema 待 Q-014 |
| Rerank | 新模型算分的方法；服務為 None／DEV／Rerank API | 共同 Component 引用＋所支援的 service_ref／內容欄位／提問來源；模型評分後保留數在結果處理，位置候選見 23，不與 Provider 的 top_n 混用 |
| ResultSet 後處理 | 去重＆合併／取 Top N／新模型算分；共同排序 | 分組、方法與參數的正式 Config Schema 仍待 Q-002／Q-014；最新 UI 原型配置見 Builder UI／Backlog手冊 |

Query Rewrite／Multi-query 的 1／N、Structured Output 與共用 LLM Adapter 提案保留，見 [Engine／Component 開發](03_engine_and_components.md#src-04-51-query-transformation)；取消答案生成及自訂答案 JSON 設定。

正式枚舉建議用 snake_case，UI 可顯示自然語言。Prototype 的 chunking.split、embedding.mappings[].source、indexing.filters、transform 等短名稱不自動視為正式 Schema；需明確 migration。Chunk 後的引用使用 fields.text／vectors.text／metadata.department；Chunking 來源用當筆 Unit 的 key，例如 text。上述拼字及預設值需 Q-002 核定，禁止同時接受未宣告別名而掩蓋錯誤。

ResultSet 是一次執行的資料；處理計畫是可保存的邏輯 Config，ResultSet.key 依 Config 路徑／群組解析，不再使用 runtime result_set_id。[資料契約相關章節](#src-05-7-共用契約與設定的對照) 對照設定與資料責任；Prototype 的 UI 配置 `retrieval.processing` 僅為展示草案，不表示正式 Engine Schema 已凍結。最新對照、有效配置與未完成邊界見 [UI Backlog](07_builder_ui.md#src-10-6-欄位組合與原文-chunk)；[Builder UI／Backlog](07_builder_ui.md) 整理現行兩層融合與四處 Top N 的 UI 對照。

<a id="src-05-64-參數與相依規則"></a>
### 參數與相依規則

| 條件 | 驗證 |
|---|---|
| Token Chunking | size 為正整數；overlap 為整數且 0 ≤ overlap < size；Tokenizer 可取得；Fixed-size 步長為 size−overlap，末塊不補齊；Header-aware 需要當筆文字的 Markdown 標題格式，不要求 heading Blocks |
| Embedding mappings | 來源為有效文字欄位；output_name 唯一；有限值、維度與 Profile 相容 |
| Indexing | 全部 Chunk.fields／metadata 保存；搜尋欄位與上游一致；必要識別／來源／ACL 強制保留；下游只需確認欄位存在、型別適合及已由 Chunking 保留，不再要求額外勾儲存 |
| Retrieval | 至少一路；每路及最終 K 為正整數；僅選已建立索引；Query Profile 由向量欄位繼承 |
| Fusion | 多 Query／多路需有明確計畫；UI 已支援同／跨 Query 各自選 Retrieval 後／Reranker 後，預設兩者勾選且在 Retrieval 後；只使用已選策略有效參數 |
| Sum Score | ES 內部 Hybrid 的預設策略；平台跨清單另可選 RRF／Sum Score。權重有限非負且使用中至少一個大於 0；可比性／轉換需顯式驗證 |
| RRF | rank 從 1；k 預設 60 且為正整數；k 與 Top-K 不同 |
| Rerank | None 不評分且不使用其 top_n，但保留必要後置合併；啟用時 top_n 為正整數、不強制 ≤ Retrieval K。四處輸出上限各自作用於對應動作；實際不足取可用數量，合併後數量可能增大 |
| Templates | 只允許宣告變數；單次替換；未知／必要變數缺少阻止保存 |
| LLM | 引用有效；刪除使用中的服務不得默默換另一個 |

純 BM25 可跳過 Embedding，但 Chunking 仍需 Tokenizer。複製欄位長度可能大於 Chunk Size，Embedding 必須逐項檢查實際輸入。Tokenizer、模型極限及溢位政策見 Q-004。

Fixed-size 的 separators／keep_separator／header_levels 保留在 UI Draft 時不參與 Effective Config、驗證或變更影響。方法名稱、size／overlap、有效 Tokenizer 及內容欄位屬執行語意；改變後需按 Ingestion 變更處理。視窗與來源位置規則見 [Engine／Component](03_engine_and_components.md#src-04-1-目標與依賴邊界)。正式 method 枚舉拼字仍待 Q-002，`fixed_size` 可作候選，不新增必須支援的別名。ParsedDocument 四鍵／Chunk 六鍵不變。

「全部保存／繼承」取代舊的使用者 stored_fields／metadata_fields 投影；原型短名稱 indexing.stored／chunking.metadata 仍待正式遷移，不直接作為新的有效配置語意。舊索引未保存或舊 Chunk 未繼承的內容不會憑空補回，必要時須重新 Ingestion／重建，不能只刪 Config 欄位就宣稱資料齊全。精確遷移與 Hash／Revision 細節留 Q-002／Q-015。

**融合配置的目標要求已存在，細節尚待 Q-014**：必須能區分演算法、融合範圍（同 Query／跨 Query）與執行時點（Rerank 前／後）。已確認兩層與預設 Retrieval 後合併；正式 Config／Adapter 支援範圍、route 型別及分數細節需再核定；不能把全部合併為一個 fusion.method 後宣稱符合需求。`fusion.stages[]` 是先前助理提出的 Schema 候選，尚非已定欄位。

<a id="src-05-7-共用契約與設定的對照"></a>
## 設定與執行資料的對照

三份資料 Schema 已有可驗證草案；完整 Engine Config／部署設定的根結構仍待 Q-002。以下列出設定責任，不提供混用 Prototype 舊欄位的完整 YAML。實際可驗證的有效切分計畫與輸出，引用 [Chunk cases.json](../examples/chunk/cases.json) 的 effective_spec／chunks。

| 設定位置 | 設定內容 | 驗證時點／下游結果 |
|---|---|---|
| Builder 上傳映射 | CSV column → document_id／source_revision／content.*／metadata.* | 每列先驗 IngestionDocument；不屬 Engine 的切分設定 |
| Parser Component | 接受的 media_type／schema_id、content 形狀與轉換、輸出 Unit 欄位／文字格式能力 | 共用輸入＋Component 內容驗證 → ParsedDocument Schema／語意驗證 |
| Component I/O 資料規格（B） | 固定細節或依有效 Config 細化 Unit／fields／vectors／metadata；資料欄位定義必要時是 Parser 參數 | 組裝與候選驗證，以及 API／各 Module 執行輸入輸出驗證；不新增一份由 User 重填的全域 Schema |
| Chunking | 基本 text；進階有序 tasks、每任務 Component／參數、split_field／output_field／copy_fields | 逐 Unit 檢查來源欄位與文字格式相容；六鍵輸出、必要 ID／任務產出及有提供時的追溯驗證 |
| Embedding | 來源欄位、向量名稱、不可變 Profile 識別 | 預設 fields.text → vectors.text；寫入 values／embedding_profile_id／source_field |
| Indexing | 全文／向量／Filter 欄位、搜尋後端、持久化模式 | 保存全部 Chunk 內容；Binding 檢查向量來源、Profile、維度及索引能力 |
| Inference | Query、搜尋欄位／Filter、兩層融合時機與四處 Top N、Rerank／檢索結果消費端 內容欄位 | 操作 QueryContext／ResultSet；使用 Chunk 已保留的內容，不強制回查 ParsedDocument |
| 部署設定 | DEV／FTEST／ENT 的服務 URL、Secret、集合與資源綁定 | 不改變同版 Config 的邏輯；Memory／MongoDB 模式不能在 Export 時任意覆寫 |

Chunk 後的 UI／跨容器引用使用 fields.text、vectors.text、metadata.department。15 的切分計畫 split_field／copy.source_field 使用當筆 Unit 的 key；output_field 與 DenseVector.source_field 使用 Chunk.fields 的 key（例如 text）。每階段明確解析，不將舊 ParsedDocument.fields 路徑當別名。

ParsedDocument.units 每筆直接放內容欄位；Chunk 的 metadata._rag.source_refs 記 unit_index、field 與 Unit 內文字範圍，不新增 structure。完整切分 spec 由 Config／Run 保存，Chunk 可選擇保存 fingerprint／ordinal／task_id，沒有也合法。

<a id="src-05-71-d-53兩項已確認的預設-component-能力v012-有-ui-模擬"></a>
### D-53：兩項已確認的預設 Component 能力（v0.12 有 UI 模擬）

- 預設 Embedding Component 可選模板組合固定文字與 fields，預設關閉；輸出獨立 fields.embedding_text，沿用來源／向量映射並保存衍生文字，向量 source_field 指向衍生來源。欄位衝突／缺失與模型長度檢查須涵蓋最終內容。
- 預設 Chunker 可獨立勾選「額外保留原文 Chunk」，預設關閉；以每 Unit／任務的完整來源為準，若已有相同切片不重複產生，不跨 Unit 合併。與既有 copy 原文欄位不同。
- 兩者屬邏輯 Config，不因環境綁定而改變；不要求所有自訂 Component 實作，不新增共用資料根鍵／Pipeline Module。具體 Config 拼字尚未凍結；完整語意見 [Chunk](02_data_contracts.md#src-15-9-後續確認與欄位組裝d-532026-11-03-已確認功能方向)，UI 待辦 UIB-018／019。

<a id="src-05-8-config-變更影響矩陣"></a>
## 變更影響與重新 Ingestion 的範圍

| 有效變更 | 影響 |
|---|---|
| 影響資料規格的 Component 版本／參數、Import／Parsing／Chunking／Embedding／Indexing 的邏輯配置 | 新 Config Revision，標記需重新 Ingestion；中間產物重用另決 |
| D-53 模板／衍生欄位／映射 | 需重新組合、Embedding／Indexing；Chunk 重用依來源保留與版本政策，不保證自動局部重跑 |
| D-53 額外原文 Chunk 開關 | Chunk 集合改變，需重新 Ingestion；沿用既有資料替換／發布政策 |
| 部署設定的 DB／實體索引目標 | Config Revision 不因此改變；更新部署綁定，目標需有相容資料或重新 Ingestion |
| 同 Profile 的模型服務 URL／Secret | 邏輯 Config 不變；驗證連線與實際模型相容性，不能把不相容模型當成純換 URL |
| Query Transformation、Retrieval、Rerank、被引用的 LLM | 不需重建；需重新測試／評估 |
| Indexing filter_fields | 需重建搜尋能力 |
| Retrieval filters 詞值、本次 filters | 僅影響查詢 |
| 顯示名稱 | 不更換穩定 collection |
| 未啟用／未引用服務的草稿 | 不改有效 Pipeline 或重建判定 |

「舊評估失效」是不能代表新版，不等於刪除歷史報告。Prototype 清除示意值的行為不應直接變成正式歷史資料刪除政策。

CSV 映射保存、Revision 計算、canonical JSON／Hash、部署綁定是否可重用資料版本需 Q-015 核定。邏輯 Config Hash 不混入部署 URL／認證／資料目標；部署綁定另記版本／識別以追蹤實際環境。不得記真實 Secret；有語意順序的陣列不可任意排序。

<a id="src-05-81-重新-ingestion索引重建的範圍"></a>
### 「重新 Ingestion／索引重建」的範圍

重建需說明受影響資料與需要重做的步驟，不一律代表清空整個資料庫。先前 Q-010／Q-015 的討論主要指有效 Ingestion 設定改變後，既有資料需要重新處理時的查詢可見性；以下區分不同情境：

| 情境 | 受影響範圍／需要的處理 |
|---|---|
| 新增來源文件 | 處理新增文件及其 Chunk／索引；不因新增就預設整批重建 |
| 更新單份文件內容 | 更新該文件產生的 Chunk／vectors／索引；舊片段替換與提交政策仍待 Q-008／Q-009 |
| 修改共用 Chunk Size／切分規則 | 重新處理採用該規則的既有文件，可能涵蓋此 System 全部文件；後續 Embedding／索引隨新的 Chunk 更新 |
| 更換 Embedding 語意 Profile | 針對受影響內容重算向量並建立相容的向量索引；是否可重用 Chunk 等中間產物待 Q-015 |
| 改 Indexing 欄位／Mapping | 重建或補建受影響索引能力；實際步驟由 ES／Local Adapter 及相容政策決定 |
| 只改 Query Transformation／Retrieval／Rerank／檢索結果消費端 | 不重做 Ingestion；重新測試／評估 |
| Local Memory 程序重啟 | 記憶體 Chunk／vectors／搜尋結構已遺失，需重新 Ingestion 才可 Query |
| Local MongoDB 程序重啟 | 以已保存 Chunk／vectors 恢復 FAISS／BM25／Chunk Store；相容時不需重新 Parsing／Embedding，屬索引恢復 |

D-60 已確認不因寫入阻擋 Query、不加平台讀寫鎖，接受更新期間的新舊混合；同文件重複 Ingestion 拒絕仍維持。實體提交／失敗清理、版本相容與重建策略仍待 Q-008～Q-010／Q-015，不以此承諾原子快照。

<a id="src-23-1-這次要定義什麼"></a>
## 這次要定義什麼

System Config 是 [A～E 責任：的 D](01_architecture.md#src-20-3-最終詳細總表)：保存某個 Retrieval System 的 Component 選擇、版本、參數、資料欄位、邏輯引用與處理計畫。Component Developer 提供的 B／C 定義可選項與限制，E 解決特定環境的連線／資源。

| 層次 | 放什麼 | 本稿如何使用 |
|---|---|---|
| A 共用資料／I/O | IngestionDocument、ParsedDocument、Chunk、QueryContext[]、IndexBinding | 引用既有契約；不複製到 Config，不把執行結果寫回設定 |
| B Component Descriptor | 識別／版本、config_schema、I/O 與能力 | 用 component_id＋implementation_version 查 Registry，再驗證 parameters |
| C Remote Manifest | 服務操作、邊界／涵蓋範圍、參數及部署需求 | 由核可 Manifest 推導可選 Component；Config 只保存引用及開放值 |
| **D System Config** | 下面的共同骨架、所選參數與邏輯引用 | User／Builder／AI／Python 共用相同輸入與驗證 |
| E 環境設定 | URL、Secret 引用、實體索引目標、Image／部署與 Runtime 限制 | 與 D 一起準備可執行資源；[Runtime API／部署](06_runtime_api_and_deployment.md) 管可調控制項 |

System ID、Workspace／顯示名稱、Config Revision、Runtime Image 引用屬可信管理／交付包裝；建議不重複放入 D。Component 版本仍在 D，因為它決定處理語意。省略 source_revision 的生成規則與索引失敗清理仍屬既有 Q-007～Q-010，這份 Config 草案不代為定案。

<a id="src-23-2-共同骨架初版"></a>
## 共同骨架初版

共同骨架以本節文字稿繼續討論。舊 [D-66 system_config.schema.json](history/superseded/system_config_d66/system_config.schema.json) 含已取消的 document_schema，僅供歷史對照；不以它驗證新設計。Component I/O 細化規則與剩餘 SC 決策確定後，再同步機器 Schema／案例。

| 候選位置 | 初版內容 | 規則／待議處 |
|---|---|---|
| contract_version | system-config/0.1-draft | 格式版本；與 Component／Config Revision／資料版本分開 |
| I/O 資料規格（推導結果，不新增頂層欄位） | 由 Descriptor／Manifest＋有效 Config 提供 | D-67：不重複手填 document_schema；Parser 必要時開放資料欄位定義參數；共用 Contract 不變 |
| llms | System 共用 LLM 名稱 → profile_id／service_ref | Rewrite 以 llm_ref 選用；URL／Secret 在 E。Profile 的保存／鎖定見 SC-06 |
| pipelines.ingestion | Import／Parsing／Chunking／Embedding／Indexing 與整段引用 | 固定 Module 骨架，不是任意步驟陣列／DAG |
| pipelines.inference | Query Transformation／Retrieval／Rerank 與結果處理 | 沿用 QueryContext[]，不加入 Generation 或歷史 State |

`execution` 曾是模糊候選名稱；本稿先分開結果計畫與環境控制。Queue／Rate／Deadline／紀錄保留歸 E；結果合併／Top N 的候選位置為 inference.processing，是否改由 Component parameters 表達仍待審閱。這是具體表示的建議，正式鍵名見 SC-01／SC-07。

<a id="src-23-21-每次-component-選擇"></a>
### 每次 Component 選擇

```json
{
  "component_id": "example.chunking.recursive",
  "implementation_version": "1.0.0-fixture",
  "parameters": {
    "split_field": "text",
    "output_field": "text",
    "copy_fields": [],
    "max_tokens": 500,
    "overlap_tokens": 50,
    "tokenizer_profile_id": "example.tokenizer/v1"
  }
}
```

共同骨架只知道識別與 parameters 是 object；具體欄位由該 Component 的 config_schema 驗證。固定版本避免自動追 latest；Registry 不存在該版本時拒絕，不能只因 JSON 合法就改用另一個元件。所有 example.* 都是離線 fixture，並非已安裝的內建元件 ID。

<a id="src-23-22-固定骨架內的多選與略過"></a>
### 固定骨架內的多選與略過

| 位置 | 候選表示／行為 |
|---|---|
| import | 首版可省略，由共同入口執行既有驗證／resolver；如開放自訂 Import，可放同型 Component 引用，但不能跳過共同輸入驗證與 Runtime 限制 |
| parsing.profiles | 名稱 → Component 選擇；API 的 parsing_profile 對應該名稱，非任意 component_id。多個格式由能力自動路由 |
| parsing.default_profile | 有格式重疊時選用的已設定名稱；單一 Parser 不必填 |
| chunking.tasks[] | task_id＋Component；基本 UI 自動產生單一 text 任務，進階才展開。每個任務處理各 Unit，輸出相加、每任務內獨立 copy |
| embedding | Component 參數含 mappings、Profile／服務引用；純全文可省略 |
| indexing | 單一索引 Component；保存完整 Chunk，只選全文／向量／Filter 能力。persistence 仍屬 D，實體目標在 E |
| query_transformation／rerank | 省略代表略過／None，不引用虛構的 none 元件；與 UI Draft 保留值的正規化見 SC-08 |
| retrieval | 保存實際所選相容 Component，但基本 UI 可由 Indexing 推導／唯讀顯示；不能讓 User 配出不相容後端 |
| segments[] | 引用核可的連續多 Module 元件／服務；涵蓋範圍由 Descriptor／Manifest 推導，受接管的本地 slot 不重複保存於有效計畫 |

slot 的完整性不是只靠 required：例如 Parsing～Embedding 已由一段 Remote 承接，三個本地設定可省略；Engine 必須驗證每個必要 Module 剛好被涵蓋一次。不能只允許所有 slot 缺省，再把空流程當合法。多 Parser 是分派到一個相容實例，不是依序全部執行；task_id 是配置定位，不強制寫入 Chunk._rag。

<a id="src-23-23-結果處理仍保留兩層與四個位置"></a>
### 結果處理仍保留兩層與四個位置

```json
{
  "same_query": {"enabled": true, "after": "retrieval", "fusion": {"method": "rrf", "parameters": {"k": 60}}},
  "cross_query": {"enabled": true, "after": "retrieval", "fusion": {"method": "rrf", "parameters": {"k": 60}}},
  "merge_key": "chunk_id",
  "top_n": {"after_retrieval_merge": 20, "after_rerank": 3}
}
```

此片段假設已啟用 Rerank；略過 Rerank 的案例沒有 after_rerank 上限。

| 既有語意 | 初版位置 |
|---|---|
| 每次搜尋 Top K | Retrieval Component 的 parameters，例如 routes[].top_k；ES Hybrid 可由該元件用 top_k 表達 |
| Retrieval 後合併 Top N | processing.top_n.after_retrieval_merge |
| Reranker 評分後 Top N | processing.top_n.after_rerank |
| Reranker 後合併 Top N | processing.top_n.after_rerank_merge |

同 Query／跨 Query 各自選 retrieval 或 rerank 後，仍可先同 Query 融合、逐 Query Rerank、最後跨 Query 融合。merge_key=document_id 在最後適用融合／分組點選代表 Chunk，不把同文件不同 Chunk 分數盲目相加。Rerank=None 仍保留必要後置融合。

ES 內部 sum_score／RRF 是 Retrieval 元件的參數，平台 processing 是跨清單處理，兩者分開。ES 只有一份 Hybrid 輸出時略過無效的同 Query 融合，不捏造分項分數。單 Query／單路等條件是否在保存或編譯時移除無效值，留 SC-08；案例保留兩層預設意圖，尚未聲稱是已正規化的 Effective Config。

<a id="src-23-3-d-66-歷史案例與待同步範圍"></a>
## D-66 歷史案例與待同步範圍

下表保留要覆蓋的五個情境；檔案是 **D-66 舊版快照**，不是採用 D-67 後的有效 Config。正式 Descriptor 規則及其餘 SC 選項未定，不以示例偷定語法。

| 案例 | 歷史檔案 | 需繼續覆蓋的情境 |
|---|---|---|
| Local Memory | [local_memory.json](history/superseded/system_config_d66/local_memory.json) | Structured JSON→Recursive→Embedding API→Local Search；BM25＋向量、預設融合；無 Rewrite／Rerank |
| Remote Parser | [remote_parser.json](history/superseded/system_config_d66/remote_parser.json) | 只換 Parsing 元件，其餘設定相同；無私有 URL／Header 混入 D |
| Remote 多 Module | [remote_segment.json](history/superseded/system_config_d66/remote_segment.json) | 一個元件涵蓋 Parsing～Embedding，三個本地 slot 省略，接 Local Indexing；只呼叫一次 |
| 多欄位與模型處理 | [advanced_fields.json](history/superseded/system_config_d66/advanced_fields.json) | text／faq 任務結果相加、copy title／summary、原文 Chunk、Embedding 模板／多向量、Multi-query、Rerank／Top 3、document_id 代表 |
| Elasticsearch Hybrid | [es_hybrid.json](history/superseded/system_config_d66/es_hybrid.json) | 索引／檢索格式配對、ES 內部 Sum Score 與平台 RRF 的邊界 |

[environment.example.json](history/superseded/system_config_d66/environment.example.json) 示範 E 的服務 URL／Secret 引用、Remote 綁定與 Runtime 限制；所有地址為 example.invalid、沒有真實 Secret。它也是 D-66 對照材料，不是已定案 E Schema 或部署 YAML。Remote Image 仍依Remote Manifest手冊／Manifest 產生額外部署描述，External 僅提供連線；D 不自行增加 URL、Image 或 data_space_id。

單位與欄位路徑保持既有責任：Chunking split_field／copy source 是 Unit key；Embedding source_field 是 Chunk.fields 的 key；搜尋／Filter／Rerank 以 fields.text／vectors.text／metadata.department 明確引用容器。衍生模板只寫在支援該能力的 Embedding Component 參數中，不新增通用處理 Module。

<a id="src-23-4-驗證順序與目前驗證範圍"></a>
## 驗證順序與目前驗證範圍

1. **共同結構**：根欄位、固定 pipeline／slot、Component 引用、tasks／profiles／processing 的形狀；共同骨架拒絕未知欄位。
2. **所選元件**：查 ID／版本 → 取 Descriptor.config_schema → 驗證 parameters → 依 24 取得當前 I/O 細節；取得描述／推導不執行業務處理或啟動模型／DB。空參數服務使用合法空物件 Schema。
3. **跨模組語意**：連續範圍與重疊、必要 Module、欄位存在／型別、每個 Chunk 任務的可用欄位、向量／Profile、Indexing／Retrieval 格式、結果處理次序。
4. **環境與啟動**：D 的邏輯引用是否有 E 綁定、部署／連線／實際 Profile 是否可用、索引就緒；這與前三層結構合法分開回報。

JSON Schema 的 default 是描述，不會自動填值；Engine 正規化仍需共同實作並保存解析後值。不要讓 Builder、AI、Python 各自套不同預設，也不要把未知／失效引用靜默換掉。

D-66 舊版離線 [validate_examples.py](history/superseded/system_config_d66/validate_examples.py) 當時已驗證五個正例及 19 個反例；這不是新 D-67 宣告規則／解析器的驗收。舊檢查涵蓋未知元件／參數、overlap、缺 Module／覆蓋重疊、欄位／向量、模板、LLM 引用、索引格式與 E 引用。它使用 [catalog.fixture.json](history/superseded/system_config_d66/catalog.fixture.json)，只驗證固定案例；不是完整 Registry、Router／能力推導、UI Renderer、實際編碼、索引寫入或部署器。平台 Sum Score 比分／轉換等未驗證語意會明示超出 fixture 範圍。

<a id="src-23-5-需要討論的選擇與建議"></a>
## 需要討論的選擇與建議

討論順序調整：先審閱 [Descriptor 候選：B Descriptor Schema 初版](04_component_descriptor.md#src-25-2-descriptor-共同骨架) 的設定／I/O／選項規則，再回來完成 D 的 SC 決策；不必先實作全部 Component。System 選用仍以 ID／版本／parameters 為骨架，不把整份 Descriptor 內嵌 D。

以下除 SC-03 的 D-67 已確認方向外，具體表示仍待核定；共同既有語意沿用已確認決策。SC-07 的獨立 processing 層亦未定案，須與 Component 實作／參數責任一起審閱。

| ID | 要決定的表示／取捨 | 建議做法與理由 | 另一種選擇／影響 |
|---|---|---|---|
| SC-01 | D 的根欄位及管理包裝 | D-67 後候選為 contract_version／llms／pipelines；System ID、Revision、E 及 Image 在可信管理／交付包裝，避免多處不一致 | 把管理欄位也放 D，需另外定跨環境／改名／Hash 規則 |
| SC-02 | Component 版本及參數的引用方式 | 固定 component_id＋implementation_version＋parameters；用 Registry 中該版本的 Descriptor 驗參數，不內嵌 Descriptor，也不直接引用可下載 URL | 版本範圍／latest 需額外解析鎖與升級政策；首版不建議 |
| SC-03 | I/O 資料規格由誰提供 | **D-67 方向已確認**：取消獨立頂層 document_schema，B／C 提供固定或依 Config 細化的資料規格；任意 JSON Parser 必要時由其參數接收欄位定義 | 正式 Descriptor／規則格式、metadata 限制的參數表達、解析快照與額外欄位政策仍待 Schema 細化手冊／Q-002；不恢復重複手填的全域權威 |
| SC-04 | Parser 多選與 Chunk 多任務包裝 | Parsing 用命名 profiles，可選 default_profile；Chunking 固定 tasks[]，單一 text 任務由 UI 自動產生，不新增一般 User 必填識別欄位 | 單一物件／陣列兩種形狀需遷移與更多分支；不建議；Import slot 是否顯式保存也在此核定 |
| SC-05 | 跨 Module 的 Component 如何放入 D | 同 Pipeline segments[] 只存元件引用，範圍／operation 由核可目錄推導；省略被涵蓋本地 slot並驗證唯一覆蓋。Local／Remote 可共用表示，Local Segment SDK 另定 | D 重複寫 start/end／operation／完整 Manifest，較直觀但須處理與服務宣告不一致；不連續／任意 DAG 仍不在範圍 |
| SC-06 | 模型／Tokenizer Profile 是定義還是引用 | 優先引用不可變 Profile ID；Export／直接 SDK 同時取得已驗證 Profile 定義或解析鎖，E 只換相容連線。保留 System 共用 llms＋llm_ref | 允許 D 直接宣告完整 Profile 可方便 BYO，但需另定 model／維度／encoding／tokenizer／版本 Schema；只有 ID 卻未交付定義不算可部署 |
| SC-07 | Fusion／Top N 放在哪裡 | 候選為 inference.processing 兩層＋merge_key＋三個收尾上限，搜尋 Top K 放 Retrieval 元件。保留 Rerank None、ES 內部融合及四位置語意 | 全塞元件 parameters 或同一 fusion.method 容易遺失跨階段語意；可接受不同鍵名，但不能減少既有能力 |
| SC-08 | 省略、停用、default 與 Effective Config | 建議停用步驟在有效計畫省略；UI Draft 保留意圖，由 Engine 統一補適用預設、排除無效值及產生解析快照。未使用的參數不影響有效 Hash／Export | enabled=false 與 null 混用會增加語意；是否在輸入 D 保存不生效的融合意圖、Hash 的精確演算法需一起定 |
| SC-09 | D／E 的引用／綁定名稱 | Component 參數及 llms 保存 service_ref 等邏輯引用；E 依環境提供實值。Remote 綁定由核可服務選擇推導，一般 User 不填 Developer URL | 完整 E Schema／Image 部署欄位與 Runtime 設定載入方式仍需另議；本稿環境範例不凍結它們 |
| SC-10 | 寫入／遷移與驗收範圍 | 先核定上述骨架，用五案例驗證，再產出正式 Config Schema／SDK、Prototype 映射與 cURL／Export；保持舊 mock 格式明確可辨識 | 直接把 Prototype 匯出當正式 Schema 會帶入舊短名稱、環境混放與未核定選項；Rewrite 1／N 統一 UI、動態 UI Meta-schema 仍各自待議 |

建議先確認 SC-01～SC-05 的共同骨架與引用，再處理 SC-06～SC-09 的具體資料／處理／正規化；SC-10 決定如何進入實作。既有來源版本、失敗清理、Filter 缺值、Tokenizer 及模型服務細節仍由對應 Q-ID 收斂，不因骨架能驗證就視為全部完成。

<a id="src-23-6-本稿未改變的決策"></a>
## 本稿未改變的決策

Retrieval-only；ParsedDocument 四鍵／Chunk 六鍵與 `_rag` 選填；QueryContext[]；單一邏輯 IndexBinding；共用 Flow、逐次 Config／Context 分開；同 System Ingestion 結束後才允許新設定生效；工作記憶體化、無續跑／無 Query 讀寫鎖；Runtime Basic；文件摘要 documents[]／source_revisions[]；Local／Remote Image／External 三種交付。不新增 Generation、Python 程式上傳、Admin UI 或任意 DAG。
