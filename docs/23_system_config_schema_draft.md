# 23 — System Config Schema 初版與待討論決策

2026-11-05｜**整合討論稿，尚未核定全部欄位名稱／包裝或發布正式 SDK。**D-67 已確認移除獨立頂層 document_schema，I/O 細節由 Component 宣告＋Config 推導，見 [24](24_component_io_schema_refinement.md)。前次校對已歸檔至 [歷史校對紀錄](history/reviews/2026-11-05_spec_alignment_review.md)，目前設定討論依本稿進行；已確認的語意沿用 D-49～D-65。D-66 可驗證結構稿／五案例已移入 [歷史草案](history/superseded/system_config_d66/README.md)，保留舊格式查驗；新 Descriptor 規則尚未核定，因此尚無對應的新機器 Schema，不替換 schemas/ 的共用資料契約。

## 1. 這次要定義什麼

System Config 是 [20 的 D](20_contract_inventory_responsibility_matrix.md)：保存某個 Retrieval System 的 Component 選擇、版本、參數、資料欄位、邏輯引用與處理計畫。Component Developer 提供的 B／C 定義可選項與限制，E 解決特定環境的連線／資源。

| 層次 | 放什麼 | 本稿如何使用 |
|---|---|---|
| A 共用資料／I/O | IngestionDocument、ParsedDocument、Chunk、QueryContext[]、IndexBinding | 引用既有契約；不複製到 Config，不把執行結果寫回設定 |
| B Component Descriptor | 識別／版本、config_schema、I/O 與能力 | 用 component_id＋implementation_version 查 Registry，再驗證 parameters |
| C Remote Manifest | 服務操作、邊界／涵蓋範圍、參數及部署需求 | 由核可 Manifest 推導可選 Component；Config 只保存引用及開放值 |
| **D System Config** | 下面的共同骨架、所選參數與邏輯引用 | User／Builder／AI／Python 共用相同輸入與驗證 |
| E 環境設定 | URL、Secret 引用、實體索引目標、Image／部署與 Runtime 限制 | 與 D 一起準備可執行資源；[22](22_runtime_settings_catalog.md) 管可調控制項 |

System ID、Workspace／顯示名稱、Config Revision、Runtime Image 引用屬可信管理／交付包裝；建議不重複放入 D。Component 版本仍在 D，因為它決定處理語意。省略 source_revision 的生成規則與索引失敗清理仍屬既有 Q-007～Q-010，這份 Config 草案不代為定案。

## 2. 共同骨架初版

共同骨架以本節文字稿繼續討論。舊 [D-66 system_config.schema.json](history/superseded/system_config_d66/system_config.schema.json) 含已取消的 document_schema，僅供歷史對照；不以它驗證新設計。Component I/O 細化規則與剩餘 SC 決策確定後，再同步機器 Schema／案例。

| 候選位置 | 初版內容 | 規則／待議處 |
|---|---|---|
| contract_version | system-config/0.1-draft | 格式版本；與 Component／Config Revision／資料版本分開 |
| I/O 資料規格（推導結果，不新增頂層欄位） | 由 Descriptor／Manifest＋有效 Config 提供 | D-67：不重複手填 document_schema；Parser 必要時開放資料欄位定義參數；共用 Contract 不變 |
| llms | System 共用 LLM 名稱 → profile_id／service_ref | Rewrite 以 llm_ref 選用；URL／Secret 在 E。Profile 的保存／鎖定見 SC-06 |
| pipelines.ingestion | Import／Parsing／Chunking／Embedding／Indexing 與整段引用 | 固定 Module 骨架，不是任意步驟陣列／DAG |
| pipelines.inference | Query Transformation／Retrieval／Rerank 與結果處理 | 沿用 QueryContext[]，不加入 Generation 或歷史 State |

`execution` 曾是模糊候選名稱；本稿先分開結果計畫與環境控制。Queue／Rate／Deadline／紀錄保留歸 E；結果合併／Top N 的候選位置為 inference.processing，是否改由 Component parameters 表達仍待審閱。這是具體表示的建議，正式鍵名見 SC-01／SC-07。

### 2.1 每次 Component 選擇

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

### 2.2 固定骨架內的多選與略過

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

### 2.3 結果處理仍保留兩層與四個位置

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

## 3. D-66 歷史案例與待同步範圍

下表保留要覆蓋的五個情境；檔案是 **D-66 舊版快照**，不是採用 D-67 後的有效 Config。正式 Descriptor 規則及其餘 SC 選項未定，不以示例偷定語法。

