# RAG Builder — 系統概覽與架構

> 文件集 v0.19 · 2026-10-16 · 開發規格草案
>
> 本輪重整 03～08 的責任，保留既有已確認方向。本文負責產品與架構總覽，具體規格及未決問題見專題文件與 08。文件更新不表示 Engine、Runtime API 或部署服務已實作。

## 1. 文件責任與狀態

| 文件 | 權威範圍 | 主要讀者 |
|---|---|---|
| 03 本文 | 正式名詞定義、產品目標、使用情境、架構邊界、功能範圍 | 所有開發者 |
| [04 Engine 與模組](docs/04_module_components_io_contracts.md) | Engine 載入、組裝、執行、Component 擴充機制及各模組行為 | Engine／Module Developer |
| [05 資料與 Config](docs/05_data_contracts_search_design.md) | 共用資料結構、設定形狀、欄位及版本規則 | 前後端、Engine |
| [06 UI](docs/06_ui_development_spec.md) | 畫面、互動、漸進式設定、CSV 與 AI 助手 | 前端／產品 |
| [07 Backend 與 Runtime](docs/07_backend_runtime_integration.md) | HTTP API、管理資料、任務、部署及串接 | Backend／Runtime／DevOps |
| [08 開發計畫與決策](docs/08_implementation_plan.md) | 階段、驗收、確認決策、未決問題與阻擋範圍 | Coding agent／負責人 |
| [11 Component 開發指南](docs/11_component_developer_guide.md) | SDK 使用、Component 實作／測試／打包與交付流程；引用 04／05 契約 | Module Developer |
| [12 Component 設定描述](docs/12_component_schema_ui_contract.md) | Config Schema、UI hints、動態選項、相依規則與驗證回傳草案 | Module／Engine／Frontend Developer |

狀態用語：**已確認**為先前明確採用的方向；**建議**為本輪技術草案；**待決**以 Q-ID 追蹤；**後續**為未納入目前實作承諾的能力。03～07 引用問題 ID，08 是決策狀態的單一追蹤位置。文件版本不等於 Config contract_version、Engine 版本或完成進度。

舊 04 的 Chunk.text／獨立 VectorSet／單一向量假設已由新版 05 取代；舊 05 的逐次討論已按責任移入 04～07，不再依後章覆蓋前章閱讀。歷史內容保留在 Git commit `cf4dfdc0e29acc91a2fe63b1993f867c8facaf6d` 及以前的版本。遇到衝突，回報並修正相應權威文件，不自行按檔案日期猜測優先級。

## 2. 產品目的與核心概念

**以合理預設與 AI 引導，讓剛上手的使用者快速建立可測試的 RAG；提供逐步展開的設定與受控擴充能力，支援熟悉 RAG 者的特殊需求。**

已確認的三個方向：

1. AI 設定助手協助建立與修改設定。
2. 可從 CSV 開始，依資料及用途建議 Schema、映射與 Pipeline。
3. 初始畫面保留基本設定，進階設定由使用者展開。

兩種操作深度使用同一份 Config。AI 建議需經與手動設定相同的 Validator。CSV 能提供資料特徵，不能單獨證明最佳檢索策略；需配合問題範例及 Evaluation。

