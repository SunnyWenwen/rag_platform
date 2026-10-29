# RAG Builder — 使用流程與 UI 開發規格

> 文件集 v0.19 · 2026-10-16 · 開發規格草案
>
> 本文定義 UI 目標互動。現有 HTML Prototype 的搜尋、模型、評估及 API 為模擬。Parsing 的預設收合、LLM／Prompt／範例按鈕等已確認要求如下；其他基本／進階分組、正式框架、範本與試跑優先級仍待決。

2026-10-16 起，先更新規格，Prototype 對應調整集中至 [10 §7 UI Backlog](10_ui_adjustment_backlog.md#ui-backlog-pending)，待使用者要求修改 UI 再實作。本文新增的 Fixed-size 與助手整合為目標規格，現有原型仍 v0.9；歷史完成項目與新待辦分開記錄。

2026-10-28 D-41 確認：Builder Frontend／Backend 位於 rag_platform，SDK／Engine／Components／Runtime API 位於 rag_engine。UI 經 Backend 使用目標 Runtime 的 Component 目錄、Schema 與驗證能力，見 [07 §5.8](07_backend_runtime_integration.md#runtime-capability-contract)；Prototype 對應變更仍記於 UIB-010，未因此實作。

## 1. 目標、相依與範圍

- 新手透過預設、CSV 與 AI 助手快速開始；熟悉 RAG 者可展開完整設定。
- 同一份 Config 可由手動或 AI 修改，不建立兩套不相容模式。
- 畫面名詞與元件關係以 [03 §3](../03_architecture_proposal.md#terminology) 為準；UI 標籤與說明不得另定同名概念。
- 資料／Config 以 [05](05_data_contracts_search_design.md) 為準；模組能力由 [04](04_module_components_io_contracts.md) 提供；API 見 [07](07_backend_runtime_integration.md)。
- 正式階層為 Workspace → System；側欄選 Workspace，主區顯示 System 卡片與操作視窗，不另建 Group。原型的 Groups 標籤／內部變數屬舊命名，正式化時遷移，不新增通用 DAG 編輯器。
- 保留單一主畫面：左側切換 Workspace，中間以圖示／卡片呈現已建 System，卡片提供 Ingest／Inference／Evaluation／Edit Config／Export 入口。
- 右上角放顯眼的「Create RAG System」。開啟設定介面時沿用此名稱；Edit Config 重用同一份表單與模組設定元件，載入所選 System 的獨立草稿。
- UI 設定 Config，Engine 組裝實例；前端不直接存取 Secret 或自行執行正式 Pipeline。

## 2. 畫面與操作地圖

| 畫面／操作 | 使用者工作 | 主要結果 |
|---|---|---|
| Workspace 首頁 | 檢視與選擇 System | 名稱、版本、資料／索引狀態與操作入口 |
| Create／Edit | 設定 Schema、模組 Component／參數、Pipeline 與服務邏輯引用 | 經驗證的 Config 草稿／Revision；環境連線另存部署設定 |
| 從 CSV 開始 | 樣本、用途、映射與 AI 建議 | 建議草稿；確認後仍由使用者建立／匯入 |
| Ingest | 上傳、預覽、確認映射、執行 | run_id、進度、結果及可處理錯誤 |
| Inference | 問題、本次 filters | 回答、引用、可展開診斷 |
| Evaluation | 選 Dataset／指標、啟動 | 工作狀態、報告、與版本對應 |
| Export | 補齊 FTEST／ENT 目標服務 | 待設定草稿／已填妥但未驗證的匯出檔 |
| 查看 API | 查看目前 System／Runtime 的呼叫方法 | 端點、輸入／回應範例；不啟動工作 |

基本引導為 Build → Ingest → Inference → Evaluation → Export；Edit 可回到 Ingest 或 Inference。使用者可重複測試，不把引導步驟做成不必要的強制鎖。

## 3. Create／Edit 的資料與互動

### 3.1 草稿管理

Create 產生獨立 Draft；Edit 複製選定 Revision。取消不修改已保存配置；AI 套用也只修改 Draft，直到 Create／Save 才生效。版本衝突不可悄悄覆蓋他人修改，行為由 Q-015／Q-019 決定。

表單順序：Document Schema → 共用 LLM／外部服務 → Ingestion 模組 → Inference 模組。Document Schema 是系統契約，不是 Pipeline 中新增的一步。服務可由相應模組開啟管理，但引用同一服務資料。UI 可在相同操作流程編輯 DEV 部署綁定，保存時仍分開邏輯 Config 與部署設定，不能因畫面放一起就混為同一 Config Hash。

### 3.2 已確認互動與基本／進階分組

以下涵蓋已確認的使用者要求及既有 Prototype 行為（U／B 來源見 08 §10）；不將明確要求重新列為是否需要的待決項目：

- Parsing 初始只顯示「結構化 JSON」；其他格式及所有相關設定集中在預設關閉的「進階選項」，展開才出現。正式 Parser 能力另依 Q-005，顯示選項不等於可執行。
- Create／Edit 前段有 Document Schema；先宣告 fields／metadata，再產生下游欄位選項。
- 2026-10-16 已確認：Indexing 預設保存全部 Chunk.fields／metadata，移除「儲存內容」選單，只選全文／向量索引與可過濾欄位；Chunking 預設繼承全部合法 metadata，第一版不新增排除表單。對應 UI 尚未修改，見 10 的 UIB-005／006。
- LLM 服務集中管理；Rewrite／Multi-query／Generation 在需要時以下拉引用，同一服務不重填連線。
- Rewrite／Multi-query 的 Prompt 可編輯，分別保留草稿；提供變數插入、驗證與預覽。
- Generation 有「模板說明與範例」及「套用範例」入口，展示兩筆 Chunk→逐筆模板→Context→完整回答 Prompt。
- Rerank 可查看固定平台 Request／Response 範例及 index／score 對應說明；不宣稱是所有模型的統一標準。
- collection 由 Workspace＋System 名稱／穩定 ID 自動帶入且唯讀；改顯示名稱不換既有實體。
- Retrieval 不另選 Implementation；由使用者選全文／向量欄位推導模式。原型 v0.9 已提供同 Query／跨 Query 兩層合併及各自的 Retrieval 後／Reranker 後時點；正式 Config 與 Engine 執行細節仍由 Q-014 追蹤。

下表其餘分組仍為建議，待 Q-025；其中 Parsing 與上述已確認方向不可退回待定。

| 區塊 | 基本預設呈現 | 展開進階呈現 |
|---|---|---|
| Document Schema | 主要 text、需要的內容欄位、metadata | 型別、required／default／source、unknown_fields |
| 服務 | DEV／自行提供、必要 URL／模型／認證引用 | Timeout、精確 Profile／Tokenizer 等 |
| Parsing（已確認） | 只顯示結構化 JSON | 其他格式及相關設定全部收在預設關閉進階區 |
| Chunking | Fixed-size／Recursive／Header-aware、主要切分欄位、複製欄位；metadata 預設全繼承 | 共用 Token Size／Overlap／Tokenizer；分隔符／標題層級依方法啟用；不提供 metadata 排除表單，UI 尚待辦 |
| Embedding | 來源欄位、輸出向量、模型 | 維度／Encoding／Normalization、Batch、輸入限制 |
| Indexing | 後端、全文／向量欄位、過濾能力；全部內容自動保存的摘要 | 後端特有參數、進階 Mapping（支援後才顯示）；不要求再勾選保存內容 |
| Query Transformation | 既有 None／Rewrite／Multi-query、LLM；合併提案見 §3.3.2 | Prompt、count、include_original |
| Retrieval／Fusion Plan | 搜尋欄位、每 Query／每路 Top K、有效流程摘要、預設 filters | 同／跨 Query 合併、時點、演算法、去重及兩處合併後 Top N；見 §3.4 |
| Rerank | None／服務、單一評分內容欄位、評分後 Top N（預設 3）、實際提問來源 | 逐 Query 問題選擇、附加內容欄位、Timeout／服務輸入限制 |
| Generation | LLM、回答要求；預設輸出格式提案見 §3.5 | 兩層模板、變數、Temperature、Budget；自訂 JSON Schema（提案） |

必填但缺失的設定不能因進階區收合而無法發現；錯誤摘要可直接展開並定位。改動過的進階設定收起後，建議顯示已修改項數／簡短摘要。範圍、預設值及「每次記住展開」政策見 Q-025。

### 3.2.1 服務來源選項（保留已確認範圍）

| 設定位置 | 來源／選項 | 條件設定 |
|---|---|---|
| Embedding | DEV test use／Embedding API | 自行提供時設定 API URL、Model、認證引用及必要模型資訊；不另增加使用者管理本地模型的選項 |
| Indexing／Elasticsearch | DEV test use／使用者提供 Elasticsearch | 後者才要求 ES URL／認證等連線設定 |
| Indexing／Local Search | Memory／MongoDB | 選 MongoDB 才展開 DEV test use／使用者提供 MongoDB；Memory 不要求 DB。模式隨 Config 跨環境固定，不在 Export 中改模式 |
| 共用 LLM 服務 | DEV test use／OpenAI-compatible API | 自行提供時設定 Base URL、Model、認證引用；Query Transformation／Generation 以下拉 llm_ref 引用，不各填一份連線 |
| Rerank | None／DEV test use／Rerank API | 啟用時設定內容欄位與 Top-N；自行提供時另填 API URL、Model、認證引用 |

DEV test use 使用平台測試資源；匯出部署時需填入使用單位的綁定。Embedding／LLM 的現有原型格式分別為 OpenAI-compatible embeddings／Chat Completions，Rerank 為 04 的平台契約；首組真實服務的相容範圍仍由 Q-003 核定。

### 3.3 條件欄位與相依驗證

- 外部服務選自行提供才要求必要 URL／Model／Secret reference；DEV 不曝光平台憑證。
- Local Search 選 MongoDB 才呈現 DB 連線；Memory 不要求資料庫。
- Query Transformation／Generation 只選 llm_ref；共用服務只管理一次。
- None 的 Top-N／Prompt 等欄位可保留草稿但停用，不參與有效 Config 驗證／匯出。
- 上游刪欄位或模型引用失效：保留失效選擇、標示原因、阻止儲存；不自動選另一值。
- 不支援能力顯示且停用，附可理解原因；不能讓顯示的 Mock 選項假裝正式可用。
- 前端 Validator 提供即時回饋，Backend／Engine 仍重新驗證。Schema 及規則來源需共用或由後端產生，避免手寫三份不同規則。
- Component 目錄／Config Schema 與驗證結果綁定目標 Runtime 版本；目錄變動不靜默升級既有 System 或覆寫草稿。API／Schema 與既有控制項相容時，新增 Component 可在 Runtime 更新後供原版 Builder 選用；未知控制項／不相容格式明示需支援，不假裝可完整設定。目錄快取與版本協調見 07，畫面待辦見 10 UIB-010。

錯誤顯示 `[模組] 原因`；進一步可提供欄位位置、修正方式與是否需重新 Ingestion。UI 不要求使用者理解內部 Python 類別或堆疊。

相依卡控需能直接說明上游原因，保留必要顯示：

| 上游條件 | 下游呈現與驗證 |
|---|---|
| Indexing 選 ES／Local Search | Retrieval 顯示繼承的後端資訊，不增加 Implementation 選單 |
| 欄位未建立全文／向量索引 | 對應搜尋選項顯示且停用，說明需先在 Indexing 建立能力；既有選擇失效則保留錯誤並阻止保存 |
| Embedding 移除某個 output_name | Indexing／Retrieval 的向量引用標為失效，不默默改為其他向量或欄位 |
| 欄位未建立全文／向量索引，但已存在於 Chunk | 仍可用於 Rerank／Generation 等內容消費；只有相對應的搜尋能力不能選，不能以「未勾儲存」拒絕 |
| metadata 已繼承／保存但未宣告可過濾 | 保留內容，Filter 選單停用該欄位並說明要先在 Indexing 啟用；不自動索引全部 metadata |
| Chunking 選 Fixed-size（待實作） | Token Size／Overlap／Tokenizer 有效；分隔符／keep_separator／標題層級不生效且保留草稿，不要求 Parsing headings |
| Header-aware 所需標題能力未開啟 | 顯示相依原因，提供定位 Parsing 進階設定的方式；無法滿足時阻止保存 |

卡控只處理設定相依；不代替實際後端能力、Profile 或連線驗證。規則由 04／05 共用來源推導。

2026-10-28 D-42 將動態 Component 表單列為已確認規劃方向，描述／規則草案與案例集中於 [12](12_component_schema_ui_contract.md)。Create／Edit 保持固定介面，Component 參數才依 Schema 產生；無關分支欄位隱藏，進階預設收合，不相容選項顯示且停用。上游變更使已選值失效時保留並標錯，可以繼續編輯，但正式儲存／建立／套用需通過 Engine 驗證；草稿持久化仍依 Q-016／Q-025。

動態候選使用目前有效欄位／服務／索引能力，前端不自行指定可信 Context。多個相同 Module 的錯誤以 node_ref＋欄位路徑定位。未知必要 UI feature 明示不支援且不能套用不完整設定；不自動改為任意 JSON 編輯器。實作與 SUI-01～14 互動驗收記在 10 UIB-010，尚未修改 Prototype。

### 3.3.1 討論提案：Query Rewrite 單模組測試

**待使用者確認，尚未改 UI。** 建議在 Query Transformation 放「測試 Rewrite／Multi-query」：輸入一個問題，用當前草稿的 Prompt／LLM／count 執行該模組，不要求先建立／保存 System 或 Ingestion，也不執行 Retrieval／Rerank／Generation。

測試前驗證本模組與引用服務的必要設定，不以其他無關模組未填完阻擋。顯示實際生成的 Prompt、要求筆數、解析後 Query 清單、原始問題是否另外加入及格式／筆數／非空／重複驗證；原始回應可收合，耗時／Token 用量僅顯示實際可取得數據。None 不呼叫 LLM。

測試使用與正式執行相同的 Engine 模組、Adapter、Schema 與驗證；LLM 輸出策略提案見 [04 §5.1.1](04_module_components_io_contracts.md#511-討論提案rewrite-的結構化輸出與共用-llm-邊界)。未接真實服務則明示模擬。修改 Prompt／LLM／count／保留原始問題或測試輸入後，舊結果標示過期；過期非同步回應不覆蓋新測試。試跑結果不自動套用／保存 Config，也不新增「必須先測試才能儲存」的 Gate。

### 3.3.2 討論提案：以數量統一 Query Rewrite

**待確認，UIB-008 未實作。** 建議用「啟用 Query Rewrite」＋產生 Query 數量 N，取代兩個分開的方法選項；N=1 單 Query 改寫，N>1 多 Query，停用直接沿用原始問題。保留一份有效 Prompt、共用 LLM 引用與 include_original，後者不計入 N。

數量設定動態產生輸出 Schema；Prompt 可編輯改寫內容與角度，平台補上格式／數量要求。UI 說明「count 決定筆數，Prompt 決定內容」，可看實際格式要求，避免誤以為 Prompt 寫任意筆數就可覆寫設定；非空／重複與語意驗證仍需要。多筆預設 Prompt 應描述多樣性，但使用者改 count 時不自動覆蓋已編輯 Prompt。

UIB-007 試跑如採用，也改用這組相同草稿與 Schema。Edit／AI／匯出及合併計畫預覽需沿用同一有效設定；舊 Rewrite 保留 N=1、舊 Multi-query 保留 N 與原本有效 Prompt，不能遷移時丟失另一份手寫草稿。具體保存政策 Q-002，原型仍維持兩種選項。

### 3.4 Inference 結果處理的整合提案

三種操作「去重＆合併／取 Top N／新模型算分」與共同排序規則已確認，見 [05 §4.6](05_data_contracts_search_design.md#inference-state-draft)。2026-10-15 15:53 的清單經使用者 18:55 要求開始實作，原型 v0.9 已完成 [10 §1～6](10_ui_adjustment_backlog.md) 的歷史結果處理 UI：保留單一 Create／Edit，基本／進階共用設定；進階預設收合，兩種合併預設勾選且在 Retrieval 後，Top N 附在四個動作位置，不新增獨立 Top N 卡片。10 §7 為後續待辦，不屬於 v0.9 已完成範圍。

基本表單讓使用者選可讀的上游步驟、每個 Query 內／跨 Query 範圍、方法及參數；runtime IDs 與 operation／source 由執行時產生。排序及 rank 更新固定執行，不提供排序開關；score_kind／score_order 由方法決定。ES 內部 Hybrid 已回傳一份清單時，預覽不得假裝仍有獨立全文／向量排名。

早期方案與案例保留於 [09 UI 整合提案](09_inference_contract_ui_plan.md)，最新控制項、預設與卡控以 10 為準。v0.9 只推導清單身分、數量上限與有效設定，不實際計算搜尋／模型分數。正式 Config、遷移、模型覆蓋率及 Adapter 能力仍由 Q-002／Q-003／Q-014／Q-025 核定。

同 Query 合併以 Query 身分分組，跨 Query 合併以相同搜尋路徑群組分組，兩層可各自移到 Reranker 後。ES 預設內部融合時，不再套同 Query 的跨路融合。跨 Query 已合併時，Reranker 有效提問固定原始問題，但保留各自 Query 選擇的草稿。Rerank=None 不會取消後置處理。

文件模式先完成 chunk_id 融合，再於選定時點按 document_id 選最高分代表 Chunk，最後 Top N；文件去重不得早於最後一次跨清單合併。原型尚不提供 Generation 多份清單的消費策略，因此最終不為單一 ResultSet 時阻止保存，並定位合併設定，不隱含串接清單。

### 3.5 討論提案：Generation 預設／進階輸出格式

**待確認，UIB-009 未實作。** 基本區沿用預設回答文字與平台引用的格式，提供簡短預覽；「進階輸出設定」預設收合，自訂 JSON 開關預設關閉。只展開說明不改 Config；啟用後才讓自訂 Schema 生效。

| 控制項 | 提案行為 |
|---|---|
| 自訂 JSON 輸出 | 使用者有需要才啟用；停用保留自訂草稿，不驗證／匯出其停用參數 |
| 回答內容 JSON Schema | 定義欄位名、型別、必填、陣列等；有說明／預設 Schema 可參考，不只填一份 JSON 範例就假裝限制型別 |
| 格式範例與驗證 | 顯示預期業務內容形狀，檢查 Schema 與所選 Provider 支援能力；未接模型的範例明示示意 |
| 主要回答文字欄位 | 自訂時可選 summary 等文字路徑供 UI／Evaluation 使用；無效／非文字路徑可定位，無適用文字時需明示相容政策 |
| 平台回應資訊 | request_id／版本／可信 citations 等由平台管理，與可自訂的回答內容分開；不在此編輯整個 Runtime API 回應 |

若採用，保留既有 chunk_template → context → prompt，不增加 Output 模組。預設格式、Schema 子集、主要回答路徑及 API payload 容器／遷移仍需核定，見 [04 §5.4.1](04_module_components_io_contracts.md#541-討論提案預設格式與進階自訂-json-輸出)／Q-002／Q-003／Q-018／Q-019。自訂格式只影響 Inference，修改後重測而不重建索引；若初版先完整生成後回傳，不宣稱支援自訂 JSON 的逐字 Streaming。

## 4. 從 CSV 開始

### 4.1 兩個入口

A. 先 Create Config，之後 Ingest 上傳 CSV 並映射。
B. 先上傳 CSV 樣本，描述用途／問題範例，AI 提出 Schema、映射及 Pipeline 草稿，使用者確認後建立 System。

CSV 每 row 對應一筆 records，不把每個 column 當文件。需要以多列合併文件的能力尚未定案，見 Q-007／Q-025。

### 4.2 映射與預覽

| 項目 | 要求 |
|---|---|
| CSV 預檢 | 處理 BOM／引號／換行；欄名非空唯一；每列欄數一致；正式編碼／超限政策待決 |
| 目標 | document_id、source_revision、Schema 中 input 的 fields.*／metadata.* |
| 映射 | 可將同一 column 填入多個目標；未映射欄位不送出 |
| 必填 | 無預設值的 input 必填欄位須映射 |
| 型別 | number 有限值；boolean 規則明確；array 用 JSON 解析；正式強制轉型政策 Q-002 |
| ID | 優先映射穩定鍵；自動 ID 的跨批更新限制要明示 |
| 預覽 | 原始列、標準 API Record、ParsedDocument；Schema 錯誤與列號對應 |
| 保存 | 成功後保存映射；是否成為執行 Config Revision 的一部分見 Q-015 |

Prototype 限制 ≤1 MB 且在瀏覽器讀取，不等於正式產品限制。正式檔案上傳、樣本保留、敏感欄位與大小限制見 Q-016／Q-019／Q-024。

### 4.3 AI 配置助手

已確認的互動方向：需求／樣本 → 建議 → 差異 → Validator → 使用者套用草稿 → Create／Save。規則模擬與真實 LLM 服務必須清楚區分。

**M4／M5 的分界已確認**：M4 的助手核心可不開 Builder，透過 Python／API 產生／修改同一種 Config；M5 同時交付 Builder 前後端與真實助手整合，另驗收下列 UI 差異。M4 已能回傳 Config，不能代替 M5 的驗收；完整情境見 [08 §4.2](08_implementation_plan.md#42-m4-與-m5-的助手驗收分界)。

| Builder 情境 | M5 需要處理的差異 |
|---|---|
| 從資料樣本開始 | 把已允許的樣本、欄位映射及用途交給助手，建議能對回 Schema／Chunking 等控制項 |
| 在 Create／Edit 修改既有設定 | 傳當前 UI Draft、選用服務與草稿基準；保留人工已填設定，區分新建建議與局部修改 |
| 顯示與套用建議 | 對照 before／after、有效參數及重建影響；同一 Validator 通過後，由使用者明確套用至草稿 |
| 回應期間草稿又被修改 | 比對基準版本／Hash；過期建議不得覆蓋新修改，提示重新產生或核定的合併流程 |
| 取消與儲存 | 取消建議不改草稿；取消 Create／Edit 不改已存 System；Create／Save 前不改 active Config，不自動 Ingestion |
| 欄位與方法能力 | AI 建議、手動表單與 Engine 使用同一份 Schema／Registry；未支援方法、失效欄位／服務可定位，不靜默換值 |

助手的結構化輸出與 UI 的暫存／收合等呈現狀態分開；手寫 Config 與 UI Draft 可有不同包裝，但產生的有效 Config 語意需一致。此處不新增原始 Config 編輯器或另一個 RAG 主畫面；Prototype 調整先列 10。

**建議的正式流程，需 Q-024 核定**：

1. 取得明確允許的樣本及使用目的；列出抽樣範圍，不自動傳全表。
2. 由 Registry／Schema 限制可建議的方法、欄位及參數。
3. 回傳結構化建議與理由，預覽 before／after 及重建影響。
4. 先通過結構及跨模組 Validator；不合法項目不能套用。
5. 檢查建議基準 Draft 版本；人工已修改時要求重新產生或明確合併。
6. 套用後可繼續手動改；撤銷／選擇性套用細節待決。

助手不猜 Secret、不自動呼叫 Ingestion、不因文字說「效果更好」就視為驗證完成。不支援需求應說明限制。資料本身的文字不作為修改平台政策／服務權限的指令。

## 5. Ingestion 畫面

上傳／records → 預覽與檢查 → 明確啟動 → 顯示 run_id／狀態 → 結果。長工作由 07 管理，不依靠前端視窗存活。

- 區分接收成功、處理完成、索引可查詢；202 不代表可問答。
- 顯示文件數與 Chunk 數時分開標示；進度分母不混用檔案／records／Chunk。
- 部分失敗列出可對應 item 的錯誤，不用單一成功 Toast 遮蔽。
- 重新打開視窗應可查現有工作；跨重啟是否恢復依 Job Store 政策。
- 重送／取消／重試按鈕僅在對應 API 及冪等行為實作後開放。
- 真實 Parser／Chunk 小量試跑是建議能力，Q-025 核定前不能用瀏覽器格式預覽冒充。

## 6. Inference 與診斷

問題＋本次 filters → 呼叫相同 Runtime API → 回答及引用。基礎結果簡潔呈現；詳細資訊按需展開。

| 層級 | 建議呈現 |
|---|---|
| 基本 | 回答、來源引用、索引未就緒／服務錯誤 |
| 進階 | 原始與衍生 Query、各路候選、融合結果、Rerank 前後、實際 Context、耗時／用量 |
| 版本 | config_revision、index_generation、request_id；不可顯示為另一版的結果 |

Trace 保存與敏感內容政策見 Q-016；診斷顯示範圍 Q-025。Filter 預設條件與本次附加條件要區分，空清單不能取消後端 ACL。API 說明隨時可查看，不需先 Ingestion。Ingest／Inference 皆有「查看 API 端點」入口，內容包含當前 Base URL、認證示意、JSON／multipart、cURL、回應與錯誤；Ingest 另示範 run_id 輪詢。查看說明不執行工作或模型／DB 測試。

## 7. Evaluation 與 Edit Config

### 7.1 Evaluation

Dataset 欄位預覽 → 指標所需標註檢查 → 執行 → 進度／逐題結果／摘要。缺 Ground Truth 不顯示虛構分數；skipped／failed／scored 分開。設定改動後舊報告標記對應舊版，保留歷史的正式政策由 07 決定。

Comparison、門檻與 Release Gate 為 Q-018；UI 不自行認定所有測試都通過即可部署。

### 7.2 儲存前變更摘要

依 05 的有效 Config 比較，列出模組與影響：

| 變更 | 使用者看到的結果 |
|---|---|
| Ingestion 邏輯配置／Schema | 新 Config Revision，需要重新 Ingestion |
| 部署資料目標 | 同版 Config，部署綁定改變；需驗證目標資料或 Ingestion |
| Inference 配置 | 不需重匯；需重新測試／評估 |
| 顯示名稱／未啟用草稿 | 不更換實體 collection，不誤判需重建 |

Runtime 的新舊 Revision／Index 發布策略見 Q-010／Q-015；UI 不單靠本機 boolean 決定正式可查詢狀態。

## 8. Export 與部署說明

- 沿用選定 System 的同版 Config，逐項填入部署環境的 LLM、Embedding、Rerank、ES／MongoDB 綁定；同 llm_ref 不重複填連線。改 URL／Secret 不覆寫邏輯 Config。
- 使用 DEV 綁定者可下載待設定草稿；必要資訊已填妥者標示「已填妥，尚未驗證」。
- 只允許合法環境覆寫；更改 Embedding Model 提示返回 Edit Config 並重建。
- 不含實際 Secret、Chunk／vectors 或測試原文；提醒需在目標環境準備資料／Ingestion。
- Local Search 單程序／單副本；不可透過 UI 匯出多副本而宣稱可共享索引。
- FTEST／ENT 檔名、環境值與完整 Bundle 待 Q-021；正式文案稱 Config／部署設定。原型舊的 RAGBlueprint／blueprint.json 僅是待遷移標籤，不是另立的產品物件；單份示意 YAML 不代表正式交付完成。

## 9. 互動品質與驗收

**建議驗收基準**：鍵盤可操作、收合區可定位錯誤、Dialog 焦點可返回原入口；窄版可操作、長 JSON／Prompt 不破壞版面；非同步樣本讀取不覆蓋較新的選擇；送出中避免重複提交；錯誤可修正而不遺失草稿。

核心情境：空白建立、CSV 起始、人工修正 AI、取消 Edit、刪使用中 LLM、上游移除欄位、格式錯誤、索引未就緒、服務失敗、修改 Ingestion 與只改 Prompt、匯出 DEV 草稿及配置完成稿。

UI Mock、Schema 驗證、HTTP integration、實際端對端驗收分開記錄；只通過 Prototype DOM test 不能視為正式串接完成。

## 10. 待討論與決策

| ID | 尚待明確的內容 |
|---|---|
| [Q-001](08_implementation_plan.md#q-001) | 正式前端框架、狀態／表單與測試工具 |
| [Q-015](08_implementation_plan.md#q-015) | 保存／版本衝突、CSV 映射與 Revision |
| [Q-019](08_implementation_plan.md#q-019) | API 認證、檔案大小、工作查詢及錯誤 Envelope |
| [Q-024](08_implementation_plan.md#q-024) | 真實 AI 模型、樣本範圍、結構化輸出、合併與撤銷 |
| [Q-025](08_implementation_plan.md#q-025) | 除已確認 Parsing 等要求外，其餘分組、試跑／範本／診斷範圍 |
| [Q-014](08_implementation_plan.md#q-014) | 融合範圍與合併時點的正式選單、相依卡控及預設 |
| [Q-018](08_implementation_plan.md#q-018) | Evaluation 介面指標、比較與 Gate |

決策狀態與實作階段見 [08](08_implementation_plan.md)。