| 案例 | 歷史檔案 | 需繼續覆蓋的情境 |
|---|---|---|
| Local Memory | [local_memory.json](history/superseded/system_config_d66/local_memory.json) | Structured JSON→Recursive→Embedding API→Local Search；BM25＋向量、預設融合；無 Rewrite／Rerank |
| Remote Parser | [remote_parser.json](history/superseded/system_config_d66/remote_parser.json) | 只換 Parsing 元件，其餘設定相同；無私有 URL／Header 混入 D |
| Remote 多 Module | [remote_segment.json](history/superseded/system_config_d66/remote_segment.json) | 一個元件涵蓋 Parsing～Embedding，三個本地 slot 省略，接 Local Indexing；只呼叫一次 |
| 多欄位與模型處理 | [advanced_fields.json](history/superseded/system_config_d66/advanced_fields.json) | text／faq 任務結果相加、copy title／summary、原文 Chunk、Embedding 模板／多向量、Multi-query、Rerank／Top 3、document_id 代表 |
| Elasticsearch Hybrid | [es_hybrid.json](history/superseded/system_config_d66/es_hybrid.json) | 索引／檢索格式配對、ES 內部 Sum Score 與平台 RRF 的邊界 |

[environment.example.json](history/superseded/system_config_d66/environment.example.json) 示範 E 的服務 URL／Secret 引用、Remote 綁定與 Runtime 限制；所有地址為 example.invalid、沒有真實 Secret。它也是 D-66 對照材料，不是已定案 E Schema 或部署 YAML。Remote Image 仍依 18／Manifest 產生額外部署描述，External 僅提供連線；D 不自行增加 URL、Image 或 data_space_id。

單位與欄位路徑保持既有責任：Chunking split_field／copy source 是 Unit key；Embedding source_field 是 Chunk.fields 的 key；搜尋／Filter／Rerank 以 fields.text／vectors.text／metadata.department 明確引用容器。衍生模板只寫在支援該能力的 Embedding Component 參數中，不新增通用處理 Module。

## 4. 驗證順序與目前驗證範圍

1. **共同結構**：根欄位、固定 pipeline／slot、Component 引用、tasks／profiles／processing 的形狀；共同骨架拒絕未知欄位。
2. **所選元件**：查 ID／版本 → 取 Descriptor.config_schema → 驗證 parameters → 依 24 取得當前 I/O 細節；取得描述／推導不執行業務處理或啟動模型／DB。空參數服務使用合法空物件 Schema。
3. **跨模組語意**：連續範圍與重疊、必要 Module、欄位存在／型別、每個 Chunk 任務的可用欄位、向量／Profile、Indexing／Retrieval 格式、結果處理次序。
4. **環境與啟動**：D 的邏輯引用是否有 E 綁定、部署／連線／實際 Profile 是否可用、索引就緒；這與前三層結構合法分開回報。

JSON Schema 的 default 是描述，不會自動填值；Engine 正規化仍需共同實作並保存解析後值。不要讓 Builder、AI、Python 各自套不同預設，也不要把未知／失效引用靜默換掉。

D-66 舊版離線 [validate_examples.py](history/superseded/system_config_d66/validate_examples.py) 當時已驗證五個正例及 19 個反例；這不是新 D-67 宣告規則／解析器的驗收。舊檢查涵蓋未知元件／參數、overlap、缺 Module／覆蓋重疊、欄位／向量、模板、LLM 引用、索引格式與 E 引用。它使用 [catalog.fixture.json](history/superseded/system_config_d66/catalog.fixture.json)，只驗證固定案例；不是完整 Registry、Router／能力推導、UI Renderer、實際編碼、索引寫入或部署器。平台 Sum Score 比分／轉換等未驗證語意會明示超出 fixture 範圍。

## 5. 需要討論的選擇與建議

討論順序調整：先審閱 [25 B Descriptor Schema 初版](25_component_descriptor_schema_draft.md) 的設定／I/O／選項規則，再回來完成 D 的 SC 決策；不必先實作全部 Component。System 選用仍以 ID／版本／parameters 為骨架，不把整份 Descriptor 內嵌 D。

以下除 SC-03 的 D-67 已確認方向外，具體表示仍待核定；共同既有語意沿用已確認決策。SC-07 的獨立 processing 層亦未定案，須與 Component 實作／參數責任一起審閱。