AI 設定助手分兩階段交付：M4 先完成不依賴 Builder 的核心與 Python／API 入口；M5 再完成 Builder 前後端及助手互動整合。M5 另驗收當前草稿、樣本／欄位映射、Diff、使用者套用、取消與過期建議，不能以 M4 已能輸出 Config 代替 UI 驗收。完整 M0～M7 與驗收見 [08 §4](docs/08_implementation_plan.md#4-開發階段與驗收)。

2026-10-16 起，後續需求先更新規格；需要變更 Prototype 的項目記入 [10 UI Backlog](docs/10_ui_adjustment_backlog.md)，待使用者明確要求修改 UI 才實作。新增 Fixed-size 及本輪助手規劃均屬文件更新，現有原型維持 v0.9。

2026-10-16 10:05 確認的簡化：Chunking 預設繼承全部有效 metadata，Indexing 保存全部 Chunk.fields／metadata；使用者只選全文／向量索引與可過濾欄位，移除「儲存內容」與逐欄 metadata 繼承選單，第一版不新增排除表單。保存與搜尋能力分開，未選全文索引的 title 仍可供回答使用，保存 metadata 不代表自動建立 Filter 索引。規格見 04／05，UI 尚待 10 的 UIB-005／006；Rewrite 單模組試跑及 LLM 輸出策略為待確認提案，不與已確認保存規則混同。

10:22 延續討論的提案：Rewrite／Multi-query 可共用一種方法，以產生數量 1／N 控制；Generation 保留預設格式，另在預設收合的進階區提供自訂回答 JSON Schema。Schema 約束結構，Prompt 指定內容；自訂業務內容與平台 API 資訊／可信引用分開，QueryResult／API 相容及評估讀取路徑仍需核定。提案見 04／06，UIB-008／009 尚未實作，不能以本段當作所有具體選項已被確認。

| 使用者 | 起始需求 | 目標能力 |
|---|---|---|
| 剛上手／快速試用 | 少量設定後看到測試結果 | CSV 入口、預設值、AI 設定草稿、資料預覽 |
| 熟悉 RAG | 控制欄位、方法、Prompt 與搜尋策略 | 完整設定、變更差異、可展開 Trace、Config 匯出 |
| Module Developer | 實作新的 Module Component，支援特殊資料／檢索策略 | SDK／公開 Contract、獨立套件、契約測試與受控交付；精確介面及發布政策另決 |

起始範本、小量試跑、自動診斷及自訂程式上傳的優先級尚未全部定案，見 [Q-022](docs/08_implementation_plan.md#q-022)、[Q-025](docs/08_implementation_plan.md#q-025)。本段不直接擴大第一期範圍。

2026-10-28 加入 Module Developer 的開發需求：允許開發者在公開契約下提供 Component，供 RAG Builder User 選用；角色與 Engine 關係已呈現於 L1 圖。04 記錄 Engine 擴充規格，11 記錄開發者流程。建議起步採本機 IDE＋SDK／範本＋受控套件交付；精確 SDK／Schema、發布權限與隔離仍依 08 核定，並不承諾所有 GraphRAG 策略都已符合目前固定 Pipeline。

<a id="terminology"></a>

## 3. 名詞定義與元件責任

**本章是整份文件集共用名詞定義的唯一依據。**04～07 引用本章，分別補充模組行為、資料／Config 結構、UI 及後端串接；08 記錄決策來源、狀態與待決事項，11 說明 Component 開發流程。名詞或邊界變動時，先更新本章，再同步受影響的規格；不能在各文件另定同名概念。

以下整理已確認方向及既有基線，不因此核定尚未決定的公共型別、欄位拼字、權限或部署政策。

<a id="system-terms"></a>

### 3.1 系統組成與管理階層

| 名詞 | 定義 |
|---|---|
| RAG Builder | 建立與管理 RAG System 的平台，提供 Workspace、設定 UI、測試、評估及匯出能力 |
| Workspace | Builder 中組織與管理 System 的容器；正式管理階層為 Workspace → System，不增加 Group 層 |
| RAG Engine Platform | 架構圖中共用執行技術堆疊的分組，包含 RAG Engine、Runtime API 封裝及其共用 Runtime Image；不是 DEV／獨立 Runtime 執行時必須呼叫的中央服務 |
| RAG Engine | 可依 Config 選擇、串接與執行模組的核心框架，可獨立於 Builder／HTTP 使用 |
| RAG Runtime | 為 Engine 加上 Ingest／Query／Status／Health API 的執行服務；載入設定後提供 System 的 API，可與 Builder 分開部署 |
| RAG System | 套用特定 Config、綁定服務與資料／索引所建立的具體 RAG 應用；具穩定邏輯識別，可處於未啟動／執行／停止狀態，直接使用 Engine 也可建立 |
| RAG Service（圖面用語） | Runtime 內由 Engine 載入 Config、綁定環境服務與資料後建立的 System 執行實例；不新增管理層級、必要微服務或另一組 API，也不指 Kubernetes Service 物件 |
| AI 設定助手 | 依需求、樣本、可用方法及 Config Schema 產生設定草稿的能力；可獨立由 Python／API 使用，Builder 另外提供互動、差異預覽及套用介面，不是 Ingestion／Inference 的必經模組 |
| Evaluation Runner | 批次執行 Dataset 與收集指標；重用 04 的評估邏輯，由 07 管理任務與儲存 |

Engine 是可重用的處理框架，Runtime 是提供 API 的服務載體，System 是使用者建立的具體應用。RAG Engine Platform 將共用實作抽出展示；Runtime 圖內的 RAG Service 表示套用設定後的 System 執行實例。建立／啟動 Runtime 是載入共用程式／Image、Config 與部署設定，不要求每份 Config 重新建 Image。System 的邏輯識別不等同於 Pod、程序或 API 端點；一個 Runtime 如何管理多個 System／執行實例，仍由 [Q-017](docs/08_implementation_plan.md#q-017)、[Q-020](docs/08_implementation_plan.md#q-020) 核定。

<a id="pipeline-terms"></a>

### 3.2 模組與處理流程

| 名詞 | 定義 |
|---|---|
| Module（模組） | Pipeline 中的功能分類與契約，定義職責、Input／Output 及語意，例如 Parsing、Chunking、Retrieval、Generation |
| Component（元件） | 遵守某個 Module 契約、可註冊及選用的具體實作，例如 Chunking 的 FixedSizeChunker／RecursiveChunker；包含參數描述、相依能力與執行邏輯 |
| Component Instance（元件實例） | 選定 Component 並套用 Config／資源綁定後的執行實例；同一 Component 可用不同參數建立多個實例 |
| Pipeline（處理流程） | Module 及其執行規則組成的流程；本產品採固定骨架，依 Config 選擇 Component、參數及核定的組合策略 |
| Ingestion | 將輸入資料經 Import、Parsing、Chunking、Embedding、Indexing 處理，準備可供查詢的資料／索引 |
| Inference | 接收問題，執行 Query Transformation、Retrieval、依配置進行 Fusion／Rerank，最後由 Generation 產生回答 |

Module／Component 是職責與選擇層次，不以 Python Class 或 Function 的實作形式區分；實作及 I/O Contract 見 [04](docs/04_module_components_io_contracts.md)。Ingestion 與 Inference 透過資料／索引綁定銜接，不要求每次提問都重新 Ingestion。純全文模式略過 Embedding、None 的 pass-through，以及 Fusion 的合併時點等執行規則見 §5／04；本節不增加通用 DAG 編輯器。

各 Module 規劃提供內建 Components，Module Developer 也可加入遵循相同契約、設定描述與相依要求的 Component。內建／自訂元件經同一 Registry 管理，使用者在 Builder 選用目標 Runtime 實際包含且核可的元件；預設提供不等於全部同時執行。[Module／Component 示意圖](diagrams/03_module_component_concept.png) 以 Parsing、Chunking、Indexing 為例，其他 Modules 同理；示例不是目前已完成的元件清單。

<a id="config-terms"></a>

### 3.3 Config 與部署設定

| 名詞 | 定義 |
|---|---|
| Config | System 的邏輯處理設定，包含 Module 的 Component／參數，以及 Pipeline、Document Schema、欄位、Prompt、模型語意 Profile 與邏輯服務引用 |
| 部署設定（Deployment Settings） | 特定環境的執行與連線綁定，包含服務 URL、認證／Secret 引用、DB／實體索引目標及 Runtime／K8s 資源 |
| UI Draft（UI 草稿） | 編輯過程中的設定狀態，可保存尚未啟用的方法／欄位；不表示所有內容都參與執行 |
| Effective Config（有效 Config） | 從草稿或輸入設定中，取出實際使用的方法、參數及引用後形成的有效邏輯設定；手動、AI 與手寫設定使用相同驗證規則 |

同一 System、同一 Config Revision 在 DEV／FTEST／ENT 沿用相同邏輯 Config，各環境可使用不同部署設定。例如只換服務 URL 或 Secret 引用屬部署綁定；改 Chunk Size、Generation Prompt 或模型語意 Profile 屬 Config 變更，不能以環境覆寫掩蓋。System 日後編輯會產生新 Revision，不要求它永遠只有一版 Config。

Config 與部署設定的欄位、有效設定規則及範例見 [05 §6～8](docs/05_data_contracts_search_design.md#config-spec)。正式 Schema、檔案包裝與版本綁定仍由 Q-002／Q-015／Q-021 核定；本章的名詞定義不凍結程式型別名稱。

先前助理引入的 **Blueprint 不作正式領域物件**，統一使用 Config／部署設定。Prototype 舊有 RAGBlueprint、blueprint.json、Groups 等標籤／變數的遷移見 05／06；舊程式名稱不另創正式概念。

<a id="version-terms"></a>

### 3.4 版本概念

| 名詞 | 代表什麼 |
|---|---|
| 開發文件版本 | 本 repository 規格內容的修訂，例如文件集 v0.12；不代表 Config 或程式版本，也不代表功能已完成 |
| Config Revision（config_revision） | 同一 System 的邏輯設定版本；改方法、參數、Prompt 等可形成新版本 |
| 文件內容版本（source_revision） | 每份匯入 RAG 的來源文件之內容版本；不同文件各自追蹤 |
| 索引資料版本（index_generation） | 某次可追蹤的索引資料狀態／發布批次，對應納入的文件版本及處理／建索引結果；可涵蓋多份文件 |
| 契約版本（contract_version） | 資料／Config 結構契約的格式版本；目前欄位與遷移規則屬建議，仍待 Q-002 核定 |

本節的「文件內容版本」指**匯入 RAG 的來源資料**，與 03～08 Markdown 規格的文件版本不同。改來源內容可在相同 Config 下形成新索引資料；來源不變而改切分／Embedding 也可能需要重建。只改 Inference Prompt 則可沿用相容的索引資料。

各版本不是一對一。相同 Config 的不同環境也可使用不同資料／索引。具體欄位、變更範例及索引相容規則見 [05 §2](docs/05_data_contracts_search_design.md#identity-versions)／§8；版本 ID 生成、快照保存及發布原子性仍由 Q-007／Q-010／Q-015 核定。

### 3.5 元件關係與實作責任

**04＋05 應足以讓開發者手寫 Config 直接執行 Engine，建立 RAG System；不要求 API 才能成立。**06 產生設定，07 保存設定並管理 Runtime 請求。UI 產生 Config，由同一套 Engine 建立對應 Pipeline 實例。

| 元件 | 責任 | 邊界 |
|---|---|---|
| Builder Frontend | 草稿、表單、預覽、結果與互動 | 後端重新驗證所有請求 |
| Builder Backend | 身分／權限、System／Revision、Dataset、任務、Export、AI 助手服務 | 不重寫模組演算法 |
| Engine | Config 編譯、Registry、初始化、Pipeline、模組及搜尋 Adapter | 不讀取前端草稿或依賴 Builder DB |
| Runtime API | HTTP 對應、任務包裝、Engine 生命週期、健康檢查 | 獨立部署後不依賴 Builder |
| 外部依賴 | LLM、Embedding、Rerank、ES、選配 MongoDB、Secret 與觀測服務 | 不隨 YAML 自動建立 |

技術方向以 Python、Pydantic 與部門既有 LangChain／LangGraph 生態為基礎；使用者已說明部門技術棧，Haystack 是早期比較候選，不是本專案已選框架。固定模組骨架可直接組裝，受控融合路徑不等於通用 DAG 編輯器。套件版本及前後端框架仍見 [Q-001](docs/08_implementation_plan.md#q-001)。

<a id="developer-terms"></a>

### 3.6 開發角色與擴充套件（2026-10-28）

| 名詞 | 責任／定義 |
|---|---|
| RAG Builder User | 使用可用方法設定 Config，執行測試／評估並匯出；不需撰寫 Component 程式 |
| Module Developer | 依公開 Module 契約開發、測試與維護 Component package；發布權限與資料存取另行授權 |
| Platform Developer | 維護 rag_platform 的 Builder 前後端與管理整合；可兼任管理者或 Engine Developer，實際授權另定 |
| Engine Developer | 維護 rag_engine 的 SDK、共用契約、Engine／Runtime API、相容驗證與 Component 載入政策；審查影響共用介面的變更 |
| RAG Engine Developer（L1 圖） | 圖面開發角色的概括名稱；D1～D2 對應 Module Developer 依契約開發，D3～D4 包含審查者、CI／發布及平台部署分工，不表示每個開發者都有部署權限，或每次新增 Component 都要修改 Engine 核心 |
| RAG Engine SDK（套件暫名 rag-engine-sdk） | 提供 Component 開發所需的公開型別、Module 介面、資源契約及開發工具；套件與精確 API 尚未實作／凍結 |
| Component package | 可安裝及版本化交付的 Python distribution，依賴 SDK，可以提供一個或多個 Module 的 Component |
| Registry | Engine 用來查找已註冊 Component、設定 Schema、能力、版本與建構入口的目錄；不等同於 Git repo、套件倉庫或套件安裝器 |
| component_id | Component 的穩定識別；搭配 implementation_version 定位發布實作，與 module_type、實例引用、Python class 名稱及套件名稱分開 |

本章的角色與套件分工配合 §3.7 已確認的兩個 repo 邊界；Python 套件名稱與內部目錄仍為草案。Component 實作版本、套件版本、SDK／Engine 版本與 §3.4 的 Config／Contract／資料版本分開記錄；精確欄位與版本鎖定規則留 Q-002／Q-015／Q-022。

本文新增的 SDK 指 Component 開發用套件。既有「透過 SDK／Python 直接使用 Engine」描述的是無 HTTP 的 Engine 公開呼叫能力，不表示它與 Component SDK 必須是同一發行套件，也不等於 Runtime HTTP client。具體邊界見 04 §1.1。

<a id="repository-boundaries"></a>

### 3.7 Repository、建置與部署邊界（2026-10-28 已確認）

採用兩個 repo，以 Builder 與 Runtime 的責任分開管理：

| Repo | 主要內容 | 建置／部署產物 |
|---|---|---|
| `rag_platform` | RAG Builder Frontend／Backend、Workspace／System 管理、設定助手整合、Evaluation 任務及 Export | Builder 的 Frontend／Backend Image，依服務邊界建置／部署 |
| `rag_engine` | SDK／共用 Contract、Engine／Registry、各 Module 的內建與客製 Components／Adapters、Runtime API | 包含 Engine＋核可 Components＋Runtime API 的完整 RAG Runtime Image；SDK 可另作 Python package |

Module Developer 在 rag_engine 的 components 目錄提交 PR；Engine 與 Components 在同一 repo 進行整合測試與 Runtime 發布。仍保留公開 SDK、可分別安裝的 Python package 及 Component 層級測試，不因同 repo 就允許依賴 Engine 私有實作。目錄配置與獨立助手核心的包裝建議見 [07 §2](docs/07_backend_runtime_integration.md#repository-build-boundaries)。

Builder 透過 Runtime API 與目標 Runtime 的 Component 目錄／Schema／驗證能力合作。API、Config 契約及 Builder 表單能力相容時，可各自升級；新增 Component 通常只需發布並部署新 Runtime，Builder 取得該 Runtime 的可用目錄。涉及不相容 API／Schema 或新型 UI 控制項時，仍需協調雙方版本。

Repo 是程式維護單位，Image 是交付產物，服務是部署單位；一個 repo 可產出多個 Image／package。Engine 或 Component 變更後，欲採用新版的執行環境仍需重建、測試並部署 Runtime。新版發布不自動升級既有 System，也不要求所有環境同時更新；選定版本的 DEV 測試與 FTEST／ENT 交付維持一致。

本決策取代先前「平台 repo 含 Engine、Component 分散至其他 repo」及「獨立擴充 repo 以 Engine 基底組裝 Image」的預設方向。外部 Component repo 可留作未來明確需求的擴充，不是首期必要配套。現在的 rag_platform repository 仍保存規劃文件與 Prototype；本輪僅更新目標架構，尚未建立 rag_engine repository 或搬移程式。

<a id="component-terminology-migration"></a>

### 3.8 Component 命名統一（2026-10-29，D-43）

使用者確認將原先表示「Module 下的可替換實作」的 Method 統一稱為 **Component（元件）**。Module Developer 角色名稱保留，工作是依 Module 契約開發 Component；Implementation 可作「具體實作」的敘述，不另增一個架構層級。Node 若用於圖面／配置引用，表示具體位置或實例，不與 component_id 混用。

| 舊稱／草案 | 新稱／草案 | 調整範圍 |
|---|---|---|
| Method／Method package | Component／Component package | 文件中的擴充單位與交付套件 |
| method_id | component_id | Registry、Descriptor、Config 目標識別與錯誤定位；範例 ID 值維持不變 |
| BaseMethod／ChunkingMethod | BaseComponent／ChunkingComponent | SDK 類別示意，尚未存在正式 SDK |
| methods/、rag_methods、rag-methods | components/、rag_components、rag-components | rag_engine 內的建議目錄、import package、distribution 名稱；不新增 repo |
| rag_engine.methods | rag_engine.components | 候選 entry point group；精確載入協定仍待核定 |
| method-ui-0.1-draft、目錄 methods、target.kind=method | component-ui-0.1-draft、目錄 components、target.kind=component | 尚未實作的設定描述協定同步改名 |

這是術語及草案介面的一致性更新，沒有改變模組分工、I/O、相依規則或兩個 repo 的部署流程。`module_type`、`implementation_version`、`config_type`、`node_ref` 仍各有用途；不因改名重產生 Component 識別值或自動升級 System。

Python 的 method／`@classmethod`／abstract method、HTTP method，以及既有 Inference ResultSet 中表示演算法／操作紀錄的 `method` 保留原義。05 的舊版完整 Config YAML／Prototype 仍使用部分 `method` 選擇欄位，屬明確標示的待遷移草案；不是新 Component Registry 的 component_id。正式 Config 遷移由 Q-002／Q-015 處理，需按格式版本明確映射與檢查衝突，不能全域替換所有 method 或宣稱 Runtime 已接受舊別名。

04／11／12 檔名同步使用 components／component，所有文件內引用更新；歷史敘述中的擴充單位採現行術語，原決策日期與功能狀態保留。L1 的 MMD／SVG／PNG 同步改標籤並保持既有版面與連線；Prototype 的實際介面及內部欄位留待 UIB-010 遷移。

## 4. 使用流程與執行入口

1. Build：設定 Schema、模組與外部服務，建立 RAG System。
2. Ingestion：接收資料，建立 Chunk／Index。
3. Inference：對該 System 測試問題與引用。
4. Evaluation：用 Dataset 檢查品質；不達標回 Edit Config。
5. Export YAML：補齊 FTEST／ENT 服務設定並匯出 Runtime 配置。
6. Deploy YAML in FTEST／ENT：使用單位自行在 K8s 部署。

1～5 與 Edit Config 屬 Builder 測試範圍，6 在其外。這是引導順序；Build 後可匯出草稿，Ingestion／Inference 可重複，Evaluation 不要求先手動問答。是否強制 Evaluation Release Gate 另決。

流程圖：[L1 PNG](diagrams/01_user_system_l1.png)、[Mermaid](diagrams/01_user_system_l1.mmd)、[固定版面 SVG](diagrams/01_user_system_l1.svg)。架構圖：[PNG](diagrams/02_infra_architecture.png)、[Mermaid](diagrams/02_infra_architecture.mmd)。2026-10-27 依使用者要求抽出共用 RAG Engine Platform，Runtime 內改標 RAG Service，並同步本章名詞／圖面規則。使用者確認後移除 Image→YAML 的「鎖定 Image 版本／Digest」連線並同步更新 PNG；Image 引用仍由 Export 記入 YAML，版本／Digest 規則保留於 07 的部署規格。同日後續 Mermaid 調整為 Platform 邊界直接連到 DEV 與獨立 Runtime，並增加自行部署環境外框；此輪只更新 Mermaid 與本章說明，PNG 保留前次同步版。本次不調整 L1。

圖面的既有使用者要求也屬規格，後續更新須保持：

2026-10-29 新增 Developer 四步 block 及 Module／Component 示意圖：L1 下方依序 D1 選 Module／讀契約、D2 開發 Component、D3 測試與 PR 審查、D4 發布並更新 Runtime，再連至共用 Engine 的選用能力。四步是既有開發／交付流程的摘要，精確權限與工具仍待核定，見 [11](docs/11_component_developer_guide.md#developer-flow-blocks)。Module 圖的 [Mermaid](diagrams/03_module_component_concept.mmd) 與 [SVG](diagrams/03_module_component_concept.svg) 維護相同關係；兩圖皆以固定 SVG 版面輸出 PNG。

- L1 的 1～5 左到右同一水平列，與「修改 Config」位於「RAG Builder測試」框內；6「Deploy YAML in FTEST/ENT」在框外右側。
- 下方測試實體名稱為「RAG System for RAG Builder 測試」；6 以虛線連其下方「RAG System in k8s」，YAML 設定檔另有虛線連到該實體。
- Evaluation→Export 標示「準備部署到 k8s」；Evaluation→修改 Config 標示「驗證不達標，需調整」。修改後依 Ingestion／Inference 變更返回相應步驟，並以虛線更新測試實體。
- Infra 使用「RAG Builder Control Plane」，明列 Frontend／Backend；Config／Validator／服務設定及 Export 合併為 Backend 職責，不因圖面重畫拆成必要微服務。
- tSSO 作登入入口；Backend 的「建立／設定 Runtime」連到整個 DEV RAG Runtime 邊界，由 Runtime 內部依 Config 組裝 System 執行實例。
- RAG Engine Platform 作為獨立共用實作區塊，展示 RAG Engine 與共用 Runtime Image；Platform 外框直接以虛線連到 DEV RAG Runtime 與獨立 RAG Runtime 的外框，表達使用共用執行框架。Runtime Image 保留於 Platform 內，不另由 Image 節點連到 Runtime。DEV／FTEST／ENT 重用相同版本程式／Image，虛線表示程式重用與設定載入，不代表向中央 Platform 發送業務請求。
- Runtime 內保留 Runtime API，原 RAG Engine 節點改標「RAG Service｜System 執行實例」；Engine 名稱保留於共用框架。Config 與各環境部署綁定分開，同一 System／Revision 沿用相同邏輯 Config。Engine 標籤不加「含 Local Search」。
- FTEST/ENT YAML 使用文件形狀；以「自行部署環境｜FTEST / ENT」外框包住 Secret Vault、獨立 RAG Runtime、部署依賴及 Logs／Metrics／Traces。Runtime 仍保留內層邊界，Vault／依賴／觀測工具位於 Runtime 外、部署環境內；使用者應用程式與部署操作維持在環境外框外。Config Store 保持簡化；本版圖不畫 Evaluation→Store、Backend→tSSO 線，這是圖面省略，不代表取消評估保存或後端授權驗證。

| 面向 | Builder 測試 | 獨立 Runtime |
|---|---|---|
| 入口 | UI 或已綁定 System 的 API | API；開發時也能直接呼叫 Engine |
| 設定 | Create／Edit／Revision | 載入 Config 與環境覆寫 |
| 外部服務 | DEV test use／使用者提供 | 使用單位提供可達且有權限的服務 |
| 評估 | 平台 Runner、Dataset、報告 | 外部工具可呼叫 Query API，不預設附評估 UI |
| 依賴 | 平台保存管理資料 | 啟動與日常執行不依賴 Builder |

## 5. Pipeline 與搜尋架構

| 流程 | 執行順序 |
|---|---|
| Ingestion | Import → Parsing → Chunking → Embedding → Indexing |
| Inference | Query Transformation → Retrieval → 依配置組合去重合併／取 Top N／模型算分 → Generation；每次輸出共同排序，現有 Prototype 仍為融合在 Rerank 前的舊基線 |
| Evaluation | Dataset → 呼叫相同檢索／Inference 入口 → 指標 → 報告 |

全文模式可略過 Embedding；None 模組明確 pass-through。Ingestion 與 Inference 透過 IndexBinding 銜接，不是同一次串行呼叫。使用者已要求可設定融合策略及合併時點；v0.8 原型的單層、Rerank 前融合只是歷史基線。v0.9 已依 [10](docs/10_ui_adjustment_backlog.md) 實作兩層合併的 UI 設定、時點連動與四處 Top N 預覽；Engine 尚未實作，正式 Config 與 Adapter 細節仍由 Q-014 核定。三類結果操作與共同排序見 04／05；[09](docs/09_inference_contract_ui_plan.md) 保留早期提案，最新 UI 以 10 為準。

| 搜尋模式 | 搜尋與資料 | 執行限制 |
|---|---|---|
| Elasticsearch | ES 保存 Chunk，提供全文／向量搜尋 | 版本、授權與相容能力需驗證 |
| Local Search／Memory | Engine 內 FAISS＋BM25＋Chunk Store | 同程序 Ingest／Query、單副本；重啟重新 Ingestion |
| Local Search／MongoDB | 同樣在 Engine 搜尋；MongoDB 保存 Chunk／vectors | 重啟可重建索引；第一版仍單程序／單副本 |

MongoDB 在此不執行向量檢索。每個向量欄位的 FAISS index 由 Adapter 管理。多程序不自動共享記憶體；MongoDB 也不自動同步 Pod 的索引。演算法及恢復流程見 04／07。

Local Search 的 Memory／MongoDB 持久化模式隨邏輯 Config 固定：DEV 用 Memory，FTEST／ENT 也用 Memory；同一 Config Revision 不藉部署設定切換模式。MongoDB 模式的連線／Secret／DB／Collection 可依環境提供。使用者已於 2026-10-15 確認此方向，見 08 D-33；具體 Schema／恢復政策仍由 Q-002／Q-012 核定。

## 6. 設定、服務與交付原則

- UI、AI 助手、手寫 YAML 最終使用相同有效 Config；跨環境相同 Revision 的邏輯設定保持一致，部署綁定另存。未啟用草稿不影響執行。
- Config Revision、source_revision、Index 資料版本分開管理。
- Ingestion 有效配置變動標記需重建；Inference 配置變動需重測。精確矩陣見 05。
- LLM 清單以 System 為作用域；Query Transformation／Generation 以 llm_ref 引用；Embedding／Rerank 保留自己的服務契約。
- Secret 僅存引用，不把憑證寫入 Config、Prompt、Trace 或匯出檔。
- Export 交付 Runtime Image 引用、Config、Secret 引用與部署說明，不包含 Chunk／vectors 或外部服務。
- 已填妥不等於連線、模型或部署已驗證；目標環境須驗證並準備資料。

## 7. 現況與範圍

基準版本只有 HTML Prototype 及其測試。CSV／JSON 讀取、Schema／映射檢查、草稿互動在瀏覽器執行；模型、搜尋、評估、API、部署為模擬。AI 助手是規則示意，未呼叫 LLM。README 記錄實作現況，06 記錄目標互動，Mock 不代表後端完成。

已選方向：固定流程、文字 RAG、多欄位、ES／Local Search、CSV／records、手動與 AI 設定、漸進式 UI、獨立 Runtime。Parser／OCR、套件、更新一致性、平台儲存等仍待決。

後續能力：通用 DAG、多模態向量、自動摘要、Parent–Child、Plugin Marketplace、Local Search 跨 Pod 同步、Streaming／History、熱更新。沒有核可前不自動加入。

## 8. 待討論與決策

| 問題 | 影響 | 追蹤 |
|---|---|---|
| 技術版本與首批格式 | MVP 基礎環境 | [Q-001](docs/08_implementation_plan.md#q-001)、[Q-005](docs/08_implementation_plan.md#q-005) |
| DEV 多 System 隔離 | 共享 Runtime 資源策略 | [Q-020](docs/08_implementation_plan.md#q-020) |
| 自訂程式範圍 | 特殊需求與安全執行 | [Q-022](docs/08_implementation_plan.md#q-022) |
| 基本／進階、範本、試跑 | 新手與進階體驗 | [Q-025](docs/08_implementation_plan.md#q-025) |
| Evaluation Gate | 匯出與部署流程 | [Q-018](docs/08_implementation_plan.md#q-018) |

所有問題狀態、決策負責人及階段阻擋範圍見 08。
