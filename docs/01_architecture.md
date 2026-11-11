# Retrieval Builder：架構、名詞與責任

## 閱讀目錄

- [產品目的與現行範圍](#產品目的與現行範圍)
- [系統組成與管理階層](#src-03-31-系統組成與管理階層)
- [模組與處理流程](#src-03-32-模組與處理流程)
- [Config 與部署設定](#src-03-33-config-與部署設定)
- [版本概念](#src-03-34-版本概念)
- [元件關係與實作責任](#src-03-35-元件關係與實作責任)
- [A～E 契約與角色責任總表](#src-20-3-最終詳細總表)
- [使用流程與圖面解讀](#src-03-4-使用流程與執行入口)
- [歷史名稱與遷移對照](#歷史名稱與遷移對照)
- [主責與一致性規則](#主責與一致性規則)


更新：2026-11-05。本手冊維護產品範圍、名詞與 A～E 責任；具體資料、Component、設定、API、UI 與開發狀態分別由其他七份手冊維護。唯一入口為 [README](../README.md)。

## 產品目的與現行範圍

Retrieval Builder 協助 User 建立、測試與匯出 Retrieval System，提供合理預設、CSV 測試與 AI 設定助手。Library＋Config＋必要資源綁定構成具體 System；同一 Runtime／共用 Flow 可服務多份 System 設定。

- Retrieval-only，沒有 Generation；Rewrite／AI 助手仍可使用 LLM，Evaluation 保留 M6。
- UI 是 Workspace／Group 與 System 卡片、單一 Create／Edit，提供 Ingest／Inference／Evaluation／Export。
- 可先設定再上傳資料，也可先提供 CSV，由 AI 助手建議設定；建議與手動操作使用同一驗證。
- 原型展示設定、契約與請求的瀏覽器模擬。
- M4 先交付可獨立使用的 AI 設定助手，M5 再完成 Builder 與助手整合；其餘 M0～M7 以計畫手冊為準。

<a id="system-terms"></a>

<a id="src-03-31-系統組成與管理階層"></a>
## 系統組成與管理階層

| 名詞 | 定義 |
|---|---|
| Retrieval Builder | 設定、管理、測試與匯出 Retrieval System 的開發平台；含 Frontend／Backend |
| Workspace | Builder 中管理 System 的容器；正式階層為 Workspace → System |
| Retrieval Engine Library | 可匯入的程式庫，提供 SDK 契約、Registry、Config 驗證、模組組裝與執行核心；本身不是已啟動服務，也不是某一個 System |
| Retrieval Engine Platform | 共用執行技術堆疊，包含 Library、Runtime API 封裝及共用 Runtime Image；不是 Builder 的別名，也不是 Runtime 每次執行必須呼叫的中央服務 |
| Retrieval Runtime | 載入 Library／Registry 與服務基礎設定，提供 Ingest／Query／文件管理／Health API；Builder 共用模式管理多個 System／Config，獨立模式啟動時綁定單一 System Config |
| Retrieval System | Library 依特定 Config 組裝，並完成必要服務及資料／索引綁定後建立的具體檢索系統；可由 Python 直接使用，也可由 Runtime 對外提供 API |
| Retrieval Service（圖面用語） | Runtime 內的 System 執行實例；不是新的管理層級、必要微服務或 Kubernetes Service 物件 |
| AI 設定助手 | 依需求、樣本、可用方法及 Config Schema 產生設定草稿的能力；可獨立由 Python／API 使用，Builder 另外提供互動、差異預覽及套用介面，不是 Ingestion／Inference 的必經模組 |
| Evaluation Runner | 批次執行 Dataset 與收集指標；重用 04 的評估邏輯，由 Runtime API／部署手冊 管理任務與儲存 |

核心關係是 **Retrieval Engine Library ＋ Config → Retrieval System**；實際執行還需解析必要的資源／服務綁定。Python 使用者可直接載入 Library 建立 System，不需要 HTTP 或 Builder。Platform 將 Library 與 Runtime API 打包為共用 Image，部署時再載入 Config／環境設定，無須每份 Config 重新建 Image。

Builder 管理設定與測試，Library 執行模組，Platform 交付執行框架，Runtime 承載 API，System 是依 Config 建立的具體應用。System 不等於 Pod／程序；Builder Local 共用 Runtime 指同一 API service／程序內建立多個 System，不只是共用 Pod，各自保有設定與資料作用範圍，資源限制與生命週期細節仍見 Q-017／Q-020。外部 Remote API 由服務提供者部署，Runtime 使用環境連線。 重啟 API service 程序即使不重建 Pod，仍影響該程序內所有 System 的 Memory 資料／工作；D-62 採共用 Flow／Executor，Builder Config 更新以新版配置快照及必要資源準備生效，不要求重建每份 Config 的專屬 Flow，也不必逐 Config 重啟共用 API service；D-63 確認該 System 的 Ingestion 結束後才允許新版設定生效；資源回收細節待定，模式對照見下一節。

<a id="runtime-deployment-modes"></a>

<a id="src-03-311-builder-共用與-ftestent-獨立模式d-61d-62"></a>
### Builder 共用與 FTEST／ENT 獨立模式（D-61／D-62）

| 環境 | Config 與 API service 的對應 | API service 啟動時 | Config 更新 |
|---|---|---|---|
| Builder DEV | UI 保存多份 System Config，共用一組或少數幾組 API service；每組均提供 Ingestion＋Inference，不逐張卡建立服務 | 載入 Library／Registry、服務／資源基礎設定，不被單一 System Config 定型；透過可信管理取得各 System Config | 驗證新版 Config 快照及相依資源，後續請求由共用 Executor 選 Component；不要求重建專屬 Flow；有 queued／running Ingestion 時僅存草稿，工作結束後才允許套用，資源切換仍待細化 |
| FTEST／ENT | 主 Runtime 第一版基準為一個 Pod＋一組 API service＋一份 System Config | 綁定該 Config 與環境資源，建立該 System 實例，業務請求不另選 System | 以重啟／重新部署該 API service 採用新 Config；資料／索引相容與需否重新 Ingestion 仍需驗證 |

Builder Backend 下發／註冊 Config 與目標 Runtime 的對應，Runtime 依可信 System 識別取得已驗證 Config 快照，由共用 Flow／Executor 執行；各 Module 解析所選 Component 並傳入該次 Config／Context，Library 不直接讀 Builder DB。服務啟動不綁單份 Config，不代表 Engine／已安裝 Component 版本可任意熱替換；新增 Local 程式仍按原 Image／版本交付流程。

少數共用服務可以依 Namespace／資源池等方式分組，但分組單位、數量與管理機制待決；不將 Namespace 與 Workspace／System 當成同一概念，也不新增 User 必填分組設定。Config 解析結果、Component 實例與資源可按需求快取；精確預載、LRU／回收與配額依 Q-020。共用 Flow 不要求共用所有 Component 實例，保存多份 Config 也不等於同時初始化所有模型／索引。每次請求／已接收文件固定使用同一 Config 快照，不在執行到各步時重新讀取最新版；D-63：該 System 有 queued／running Ingestion 時可保存草稿，暫不啟用新版；既有工作結束後才允許套用。其他 System 不受影響，不新增 Query 讀寫鎖；舊 Query 資源回收與 Remote 結果不明的判定仍待細化。

FTEST／ENT 的一 Pod 基準指主 Runtime。外部 API、模型、DB 及 Secret 為部署依賴。Ingestion／Inference 是同組 Runtime 的 API 能力，不強制各自一個 Pod／程序。

**範圍：Retrieval-only，不提供 Generation。** Inference 回傳排序後的檢索結果、分數與來源／追溯資訊，由呼叫端決定如何消費。Query Rewrite／Multi-query 與 AI 設定助手仍可使用 LLM；取消 Generation 不等於移除所有 LLM。

<a id="pipeline-terms"></a>

<a id="src-03-32-模組與處理流程"></a>
## 模組與處理流程

| 名詞 | 定義 |
|---|---|
| Module（模組） | Pipeline 中的功能分類與契約，定義職責、Input／Output 及語意，例如 Parsing、Chunking、Retrieval、Rerank |
| Component（元件） | 遵守某個 Module 契約、可註冊及選用的具體實作，例如 Chunking 的 FixedSizeChunker／RecursiveChunker；包含參數描述、相依能力與執行邏輯 |
| Component Instance（元件實例） | Component 的執行物件；每次執行接收本次參數及 Context。無狀態且可安全併行者可共用，有狀態或綁定特定資源者可依 System／資源分開，不要求每份 Config 各有一份實例 |
| Pipeline（處理流程） | Module 及其執行規則組成的流程；本產品採固定骨架，依 Config 選擇 Component、參數及核定的組合策略 |
| Ingestion | 將輸入資料經 Import、Parsing、Chunking、Embedding、Indexing 處理，準備可供查詢的資料／索引 |
| Inference | 接收問題，由 Inference Input 初始化 QueryContext[]，執行 Query Transformation、Retrieval、依配置進行 Fusion／Rerank，回傳最終排序的檢索結果 |

Module／Component 是職責與選擇層次，不以 Python Class 或 Function 的實作形式區分；實作及 I/O Contract 見 [Engine／Component 開發](03_engine_and_components.md)。Ingestion 與 Inference 透過資料／索引綁定銜接，不要求每次提問都重新 Ingestion。純全文模式略過 Embedding、None 的 pass-through，以及 Fusion 的合併時點等執行規則見 [架構與責任相關章節](#src-03-31-系統組成與管理階層)／Engine手冊；本節不增加通用 DAG 編輯器。

各 Module 提供平台內建方法。User 可對支援的單節點或連續區段設定 Remote API。索引相依依有效 Retrieval 模式解析。

<a id="config-terms"></a>

<a id="src-03-33-config-與部署設定"></a>
## Config 與部署設定

| 名詞 | 定義 |
|---|---|
| Config | System 的邏輯處理設定，包含 Module 的 Component／參數，以及 Pipeline、資料欄位相關參數、Prompt、模型語意 Profile 與邏輯服務引用；I/O 資料細節由 Component 宣告＋Config 推導，見 [Descriptor](04_component_descriptor.md) |
| 部署設定（Deployment Settings） | 特定環境的執行與連線綁定，包含服務 URL、認證／Secret 引用、DB／實體索引目標及 Runtime／K8s 資源 |
| Builder DEV | Retrieval Builder 提供的開發／測試環境，涵蓋前後端、測試 Runtime 與可選平台測試資源；既有文件未特別註明的 DEV 指此情境 |
| FTEST／ENT | 使用單位匯出設定後自行部署 Runtime／必要服務的目標環境；不預設平台測試資源或資料會一併移轉 |
| UI Draft（UI 草稿） | 編輯過程中的設定狀態，可保存尚未啟用的方法／欄位；不表示所有內容都參與執行 |
| Effective Config（有效 Config） | 從草稿或輸入設定中，取出實際使用的方法、參數及引用後形成的有效邏輯設定；手動、AI 與手寫設定使用相同驗證規則 |

同一 System、同一 Config Revision 在 Builder DEV／FTEST／ENT 沿用相同邏輯 Config，各環境可使用不同部署設定。例如只換服務 URL 或 Secret 引用屬部署綁定；改 Chunk Size、Query Rewrite Prompt 或模型語意 Profile 屬 Config 變更，不能以環境覆寫掩蓋。System 日後編輯會產生新 Revision，不要求它永遠只有一版 Config。

Builder DEV 與 FTEST／ENT 都使用環境綁定，但用途與管理邊界不同：前者由平台支援開發／測試，後者由使用單位準備部署資源。`DEV test use` 只是選用平台測試資源，不能視為 FTEST／ENT 已有可用連線；匯出時需補齊目標綁定，模型／索引語意仍須相容。Memory 可以沿用到目標環境，不因部署而自動改成 MongoDB；重啟後需重新 Ingestion。責任分工與案例見 [A～E 責任](#src-20-3-最終詳細總表)。

Config 與部署設定的欄位、有效設定規則及範例見 [資料契約：～8](05_system_config.md)。正式 Schema、檔案包裝與版本綁定仍由 Q-002／Q-015／Q-021 核定；本章的名詞定義不凍結程式型別名稱。

先前助理引入的 **Blueprint 不作正式領域物件**，統一使用 Config／部署設定。Prototype 舊有 RAGBlueprint、blueprint.json、Groups 等標籤／變數的遷移見 資料契約手冊／UI手冊；舊程式名稱不另創正式概念。

<a id="version-terms"></a>

<a id="src-03-34-版本概念"></a>
## 版本概念

| 名詞 | 代表什麼 |
|---|---|
| 開發文件版本 | 本 repository 規格內容的修訂，例如文件集 v0.12；不代表 Config 或程式版本，也不代表功能已完成 |
| Config Revision（config_revision） | 同一 System 的邏輯設定版本；改方法、參數、Prompt 等可形成新版本 |
| 文件內容版本（source_revision） | 每份匯入 Retrieval 的來源文件之內容版本；不同文件各自追蹤 |
| 索引資料版本（index_generation） | 某次可追蹤的索引資料狀態／發布批次，對應納入的文件版本及處理／建索引結果；可涵蓋多份文件 |
| 契約版本（contract_version） | 資料／Config 結構契約的格式版本；目前欄位與遷移規則屬建議，仍待 Q-002 核定 |

本節的「文件內容版本」指**匯入 Retrieval 的來源資料**，與 03～08 Markdown 規格的文件版本不同。改來源內容可在相同 Config 下形成新索引資料；來源不變而改切分／Embedding 也可能需要重建。只改 Inference Prompt 則可沿用相容的索引資料。

各版本不是一對一。相同 Config 的不同環境也可使用不同資料／索引。具體欄位、變更範例及索引相容規則見 [資料契約](05_system_config.md#草稿有效設定與部署)／[架構與責任相關章節](#src-03-31-系統組成與管理階層)；版本 ID 生成、快照保存及發布原子性仍由 Q-007／Q-010／Q-015 核定。

<a id="src-03-35-元件關係與實作責任"></a>
## 元件關係與實作責任

| 責任者 | 工作 |
|---|---|
| User | 管理 System、設定欄位與方法、接入自有 Remote API、選用模板、測試並匯出 |
| Admin | 維護全域版本化模板及平台資源政策 |
| 平台團隊 | 維護內建方法、Schema 推導、Engine、Runtime API 與 Builder |
| 外部服務維運者 | 維持服務端點、資料、相容契約及授權 |

<a id="src-20-3-最終詳細總表"></a>
### 契約分工

| 契約 | 主責 |
|---|---|
| A 資料與 I/O | [Data、QueryContext、IndexBinding](02_data_contracts.md) |
| B 內建方法描述 | [Config Schema 與有效 I/O 推導](04_component_descriptor.md) |
| C Remote API | [接入範圍、固定 HTTP 封裝與回應驗證](03_engine_and_components.md#remote-api) |
| D System Config | [流程、參數、欄位及邏輯服務引用](05_system_config.md) |
| E 部署設定 | [環境 Endpoint、Secret、索引目標與 Runtime 控制](06_runtime_api_and_deployment.md) |

<a id="src-03-4-使用流程與執行入口"></a>
## 使用流程與圖面解讀

User 在 Workspace 建立 System，選用模板或自行設定 Import、Ingestion 和 Inference。以 Builder DEV 驗證設定及試跑，再匯出 Config／環境綁定供 FTEST／ENT 獨立 Runtime。Admin 維護全域模板；套用時複製所選版本至 User 草稿。Engine 依有效設定選用內建方法或呼叫 User 設定的外部 API。

- [User 流程](../diagrams/01_user_system_l1.png)
- [Runtime 架構](../diagrams/02_infra_architecture.png)
- [模組與 System](../diagrams/03_module_component_concept.png)
- [Remote 與模板](../diagrams/04_component_delivery_modes.png)

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

這是術語及草案介面的一致性更新，沒有改變模組分工、I/O、相依規則或兩個 repo 的部署流程。`module_type`、`implementation_version`、`config_type`、`node_ref` 仍各有用途；不因改名重產生 Component 識別值或自動升級 System。

Python 的 method／`@classmethod`／abstract method、HTTP method，以及融合 Config 中表示演算法的 `method` 保留原義。Prototype 仍使用部分 `method` 選擇欄位，屬明確標示的待遷移草案；不是新 Component Registry 的 component_id。正式 Config 遷移由 Q-002／Q-015 處理，需按格式版本明確映射與檢查衝突，不能全域替換所有 method 或宣稱 Runtime 已接受舊別名。

Engine手冊／Engine／Descriptor 手冊 檔名同步使用 components／component，所有文件內引用更新；歷史敘述中的擴充單位採現行術語，原決策日期與功能狀態保留。L1 的 MMD／SVG／PNG 同步改標籤並保持既有版面與連線；Prototype 的實際介面及內部欄位留待 UIB-010 遷移。

## 主責與一致性規則

共用資料形狀由 schemas/ 與資料契約手冊維護；Module 演算法／SDK 由 Engine 手冊維護；B 的宣告與 DS 候選只在 Descriptor 手冊；D 的 SC 候選只在 System Config；HTTP 與環境限制只在 Runtime 手冊。UI 手冊保存互動與 Prototype 差異，計畫手冊保存已確認基線、Q 與里程碑。

相同議題只有一個主責位置；其他手冊用連結。已確認、候選、已實作／僅模擬、歷史證據必須分開。文件整合不核定任何尚未決定的 DS／SC／Q，也不改變共用資料或產品功能。
