# RAG Builder — 使用流程與 UI 開發規格

> 文件集 v0.13 · 2026-10-15 · 開發規格草案
>
> 本文定義 UI 目標互動。現有 HTML Prototype 的搜尋、模型、評估及 API 為模擬。Parsing 的預設收合、LLM／Prompt／範例按鈕等已確認要求如下；其他基本／進階分組、正式框架、範本與試跑優先級仍待決。

## 1. 目標、相依與範圍

- 新手透過預設、CSV 與 AI 助手快速開始；熟悉 RAG 者可展開完整設定。
- 同一份 Config 可由手動或 AI 修改，不建立兩套不相容模式。
- 畫面名詞與元件關係以 [03 §3](../03_architecture_proposal.md#terminology) 為準；UI 標籤與說明不得另定同名概念。
- 資料／Config 以 [05](05_data_contracts_search_design.md) 為準；模組能力由 [04](04_module_methods_io_contracts.md) 提供；API 見 [07](07_backend_runtime_integration.md)。
- 正式階層為 Workspace → System；側欄選 Workspace，主區顯示 System 卡片與操作視窗，不另建 Group。原型的 Groups 標籤／內部變數屬舊命名，正式化時遷移，不新增通用 DAG 編輯器。
- 保留單一主畫面：左側切換 Workspace，中間以圖示／卡片呈現已建 System，卡片提供 Ingest／Inference／Evaluation／Edit Config／Export 入口。
- 右上角放顯眼的「Create RAG System」。開啟設定介面時沿用此名稱；Edit Config 重用同一份表單與模組設定元件，載入所選 System 的獨立草稿。
- UI 設定 Config，Engine 組裝實例；前端不直接存取 Secret 或自行執行正式 Pipeline。

## 2. 畫面與操作地圖

| 畫面／操作 | 使用者工作 | 主要結果 |
|---|---|---|
| Workspace 首頁 | 檢視與選擇 System | 名稱、版本、資料／索引狀態與操作入口 |
| Create／Edit | 設定 Schema、模組 Method／參數、Pipeline 與服務邏輯引用 | 經驗證的 Config 草稿／Revision；環境連線另存部署設定 |
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
- LLM 服務集中管理；Rewrite／Multi-query／Generation 在需要時以下拉引用，同一服務不重填連線。
- Rewrite／Multi-query 的 Prompt 可編輯，分別保留草稿；提供變數插入、驗證與預覽。
- Generation 有「模板說明與範例」及「套用範例」入口，展示兩筆 Chunk→逐筆模板→Context→完整回答 Prompt。
- Rerank 可查看固定平台 Request／Response 範例及 index／score 對應說明；不宣稱是所有模型的統一標準。
- collection 由 Workspace＋System 名稱／穩定 ID 自動帶入且唯讀；改顯示名稱不換既有實體。
- Retrieval 不另選 Implementation；由使用者選全文／向量欄位推導模式。融合除演算法外，還需可設定合併時點；正式時點選項與兩層 UI 待 Q-014。

下表其餘分組仍為建議，待 Q-025；其中 Parsing 與上述已確認方向不可退回待定。

| 區塊 | 基本預設呈現 | 展開進階呈現 |
|---|---|---|
| Document Schema | 主要 text、需要的內容欄位、metadata | 型別、required／default／source、unknown_fields |
| 服務 | DEV／自行提供、必要 URL／模型／認證引用 | Timeout、精確 Profile／Tokenizer 等 |
| Parsing（已確認） | 只顯示結構化 JSON | 其他格式及相關設定全部收在預設關閉進階區 |
| Chunking | 方法、主要切分欄位、複製欄位 | Size／Overlap、Tokenizer、分隔符、標題層級 |
| Embedding | 來源欄位、輸出向量、模型 | 維度／Encoding／Normalization、Batch、輸入限制 |
| Indexing | 後端、保存／全文／向量欄位、過濾能力 | 後端特有參數、進階 Mapping（支援後才顯示） |
| Query Transformation | None／Rewrite／Multi-query、LLM | Prompt、count、include_original |
| Retrieval／Fusion Plan | 搜尋欄位、Top-K、推導模式 | 每路 K、演算法、同／跨 Query 範圍及合併時點、預設 filters；細節 Q-014 |
| Rerank | None／服務、內容欄位、Top-N | Timeout／服務輸入限制 |
| Generation | LLM、回答要求 | 兩層模板、變數、Temperature、Budget |

必填但缺失的設定不能因進階區收合而無法發現；錯誤摘要可直接展開並定位。改動過的進階設定收起後，建議顯示已修改項數／簡短摘要。範圍、預設值及「每次記住展開」政策見 Q-025。

### 3.2.1 服務來源選項（保留已確認範圍）

| 設定位置 | 來源／選項 | 條件設定 |
|---|---|---|
| Embedding | DEV test use／Embedding API | 自行提供時設定 API URL、Model、認證引用及必要模型資訊；不另增加使用者管理本地模型的選項 |
| Indexing／Elasticsearch | DEV test use／使用者提供 Elasticsearch | 後者才要求 ES URL／認證等連線設定 |
| Indexing／Local Search | Memory／MongoDB | 選 MongoDB 才展開 DEV test use／使用者提供 MongoDB；Memory 不要求 DB。持久化選擇的 Config／部署歸屬見 Q-002／Q-021 |
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

錯誤顯示 `[模組] 原因`；進一步可提供欄位位置、修正方式與是否需重新 Ingestion。UI 不要求使用者理解內部 Python 類別或堆疊。

相依卡控需能直接說明上游原因，保留必要顯示：

| 上游條件 | 下游呈現與驗證 |
|---|---|
| Indexing 選 ES／Local Search | Retrieval 顯示繼承的後端資訊，不增加 Implementation 選單 |
| 欄位未建立全文／向量索引 | 對應搜尋選項顯示且停用，說明需先在 Indexing 建立能力；既有選擇失效則保留錯誤並阻止保存 |
| Embedding 移除某個 output_name | Indexing／Retrieval 的向量引用標為失效，不默默改為其他向量或欄位 |
| Header-aware 所需標題能力未開啟 | 顯示相依原因，提供定位 Parsing 進階設定的方式；無法滿足時阻止保存 |

卡控只處理設定相依；不代替實際後端能力、Profile 或連線驗證。規則由 04／05 共用來源推導。

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