| ID | 要決定的表示／取捨 | 建議做法與理由 | 另一種選擇／影響 |
|---|---|---|---|
| SC-01 | D 的根欄位及管理包裝 | D-67 後候選為 contract_version／llms／pipelines；System ID、Revision、E 及 Image 在可信管理／交付包裝，避免多處不一致 | 把管理欄位也放 D，需另外定跨環境／改名／Hash 規則 |
| SC-02 | Component 版本及參數的引用方式 | 固定 component_id＋implementation_version＋parameters；用 Registry 中該版本的 Descriptor 驗參數，不內嵌 Descriptor，也不直接引用可下載 URL | 版本範圍／latest 需額外解析鎖與升級政策；首版不建議 |
| SC-03 | I/O 資料規格由誰提供 | **D-67 方向已確認**：取消獨立頂層 document_schema，B／C 提供固定或依 Config 細化的資料規格；任意 JSON Parser 必要時由其參數接收欄位定義 | 正式 Descriptor／規則格式、metadata 限制的參數表達、解析快照與額外欄位政策仍待 24／Q-002；不恢復重複手填的全域權威 |
| SC-04 | Parser 多選與 Chunk 多任務包裝 | Parsing 用命名 profiles，可選 default_profile；Chunking 固定 tasks[]，單一 text 任務由 UI 自動產生，不新增一般 User 必填識別欄位 | 單一物件／陣列兩種形狀需遷移與更多分支；不建議；Import slot 是否顯式保存也在此核定 |
| SC-05 | 跨 Module 的 Component 如何放入 D | 同 Pipeline segments[] 只存元件引用，範圍／operation 由核可目錄推導；省略被涵蓋本地 slot並驗證唯一覆蓋。Local／Remote 可共用表示，Local Segment SDK 另定 | D 重複寫 start/end／operation／完整 Manifest，較直觀但須處理與服務宣告不一致；不連續／任意 DAG 仍不在範圍 |
| SC-06 | 模型／Tokenizer Profile 是定義還是引用 | 優先引用不可變 Profile ID；Export／直接 SDK 同時取得已驗證 Profile 定義或解析鎖，E 只換相容連線。保留 System 共用 llms＋llm_ref | 允許 D 直接宣告完整 Profile 可方便 BYO，但需另定 model／維度／encoding／tokenizer／版本 Schema；只有 ID 卻未交付定義不算可部署 |
| SC-07 | Fusion／Top N 放在哪裡 | 候選為 inference.processing 兩層＋merge_key＋三個收尾上限，搜尋 Top K 放 Retrieval 元件。保留 Rerank None、ES 內部融合及四位置語意 | 全塞元件 parameters 或同一 fusion.method 容易遺失跨階段語意；可接受不同鍵名，但不能減少既有能力 |
| SC-08 | 省略、停用、default 與 Effective Config | 建議停用步驟在有效計畫省略；UI Draft 保留意圖，由 Engine 統一補適用預設、排除無效值及產生解析快照。未使用的參數不影響有效 Hash／Export | enabled=false 與 null 混用會增加語意；是否在輸入 D 保存不生效的融合意圖、Hash 的精確演算法需一起定 |
| SC-09 | D／E 的引用／綁定名稱 | Component 參數及 llms 保存 service_ref 等邏輯引用；E 依環境提供實值。Remote 綁定由核可服務選擇推導，一般 User 不填 Developer URL | 完整 E Schema／Image 部署欄位與 Runtime 設定載入方式仍需另議；本稿環境範例不凍結它們 |
| SC-10 | 寫入／遷移與驗收範圍 | 先核定上述骨架，用五案例驗證，再產出正式 Config Schema／SDK、Prototype 映射與 cURL／Export；保持舊 mock 格式明確可辨識 | 直接把 Prototype 匯出當正式 Schema 會帶入舊短名稱、環境混放與未核定選項；Rewrite 1／N 統一 UI、動態 UI Meta-schema 仍各自待議 |

建議先確認 SC-01～SC-05 的共同骨架與引用，再處理 SC-06～SC-09 的具體資料／處理／正規化；SC-10 決定如何進入實作。既有來源版本、失敗清理、Filter 缺值、Tokenizer 及模型服務細節仍由對應 Q-ID 收斂，不因骨架能驗證就視為全部完成。

## 6. 本稿未改變的決策

Retrieval-only；ParsedDocument 四鍵／Chunk 六鍵與 `_rag` 選填；QueryContext[]；單一邏輯 IndexBinding；共用 Flow、逐次 Config／Context 分開；同 System Ingestion 結束後才允許新設定生效；工作記憶體化、無續跑／無 Query 讀寫鎖；Runtime Basic；文件摘要 documents[]／source_revisions[]；Local／Remote Image／External 三種交付。不新增 Generation、Python 程式上傳、Admin UI 或任意 DAG。
