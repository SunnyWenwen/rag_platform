# Retrieval Builder UI、原型狀態與 Backlog

## 閱讀目錄

- [目標、相依與範圍](#src-06-1-目標相依與範圍)
- [畫面與操作地圖](#src-06-2-畫面與操作地圖)
- [Create／Edit 的資料與互動](#src-06-3-createedit-的資料與互動)
- [從 CSV 開始](#src-06-4-從-csv-開始)
- [Ingestion 畫面](#src-06-5-ingestion-畫面)
- [Inference 與診斷](#src-06-6-inference-與診斷)
- [Evaluation 與 Edit Config](#src-06-7-evaluation-與-edit-config)
- [Export 與部署說明](#src-06-8-export-與部署說明)
- [互動品質與驗收](#src-06-9-互動品質與驗收)
- [結果處理控制項、預設值與共同卡控](#src-09-3-現行-ui-規劃)
- [結果處理說明案例](#src-09-4-說明案例)
- [Prototype／Backlog：已完成的原型能力](#src-10-1-已完成的原型能力)
- [Prototype／Backlog：結果處理與有效設定](#src-10-2-結果處理與有效設定)
- [Prototype／Backlog：累積需求處理狀態](#src-10-3-累積需求處理狀態)
- [Prototype／Backlog：Component 與 Remote 的原型範圍](#src-10-4-component-與-remote-的原型範圍)
- [Prototype／Backlog：選填追溯與文件提示](#prototypebacklog選填追溯與文件提示)
- [Prototype／Backlog：欄位組合與原文 Chunk](#src-10-6-欄位組合與原文-chunk)
- [Prototype／Backlog：驗證與剩餘整合](#src-10-7-驗證與剩餘整合)
- [Prototype／Backlog：UIB-021：D-55 單組 IndexBinding／索引格式配對（已確認，待改 UI）](#src-10-uib-021d-55-單組-indexbinding索引格式配對已確認待改-ui)
- [Prototype／Backlog：UIB-022：D-56 非同步 Ingestion／文件狀態與 Runtime 控制（已確認，待改 UI）](#src-10-uib-022d-56-非同步-ingestion文件狀態與-runtime-控制已確認待改-ui)
- [Prototype／Backlog：UIB-023：批次 Request 與文件管理 API](#src-10-uib-023d-58-統一-list-與文件管理-apiapi-方向確認ui-待規劃)
- [Prototype／Backlog：UIB-024：Descriptor 驅動 I/O 規格與逐層相依（D-67）](#src-10-uib-024descriptor-驅動-io-規格與逐層相依d-67)


更新：2026-11-11。本手冊同時管理目標互動與 Prototype 差異，兩者分區。**Prototype 是瀏覽器模擬；欄位推導使用本機示範規則，未串接正式 Engine／DB／模型。**

UIB-021 保留給 D-55 索引綁定；後加入且重號的 Descriptor 驅動規格改為 **UIB-024**。保留舊 uib-021-io-schema-refinement 錨點作相容別名；正式需求 ID 以 UIB-024 為準，所有待辦保留。

<a id="src-06-1-目標相依與範圍"></a>
## 目標、相依與範圍

- 新手透過預設、CSV 與 AI 助手快速開始；熟悉 Retrieval 者可展開完整設定。
- 同一份 Config 可由手動或 AI 修改，不建立兩套不相容模式。
- 畫面名詞與元件關係以 [架構與責任](01_architecture.md#src-03-31-系統組成與管理階層) 為準；UI 標籤與說明不得另定同名概念。
- 資料／Config 以 [資料契約](02_data_contracts.md) 為準；模組能力由 [Engine／Component 開發](03_engine_and_components.md) 提供；API 見 [Runtime API／部署](06_runtime_api_and_deployment.md)。
- 正式階層為 Workspace → System；側欄選 Workspace，主區顯示 System 卡片與操作視窗，不另建 Group。原型的 Groups 標籤／內部變數屬舊命名，正式化時遷移，不新增通用 DAG 編輯器。
- 保留單一主畫面：左側切換 Workspace，中間以圖示／卡片呈現已建 System，卡片提供 Ingest／Inference／Evaluation／Edit Config／Export 入口。
- 右上角放顯眼的「Create Retrieval System」。開啟設定介面時沿用此名稱；Edit Config 重用同一份表單與模組設定元件，載入所選 System 的獨立草稿。
- UI 設定 Config，Engine 組裝實例；前端不直接存取 Secret 或自行執行正式 Pipeline。

<a id="src-06-2-畫面與操作地圖"></a>
## 畫面與操作地圖

| 畫面／操作 | 使用者工作 | 主要結果 |
|---|---|---|
| Workspace 首頁 | 檢視與選擇 System | 名稱、版本、資料／索引狀態與操作入口 |
| Create／Edit | 設定 Schema、模組 Component／參數、Pipeline 與服務邏輯引用 | 經驗證的 Config 草稿／Revision；環境連線另存部署設定 |
| 從 CSV 開始 | 樣本、用途、映射與 AI 建議 | 建議草稿；確認後仍由使用者建立／匯入 |
| Ingest | 上傳、預覽、確認映射、執行 | run_id、工作狀態及結果；進度管控細節另議 |
| Inference | 問題、本次 filters | 檢索清單、分數／來源、可展開診斷 |
| Evaluation | 選 Dataset／指標、啟動 | 工作狀態、報告、與版本對應 |
| Export | 補齊 FTEST／ENT 目標服務 | 待設定草稿／已填妥但未驗證的匯出檔 |
| 查看 API | 查看目前 System／Runtime 的呼叫方法 | 端點、輸入／回應範例；不啟動工作 |

基本引導為 Build → Ingest → Inference → Evaluation → Export；Edit 可回到 Ingest 或 Inference。使用者可重複測試，不把引導步驟做成不必要的強制鎖。

<a id="src-06-3-createedit-的資料與互動"></a>
## Create／Edit 的資料與互動

<a id="src-06-31-草稿管理"></a>
### 草稿管理

Create 產生獨立 Draft；Edit 複製選定 Revision。取消不修改已保存配置；AI 套用也只修改 Draft，直到 Create／Save 才生效。版本衝突不可悄悄覆蓋他人修改，行為由 Q-015／Q-019 決定。

Create／Edit 可選用全域模板，設定 Import 入口欄位及參數，再設定 Ingestion 與 Inference 方法。各節點顯示由有效設定推導的契約。

<a id="src-06-32-已確認互動與基本進階分組"></a>
### 已確認互動與基本／進階分組

以下涵蓋已確認的使用者要求及既有 Prototype 行為（確認決策見 [計畫與決策](08_plan_and_decisions.md#3-已確認方向與保留基線)）；不將明確要求重新列為是否需要的待決項目：

- Parsing 初始只顯示「結構化 JSON」；其他格式及所有相關設定集中在預設關閉的「進階選項」，展開才出現。正式 Parser 能力另依 Q-005，顯示選項不等於可執行。
- D-67：由 Parser Descriptor＋Config 推導 Unit／metadata 細節，再沿 Pipeline 提供下游選項與卡控；多分支須保留可用性，缺欄位不靜默替換。詳細規則見 [Descriptor](04_component_descriptor.md)，UI 待辦 UIB-024。
- 2026-10-16 已確認：Indexing 預設保存全部 Document.structdata／metadata，移除「儲存內容」選單，只選全文／向量索引與可過濾欄位；Chunking 預設繼承全部合法 metadata，第一版不新增排除表單。Prototype v0.12 已有上述保存／繼承互動，見 Builder UI／Backlog手冊 的 UIB-005／006；真實儲存 Adapter 尚待實作。
- LLM 服務集中管理；Rewrite 以下拉選擇 System 已設定的服務。
- Rewrite 提供一份可編輯 Prompt、改寫數量與原始問題開關，並提供變數插入、驗證及預覽。
- Rerank 可查看固定平台 Request／Response 範例及 index／score 對應說明；不宣稱是所有模型的統一標準。
- collection 由 Workspace＋System 名稱／穩定 ID 自動帶入且唯讀；改顯示名稱不換既有實體。
- 內建 Retrieval 依全文／向量欄位推導搜尋模式。Retrieval 設定同 Query 多路融合，Query Transformation 設定跨 Query 融合的時點。見[結果處理控制項](#src-09-3-現行-ui-規劃)。

下表其餘分組仍為建議，待 Q-025；其中 Parsing 與上述已確認方向不可退回待定。

| 區塊 | 基本預設呈現 | 展開進階呈現 |
|---|---|---|
| Parser 資料規格（D-67 目標） | 顯示當前輸入／輸出欄位摘要；不重填固定輸出 | 僅當 Parser 開放時設定欄位定義／映射及 metadata 限制；Schema 正式語法待核定 |
| 服務 | DEV／自行提供、必要 URL／模型／認證引用 | Timeout、精確 Profile／Tokenizer 等 |
| Parsing（已確認） | 只顯示結構化 JSON | 其他格式及相關設定全部收在預設關閉進階區 |
| Chunking（欄位簡化已確認） | 切分方式／必要參數，直接用 text；不顯示切分／複製欄位選單，metadata 全繼承 | 單一切分來源、輸出名稱、可選複製欄位及完整原文保留。依方法顯示 Token、分隔符／標題層級設定。見 UIB-013。 |
| Embedding | 來源欄位、輸出向量、模型 | 維度／Encoding／Normalization、Batch、輸入限制 |
| Indexing | 後端、全文／向量欄位、過濾能力；全部內容自動保存的摘要 | 後端特有參數、進階 Mapping（支援後才顯示）；不要求再勾選保存內容 |
| Query Transformation | None／Rewrite／Remote API；Rewrite 選共用 LLM 並設定改寫數量 | Prompt、include_original；可能產生多 Query 時設定跨 Query 融合 |
| Retrieval／Fusion Plan | 全文／向量欄位、`per_route_k`、預設 filters、多路搜尋時選 RRF 或 Sum Score | 可選當步分組及 Retrieval Top N。跨 Query 規則由 Query Transformation 設定。 |
| Rerank | None／服務、單一評分內容欄位、Rerank Top N（原型預設 3）、實際提問來源 | 當步分組、逐 Query 問題選擇、附加內容欄位、Timeout／服務輸入限制 |

必填但缺失的設定不能因進階區收合而無法發現；錯誤摘要可直接展開並定位。改動過的進階設定收起後，建議顯示已修改項數／簡短摘要。範圍、預設值及「每次記住展開」政策見 Q-025。

<a id="src-06-321-服務來源選項保留已確認範圍"></a>
### 服務來源選項（保留已確認範圍）

| 設定位置 | 來源／選項 | 條件設定 |
|---|---|---|
| Embedding | DEV test use／Embedding API | 自行提供時設定 API URL、Model、認證引用及必要模型資訊；不另增加使用者管理本地模型的選項 |
| Indexing／Elasticsearch | DEV test use／使用者提供 Elasticsearch | 後者才要求 ES URL／認證等連線設定 |
| Indexing／Local Search | Memory／MongoDB | 選 MongoDB 才展開 DEV test use／使用者提供 MongoDB；Memory 不要求 DB。模式隨 Config 跨環境固定，不在 Export 中改模式 |
| 共用 LLM 服務 | DEV test use／OpenAI-compatible API | 自行提供時設定 Base URL、Model、認證引用；Query Transformation 以下拉 llm_ref 引用，不各填一份連線 |
| Rerank | None／DEV test use／Rerank API | 啟用時設定內容欄位與 Top-N；自行提供時另填 API URL、Model、認證引用 |

DEV test use 使用平台測試資源；匯出部署時需填入使用單位的綁定。Embedding／LLM 的現有原型格式分別為 OpenAI-compatible embeddings／Chat Completions，Rerank 為 04 的平台契約；首組真實服務的相容範圍仍由 Q-003 核定。

<a id="src-06-322-已註冊-developer-serviceremote-pipelined-51已有原型模擬真實整合待做"></a>
### User Remote API 與選用模板

User 在節點切換到 Remote API，設定 Endpoint、認證、參數及替換範圍。涵蓋的節點顯示管理來源，原內建設定留在草稿。Builder 顯示由上游推導的 Request 與有效 Response Schema，並提供本機回應驗證。涵蓋 Embedding 時宣告向量輸出；內建向量 Retrieval 按 Profile 設定 Query Encoder。

Admin 在 Builder 以外維護版本化全域模板。Builder 顯示可選版本，套用時複製至目前草稿。User 可調整設定及環境綁定。模板目錄為唯讀，系統儲存沿用既有驗證。
### 條件欄位與相依驗證

- 自行提供模型／DB 或 Remote API 時填必要連線與 Secret reference。平台測試資源使用部署綁定。
- Local Search 選 MongoDB 才呈現 DB 連線；Memory 不要求資料庫。
- Query Transformation 只選 llm_ref；共用服務只管理一次。
- None 的 Top-N／Prompt 等欄位可保留草稿但停用，不參與有效 Config 驗證／匯出。
- 上游刪欄位或模型引用失效：保留失效選擇、標示原因、阻止儲存；不自動選另一值。
- 不支援能力顯示且停用，附可理解原因；不能讓顯示的 Mock 選項假裝正式可用。
- 前端 Validator 提供即時回饋，Backend／Engine 仍重新驗證。Schema 及規則來源需共用或由後端產生，避免手寫三份不同規則。
- Component 目錄／Config Schema 與驗證結果綁定目標 Runtime 版本；目錄變動不靜默升級既有 System 或覆寫草稿。API／Schema 與既有控制項相容時，新增 Component 可在 Runtime 更新後供原版 Builder 選用；未知控制項／不相容格式明示需支援，不假裝可完整設定。目錄快取與版本協調見 07，畫面待辦見 Builder UI／Backlog手冊 UIB-010。

錯誤顯示 `[模組] 原因`；進一步可提供欄位位置、修正方式與是否需重新 Ingestion。UI 不要求使用者理解內部 Python 類別或堆疊。

相依卡控需能直接說明上游原因，保留必要顯示：

| 上游條件 | 下游呈現與驗證 |
|---|---|
| Indexing 選 ES／Local Search | Retrieval 顯示繼承的後端資訊，不增加 Implementation 選單 |
| 欄位未建立全文／向量索引 | 對應搜尋選項顯示且停用，說明需先在 Indexing 建立能力；既有選擇失效則保留錯誤並阻止保存 |
| Embedding 移除某個 output_name | Indexing／Retrieval 的向量引用標為失效，不默默改為其他向量或欄位 |
| 欄位未建立全文／向量索引，但已存在於 Chunk | 仍可用於 Rerank／檢索結果消費端 等內容消費；只有相對應的搜尋能力不能選，不能以「未勾儲存」拒絕 |
| metadata 已繼承／保存但未宣告可過濾 | 保留內容，Filter 選單停用該欄位並說明要先在 Indexing 啟用；不自動索引全部 metadata |
| Chunking 選 Fixed-size（待實作） | Token Size／Overlap／Tokenizer 有效；分隔符／keep_separator／標題層級不生效且保留草稿，不要求 Parsing headings |
| Header-aware 所需標題能力未開啟 | 顯示相依原因，提供定位 Parsing 進階設定的方式；無法滿足時阻止保存 |

卡控只處理設定相依；不代替實際後端能力、Profile 或連線驗證。規則由 Engine／Component 開發手冊／資料契約手冊 共用來源推導。

2026-10-28 D-42 將動態 Component 表單列為已確認規劃方向，描述／規則草案與案例集中於 [Descriptor](04_component_descriptor.md)。Create／Edit 保持固定介面，Component 參數才依 Schema 產生；無關分支欄位隱藏，進階預設收合，不相容選項顯示且停用。上游變更使已選值失效時保留並標錯，可以繼續編輯，但正式儲存／建立／套用需通過 Engine 驗證；草稿持久化仍依 Q-016／Q-025。

動態候選使用目前有效欄位／服務／索引能力，前端不自行指定可信 Context。多個相同 Module 的錯誤以 node_ref＋欄位路徑定位。未知必要 UI feature 明示不支援且不能套用不完整設定；不自動改為任意 JSON 編輯器。實作與 SUI-01～14 互動驗收記在 10 UIB-010；v0.12 僅完成簡單模擬表單，正式協定驗收仍待整合。

<a id="src-06-331-討論提案query-rewrite-單模組測試"></a>
### 討論提案：Query Rewrite 單模組測試

**待使用者確認，尚未改 UI。** 建議在 Query Transformation 放「測試 Rewrite」：輸入一個問題，用當前草稿的 Prompt／LLM／count 執行該模組，不要求先建立／保存 System 或 Ingestion，也不執行 Retrieval／Rerank／檢索結果消費端。

測試前驗證本模組與引用服務的必要設定，不以其他無關模組未填完阻擋。顯示實際生成的 Prompt、要求筆數、解析後 Query 清單、原始問題是否另外加入及格式／筆數／非空／重複驗證；原始回應可收合，耗時／Token 用量僅顯示實際可取得數據。None 不呼叫 LLM。

測試使用與正式執行相同的 Engine 模組、Adapter、Schema 與驗證；LLM 輸出策略提案見 [Engine／Component](03_engine_and_components.md#remote-api)。未接真實服務則明示模擬。修改 Prompt／LLM／count／保留原始問題或測試輸入後，舊結果標示過期；過期非同步回應不覆蓋新測試。試跑結果不自動套用／保存 Config，也不新增「必須先測試才能儲存」的 Gate。

<a id="src-06-332-討論提案以數量統一-query-rewrite"></a>
### 單一 Rewrite Component

Query Transformation 的「執行方式」可選 None、Rewrite 或 Remote API。選 Rewrite 後，使用同一份 Prompt，`count` 設定改寫筆數。`include_original` 決定是否也搜尋原始問題。例如兩筆改寫加上原始問題，會交給 Retrieval 三個 Query。

正式 UI 採上述選項。Prototype 現有的 Rewrite／Multi-query 分開選項及草稿保留方式，留待 UI 對齊時處理。單步試跑的提案見 UIB-007。

<a id="src-06-35-檢索結果呈現取代舊答案輸出設定"></a>
### 檢索結果呈現（取代舊答案輸出設定）

Inference 顯示 QueryContext[] 中的目前 ResultSets／ResultItems、依序名次、選填分數及 Chunk 內容。metadata／filters 隨 context 保留；診斷與計畫在資料外顯示，來源只顯示 Component 實際提供的內容。跨 Query 未合併時分組呈現，不捏造單一答案／生成引用。不提供 Generation Module、答案模板、Context Budget 或答案 JSON Schema 編輯器；Prototype 遷移見 UIB-015。

<a id="src-06-4-從-csv-開始"></a>
## 從 CSV 開始

<a id="src-06-41-兩個入口"></a>
### 兩個入口

A. 先 Create Config，之後 Ingest 上傳 CSV 並映射。
B. 先上傳 CSV 樣本，描述用途／問題範例，AI 提出 Schema、映射及 Pipeline 草稿，使用者確認後建立 System。

CSV 每 row 對應一份 Document，不把每個 column 當文件。需要以多列合併文件的能力尚未定案，見 Q-007／Q-025。

<a id="src-06-42-映射與預覽"></a>
### 映射與預覽

| 項目 | 要求 |
|---|---|
| CSV 預檢 | 處理 BOM／引號／換行；欄名非空唯一；每列欄數一致；正式編碼／超限政策待決 |
| 目標 | document_id、source_revision、Parser 接受的 content.*／外層 metadata.*；解析後的 Unit 欄位宣告用來核對內容映射 |
| 映射 | 可將同一 column 填入多個目標；未映射欄位不送出 |
| 必填 | 無預設值的 input 必填欄位須映射 |
| 型別 | number 有限值；boolean 規則明確；array 用 JSON 解析；正式強制轉型政策 Q-002 |
| ID | 優先映射穩定鍵；自動 ID 的跨批更新限制要明示 |
| 預覽 | 原始列 → 批次 Request → 各階段 Document；標示實際解析或模擬，錯誤對應列號／模組／欄位 |
| 保存 | 成功後保存映射；是否成為執行 Config Revision 的一部分見 Q-015 |

Prototype 限制 ≤1 MB 且在瀏覽器讀取，不等於正式產品限制。正式檔案上傳、樣本保留、敏感欄位與大小限制見 Q-016／Q-019／Q-024。

<a id="src-06-43-ai-配置助手"></a>
### AI 配置助手

已確認的互動方向：需求／樣本 → 建議 → 差異 → Validator → 使用者套用草稿 → Create／Save。規則模擬與真實 LLM 服務必須清楚區分。

**M4／M5 的分界已確認**：M4 的助手核心可不開 Builder，透過 Python／API 產生／修改同一種 Config；M5 同時交付 Builder 前後端與真實助手整合，另驗收下列 UI 差異。M4 已能回傳 Config，不能代替 M5 的驗收；完整情境見 [計畫與決策](08_plan_and_decisions.md)。

| Builder 情境 | M5 需要處理的差異 |
|---|---|
| 從資料樣本開始 | 把已允許的樣本、欄位映射及用途交給助手，建議能對回 Schema／Chunking 等控制項 |
| 在 Create／Edit 修改既有設定 | 傳當前 UI Draft、選用服務與草稿基準；保留人工已填設定，區分新建建議與局部修改 |
| 顯示與套用建議 | 對照 before／after、有效參數及重建影響；同一 Validator 通過後，由使用者明確套用至草稿 |
| 回應期間草稿又被修改 | 比對基準版本／Hash；過期建議不得覆蓋新修改，提示重新產生或核定的合併流程 |
| 取消與儲存 | 取消建議不改草稿；取消 Create／Edit 不改已存 System；Create／Save 前不改 active Config，不自動 Ingestion |
| 欄位與方法能力 | AI 建議、手動表單與 Engine 使用同一份 Schema／Registry；未支援方法、失效欄位／服務可定位，不靜默換值 |

助手的結構化輸出與 UI 的暫存／收合等呈現狀態分開；手寫 Config 與 UI Draft 可有不同包裝，但產生的有效 Config 語意需一致。此處不新增原始 Config 編輯器或另一個 Retrieval 主畫面；Prototype 調整先列 10。

**建議的正式流程，需 Q-024 核定**：

1. 取得明確允許的樣本及使用目的；列出抽樣範圍，不自動傳全表。
2. 由 Registry／Schema 限制可建議的方法、欄位及參數。
3. 回傳結構化建議與理由，預覽 before／after 及重建影響。
4. 先通過結構及跨模組 Validator；不合法項目不能套用。
5. 檢查建議基準 Draft 版本；人工已修改時要求重新產生或明確合併。
6. 套用後可繼續手動改；撤銷／選擇性套用細節待決。

助手不猜 Secret、不自動呼叫 Ingestion、不因文字說「效果更好」就視為驗證完成。不支援需求應說明限制。資料本身的文字不作為修改平台政策／服務權限的指令。

<a id="src-06-5-ingestion-畫面"></a>
## Ingestion 畫面

上傳／JSON → 批次 Request 預覽與檢查 → 明確啟動 → 顯示 run_id／狀態 → 結果。長工作由 Runtime API／部署手冊 管理，不依靠前端視窗存活。

- 區分接收成功、處理完成、索引可查詢；202 不代表可檢索查詢。
- 文件數與 Chunk 數各自標示。Ingestion 進度的呈現方式與工作操作留待後續討論。
- 部分失敗列出可對應 item 的錯誤，不用單一成功 Toast 遮蔽。
- 重新打開視窗應可查現有工作；跨重啟是否恢復依 Job Store 政策。
- 重送／取消／重試按鈕僅在對應 API 及冪等行為實作後開放。
- 真實 Parser／Chunk 小量試跑是建議能力，Q-025 核定前不能用瀏覽器格式預覽冒充。

<a id="src-06-6-inference-與診斷"></a>
## Inference 與診斷

問題＋本次 filters → 呼叫相同 Runtime API → 排序的檢索清單及來源。基礎結果簡潔呈現；詳細資訊按需展開。

| 層級 | 建議呈現 |
|---|---|
| 基本 | 檢索內容、分數／排名／來源、索引未就緒／服務錯誤 |
| 進階 | 原始與衍生 Query、各路候選、融合結果、Rerank 前後、實際 Context、耗時／用量 |
| 版本 | config_revision、index_generation、request_id；不可顯示為另一版的結果 |

Trace 保存與敏感內容政策見 Q-016，診斷顯示範圍見 Q-025。Filter 預設條件與本次附加條件要區分。Inference 執行失敗時顯示 Runtime 的錯誤，成功但無候選時顯示無命中。API 說明隨時可查看，不需先 Ingestion。Ingest／Inference 皆有「查看 API 端點」入口，內容包含當前 Base URL、認證示意、JSON／multipart、cURL、回應與錯誤；Ingest 另示範 run_id 輪詢。查看說明不執行工作或模型／DB 測試。

<a id="src-06-7-evaluation-與-edit-config"></a>
## Evaluation 與 Edit Config

<a id="src-06-71-evaluation"></a>
### Evaluation

Dataset 欄位預覽 → 指標所需標註檢查 → 執行 → 進度／逐題結果／摘要。缺 Ground Truth 不顯示虛構分數；skipped／failed／scored 分開。設定改動後舊報告標記對應舊版，保留歷史的正式政策由 Runtime API／部署手冊 決定。

Comparison、門檻與 Release Gate 為 Q-018；UI 不自行認定所有測試都通過即可部署。

<a id="src-06-72-儲存前變更摘要"></a>
### 儲存前變更摘要

依 05 的有效 Config 比較，列出模組與影響：

| 變更 | 使用者看到的結果 |
|---|---|
| Ingestion 邏輯配置／Schema 變更使索引不相容 | 套用新 Config Revision 會清除舊索引資料；建好新索引後由 Builder 使用保存的原始資料重新 Ingestion。 |
| 部署資料目標 | 同版 Config，部署綁定改變；需驗證目標資料或 Ingestion |
| Inference 配置 | 不需重匯；需重新測試／評估 |
| 顯示名稱／未啟用草稿 | 不更換實體 collection，不誤判需重建 |

Runtime 的新舊 Revision／Index 發布策略見 Q-010／Q-015。原始資料與重匯入的管理流程由 Builder 後續規劃，見 [Q-016](08_plan_and_decisions.md#q-016)。UI 依 Runtime 狀態呈現正式可查詢狀態。

<a id="src-06-8-export-與部署說明"></a>
## Export 與部署說明

- 沿用選定 System 的同版 Config，逐項填入部署環境的 LLM、Embedding、Rerank、ES／MongoDB 綁定；同 llm_ref 不重複填連線。改 URL／Secret 不覆寫邏輯 Config。
- 使用 DEV 綁定者可下載待設定草稿；必要資訊已填妥者標示「已填妥，尚未驗證」。
- 只允許合法環境覆寫；更改 Embedding Model 提示返回 Edit Config 並重建。
- Remote API 匯出環境連線與 Secret 引用。
- 不含實際 Secret、Image 本體、Chunk／vectors 或測試原文；提醒需在目標環境準備資料／Ingestion。
- Local Search 單程序／單副本；不可透過 UI 匯出多副本而宣稱可共享索引。
- FTEST／ENT 檔名、環境值與完整 Bundle 待 Q-021；正式文案稱 Config／部署設定。原型舊的 RAGBlueprint／blueprint.json 僅是待遷移標籤，不是另立的產品物件；單份示意 YAML 不代表正式交付完成。

<a id="src-06-9-互動品質與驗收"></a>
## 互動品質與驗收

**建議驗收基準**：鍵盤可操作、收合區可定位錯誤、Dialog 焦點可返回原入口；窄版可操作、長 JSON／Prompt 不破壞版面；非同步樣本讀取不覆蓋較新的選擇；送出中避免重複提交；錯誤可修正而不遺失草稿。

核心情境：空白建立、CSV 起始、人工修正 AI、取消 Edit、刪使用中 LLM、上游移除欄位、格式錯誤、索引未就緒、服務失敗、修改 Ingestion 與只改 Prompt、匯出 DEV 草稿及配置完成稿。

UI Mock、Schema 驗證、HTTP integration、實際端對端驗收分開記錄；只通過 Prototype DOM test 不能視為正式串接完成。

<a id="src-09-3-現行-ui-規劃"></a>
## 結果處理控制項、預設值與共同卡控

結果處理控制項分別放在 Query Transformation、Retrieval 和 Rerank 的表單。流程預覽顯示每條跨 Query 規則選定的執行時點。

<a id="src-09-31-兩層合併"></a>
### 融合與分組設定

| UI 位置 | 控制項 |
|---|---|
| Query Transformation | 在可能產生多 Query 時顯示跨 Query 融合。包含 `count>1` 或保留原始問題的 Rewrite，以及由平台負責融合的 Remote Query Transformation。選 Retrieval 或 Rerank 的最後一步，再選融合方法、分組欄位及可選 Top N。 |
| Retrieval | 內建搜尋有多路時必選 RRF 或 Sum Score，所有路徑融合成每 Query 一份清單。另可設定分組和 Retrieval Top N。 |
| Rerank | 設定模型、內容欄位、提問來源，以及評分後每份清單的分組和 Rerank Top N。 |

跨 Query 融合預設在 Retrieval 完成後。內建 Retrieval 的流程預覽會顯示搜尋路徑與選定策略，結果只呈現每個 Query 的一份清單。RRF／Sum Score 的進階參數待逐 Component 定義。

每個分組控制項都可選一個或多個有效候選欄位。第一次開啟時預選 `document_id`，欄位選單可改選有效候選 Schema 中的單值欄位。多欄一起構成分組鍵，操作順序見 [Engine 結果處理](03_engine_and_components.md#result-processing)。

<a id="src-09-32-四個固定-top-n-位置"></a>
### 四個固定截斷位置

| 位置 | 作用範圍 |
|---|---|
| Retrieval `per_route_k` | 每個 Query 在每條路徑的搜尋上限，套用於同 Query 融合前 |
| Retrieval Top N | 每份清單完成同 Query 融合和分組後 |
| Rerank Top N | 每份清單完成模型評分、重排和分組後 |
| 跨 Query Top N | 在所選步驟完成後，對已跨 Query 融合及分組的每份輸出清單截斷 |

預覽標出每個時點的清單數與上限。Rerank 選 None 時停用評分、當步分組與 Top N，跨 Query 可在 Rerank 後使用當前清單。完整 Remote Inference 由外部服務負責結果處理，Builder 顯示區段契約與回應驗證。

<a id="src-09-33-模型與內容欄位"></a>
### 模型與內容欄位

Reranker 預選合法的 structdata.text；基本區選一個內容欄位，進階才展開其他內容設定。提問預設原始問題；逐 Query 情境可依有效計畫使用當前 Query，跨 Query 已合併則使用原始問題。內容欄位來自 Chunk，依 System 候選 Schema 驗證。

Provider 的 top_n 與平台評分後保留數分開：Adapter 應取得選入候選的完整評分，再由平台截斷；服務不支援時明示能力／限制，不隱性少回結果。正式覆蓋率／錯誤政策見 Q-003／Q-014。

API 回傳最終有效清單。D-52：Chunk.metadata._rag.source_refs 為選填，有提供才追溯原始 Unit／文字位置；ResultItem 不另保存分數血緣，過程寫 Logs。

<a id="src-09-34-共同卡控"></a>
### 共同卡控

- 後端由 Indexing 繼承；搜尋只能選已建立索引且型別相容的欄位。
- 選兩條以上搜尋路徑時須選融合策略。單一路徑直接使用搜尋結果。Builder 顯示每個 Query 的輸出上限及已選融合方法。
- 單 Query／單路徑停用不適用控制項並保留草稿；切回多路時恢復選擇。
- 改上游欄位／服務造成失效時保留原值，錯誤顯示 `[Module]` 與欄位；不能靜默替換。
- 展開進階不改 Config。Create／Edit／AI／預覽／匯出使用同一有效計畫；取消不修改既有 System。

<a id="src-09-4-說明案例"></a>
## 結果處理說明案例

| 案例 | Retrieval 輸出 | 有效處理順序 |
|---|---|---|
| 單 Query＋ES Hybrid | 一份已融合清單 | 每路取 `per_route_k` → 選定策略融合 → Retrieval 分組／Top N → Rerank |
| 多 Query＋ES Hybrid | 每 Query 一份清單 | Retrieval Top N → 跨 Query RRF／Top N → 用原始問題 Rerank |
| 多 Query＋Local 多路 | 每 Query 一份已融合清單 | 同 Query 融合 → Retrieval 分組／Top N → 跨 Query 融合／Top N → Rerank |
| 先逐 Query 評分 | 每 Query 有可辨識的候選清單 | Retrieval 按母 Chunk 分組／Top N → 逐 Query Rerank／Top N → 跨 Query RRF → 按文件分組 → 最終 Top N |

最後一例若要保留每個 Query 的 Rerank 順序，將跨 Query 時點選在 Rerank 後。

<a id="src-10-1-已完成的原型能力"></a>
## Prototype／Backlog：已完成的原型能力

單一 Workspace／Group 主畫面，Create／Edit 共用設定介面，提供 Ingest、Inference、檢索 Evaluation、Export。全部為瀏覽器記憶體內操作，重新整理重設；沒有真實 Engine、模型、DB、Registry、服務健康探測或部署控制器。

- Import 欄位及 CSV 映射、各階段有效 Document Schema、批次 Ingestion Request 與逐文件驗證。
- Fixed-size／Recursive／Header-aware 的配置、Tokenizer 連動及 metadata 繼承。原型曾示範多任務切分，正式設定只選一個切分欄位。
- 全部 Chunk 內容預設保存；全文、向量、Filter 能力分開，失效欄位保留並報錯。
- 推論 QueryContext[]／filters／metadata、兩層融合與四處 Top N；可以回多份分組清單。
- 選填 _rag；Embedding 欄位模板；複製原文欄位與額外原文 Chunk 的獨立設定。
- 內建與 User Remote API 模式、連續範圍鎖定、契約驗證及 Admin 全域模板選用。
- AI 助手依本機規則產生 Diff，套用前驗證／過期草稿檢查；沒有 LLM 呼叫。

<a id="6-v09-實作細節展示預設與限制"></a>
<a id="src-10-2-結果處理與有效設定"></a>
## Prototype／Backlog：結果處理與有效設定

現有 Prototype 的舊版控制項集中在 Retrieval 進階設定。同 Query 多路與跨 Query 控制項預設收合，兩種融合預設勾選且可各自選時點。正式 UI 依[已確認設計](#src-09-3-現行-ui-規劃)將內建多路搜尋固定為融合後每 Query 一份，原型的分路輸出選項待對齊。ES 已內部融合時停用重複融合；單 Query／單路保留草稿意圖。預設平台 RRF，ES 內部預設 Sum Score。權重／RRF k 僅對有效策略驗證。

| 位置 | 作用範圍 |
|---|---|
| Retrieval 搜尋 Top K | 每 Query／每路；ES Hybrid 為每 Query 的一份輸出 |
| Retrieval 後合併 Top N | 該時點處理後的每份清單 |
| Reranker Top N | 每份模型評分清單，預設 3 |
| 舊版 Reranker 後合併 Top N | 舊版控制項可在 Rerank 後處理清單 |

ResultSet.key 對應 Config 路徑／群組；items 位置即名次。RRF 可用無 score 的有序結果；Sum Score 需完整且可比分數。Prototype 的推導器只計算流程與候選上限；mockRetrieval 用固定示意候選，不真的搜尋、融合或評分。畫面說明與計畫獨立於 QueryContext JSON，不新增外框或歷史記錄。

原始 Draft 保留停用參數；effectiveConfig 排除它們。Create／Edit／AI 套用／匯出使用同一驗證入口。取消不改已存 System；純 Inference 改動只使舊示意結果失效，Ingestion 模組有效改動提示重跑 Ingestion。

<a id="ui-backlog-pending"></a>
<a id="uib-010-component-catalog"></a>
<a id="uib-011-ingestion-parser-routing"></a>
<a id="uib-013-chunk-contract"></a>
<a id="uib-014-flat-units"></a>
<a id="src-10-3-累積需求處理狀態"></a>
## Prototype／Backlog：累積需求處理狀態

「原型完成」只代表配置／互動／模擬預覽，不代替真實功能驗收。

| 編號 | 需求 | v0.13 狀態 |
|---|---|---|
| UIB-001／002 | Fixed-size 及 Tokens 說明 | 原型已完成；真實 Tokenizer／切分待 Engine |
| UIB-003 | AI 助手串接 M4 核心／API | 待後端整合；目前明示本機規則 |
| UIB-004 | Diff、驗證、套用、取消與過期回應 | 本機模擬完成；真實非同步 API／版本一致性待整合 |
| UIB-005／006 | 全 Chunk 保存、metadata 全繼承 | 原型已完成；儲存 Adapter 待實作 |
| UIB-007 | Rewrite 單步試跑及模型回應驗證 | 試跑介面與 Provider 整合仍待討論 |
| UIB-008 | 單一 Rewrite Component，以 count 設定改寫筆數 | 規格已確認，Prototype 舊選項待對齊 |
| UIB-009 | Generation 自訂輸出 | D-50 取消 Generation，關閉此待辦 |
| UIB-010 | Component Descriptor 動態表單 | 模擬目錄及基本 Schema／UI hints 表單已完成；完整 12 協定／版本回應及真實 Registry 待整合 |
| UIB-011 | JSON API／多 Parser 自動派送 | 三來源 API 說明、CSV／JSON／明確 Units Adapter 已有；二進位 resolver、能力派送及衝突政策待真實 Parser |
| UIB-012 | text-spans／page-blocks 舊分類 UI | 已由 UIB-014 取代，刪除舊工作項 |
| UIB-013／014 | 單欄位切分及平面 Units | 原型已有切分示意；表單收斂為單一來源，實際切片與來源追溯仍依 Component |
| UIB-015 | Retrieval 命名與結果呈現 | 已完成；取消 Generation 與強制單清單 Gate |
| UIB-016 | User Remote API 與連續區段 | 原型支援配置及契約驗證；真實呼叫待整合 |
| UIB-017 | KISS 選填追溯／metadata 提示 | 原型完成；不捏造 _rag；真實 Component 自行支援 |
| UIB-018 | Embedding 前欄位模板 | 字串替換／驗證／Picker／預覽／有效匯出完成；模型 Token 上限仍待真實 Tokenizer |
| UIB-019 | 額外原文 Chunk | 控制、獨立 copy、每 Unit/task 去重示例及變更影響完成；真實切分待 Engine |
| UIB-020 | 簡化推論 Contract | D-54 本輪完成：root QueryContext[]，含 filters／metadata；無歷史物件 |
| UIB-024 | Descriptor 驅動 I/O 資料規格與逐層相依 | v0.13 完成本機互動示範，正式 Engine／Registry／API 待整合，見文末 |

<a id="uib-010-component-selection"></a>
<a id="src-10-4-component-與-remote-的原型範圍"></a>
## Prototype／Backlog：Remote API

原型涵蓋 [支援的連續範圍](03_engine_and_components.md#remote-api)、單一 Document、輸出向量宣告、有效 I/O 與參數引用。外部 Retrieval 使用 System 有效候選 Schema，測試可略過平台 Ingestion。Endpoint 與憑證解析顯示為配置預覽；真實 HTTP、認證、資料和索引仍由 Runtime 整合驗收。
## Prototype／Backlog：選填追溯與文件提示

內建預覽預設沒有 _rag，不以缺少 source_refs／fingerprint／ordinal 阻擋儲存或執行。Component 未提供來源就不捏造。Chunk.metadata._rag 保留為選填擴充；ResultItem 不另帶分數血緣，流程診斷交 Logs。

內建 Chunker 的示例可讀 metadata.chunking_mode="passthrough"，逐 Unit／task 完整轉 Chunk；預設無提示時正常切分。由 CSV 映射或 JSON Document 傳入 metadata。提示的支援範圍由各 Component 的宣告決定。

<a id="uib-018-embedding-composition"></a>
<a id="src-10-6-欄位組合與原文-chunk"></a>
## Prototype／Backlog：欄位組合與原文 Chunk

| 功能 | Prototype 草案設定 | 行為 |
|---|---|---|
| 模板組合 | embedding.composition.enabled／template／output_field | 預設關閉；產生獨立 structdata.embedding_text；固定文字＋structdata.* 字串變數 |
| 向量來源 | embedding.mappings | 明確選 embedding_text→vectors.text，source_field 記 embedding_text |
| 原文欄位 | chunking.preserve_original | 預設複製到 original_text；進階可設定複製映射，輸出名稱須唯一 |
| 原文 Chunk | chunking.include_original_chunk | 每個 Unit 可額外保留所選欄位的完整原文；已有相同完整片段時沿用 |

欄位組合在預設 Embedding 的前處理，不新增 Module。模板缺變數、來源非字串、缺欄位、語法錯誤或輸出撞名時阻止保存／樣本預覽；不執行 Python／LLM。衍生欄位出現在 Embedding／全文 Indexing／Filter／Rerank Picker。關閉保留草稿但不進有效設定；有效改動需重新 Ingestion。

<a id="uib-019-original-chunk"></a>
兩頁示例為 7／15 字元，每 10 字元、overlap=0：關閉 3 筆、開啟 4 筆，短頁不重複。不同 Unit／task 不互相去重，也不跨 Unit 合併。完整原文走同樣的模板、Embedding、Indexing；真實 Component 必須驗證最終模型輸入長度，包含 Profile 前綴／特殊 Token。**原型只做字元教學示例，不計算真實 Token，也不宣稱零向量有效。**

<a id="src-10-7-驗證與剩餘整合"></a>
## Prototype／Backlog：驗證與剩餘整合

現行驗收要求與未完成整合如下；歷次瀏覽器／契約驗證結果見 [歷史驗證紀錄](history/validation/2026-11-03_prototype_v0.12.md)。

- [ ] 真實 SDK／Config Schema／Registry 與 12 的完整動態 UI 協定。
- [ ] 真實 Tokenizer、Parser／Resolver、多 Parser 路由、Embedding／ES／Rerank API 與品質驗收。
- [ ] 真實 Image 啟停／健康狀態／失敗清理、Secret／儲存隔離、正式 FTEST／ENT Export。
- [ ] 真實 AI 助手 API、目錄／Draft 版本一致性；UIB-007／008 先決策再實作。

這些未完成工作不阻止展示已確認的 UI 設定流程，但不可當作 Engine／部署里程碑完成證據。後續需求先記文件；使用者要求改 UI 時再更新原型。

<a id="uib-021-index-binding"></a>
<a id="src-10-uib-021d-55-單組-indexbinding索引格式配對已確認待改-ui"></a>
## Prototype／Backlog：UIB-021：D-55 單組 IndexBinding／索引格式配對（已確認，待改 UI）

- [ ] 保持每 System 一組索引，不增加 index_ref、多組選擇或資源引用填寫表單。
- [ ] 讀取 Runtime 已驗證的 artifact_type／target／全文／Filter／向量能力；展示可用欄位，失效引用保留並報錯。
- [ ] Retrieval 候選依支援的索引格式／版本停用不相容項，顯示原因；僅有相同 JSON 外層不足以接線。
- [ ] Binding 與 target 為唯讀交接資訊，不把 RunContext、Client、Secret 或 Runtime searchable 狀態當使用者參數。
- [ ] 正式串接後 Create／Edit／AI／匯出共用驗證，SDK／HTTP 拒絕未宣告能力；目前 mock 不算真實後端驗收。


<a id="uib-022-runtime-ingestion-status"></a>
<a id="src-10-uib-022d-56-非同步-ingestion文件狀態與-runtime-控制已確認待改-ui"></a>
## Prototype／Backlog：UIB-022：D-56 非同步 Ingestion／文件狀態與 Runtime 控制（已確認，待改 UI）

- [ ] API 說明呈現 202 僅代表接收，顯示 run_id 及可用的狀態查詢入口；精確 Batch 路徑／Envelope 待 21 核定。
- [ ] 依 Run／文件狀態與錯誤契約顯示查詢結果。進度粒度、呈現與工作操作（含取消）延後討論。
- [ ] 同文件 queued／running 時顯示忙碌原因，不重複提交；完成／失敗後才可重新覆寫。
- [ ] Runtime 重啟／紀錄消失時顯示 unknown 並結束無止境輪詢，不憑舊索引或 Builder 舊畫面宣稱本次已成功。
- [ ] Ingestion Queue 額滿、Inference Rate／併發／Timeout 有可理解提示；不在每次文件／Query 表單加入環境上限設定。
- [ ] 區分文件工作狀態、索引是否可查與 Runtime Health；Local／Remote 的未知結果不冒充可安全重試。


<a id="uib-023-document-management"></a>
<a id="src-10-uib-023d-58-統一-list-與文件管理-apiapi-方向確認ui-待規劃"></a>
## Prototype／Backlog：UIB-023：批次 Request 與文件管理 API

- [x] Prototype 的 Ingestion API 範例及 CSV／JSON 預覽採批次物件。逐文件 Queue 仍待 Runtime 整合。
- [ ] API 說明區分工作狀態與實際文件存在／ID 清單，retire 是直接刪除，不是取消工作或保留資料的停用。
- [ ] 文件 ID 清單／存在查詢／retire 在 UI 的操作位置、分頁、確認與錯誤呈現，待需求及 21 的精確介面對齊後規劃；本輪不先實作面板或刪除按鈕。
- [ ] 需由 Runtime／backend 實際查詢及刪除，不用前端記憶體列表或 Ingestion 成功紀錄假裝資料來源。


<a id="src-10-d-60讀寫並行與暫定驗證方式補充"></a>
### D-60：讀寫並行與暫定驗證方式補充

- [ ] 不因有 Ingestion／retire 寫入就禁用 Inference 或顯示等待讀寫鎖；索引實際未就緒／限流／錯誤仍按 Runtime 回應呈現。
- [ ] API 說明暫採單一 Basic 帳密操作全部 Runtime API，憑證不寫進業務 payload；不因此新增 Builder 登入或角色權限 UI。
- [ ] 更新期間 Query 可反映不同時點的資料，不在 UI 宣稱原子快照；同文件 queued／running 重複提交仍保留忙碌提示。


<a id="src-10-d-63d-64設定啟用刪除結果與錯誤補充待改-ui"></a>
### D-63／D-64：設定啟用、刪除結果與錯誤補充（待改 UI）

- [ ] 設定可保存草稿，但該 System 有 queued／running Ingestion 時不啟用新版；工作結束後才允許套用，不影響其他 System，也不因此禁用 Query。
- [ ] API 說明將 retire 更新為同步 200，顯示 deleted／not_found 的不同結果；忙碌文件顯示 409，後端異常不冒充不存在／成功。UI 刪除按鈕與確認流程位置仍待規劃。
- [ ] 工作失敗呈現 status=failed、module 與 error；HTTP 請求錯誤讀取 error 外框，驗證位置使用 path。兩者不混同，Runtime 記錄失效仍顯示 unknown。
- [ ] API／部署說明引用 22 的 Runtime 可調參數，不在單次業務表單加入環境上限或 Admin 控制頁。
- [ ] System 操作使用穩定 system_id；不將名稱、Config Revision 或 document_id 當成該識別碼，也不在業務 body 塞入整份 Config。


<a id="src-10-d-65文件摘要清單ui-位置仍待規劃"></a>
### D-65：文件摘要清單（UI 位置仍待規劃）

- [ ] API 說明將文件清單回應更新為 documents[]＋next_cursor，每筆顯示 document_id／source_revisions[]，不再只列 document_ids[]。
- [ ] 來源版本取實際儲存；多版可代表更新中／失敗後混合，不將其標為成功歷史或自行挑選最新。最近工作結果仍使用 ingestion-status。

沿用 UIB-023，不新增文件內容、版本回復或清理按鈕。分頁參數與實際面板位置後續整理；本輪未修改 Prototype。


<a id="src-10-d-66system-config-整合草案先記錄待討論改-ui"></a>
### D-66：System Config 整合草案（先記錄，待討論／改 UI）

- [ ] 定稿 System Config 後同步 Prototype 匯出示意與 Runtime 編譯。
- [ ] UI Draft 保留停用選擇；Engine 編譯出有效參數／引用並做共同驗證，錯誤仍以 Module／欄位定位。具體正規化與 Hash 依 23 的 SC-08 討論。
- [ ] Runtime 限制、URL／Secret／實體目標在 E 的資源／部署區處理，模型語意與演算法參數留 D；不增加每次 Request 任意覆寫或一般 User 的 Admin 控制頁。

分頁精確參數、實際文件管理面板位置及 System Config 遷移仍依 21～System Config手冊／SC 決策；原型未接通真實服務。需求先記待辦，收到改 UI 指示後再實作。逐輪文件整理說明見 [歷史 UI 記錄](history/changes/ui_backlog_notes.md)。

<a id="uib-021-io-schema-refinement"></a>
<a id="src-10-uib-024descriptor-驅動-io-規格與逐層相依d-67"></a>
## Prototype／Backlog：UIB-024：Descriptor 驅動 I/O 規格與逐層相依（D-67）

2026-11-06｜**v0.13 已完成瀏覽器模擬。** 規格來源見 [Descriptor](04_component_descriptor.md)，九個節點的報告範例見 [Chunking → Embedding 的 Schema 相依](04_component_descriptor.md#schema-推導)。

操作路徑：**Create Retrieval System → 套用設定示範 → ⑫ Schema 相依：欄位改名**。

1. **Chunking** 顯示 `structdata.body_text`、`structdata.title`、`structdata.page` 的輸出規格。`page` 是整數，仍可被複製到 Chunk。
2. **Embedding** 保留 `page` 供查看，但停用其來源選項；映射 `body_text → body_vec` 時，輸出規格仍有三個原欄位，另有向量來源、測試 Profile 與維度。
3. 回到 **Chunking** 把切片輸出名稱改成 `content`。儲存會被阻止；點底部驗證訊息可聚焦到失效的 Embedding 映射。修正 Embedding 的來源後，原本的 `body_vec` 向量索引選擇可沿用，仍引用 `body_text` 的全文搜尋與評分欄位則需修正。

Create／Edit 直接從 Parsing 開始。內建 Parser 的欄位和 metadata 在進階參數內調整，固定輸出服務只顯示宣告。下游依單欄位 Chunking 的切分輸出與複製欄位推導選項。AI 建議更新 Parser 參數，CSV 從 Parser 輸入取得映射目標，Export 將欄位宣告放在 Parsing 的設定內。

尚待正式整合：

- [ ] 串接 Engine 的 Descriptor 解析結果與 Registry；涵蓋 Meta-schema、未知必要規則、Profile 能力與過期回應卡控。v0.13 的本機示例不等同通用 Renderer。
- [ ] 多 Parser 的實際分派與分支規格、Header-aware 的欄位能力驗證，以及已保存舊原型設定的正式遷移。
- [ ] Runtime API 的 202 前 Parser 預檢、背景內容驗證，以及 Local／Remote 的契約錯誤示例。
